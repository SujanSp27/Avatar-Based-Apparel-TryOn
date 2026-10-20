"""Download only the pinned official MediaPipe pose model, never sample photos."""

import hashlib
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.config import settings

URL = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/1/pose_landmarker_full.task"
SHA256 = "5134a3aad27a58b93da0088d431f366da362b44e3ccfbe3462b3827a839011b1"


def main():
    path = settings.measurement_model_path
    if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == SHA256:
        print("MediaPipe pose model already verified.")
        return
    with urllib.request.urlopen(URL, timeout=120) as response:
        data = response.read(15_000_001)
    if hashlib.sha256(data).hexdigest() != SHA256:
        raise RuntimeError("Pose checkpoint checksum mismatch; no model installed.")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".partial")
    temporary.write_bytes(data)
    temporary.replace(path)
    print("Official MediaPipe pose model downloaded and verified.")


if __name__ == "__main__":
    main()
