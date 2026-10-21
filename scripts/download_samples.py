"""Download the credited demo photo; no local pose, body or GPU models."""
import hashlib
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
URL = "https://images.unsplash.com/photo-1666358085605-b3b717d5a210?w=1000&q=90"
POLO_URL = "https://image.uniqlo.com/UQ/ST3/AsianCommon/imagesgoods/465196/item/goods_51_465196.jpg"


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
