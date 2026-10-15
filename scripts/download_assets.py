"""Fetch public upstream assets; no licensed SMPL files are redistributed."""

import hashlib
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = {
    "assets/pose/pose_landmarker_full.task": "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/1/pose_landmarker_full.task",
    "data/raw/standing.jpg": "https://raw.githubusercontent.com/shubham-goel/4D-Humans/main/example_data/images/pexels-anete-lusina-4793258.jpg",
    "data/raw/skates.png": "https://raw.githubusercontent.com/shubham-goel/4D-Humans/main/example_data/images/skates.png",
    "data/raw/yoga.jpg": "https://storage.googleapis.com/mediapipe-assets/pose.jpg",
    "data/raw/studio-person.jpg": "https://images.unsplash.com/photo-1666358085605-b3b717d5a210?w=1000&q=90",
    "data/raw/fashion.jpg": "https://images.unsplash.com/photo-1617137968427-85924c800a22?w=900&q=85",
}
for sample_id in (192, 241, 257, 294, 328, 338):
    ASSETS[f"data/raw/coco-{sample_id}.jpg"] = (
        f"https://raw.githubusercontent.com/CMU-Perceptual-Computing-Lab/openpose/master/examples/media/COCO_val2014_{sample_id:012d}.jpg"
    )


def main():
    manifest = []
    for relative, url in ASSETS.items():
        path = ROOT / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            with urllib.request.urlopen(url, timeout=120) as response:
                path.write_bytes(response.read())
        manifest.append(
            {
                "path": relative,
                "source": url,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
        print(relative, path.stat().st_size, flush=True)
    (ROOT / "assets/download-manifest.json").write_text(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
