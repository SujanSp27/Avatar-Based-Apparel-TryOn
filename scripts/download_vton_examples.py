"""Fetch three pinned, small official CatVTON examples for local evaluation.

These are unpaired research fixtures, not training data or evidence of fitting
quality. The upstream upper-body collection has no solid flat-lay shirt; both
selected garments therefore have a graphic whose preservation can be inspected.
"""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
from urllib.request import Request, urlopen

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/raw/vton-official"
REVISION = "999bdbe81e6008a3f5749af7c1e0b0fa3d21b48e"
REPOSITORY = "https://github.com/Zheng-Chong/CatVTON"
BASE = f"https://raw.githubusercontent.com/Zheng-Chong/CatVTON/{REVISION}/"
MAX_TOTAL_BYTES = 3_000_000
FIXTURES = (
    {
        "filename": "person-model-5.png",
        "upstreamPath": "resource/demo/example/person/men/model_5.png",
        "bytes": 638147,
        "sha256": "5faaea84635da215bd0819cf5ce65512ca1b742c39ee8fd67176b19e084ed872",
        "role": "person",
        "description": "Front-facing man, full visible face, white sleeveless top and jeans.",
        "limitation": "Sleeveless-to-short-sleeve transfer also tests shoulder-mask expansion.",
    },
    {
        "filename": "garment-number-95.jpg",
        "upstreamPath": "resource/demo/example/condition/upper/23255574_53383833_1000.jpg",
        "bytes": 93984,
        "sha256": "332036128caffe010e377f7ecb1852791804c53ebc4865d377339b9762c6689f",
        "role": "garment",
        "category": "tshirt",
        "description": "Brown short-sleeved jersey, white number 95 and shoulder panels.",
    },
    {
        "filename": "garment-rhude.jpg",
        "upstreamPath": "resource/demo/example/condition/upper/24083449_54173465_2048.jpg",
        "bytes": 383472,
        "sha256": "3929f83104c547bcf4a74985999438c05f887d97445c700029414466680eeee3",
        "role": "garment",
        "category": "tshirt",
        "description": "Black short-sleeved round-neck T-shirt with a pink/white RHUDE graphic.",
    },
)


def main() -> None:
    if sum(item["bytes"] for item in FIXTURES) > MAX_TOTAL_BYTES:
        raise ValueError("Example download exceeds the 3 MB budget.")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    records = []
    for item in FIXTURES:
        destination = OUTPUT / item["filename"]
        source_url = BASE + item["upstreamPath"]
        if destination.is_file():
            payload = destination.read_bytes()
        else:
            request = Request(source_url, headers={"User-Agent": "avatar-vton-research-validation"})
            with urlopen(request, timeout=45) as response:
                payload = response.read(item["bytes"] + 1)
        if len(payload) != item["bytes"] or hashlib.sha256(payload).hexdigest() != item["sha256"]:
            raise ValueError(f"Pinned example verification failed: {item['filename']}")
        with Image.open(io.BytesIO(payload)) as picture:
            dimensions = list(picture.size)
            picture.verify()
        if not destination.exists():
            temporary = destination.with_suffix(destination.suffix + ".part")
            temporary.write_bytes(payload)
            temporary.replace(destination)
        records.append({**item, "sourceUrl": source_url, "dimensions": dimensions})
        print(f"Verified {item['filename']}: {dimensions}, {len(payload)} bytes")
    manifest = {
        "repository": REPOSITORY,
        "revision": REVISION,
        "repositoryLicense": "CC-BY-NC-SA-4.0",
        "licenseUrl": f"{REPOSITORY}/blob/{REVISION}/LICENSE",
        "rightsNote": (
            "Official repository example photographs, retained unmodified for local research evaluation. "
            "Individual image rights are not separately stated upstream; this manifest does not assert "
            "ownership or commercial-use clearance for pictured people, products, or trademarks."
        ),
        "usage": "Unpaired visual regression fixtures; no training or benchmark ground truth.",
        "selectionNote": (
            "No solid flat-lay T-shirt exists among the four pinned upstream upper garment examples. "
            "Two actual short-sleeved graphic shirts were selected; the cardigan and vest were excluded."
        ),
        "totalBytes": sum(item["bytes"] for item in FIXTURES),
        "files": records,
    }
    (OUTPUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
