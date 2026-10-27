"""Compile auditable real trials. Publish exactly twenty only after all gates pass."""
from __future__ import annotations

import argparse
import io
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

from backend.app.config import ROOT
from backend.app.online_vton import conditioning_image, normalized_image
from scripts.evaluate_wardrobe import DEFAULT, PEOPLE, catalog_rows, digest, inspect_source, save
from scripts.online_worker import MODEL, SOURCE

RATINGS = ("reference_fidelity", "anatomy", "boundaries", "preservation")


def artifact_checks(folder: Path, diagnostics: dict):
    """Check actual saved worker artifacts, never a surrogate segmentation."""
    errors = []
    required = ["garment-labels.png", "source-labels.png", "target-labels.png", "edit-mask.png",
                "garment-input.png", "person-input.png", "conditioning.json"]
    if any(not (folder / name).is_file() for name in required):
        return ["Worker masks/conditioning not retrieved for inspection"]
    with Image.open(folder / "person-input.png") as person, Image.open(folder / "garment-input.png") as garment:
        for name, shape in (("source-labels.png", person.size), ("target-labels.png", person.size),
                            ("edit-mask.png", person.size), ("garment-labels.png", garment.size)):
            with Image.open(folder / name) as img:
                arr = np.asarray(img)
                if img.size != shape or arr.ndim != 2:
                    errors.append(name + " does not align with its input")
                elif name == "edit-mask.png" and not .005 <= np.mean(arr > 0) <= .85:
                    errors.append("Edit mask is empty or covers nearly the whole frame")
                elif name != "edit-mask.png" and (arr.min() < 0 or arr.max() > 17):
                    errors.append(name + " contains invalid parser labels")
        with Image.open(folder / "garment-labels.png") as labels:
            clothing = {"tops": [3], "bottoms": [5, 6], "one-pieces": [4]}[diagnostics["category"]]
            if np.mean(np.isin(np.asarray(labels), clothing)) < .02:
                errors.append("Reference parser found too little category-specific garment")
    tensors = json.loads((folder / "conditioning.json").read_text())
    width, height = diagnostics.get("modelResolution", [0, 0])
    for key in ("ca_images", "garment_images", "person_poses", "garment_poses"):
        row = tensors.get(key, {})
        channels = 1 if key.endswith("poses") else 3
        if row.get("shape") != [height, width, channels] or len(row.get("float32Sha256", "")) != 64:
            errors.append("Missing or invalid real conditioning tensor: " + key)
    return errors


def assess_trial(folder: Path, source: dict, person_id: str):
    if not (folder / "trial.json").exists():
        return {"status": "pending", "reasons": ["Real inference not run"]}
    trial = json.loads((folder / "trial.json").read_text())
    errors = []
    visual_failed = False
    if trial["status"] != "generated":
        error = trial.get("error", "Inference incomplete")
        reason = error.get("message", error.get("code", "Inference failed")) if isinstance(error, dict) else str(error)
        return {"status": trial["status"], "reasons": [reason], "jobId": trial.get("jobId")}
    if trial["inputs"]["garmentSha256"] != source["sha256"]:
        errors.append("Garment bytes changed after inference")
    if trial["inputs"]["personSha256"] != digest((ROOT / PEOPLE[person_id]).read_bytes()):
        errors.append("Test-person bytes changed after inference")
    checks = trial.get("outputChecks", {})
    if not all(checks.get(k) is True for k in ("readable", "matchingDimensions", "nonEmptyEdit")):
        errors.append("Output failed objective image checks")
    if not (folder / "after.png").is_file() or digest((folder / "after.png").read_bytes()) != trial.get("outputSha256"):
        errors.append("Generated image is missing or its hash changed")
    diagnostic = trial.get("diagnostics", {})
    if (diagnostic.get("modelRevision") != MODEL or diagnostic.get("sourceCommit") != SOURCE
            or diagnostic.get("device") != "cuda"):
        errors.append("Unverified model/device provenance")
    audit = diagnostic.get("inputAudit", {})
    encoding = diagnostic.get("transport", {}).get("inputEncoding", "lossless")
    conditioned = conditioning_image(normalized_image((ROOT / source["path"]).read_bytes()), encoding)
    with Image.open(io.BytesIO(conditioned)) as model_input:
        expected_input = digest(model_input.convert("RGB").tobytes())
    if (audit.get("garment", {}).get("rgbSha256") != expected_input
            or audit.get("category") != source["modelCategory"]
            or audit.get("garmentPhotoType") != source["photoType"]):
        errors.append("Actual model input does not match the catalog garment/category")
    errors.extend(artifact_checks(folder, diagnostic))
    if not trial.get("timingTargetMet") or not 0 < trial.get("observedEndToEndSeconds", 0) < 30:
        errors.append("Measured end-to-end latency did not meet the strict under-30-second target")
    review_file = folder / "visual-review.json"
    if not review_file.is_file():
        errors.append("Full-resolution visual review pending")
    else:
        review = json.loads(review_file.read_text())
        if (review.get("outputSha256") != trial.get("outputSha256") or not review.get("reviewer")
                or not review.get("reviewedAt") or not review.get("notes")
                or review.get("decision") != "visual_pass"
                or review.get("fullResolutionInspected") is not True
                or review.get("majorArtifacts") is not False
                or any(type(review.get("ratings", {}).get(k)) is not int
                       or not 4 <= review["ratings"][k] <= 5 for k in RATINGS)):
            errors.append("Visual acceptance failed or review is incomplete/stale")
            visual_failed = (review.get("outputSha256") == trial.get("outputSha256")
                             and review.get("fullResolutionInspected") is True
                             and review.get("decision") == "failed")
    return {"status": "failed" if visual_failed else "approved" if not errors else "needs_review", "reasons": errors,
            "visualNotes": review.get("notes") if review_file.is_file() else None,
            "runId": trial.get("runId"), "jobId": trial["jobId"], "seconds": trial.get("observedEndToEndSeconds"),
            "workerStages": diagnostic.get("stageSeconds"), "output": str(folder / "after.png")}


