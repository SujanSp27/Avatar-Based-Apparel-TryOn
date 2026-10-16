"""Download the credited demo photo; no local pose, body or GPU models."""
import hashlib
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
URL = "https://images.unsplash.com/photo-1666358085605-b3b717d5a210?w=1000&q=90"


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


if __name__ == "__main__":
    main()
