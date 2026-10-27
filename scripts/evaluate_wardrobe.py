"""Audit and resume real, private-Colab catalog trials through the authenticated API.

No GPU code runs locally. HTTP success never approves a garment. Original assets,
jobs and outputs are preserved; interrupted trials reuse their idempotency key.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import cv2
import httpx
import numpy as np
from PIL import Image, ImageDraw, ImageOps

from backend.app.config import ROOT
from backend.app.garments import GARMENTS
from backend.app.online_vton import normalized_image
from ml.errors import PipelineError
from ml.vton.categories import MODEL_CATEGORIES

DEFAULT = ROOT / "experiments/wardrobe-curation"
PEOPLE = {"studio": "data/raw/studio-person.jpg", "mirror": "data/raw/fashn-samples/person5.png"}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def save(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".partial")
    temp.write_text(json.dumps(data, indent=2, allow_nan=False), encoding="utf-8")
    temp.replace(path)


def catalog_rows():
    rows = json.loads((ROOT / "data/catalog/garments-v2.json").read_text())
    for key, name, category, photo, filename, description in GARMENTS:
        rows.append(dict(id=key, name=name, category=category, photoType=photo,
                         filename=filename, description=description, commercial_use=False))
    return rows


def inspect_source(row):
    path = (ROOT / "data/raw" / row["filename"]).resolve()
    if not path.is_relative_to((ROOT / "data/raw").resolve()):
        raise ValueError("Source is outside public catalog assets")
    report = {"id": row["id"], "name": row["name"], "category": row["category"],
              "modelCategory": MODEL_CATEGORIES.get(row["category"]), "photoType": row["photoType"],
              "path": path.relative_to(ROOT).as_posix(), "commercialUse": row["commercial_use"],
              "inferenceStatus": "not_tested", "visualStatus": "not_reviewed"}
    try:
        data = path.read_bytes()
        normalized = normalized_image(data)  # The actual API decoder, EXIF and colour handling.
        with Image.open(io.BytesIO(data)) as original, Image.open(io.BytesIO(normalized)) as image:
            pixels = np.asarray(image)
            gray = cv2.cvtColor(pixels, cv2.COLOR_RGB2GRAY)
            border = np.concatenate([pixels[0], pixels[-1], pixels[:, 0], pixels[:, -1]])
            background = np.median(border, axis=0)
            deviation = np.max(np.abs(border.astype(float) - background), axis=1)
            report.update(validImage=True, sha256=digest(data), format=original.format,
                          sourceMode=original.mode, sourceSize=list(original.size),
                          normalizedSize=list(image.size), normalizedRgbSha256=digest(image.tobytes()),
                          laplacianVariance=round(float(cv2.Laplacian(gray, cv2.CV_64F).var()), 3),
                          borderOutlierFraction=round(float(np.mean(deviation > 35)), 4),
                          technicalStatus="candidate" if report["modelCategory"] else "unsupported")
            report["warnings"] = []
            if min(original.size) < 384:
                report["warnings"].append("Source short edge below 384 px; inspect lost detail.")
            if report["borderOutlierFraction"] > .10:
                report["warnings"].append("Non-uniform border: visually inspect cropping and background.")
            if report["laplacianVariance"] < 30:
                report["warnings"].append("Low edge energy: inspect focus; plain fabric can also trigger this.")
            if not report["commercialUse"]:
                report["warnings"].append("Research reference; no verified commercial publication rights.")
    except (ValueError, OSError, PipelineError) as exc:
        report.update(validImage=False, technicalStatus="failed", reason=type(exc).__name__ + ": " + str(exc))
    return report


def sheet(paths, titles, output: Path, columns=5, cell=(220, 310)):
    """Diagnostic contact sheet; source files and inference conditioning are unchanged."""
    canvas = Image.new("RGB", (columns * cell[0], ((len(paths) + columns - 1) // columns) * cell[1]), "#f8f7f2")
    draw = ImageDraw.Draw(canvas)
    for i, (path, title) in enumerate(zip(paths, titles)):
        x, y = i % columns * cell[0], i // columns * cell[1]
        if path.is_file():
            with Image.open(path) as photo:
                fitted = ImageOps.contain(photo.convert("RGB"), (cell[0] - 8, cell[1] - 45))
                canvas.paste(fitted, (x + (cell[0] - fitted.width) // 2, y))
        lines = title.splitlines()
        draw.text((x + 6, y + cell[1] - 42), lines[0][:32], fill="black")
        draw.text((x + 6, y + cell[1] - 26), (lines[1] if len(lines) > 1 else "")[:32], fill="black")
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output)


def audit(folder: Path):
    rows = [inspect_source(row) for row in catalog_rows()]
    save(folder / "baseline.json", {"createdAt": datetime.now(timezone.utc).isoformat(), "garments": rows,
         "limitations": "Border and sharpness numbers are triage only, not garment segmentation or fit scores."})
    for i in range(0, len(rows), 20):
        group = rows[i:i + 20]
        sheet([ROOT / r["path"] for r in group], [r["id"] + "\n" + r["name"] for r in group], folder / f"sources-{i // 20 + 1}.jpg")
    print(f"Audited {len(rows)} sources. No garment approved.", flush=True)


def authenticate(client, session_path):
    saved = json.loads(session_path.read_text())
    for cookie in saved["cookies"]:
        client.cookies.set(cookie["name"], cookie["value"], domain=cookie["domain"], path=cookie["path"])
    response = client.post("/api/v1/auth/refresh", headers={"Origin": "http://127.0.0.1:5173"})
    response.raise_for_status()
    # Persist rotated cookies immediately so an interrupted evaluation can resume.
    for cookie in client.cookies.jar:
        old = next((c for c in saved["cookies"] if c["name"] == cookie.name), None)
        if old:
            old["value"] = cookie.value
            old["expires"] = cookie.expires or -1
    save(session_path, saved)
    client.headers["Authorization"] = "Bearer " + response.json()["access_token"]


def create_session(session_path: Path):
    """Create one normal local evaluation account; never bypass authentication."""
    if session_path.exists() or not session_path.resolve().is_relative_to((ROOT / ".runtime").resolve()):
        raise ValueError("Use a new private .runtime session file; existing sessions are never replaced")
    with httpx.Client(base_url="http://127.0.0.1:8000", timeout=30, trust_env=False) as client:
        response = client.post("/api/v1/auth/signup", headers={"Origin": "http://127.0.0.1:5173"},
                               json={"name": "Wardrobe evaluation", "email": f"wardrobe-{uuid4().hex}@example.com",
                                     "password": "Eval!7" + secrets.token_urlsafe(24), "terms_accepted": True})
        response.raise_for_status()
        save(session_path, {"cookies": [{"name": c.name, "value": c.value, "domain": c.domain,
             "path": c.path, "expires": c.expires or -1, "httpOnly": True, "secure": c.secure,
             "sameSite": "Lax"} for c in client.cookies.jar], "origins": []})


def submit_trial(client, row, state, state_path, person, garment):
    """A 401/429/503 rejects preflight; transport ambiguity must poll the saved key."""
    response = client.post("/api/tryon", headers={"Prefer": "respond-async", "Idempotency-Key": state["jobId"]},
                           data={"garmentCategory": row["category"], "garmentPhotoType": row["photoType"], "tryonMode": "2d"},
                           files={"personImage": ("person.png", person), "garmentImage": (Path(row["filename"]).name, garment)})
    if response.status_code in {401, 429, 503}:
        state.update(status="prepared", lastSubmissionStatus=response.status_code)
        save(state_path, state)
        return False
    if response.status_code != 202:
        state.update(status="failed", error={"code": "submission_rejected", "httpStatus": response.status_code})
        save(state_path, state)
        response.raise_for_status()
        raise ValueError("Expected asynchronous job acknowledgement")
    if response.json().get("jobId") != state["jobId"]:
        raise ValueError("Server acknowledged a different job ID")
    state["status"] = "processing"
    save(state_path, state)
    return True


def validate_output(original: bytes, output: bytes):
    with Image.open(io.BytesIO(original)) as before, Image.open(io.BytesIO(output)) as after:
        after.load()
        a, b = np.asarray(before.convert("RGB")), np.asarray(after.convert("RGB"))
        same_size = before.size == after.size
        changed = float(np.mean(np.any(a != b, axis=2))) if same_size else 0.
        return {"readable": True, "format": after.format, "size": list(after.size),
                "matchingDimensions": same_size, "changedPixelFraction": round(changed, 6),
                "nonEmptyEdit": changed >= .005,
                "visualAcceptance": "pending full-resolution inspection"}


def run(folder, ids, session_path, people, prepared_dir=None):
    rows = {row["id"]: row for row in catalog_rows()}
    with httpx.Client(base_url="http://127.0.0.1:8000", timeout=30, trust_env=False) as client:
        authenticate(client, session_path)
        for person_id in people:
            for product_id in ids:
                row = rows[product_id]
                if row["category"] not in MODEL_CATEGORIES:
                    raise ValueError("Unsupported category: " + product_id)
                person = (ROOT / PEOPLE[person_id]).read_bytes()
                garment_path = prepared_dir / (product_id + ".png") if prepared_dir else ROOT / "data/raw" / row["filename"]
                garment = garment_path.read_bytes()
                case = folder / "cases" / product_id / person_id
                case.mkdir(parents=True, exist_ok=True)
                state_path = case / "trial.json"
                inputs = {"personSha256": digest(person), "garmentSha256": digest(garment),
                          "category": row["category"], "photoType": row["photoType"]}
                if state_path.exists():
                    state = json.loads(state_path.read_text())
                    if state["inputs"] != inputs:
                        raise ValueError("Inputs changed; use a separate evaluation directory")
                    if state["status"] in {"generated", "failed"}:
                        continue
                else:
                    state = {"jobId": str(uuid4()), "productId": product_id, "personId": person_id,
                             "inputs": inputs, "status": "prepared", "visualStatus": "not_reviewed"}
                    save(state_path, state)
                if state["status"] == "prepared":
                    ready = client.get("/api/tryon/availability").json()
                    if not ready.get("available"):
                        print("Paused: existing Colab worker is unavailable. No job submitted.", flush=True)
                        return
                    state.update(status="submitting", startedAt=time.time())
                    save(state_path, state)  # Persist key BEFORE transmission.
                    if not submit_trial(client, row, state, state_path, person, garment):
                        print(f"Paused: preflight HTTP {state['lastSubmissionStatus']}. Existing limits unchanged; resume this trial later.", flush=True)
                        return
                print(f"Waiting {product_id}/{person_id} ({state['jobId']})", flush=True)
                deadline = time.monotonic() + 700
                while time.monotonic() < deadline:
                    response = client.get(f"/api/tryon/jobs/{state['jobId']}")
                    if response.status_code == 401:
                        authenticate(client, session_path)
                        continue
                    if response.status_code == 404 and state["status"] == "submitting":
                        # The first POST may never have reached the server. Reuse
                        # the SAME key: backend idempotency also covers races.
                        if not submit_trial(client, row, state, state_path, person, garment):
                            return
                        continue
                    response.raise_for_status()
                    job = response.json()
                    if job["status"] in {"success", "failed"}:
                        break
                    time.sleep(2)
                else:
                    print("Paused with existing job preserved; resume to poll, not submit.", flush=True)
                    return
                save(case / "job.json", job)
                state.update(status="failed" if job["status"] == "failed" else "generated", endedAt=time.time())
                if job["status"] == "failed":
                    state["error"] = job.get("error")
                else:
                    result = job["result"]
                    before = client.get(result["originalUrl"])
                    after = client.get(result["previewUrl"])
                    before.raise_for_status()
                    after.raise_for_status()
                    (case / "before.png").write_bytes(before.content)
                    (case / "after.png").write_bytes(after.content)
                    (case / "garment.bin").write_bytes(garment)
                    state["outputChecks"] = validate_output(before.content, after.content)
                    state["timingSeconds"] = result["timingSeconds"]
                    state["observedEndToEndSeconds"] = round(time.time() - state["startedAt"], 3)
                    state["timingTargetMet"] = state["observedEndToEndSeconds"] < 30
                    state["diagnostics"] = result["provenance"]["weights"]
                    state["runId"] = result["runId"]
                    save(case / "vton-diagnostics.json", state["diagnostics"])
                    state["outputSha256"] = digest(after.content)
                    sheet([case / "before.png", garment_path, case / "after.png"],
                          ["Original person", row["name"], "Actual generated result"], case / "comparison.jpg", 3, (400, 640))
                save(state_path, state)
                print(json.dumps({"productId": product_id, "person": person_id, "status": state["status"],
                                  "seconds": state.get("timingSeconds"), "error": state.get("error")}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["audit", "run", "create-session"])
    parser.add_argument("--folder", type=Path, default=DEFAULT)
    parser.add_argument("--ids", nargs="+")
    parser.add_argument("--candidates", type=Path, help="Reviewed candidate manifest; IDs in evaluation order")
    parser.add_argument("--prepared-dir", type=Path, help="Explicit background-only experiment; use a separate output folder")
    parser.add_argument("--people", nargs="+", choices=list(PEOPLE), default=list(PEOPLE))
    parser.add_argument("--session", type=Path, default=ROOT / ".runtime/wardrobe-evaluation-session.json")
    args = parser.parse_args()
    if not args.folder.resolve().is_relative_to((ROOT / "experiments").resolve()):
        parser.error("Evaluation output must stay in the private experiments directory")
    if args.action == "create-session":
        create_session(args.session)
    elif args.action == "audit":
        audit(args.folder)
    else:
        ids = args.ids or (json.loads(args.candidates.read_text())["candidateIds"] if args.candidates else None)
        if not ids:
            parser.error("run requires explicit candidate IDs")
        if args.prepared_dir and (args.folder.resolve() == DEFAULT.resolve() or not args.prepared_dir.resolve().is_relative_to((ROOT / "experiments").resolve())):
            parser.error("Prepared-reference experiments require a separate output folder and private experiment inputs")
        run(args.folder, ids, args.session, args.people, args.prepared_dir)


if __name__ == "__main__":
    main()
