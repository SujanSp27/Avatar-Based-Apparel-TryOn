import argparse
import json
import time
from pathlib import Path

import httpx
import trimesh

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--all-categories", action="store_true")
    args = parser.parse_args()
    results = []
    with httpx.Client(base_url="http://127.0.0.1:8000", timeout=300) as client:
        assert client.get("/api/health").json()["database"] == "postgresql"
        brand = client.get("/api/brands").json()[0]["id"]
        categories = (
            ["t-shirt", "shirt", "dress", "trouser"] if args.all_categories else ["t-shirt"]
        )
        for category in categories:
            start = time.perf_counter()
            response = client.post(
                "/api/tryon",
                data={
                    "brandId": brand,
                    "garmentCategory": category,
                    "fitPreference": "regular",
                    "heightCm": 172,
                    "tryonMode": "3d",
                },
                files={
                    "personImage": (
                        "person.jpg",
                        (ROOT / "data/raw/studio-person.jpg").read_bytes(),
                        "image/jpeg",
                    ),
                    "garmentImage": (
                        "garment.png",
                        (ROOT / "data/raw/garment-demo.png").read_bytes(),
                        "image/png",
                    ),
                },
            )
            print(category, response.status_code, response.text[:1200], flush=True)
            response.raise_for_status()
            result = response.json()
            assert result["status"] == "success"
            assert result["mode"] == "3d"
            for field in ["avatarUrl", "bodyUrl", "garmentUrl", "previewUrl"]:
                asset = client.get(result[field])
                assert asset.status_code == 200
                if field.endswith("Url") and field != "previewUrl":
                    assert asset.content[:4] == b"glTF"
            mesh = trimesh.load(
                ROOT / "data/processed" / result["runId"] / "dressed.glb", force="scene"
            )
            assert len(mesh.geometry) == 2
            results.append(
                {
                    "category": category,
                    "runId": result["runId"],
                    "size": result["recommendedSize"],
                    "measurements": result["measurements"],
                    "fitting": result["fitting"],
                    "seconds": round(time.perf_counter() - start, 2),
                }
            )
    (ROOT / "experiments/api-smoke-report.json").write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
