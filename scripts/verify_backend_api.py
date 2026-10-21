"""Live local HTTP acceptance: real CPU pose, MongoDB records, sizing and SQL history.

Never submits a try-on, changes a Colab runtime, or uploads photos off this machine.
Only the measurement created by this invocation is deleted; evidence is retained.
"""

import argparse
import hashlib
import io
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.config import settings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--output", type=Path, default=ROOT / "experiments/backend-completion/live-api")
    args = parser.parse_args()
    address = urlparse(args.base_url)
    if address.hostname not in ("127.0.0.1", "localhost") or address.scheme != "http" or address.username:
        parser.error("This check only sends images to the local HTTP API.")
    args.output.mkdir(parents=True, exist_ok=True)
    image_path = ROOT / "data/raw/studio-person.jpg"
    image_data = image_path.read_bytes()
    report = {"checked_at": datetime.now(timezone.utc).isoformat(), "checks": [],
              "input_sha256": hashlib.sha256(image_data).hexdigest(), "local_gpu_used": False,
              "height_cm": 172, "height_note": "Test supplied; no tape-measure ground truth.",
              "vton_inference_submitted": False}
    headers = {"X-Admin-Token": settings.admin_token} if settings.admin_token else {}
    measurement_id = None
    with httpx.Client(base_url=args.base_url, timeout=45, headers=headers) as client:
        def checked(method, path, expected=200, **kwargs):
            started = time.perf_counter()
            response = client.request(method, path, **kwargs)
            assert response.status_code == expected, f"{method} {path}: {response.status_code} {response.text[:500]}"
            assert len(response.headers["X-Request-ID"]) == 32
            report["checks"].append({"method": method, "path": path, "status": response.status_code,
                                      "seconds": round(time.perf_counter() - started, 4)})
            return response

        try:
            checked("GET", "/api/v1/health/live")
            report["health"] = checked("GET", "/api/v1/health").json()
            checked("GET", "/api/v1/health/ready?capability=measurements")
            checked("GET", "/api/v1/health/ready?capability=sizing")
            expected = 200 if report["health"]["capabilities"]["tryon"] else 503
            checked("GET", "/api/v1/health/ready?capability=tryon", expected)
            checked("GET", "/api/brands")
            checked("GET", "/api/runs?limit=2")
            checked("GET", "/api/v1/sizing/categories")
            checked("GET", "/api/v1/sizing/brands?include_demo=true")
            nike = checked("GET", "/api/v1/sizing/brands/nike").json()
            assert nike["recommendation_available"]
            for gender in ("men", "women"):
                charts = checked("GET", f"/api/v1/sizing/charts?market=IN&gender={gender}&latest_only=true").json()
                assert {chart["brand_id"] for chart in charts} == {"nike", "puma"}
            checked("GET", "/api/v1/sizing/charts/nike/nike-in-hv4188-013/versions")
            checked("GET", "/api/v1/sizing/charts/nike/nike-in-hv4188-013?version=1")
            midpoint = checked("POST", "/api/v1/sizing/recommend", json={
                "brand_id": "nike", "apparel_id": "nike-in-hv4188-013", "chart_version": 1,
                "measurements": {"chest_circumference": 93.98, "waist_circumference": 81.915, "hip_circumference": 93.98},
            }).json()
            assert midpoint["recommended_size"] == "M" and midpoint["minimum_error"] < 1e-12
            assert abs(midpoint["fit_confidence"] - 100) < 1e-10
            report["known_midpoint"] = midpoint
            combined = checked("POST", "/api/v1/measurements/extract-and-recommend", data={
                "height_cm": 172, "brand_id": "nike", "apparel_id": "nike-in-hv4188-013", "chart_version": 1,
            }, files={"image": (image_path.name, image_data, "image/jpeg")}).json()
            extraction, recommendation = combined["extraction"], combined["recommendation"]
            measurement_id = extraction["measurement_id"]
            assert extraction["provenance"]["device"] == "cpu" and not extraction["provenance"]["local_gpu_used"]
            assert recommendation["measurement_id"] == measurement_id
            assert set(extraction["warnings"]).issubset(recommendation["warnings"])
            report["combined"] = combined
            path = f"/api/v1/measurements/{measurement_id}"
            record = checked("GET", path).json()
            assert record["measurements"] == extraction["measurements"] and record["created_at"]
            page = checked("GET", "/api/v1/measurements?limit=100").json()
            assert any(item["measurement_id"] == measurement_id for item in page["items"])
            png = checked("GET", path + "/annotation")
            assert png.headers["content-type"] == "image/png"
            assert png.content == checked("GET", extraction["annotated_image_url"]).content
            with Image.open(io.BytesIO(png.content)) as decoded:
                assert decoded.format == "PNG" and min(decoded.size) >= 256
            (args.output / "annotated.png").write_bytes(png.content)
            for source in ({"measurement_id": measurement_id}, {"measurements": extraction["measurements"]}):
                sized = checked("POST", "/api/v1/sizing/recommend", json={
                    "brand_id": "nike", "apparel_id": "nike-in-hv4188-013", "chart_version": 1, **source,
                }).json()
                for key in ("recommended_size", "minimum_error", "size_rankings", "fit_confidence"):
                    assert sized[key] == recommendation[key]
            checked("POST", "/api/v1/sizing/recommend", 422, json={
                "brand_id": "nike", "apparel_id": "nike-in-hv4188-013",
            })
            checked("GET", "/api/v1/sizing/charts/missing/unknown", 404)
            schema = checked("GET", "/openapi.json").json()
            report["documented_operations"] = sum(
                method in ("get", "post", "put", "patch", "delete")
                for path_spec in schema["paths"].values() for method in path_spec
            )
            (args.output / "openapi.json").write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
        finally:
            if measurement_id:
                path = f"/api/v1/measurements/{measurement_id}"
                checked("DELETE", path, 204)
                checked("GET", path, 404)
                checked("GET", path + "/annotation", 404)
                checked("GET", f"/static/annotated/{measurement_id}.png", 404)
                report["created_measurement_deleted"] = True
        report["status"] = "passed"
        (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "checks": len(report["checks"]),
                      "capabilities": report["health"]["capabilities"],
                      "evidence": str(args.output / "report.json")}, indent=2))


if __name__ == "__main__":
    main()
