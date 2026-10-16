"""Exercise real uploads, learned model provenance, PNGs and separate brand sizing."""

import argparse
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import httpx
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-run", default="9658bcca-8a2b-4a88-a134-cea3ff8739dd")
    args = parser.parse_args()
    folder = ROOT / "data/processed" / str(UUID(args.input_run))
    with httpx.Client(base_url="http://127.0.0.1:8000", timeout=900) as client:
        response = client.post(
            "/api/tryon",
            files={
                "personImage": (
                    "person.jpg",
                    (folder / "personInput.bin").read_bytes(),
                    "image/jpeg",
                ),
                "garmentImage": (
                    "garment.png",
                    (folder / "garmentInput.bin").read_bytes(),
                    "image/png",
                ),
            },
            data={
                "brandId": 1,
                "garmentCategory": "t-shirt",
                "fitPreference": "regular",
                "tryonMode": "2d",
            },
        )
        result = response.json()
        assert response.status_code == 200, result
        assert result["renderingMethod"] == "pretrained-vton"
        assert result["provenance"]["execution"] == "online-gpu-only"
        assert result["provenance"]["localGpuUsed"] is False
        assert result["recommendedSize"] is None and result["measurements"] is None

        def pixels(url):
            asset = client.get(url)
            asset.raise_for_status()
            return np.asarray(Image.open(io.BytesIO(asset.content)))

        original = pixels(result["originalUrl"])
        generated = pixels(result["previewUrl"])
        assert original.shape == generated.shape
        assert result["provenance"]["weights"]["preservation"]["identityPreservedExactly"]
        changed = np.any(original != generated, axis=2)
        assert changed.any(), "No garment was generated"
        size = client.post(
            "/api/sizing/recommend",
            json={
                "brandId": 1,
                "garmentCategory": "t-shirt",
                "fitPreference": "regular",
                "measurements": {"chest": 96, "waist": 82, "hip": 99, "shoulderWidth": 43},
            },
        )
        size.raise_for_status()
        assert size.json()["recommendedSize"]
        invalid = client.post(
            "/api/tryon",
            files={
                "personImage": (
                    "person.jpg",
                    (folder / "personInput.bin").read_bytes(),
                    "image/jpeg",
                ),
                "garmentImage": (
                    "garment.png",
                    (folder / "garmentInput.bin").read_bytes(),
                    "image/png",
                ),
            },
            data={
                "brandId": 1,
                "garmentCategory": "unsupported-outfit",
                "fitPreference": "regular",
                "tryonMode": "2d",
            },
        )
        assert invalid.status_code == 422
        report = {
            "recordedAt": datetime.now(timezone.utc).isoformat(),
            "inputRun": args.input_run,
            "runId": result["runId"],
            "previewUrl": result["previewUrl"],
            "model": result["provenance"],
            "seconds": result["timingSeconds"],
            "protectedPixelsUnchanged": True,
            "changedImageFraction": float(np.mean(changed)),
            "independentSizing": size.json(),
            "unsupportedCategoryError": invalid.json(),
            "visualAcceptance": "Must be recorded separately after inspecting this exact output",
        }
        (ROOT / "experiments/vton-api-report.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