def report(folder: Path):
    entries = []
    for row in catalog_rows():
        source = inspect_source(row)
        trials = {person: assess_trial(folder / "cases" / row["id"] / person, source, person) for person in PEOPLE}
        approved = source.get("validImage") and source.get("commercialUse") and all(r["status"] == "approved" for r in trials.values())
        entries.append({"id": row["id"], "name": row["name"], "category": row["category"], "photoType": row["photoType"],
                        "source": source, "trials": trials, "status": "approved" if approved else "not_approved"})
    result = {"version": 1, "generatedAt": datetime.now(timezone.utc).isoformat(), "target": 20,
              "approvedCount": sum(r["status"] == "approved" for r in entries), "garments": entries}
    save(folder / "report.json", result)
    lines = ["# Wardrobe evaluation", "", f"Approved: {result['approvedCount']} / 20. No publication implied.", "",
             "| Garment | Category | Person | Status | End-to-end seconds | Review / remaining gates |",
             "| --- | --- | --- | --- | --- | --- |"]
    for entry in entries:
        for person, trial in entry["trials"].items():
            notes = "; ".join(filter(None, [trial.get("visualNotes"), *trial["reasons"]])).replace("|", "/").replace("\n", " ")
            lines.append(f"| {entry['id']} — {entry['name']} | {entry['category'] or 'unsupported'} | {person} | "
                         f"{trial['status']} | {trial.get('seconds', '—')} | {notes} |")
    (folder / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result


def publish(folder: Path, output: Path):
    data = report(folder)
    approved = [r for r in data["garments"] if r["status"] == "approved"]
    if len(approved) < 20:
        raise ValueError(f"Only {len(approved)} garments passed; twenty required. Current wardrobe preserved.")
    approved.sort(key=lambda r: (max(t["seconds"] for t in r["trials"].values()), r["id"]))
    chosen = approved[:20]
    # Archive complete records/reasons BEFORE atomically changing the active list.
    save(folder / "catalog-archive.json", {"sourceRecords": catalog_rows(), "evaluation": data,
                                          "retainedIds": [r["id"] for r in chosen]})
    save(output, {"version": 1, "enforced": True, "status": "published", "targetCount": 20,
                  "reviewedAt": data["generatedAt"], "garments": [
                      {"id": r["id"], "category": r["category"], "photoType": r["photoType"], "status": "approved",
                       "imageSha256": r["source"]["sha256"], "testedPeople": list(r["trials"]),
                       "maximumSeconds": max(t["seconds"] for t in r["trials"].values())} for r in chosen]})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["report", "publish"])
    parser.add_argument("--folder", type=Path, default=DEFAULT)
    args = parser.parse_args()
    if not args.folder.resolve().is_relative_to((ROOT / "experiments").resolve()):
        parser.error("Evaluation evidence must stay inside experiments")
    if args.action == "publish":
        publish(args.folder, ROOT / "data/catalog/wardrobe-approved-v1.json")
    else:
        result = report(args.folder)
        print(f"{result['approvedCount']} / 20 approved; report saved. No publication change.")
