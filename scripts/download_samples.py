"""Download the credited demo photo; no local pose, body or GPU models."""
import hashlib
import json
import urllib.request
from io import BytesIO
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
URL = "https://images.unsplash.com/photo-1666358085605-b3b717d5a210?w=1000&q=90"
POLO_URL = "https://image.uniqlo.com/UQ/ST3/AsianCommon/imagesgoods/465196/item/goods_51_465196.jpg"
NAVY_URL = "https://image.uniqlo.com/UQ/ST3/gb/imagesgoods/482514/item/gbgoods_69_482514_3x4.jpg?width=1200"
FASHN_REVISION = "1c49e7328d65aab0b784637275dbe17d4c0fa1b3"


def download_catalog():
    """Download only public garment inputs, with provenance and bounded payloads."""
    samples = [("navy-tee.jpg", NAVY_URL, "model", "t-shirt")]
    for name, kind, category in [
        ("garment1.jpeg", "model", "dress"),
        ("garment3.jpeg", "flat-lay", "blouse"),
        ("garment5.jpeg", "flat-lay", "skirt"),
        ("garment6.webp", "model", "dress"),
    ]:
        samples.append((f"fashn-samples/{name}",
                        f"https://huggingface.co/spaces/fashn-ai/fashn-vton-1.5/resolve/{FASHN_REVISION}/assets/examples/{name}",
                        kind, category))
    manifest = []
    for filename, url, photo_type, category in samples:
        target = ROOT / "data/raw" / filename
        if not target.exists():
            with urllib.request.urlopen(url, timeout=60) as response:
                data = response.read(8 * 1024 * 1024 + 1)
            if len(data) > 8 * 1024 * 1024:
                raise ValueError(f"Oversized catalog image: {filename}")
            with Image.open(BytesIO(data)) as image:
                image.verify()
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        manifest.append({"path": f"data/raw/{filename}", "imageUrl": url,
                         "photoType": photo_type, "category": category,
                         "sha256": hashlib.sha256(target.read_bytes()).hexdigest()})
    (ROOT / "data/raw/garment-catalog-source.json").write_text(json.dumps({
        "rights": "Public product and official demonstration inputs for local research. No commercial image rights or endorsement asserted.",
        "samples": manifest,
    }, indent=2), encoding="utf-8")


def main():
    target = ROOT / "data/raw/studio-person.jpg"
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        with urllib.request.urlopen(URL, timeout=60) as response:
            target.write_bytes(response.read())
    (ROOT / "data/raw/sample-source.json").write_text(json.dumps({
        "source": URL, "path": "data/raw/studio-person.jpg",
        "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
    }, indent=2))

    download_catalog()
    polo = ROOT / 'data/raw/sage-polo.jpg'
    if not polo.exists():
        with urllib.request.urlopen(POLO_URL, timeout=60) as response:
            data = response.read(5 * 1024 * 1024 + 1)
        if len(data) > 5 * 1024 * 1024 or not data.startswith(b'\xff\xd8'):
            raise ValueError('The polo source did not return a bounded JPEG image')
        polo.write_bytes(data)
    (ROOT / 'data/raw/sage-polo-source.json').write_text(json.dumps({
        'source': 'https://www.uniqlo.com/jp/ja/stylingbook/stylehint/5213118',
        'imageUrl': POLO_URL, 'path': 'data/raw/sage-polo.jpg',
        'sha256': hashlib.sha256(polo.read_bytes()).hexdigest(),
        'photoType': 'flat-lay', 'category': 't-shirt',
        'rights': 'Original product photograph; local research conditioning input, not a generated result or endorsement.',
    }, indent=2))


if __name__ == "__main__":
    main()
