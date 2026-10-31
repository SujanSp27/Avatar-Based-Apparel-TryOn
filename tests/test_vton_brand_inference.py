"""Validate Virtual Try-On inference with garments from H&M, Levi's, and Westside."""
import io
import json
from pathlib import Path
from PIL import Image
import pytest

from backend.app.config import ROOT
from backend.app.online_vton import OnlineTryOn, normalized_image
from scripts.evaluate_garments import evaluate_trial

EVAL_OUTPUT = ROOT / "experiments/brand-vton-verification"
EVAL_OUTPUT.mkdir(parents=True, exist_ok=True)


def test_brands_vton_pipeline():
    person_path = ROOT / "data/raw/fashn-samples/person1.png"
    assert person_path.is_file(), "Reference person image must exist"

    test_garments = [
        # 1. H&M
        ("hm-formal-pant-1", "H&M", ROOT / "assets/garments/formal-pant1_hm.jpg", "trouser"),
        # 2. Levi's
        ("levis-shirt-1", "Levi's", ROOT / "assets/garments/levi's-shirt_levis.jpeg", "shirt"),
        # 3. Westside
        ("westside-t-shirt-1", "Westside", ROOT / "assets/garments/t-shirt_westside.jpeg", "t-shirt"),
    ]

    worker = OnlineTryOn()

    for gid, brand, gpath, cat in test_garments:
        assert gpath.is_file(), f"Garment image {gpath} must exist"
        
        metrics = evaluate_trial(
            trial_name=f"verify-{gid}",
            person_path=person_path,
            garment_path=gpath,
            category=cat,
            photo_type="flat-lay",
            worker=worker
        )
        
        trial_folder = ROOT / "experiments/garment-evaluation" / f"verify-{gid}"
        assert metrics["status"] in {"completed", "offline_simulated"}, f"Trial for {gid} failed: {metrics.get('error')}"
        assert (trial_folder / "tryon-2d.png").is_file(), f"Output image for {gid} was not generated"
        assert (trial_folder / "comparison-board.jpg").is_file(), f"Comparison board for {gid} was not generated"
        print(f"Verified {brand} ({gid}): status={metrics['status']}, timing={metrics['timingSeconds']}s")
