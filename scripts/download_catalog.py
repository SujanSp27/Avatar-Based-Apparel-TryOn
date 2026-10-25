"""Restore the reviewed public catalog. Never downloads or uploads private images.

Run: python -m scripts.download_catalog
Sources and original checksums are pinned in data/catalog/garments-v2.json.
"""

import hashlib
import io
import json
from pathlib import Path

import requests
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]


def restore():
    rows = json.loads((ROOT / "data/catalog/garments-v2.json").read_text(encoding="utf-8"))
    for row in rows:
        target = ROOT / "data/raw" / row["filename"]
        if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == row["image_sha256"]:
            continue
        response = requests.get(row["asset_url"], timeout=45)
        response.raise_for_status()
        if hashlib.sha256(response.content).hexdigest() != row["source_image_sha256"]:
            raise RuntimeError(f"Source changed for {row['id']}; review it before publishing.")
        image = ImageOps.exif_transpose(Image.open(io.BytesIO(response.content))).convert("RGB")
        image.thumbnail((1000, 1400))
        buffer = io.BytesIO()
        image.save(buffer, format="WEBP", quality=90, method=6)
        if hashlib.sha256(buffer.getvalue()).hexdigest() != row["image_sha256"]:
            raise RuntimeError("Image encoder changed; use the locked project dependencies.")
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(".download")
        temporary.write_bytes(buffer.getvalue())
        temporary.replace(target)
    print(f"Verified {len(rows)} catalog photographs. Restart the API to install the seed.")


if __name__ == "__main__":
    restore()
