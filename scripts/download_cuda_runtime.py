"""Stream the exact Windows/Python 3.12 torch 2.5.1 CUDA wheel without pip's RAM cache."""

from pathlib import Path

import requests
from download_vton import fetch

ROOT = Path(__file__).resolve().parents[1]
NAME = "torch-2.5.1+cu121-cp312-cp312-win_amd64.whl"
URL = "https://download-r2.pytorch.org/whl/cu121/torch-2.5.1%2Bcu121-cp312-cp312-win_amd64.whl"
SHA256 = "473d76257636c66b22cbfac6f616d6b522ef3d3473c13decb1afda22a7b059eb"

if __name__ == "__main__":
    fetch(requests.Session(), URL, ROOT / ".runtime/wheels" / NAME, expected=SHA256)
