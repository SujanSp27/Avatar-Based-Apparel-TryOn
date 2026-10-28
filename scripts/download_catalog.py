"""Restore the reviewed public catalog. Never downloads or uploads private images.

Run: python -m scripts.download_catalog
Sources and original checksums are pinned in data/catalog/garments-v2.json.
"""

import argparse
import hashlib
import io
import json
from pathlib import Path

import requests
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]


def restore(manifest: Path | None = None):
    rows = json.loads((manifest or ROOT / "data/catalog/garments-v2.json").read_text(encoding="utf-8"))
    for row in rows:
        target = (ROOT / "data/raw" / row["filename"]).resolve()
        if not target.is_relative_to((ROOT / "data/raw").resolve()):
            raise ValueError("Catalog asset path leaves data/raw")
        if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == row["image_sha256"]:
            continue
        if target.exists():
            raise RuntimeError(f"Local asset differs for {row['id']}; preserve it and review before replacing.")
        response = requests.get(row["asset_url"], timeout=45)
        response.raise_for_status()
        if hashlib.sha256(response.content).hexdigest() != row["source_image_sha256"]:
            raise RuntimeError(f"Source changed for {row['id']}; review it before publishing.")
        if row.get("asset_transform") == "none":
            with Image.open(io.BytesIO(response.content)) as image:
                image.verify()
            content = response.content
        else:
            image = ImageOps.exif_transpose(Image.open(io.BytesIO(response.content))).convert("RGB")
            image.thumbnail((1000, 1400))
            buffer = io.BytesIO()
            image.save(buffer, format="WEBP", quality=90, method=6)
            content = buffer.getvalue()
        if hashlib.sha256(content).hexdigest() != row["image_sha256"]:
            raise RuntimeError("Image encoder changed; use the locked project dependencies.")
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(".download")
        temporary.write_bytes(content)
        temporary.replace(target)
    print(f"Verified {len(rows)} catalog photographs. This command does not publish or approve garments.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path)
    restore(parser.parse_args().manifest)
