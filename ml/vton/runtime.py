"""Keep optional model-library caches inside the project workspace."""

import os
from pathlib import Path


def configure_local_cache() -> None:
    cache = Path(__file__).resolve().parents[2] / ".runtime" / "huggingface"
    cache.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("HF_HOME", str(cache))
    os.environ.setdefault("HF_HUB_CACHE", str(Path(os.environ["HF_HOME"]) / "hub"))
