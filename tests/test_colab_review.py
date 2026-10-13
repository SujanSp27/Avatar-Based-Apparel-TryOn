"""Offline result review must report actual pixel changes, never inferred success."""

import numpy as np
import pytest

from scripts.review_colab_results import artifact_path, preservation_metrics


def test_pixel_audit_detects_identity_damage_and_old_clothing_blending():
    labels = np.array([[1, 2, 3], [13, 6, 15]], dtype=np.uint8)
    original = np.zeros((2, 3, 3), dtype=np.uint8)
    generated = original.copy()
    generated[0, 0] = 1  # damaged face outside edit mask
    generated[0, 2] = 200
    edit = labels == 3
    alpha = edit.astype(np.uint8) * 254  # blending leaks original fabric
    report = preservation_metrics(original, generated, labels, edit, alpha)
    assert report["changedPixelsOutsideEditMask"] == 1
    assert report["protectedRegions"]["face"]["changedPixels"] == 1
    assert report["protectedRegions"]["hands"]["changedPixels"] == 0
    assert report["oldClothingPixelsNotFullyReplaced"] == 1


def test_pixel_audit_does_not_invent_missing_region_evidence():
    labels = np.full((2, 3), 3, np.uint8)
    original = np.zeros((2, 3, 3), np.uint8)
    report = preservation_metrics(original, original, labels, labels == 3, labels * 85)
    assert report["protectedRegions"]["face"] == {"pixels": 0, "changedPixels": 0}
    assert "qualityValidated" not in report


def test_mismatched_image_shape_cannot_produce_preservation_claim():
    with pytest.raises(ValueError, match="inconsistent"):
        preservation_metrics(np.zeros((2, 3, 3)), np.zeros((2, 4, 3)), *(np.zeros((2, 3)),) * 3)


def test_collection_paths_cannot_escape_to_other_files(tmp_path):
    root = tmp_path / "collected"
    root.mkdir()
    (tmp_path / "private.json").write_text("{}")
    with pytest.raises(ValueError, match="out-of-scope"):
        artifact_path(root, "../private.json")
