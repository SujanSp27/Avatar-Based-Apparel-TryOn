"""Unit and regression tests for the automated garment evaluation system."""

import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from backend.app.config import ROOT
from scripts.evaluate_garments import (
    compute_color_histogram_correlation,
    compute_edge_density_similarity,
    create_side_by_side,
    evaluate_trial,
)


def test_color_histogram_correlation_identical_and_distinct():
    # Identical image and mask should yield correlation close to 1.0
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    img[:, :] = [180, 50, 40]
    mask = np.ones((100, 100), dtype=bool)
    
    corr_self = compute_color_histogram_correlation(img, mask, img, mask)
    assert corr_self > 0.95
    
    # Very different color
    other = np.zeros((100, 100, 3), dtype=np.uint8)
    other[:, :] = [20, 240, 220]
    corr_diff = compute_color_histogram_correlation(img, mask, other, mask)
    assert corr_diff < corr_self


def test_edge_density_similarity():
    # Both smooth regions
    smooth1 = np.ones((50, 50, 3), dtype=np.uint8) * 128
    smooth2 = np.ones((50, 50, 3), dtype=np.uint8) * 200
    mask = np.ones((50, 50), dtype=bool)
    sim = compute_edge_density_similarity(smooth1, mask, smooth2, mask)
    assert sim == 1.0


def test_side_by_side_board_dimensions():
    before = np.ones((600, 400, 3), dtype=np.uint8) * 100
    after = np.ones((600, 400, 3), dtype=np.uint8) * 200
    garment = np.ones((800, 600, 3), dtype=np.uint8) * 150
    
    board = create_side_by_side(before, after, garment)
    assert isinstance(board, Image.Image)
    assert board.height == 800
    assert board.width > 800


def test_evaluate_trial_baseline(tmp_path, monkeypatch):
    person_path = ROOT / "data/raw/studio-person.jpg"
    garment_path = ROOT / "assets/garments/shirt_hm.jpg"
    
    if not person_path.is_file() or not garment_path.is_file():
        pytest.skip("Test sample assets unavailable.")
        
    res = evaluate_trial(
        trial_name="test-trial-mock",
        person_path=person_path,
        garment_path=garment_path,
        category="shirt",
        photo_type="flat-lay",
    )
    assert res["status"] in {"completed", "offline_simulated"}
    assert res["dimensionMatch"] is True
    assert "comparisonBoardUrl" in res
    assert res["preservationScore"] >= 0.0
