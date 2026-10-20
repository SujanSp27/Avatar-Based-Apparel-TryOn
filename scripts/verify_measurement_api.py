"""Exercise real HTTP, CPU MediaPipe and MongoDB; never submits a try-on job."""

import argparse
import hashlib
import io
import json
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--image", type=Path, default=ROOT / "data/raw/studio-person.jpg")
    parser.add_argument("--height-cm", type=float, default=172)
    parser.add_argument("--output", type=Path, default=ROOT / "experiments/anthropometry/live-api")
    args = parser.parse_args()
    if urlparse(args.base_url).hostname not in ("127.0.0.1", "localhost"):
        parser.error("This verification script sends images only to the local project API.")
    args.output.mkdir(parents=True, exist_ok=True)
    evidence = {
        "image": str(args.image.relative_to(ROOT)) if args.image.is_relative_to(ROOT) else args.image.name,
        "input_sha256": hashlib.sha256(args.image.read_bytes()).hexdigest(),
        "height_cm": args.height_cm,
        "height_note": "Test-supplied height, not independently measured ground truth.",
        "local_gpu_used": False, "checks": [],
    }
    with httpx.Client(base_url=args.base_url, timeout=45) as client:
        for path in ("/api/health", "/api/brands", "/api/v1/sizing/brands",
                     "/api/v1/sizing/charts?market=IN&gender=men",
                     "/api/v1/sizing/charts?market=IN&gender=women"):
            response = client.get(path)
            response.raise_for_status()
            evidence["checks"].append({"path": path, "status": response.status_code})
        for run in ("cold", "warm"):
            start = time.perf_counter()
            response = client.post(
                "/api/v1/measurements/extract", data={"height_cm": args.height_cm},
                files={"image": (args.image.name, args.image.read_bytes())},
            )
            response.raise_for_status()
            result = response.json()
            evidence[run] = {"elapsed_seconds": round(time.perf_counter() - start, 4), "response": result}
            annotated = client.get(result["annotated_image_url"])
            annotated.raise_for_status()
            with Image.open(io.BytesIO(annotated.content)) as image:
                assert image.format == "PNG"
            (args.output / f"{run}-annotated.png").write_bytes(annotated.content)
        assert evidence["cold"]["response"]["measurements"] == evidence["warm"]["response"]["measurements"]
        assert result["provenance"]["device"] == "cpu" and not result["provenance"]["local_gpu_used"]

        # Known published midpoint: this checks exact math, not anthropometric accuracy.
        fixture = {"chest_circumference": 93.98, "waist_circumference": 81.915, "hip_circumference": 93.98}
        for label, measurements in (("known_chart_midpoint", fixture), ("photo_estimates", result["measurements"])):
            response = client.post("/api/v1/sizing/recommend", json={
                "brand_id": "nike", "apparel_id": "nike-in-hv4188-013", "measurements": measurements,
            })
            response.raise_for_status()
            evidence[label] = response.json()
        assert evidence["known_chart_midpoint"]["recommended_size"] == "M"
        assert evidence["known_chart_midpoint"]["minimum_error"] < 1e-12
        assert abs(evidence["known_chart_midpoint"]["fit_confidence"] - 100) < 1e-10

        with Image.open(args.image) as image:
            partial = io.BytesIO()
            image.crop((0, 0, image.width, int(image.height * .55))).save(partial, format="PNG")
        response = client.post("/api/v1/measurements/extract", data={"height_cm": args.height_cm},
                               files={"image": ("partial.png", partial.getvalue(), "image/png")})
        assert response.status_code == 422, response.text
        evidence["partial_body_rejection"] = response.json()
    (args.output / "report.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "passed", "cold_seconds": evidence["cold"]["elapsed_seconds"],
        "warm_seconds": evidence["warm"]["elapsed_seconds"],
        "known_midpoint_size": evidence["known_chart_midpoint"]["recommended_size"],
        "evidence": str(args.output / "report.json"),
    }, indent=2))


if __name__ == "__main__":
    main()
