"""Replay the retained cropped upload against the pretrained 2D API contract.

Software checks are not visual acceptance. Model output must also be inspected.
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-run", default="4fd1db83-60cb-460f-9887-985eb1ffb82f")
    args = parser.parse_args()
    # Only a single retained UUID run may be read, not arbitrary filesystem paths.
    from uuid import UUID

    folder = ROOT / "data/processed" / str(UUID(args.input_run))
    files = {
        "personImage": ("person.png", (folder / "personInput.bin").read_bytes(), "image/png"),
        "garmentImage": ("garment.png", (folder / "garmentInput.bin").read_bytes(), "image/png"),
    }
    cases = [
        ("auto", "t-shirt", 200),
        ("2d", "t-shirt", 200),
        ("3d", "t-shirt", 422),
        ("2d", "trouser", 422),
    ]
    results = []
    with httpx.Client(base_url="http://127.0.0.1:8000", timeout=900) as client:
        for mode, category, expected in cases:
            response = client.post(
                "/api/tryon",
                data={
                    "brandId": 1,
                    "garmentCategory": category,
                    "fitPreference": "regular",
                    "tryonMode": mode,
                },
                files=files,
            )
            body = response.json()
            assert response.status_code == expected, body
            row = {"requestedMode": mode, "category": category, "httpStatus": expected}
            if expected == 200:
                assert body["mode"] == "2d"
                assert body["renderingMethod"] == "pretrained-vton"
                assert body["provenance"]["weights"]["loadVerified"] is True
                for field in (
                    "measurements",
                    "recommendedSize",
                    "avatarUrl",
                    "bodyUrl",
                    "garmentUrl",
                ):
                    assert body[field] is None
                for field in ("previewUrl", "originalUrl"):
                    asset = client.get(body[field])
                    assert asset.status_code == 200
                    assert asset.content.startswith(b"\x89PNG\r\n\x1a\n")
                assert (body["fallbackReason"] is not None) == (mode == "auto")
                row.update(
                    {
                        "mode": body["mode"],
                        "runId": body["runId"],
                        "previewUrl": body["previewUrl"],
                        "seconds": body["timingSeconds"],
                    }
                )
            else:
                code = "partial_body" if mode == "3d" else "vton_category"
                assert body["error"]["code"] == code, body
                row["code"] = code
            results.append(row)
            print(json.dumps(row), flush=True)
    report = {
        "recordedAt": datetime.now(timezone.utc).isoformat(),
        "inputRun": args.input_run,
        "cases": results,
    }
    (ROOT / "experiments/pretrained-2d-api-report.json").write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
