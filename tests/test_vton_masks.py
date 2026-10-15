"""Semantic replacement must preserve identity without leaking the old shirt.

These tests establish pixel and loading contracts, not photographic fit quality.
The optional integration case runs the real local pretrained parser.
"""

import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image

from ml.errors import PipelineError
from ml.vton.parsing import (
    FashnHumanParser,
    HumanParse,
    clothing_mask,
    compose_preserving_identity,
    preservation_mask,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def semantic_person():
    labels = np.zeros((120, 100), dtype=np.uint8)
    cv2.ellipse(labels, (50, 19), (13, 17), 0, 0, 360, 2, -1)
    cv2.ellipse(labels, (50, 22), (9, 12), 0, 0, 360, 1, -1)
    labels[33:47, 43:58] = 16
    cv2.fillPoly(
        labels,
        [
            np.array(
                [
                    (31, 43),
                    (43, 41),
                    (48, 45),
                    (56, 41),
                    (69, 43),
                    (80, 62),
                    (68, 68),
                    (67, 95),
                    (32, 95),
                    (31, 68),
                    (20, 61),
                ],
                np.int32,
            )
        ],
        3,
    )
    labels[63:83, 18:29] = 12
    labels[65:86, 72:82] = 12
    labels[83:89, 17:29] = 13
    labels[86:92, 73:82] = 13
    labels[96:120, 33:66] = 6
    # A separate bare-torso region must not be changed by a wide collar mask.
    labels[100:104, 20:24] = 16
    rgb = np.random.default_rng(10).integers(0, 256, (*labels.shape, 3), dtype=np.uint8)
    generated = 255 - rgb
    return rgb, generated, labels


def test_identity_limbs_and_lower_body_are_preserved_exactly(semantic_person):
    original, generated, labels = semantic_person
    result = compose_preserving_identity(original, generated, labels, labels)
    for label in (1, 2, 6, 12, 13):
        assert np.any(labels == label)
        np.testing.assert_array_equal(result.image[labels == label], original[labels == label])
    assert result.diagnostics["identityPreservedExactly"] is True
    assert result.diagnostics["changedPixelsOutsideEditMask"] == 0
    np.testing.assert_array_equal(original[result.preserve_mask], result.image[result.preserve_mask])
    assert not result.edit_mask[:10].any()


def test_old_clothing_is_fully_opaque_even_when_generated_parse_disagrees(semantic_person):
    original, generated, labels = semantic_person
    target = labels.copy()
    target[labels == 3] = 0
    result = compose_preserving_identity(original, generated, labels, target)
    old = labels == 3
    assert np.all(result.alpha[old] == 1.0)
    np.testing.assert_array_equal(result.image[old], generated[old])
    assert result.diagnostics["oldClothingMinimumAlpha"] == 1.0


def test_edit_mask_follows_semantics_not_bounding_rectangle(semantic_person):
    original, generated, labels = semantic_person
    result = compose_preserving_identity(original, generated, labels, labels)
    ys, xs = np.where(result.edit_mask)
    rectangle = result.edit_mask[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
    assert not rectangle.all()
    assert result.edit_mask[labels == 3].all()
    assert not result.edit_mask[labels == 1].any()


def test_collar_extension_requires_adjacent_torso_and_generated_clothing(semantic_person):
    original, generated, labels = semantic_person
    target = labels.copy()
    target[labels == 16] = 3
    # Even when a generator labels the face as clothing, it stays protected.
    target[labels == 1] = 3
    result = compose_preserving_identity(original, generated, labels, target)
    extra = result.edit_mask & (labels != 3)
    assert np.any(extra)
    assert np.all(np.isin(labels[extra], (0, 16)))
    assert np.any((result.alpha[extra] > 0) & (result.alpha[extra] < 1))
    assert not result.edit_mask[100:104, 20:24].any()
    np.testing.assert_array_equal(result.image[labels == 1], original[labels == 1])


def test_bare_torso_changes_are_limited_to_the_collar_context(semantic_person):
    original, generated, labels = semantic_person
    result = compose_preserving_identity(original, generated, labels, labels)
    distance = cv2.distanceTransform((labels != 3).astype(np.uint8), cv2.DIST_L2, 5)
    limit = (
        result.diagnostics["sourceContextRadiusPixels"]
        + result.diagnostics["outerFeatherWidthPixels"]
    )
    untouched = (labels == 16) & (distance > limit)
    assert untouched.any()
    np.testing.assert_array_equal(result.image[untouched], original[untouched])


def test_local_parser_boundary_context_removes_original_shirt_outline():
    labels = np.zeros((1000, 1000), dtype=np.uint8)
    labels[300:700, 300:700] = 3
    labels[270:300, 430:570] = 16
    original = np.full((*labels.shape, 3), 210, dtype=np.uint8)
    generated = np.full_like(original, (15, 115, 110))
    result = compose_preserving_identity(original, generated, labels, labels)
    # Parser boundaries may miss a few fabric pixels around collar/shoulder.
    np.testing.assert_array_equal(result.image[297, 450], generated[297, 450])
    np.testing.assert_array_equal(result.image[400, 297], generated[400, 297])
    assert 0 < result.alpha[400, 294] < 1
    np.testing.assert_array_equal(result.image[400, 290], original[400, 290])


def test_generated_sleeves_may_cover_adjacent_arms_but_not_hands_or_lower_clothes():
    labels = np.zeros((1000, 1000), dtype=np.uint8)
    labels[300:600, 300:700] = 3
    labels[400:600, 280:300] = 12
    labels[400:600, 270:280] = 13
    labels[600:900, 300:700] = 6
    labels[280:300, 400:450] = 1
    labels[280:300, 450:500] = 2
    generated_labels = labels.copy()
    generated_labels[275:610, 260:720] = 3
    original = np.zeros((*labels.shape, 3), dtype=np.uint8)
    generated = np.full_like(original, 230)
    result = compose_preserving_identity(original, generated, labels, generated_labels)
    assert result.alpha[450, 295] == 1
    assert result.alpha[450, 280] == 0
    assert result.alpha[450, 710] == 1
    for label in (1, 2, 6, 13):
        np.testing.assert_array_equal(result.image[labels == label], original[labels == label])
    # Unrelated hallucinated clothing cannot replace a distant body region.
    assert not result.edit_mask[250].any()


def test_generated_clothing_is_required_to_extend_onto_arms(semantic_person):
    original, generated, labels = semantic_person
    target = np.zeros_like(labels)
    result = compose_preserving_identity(original, generated, labels, target)
    assert not result.edit_mask[labels == 12].any()


def test_composite_is_deterministic_and_does_not_mutate_inputs(semantic_person):
    original, generated, labels = semantic_person
    copies = [image.copy() for image in semantic_person]
    first = compose_preserving_identity(original, generated, HumanParse(labels), labels)
    second = compose_preserving_identity(original, generated, labels, labels)
    np.testing.assert_array_equal(first.image, second.image)
    np.testing.assert_array_equal(first.alpha, second.alpha)
    assert first.diagnostics == second.diagnostics
    for before, after in zip(copies, semantic_person):
        np.testing.assert_array_equal(before, after)


def test_inference_seam_context_cannot_restore_old_shoulder_or_edit_face():
    labels = np.zeros((512, 384), np.uint8)
    labels[150:350, 160:240] = 3
    labels[120:220, 110:150] = 12
    labels[60:110, 160:220] = 1
    labels[350:490, 140:250] = 6
    generated_labels = labels.copy()
    generated_labels[115:220, 105:150] = 3
    generated_labels[labels == 1] = 3  # Bad generated labels never override identity.
    inference = np.zeros_like(labels, dtype=bool)
    inference[50:350, 100:250] = True
    original = np.full((*labels.shape, 3), 200, np.uint8)
    generated = np.full_like(original, 40)
    composite = compose_preserving_identity(
        original, generated, labels, generated_labels, inference_support=inference,
    )
    assert np.all(composite.image[140, 125] == 40)
    assert np.array_equal(composite.image[labels == 1], original[labels == 1])
    assert np.array_equal(composite.image[labels == 6], original[labels == 6])
    assert np.array_equal(composite.image[400], original[400])
    assert np.all(composite.alpha[labels == 3] == 1)


def test_shrunken_generated_shoulders_are_rejected_instead_of_erasing_skin():
    labels = np.zeros((512, 384), np.uint8)
    labels[150:350, 160:240] = 3
    labels[120:250, 100:155] = 12
    target = labels.copy()
    target[120:170, 100:155] = 0
    original = np.full((*labels.shape, 3), 200, np.uint8)
    generated = np.full_like(original, 40)
    with pytest.raises(PipelineError) as error:
        compose_preserving_identity(
            original, generated, labels, target, inference_support=labels == 12,
        )
    assert error.value.code == "vton_body_shape_changed"


def test_trousers_only_replace_lower_clothing(semantic_person):
    original, generated, labels = semantic_person
    result = compose_preserving_identity(original, generated, labels, labels, "trouser")
    assert np.array_equal(result.edit_mask, labels == 6)
    np.testing.assert_array_equal(result.image[labels == 3], original[labels == 3])


def test_supported_category_masks_and_invalid_category():
    labels = np.arange(18, dtype=np.uint8).reshape(3, 6)
    assert set(labels[clothing_mask(labels, "dress")]) == {3, 4, 5}
    assert set(labels[clothing_mask(labels, "shirt")]) == {3}
    assert set(labels[~preservation_mask(labels)]) == {3, 16}
    with pytest.raises(PipelineError) as caught:
        clothing_mask(labels, "hat")
    assert caught.value.code == "garment_category"


def test_missing_clothing_returns_actionable_error(semantic_person):
    original, generated, labels = semantic_person
    labels[labels == 3] = 16
    with pytest.raises(PipelineError) as caught:
        compose_preserving_identity(original, generated, labels, labels)
    assert caught.value.code == "clothing_not_visible"


@pytest.mark.parametrize(
    "bad_labels", [np.ones((4, 4)) * 3.5, np.full((4, 4), 18), np.ones((4, 4, 3), np.uint8)]
)
def test_invalid_semantic_maps_are_rejected(bad_labels):
    with pytest.raises(ValueError):
        clothing_mask(bad_labels)


def test_mismatched_image_dimensions_are_rejected(semantic_person):
    original, generated, labels = semantic_person
    with pytest.raises(ValueError, match="identical"):
        compose_preserving_identity(original, generated[:-1], labels, labels)


def test_diagnostics_write_actual_masks(semantic_person, tmp_path):
    original, generated, labels = semantic_person
    result = compose_preserving_identity(original, generated, labels, labels)
    result.save_diagnostics(tmp_path)
    saved = np.array(Image.open(tmp_path / "old-clothing-mask.png"))
    np.testing.assert_array_equal(saved, (labels == 3).astype(np.uint8) * 255)
    assert json.loads((tmp_path / "semantic-composite.json").read_text())[
        "identityPreservedExactly"
    ]


def test_missing_parser_assets_never_download_or_claim_success(tmp_path):
    parser = FashnHumanParser(tmp_path)
    assert not parser.available()
    with pytest.raises(PipelineError) as caught:
        parser.predict(np.zeros((32, 32, 3), dtype=np.uint8))
    assert caught.value.code == "parser_unavailable"
    assert caught.value.status_code == 503
    assert not list(tmp_path.iterdir())


def test_corrupt_checkpoint_is_rejected_before_loading_model(tmp_path):
    for name in ("config.json", "download-manifest.json"):
        (tmp_path / name).write_text("{}")
    (tmp_path / "model.safetensors").write_bytes(b"corrupted")
    parser = FashnHumanParser(tmp_path)
    with pytest.raises(PipelineError) as caught:
        parser.predict(np.zeros((32, 32, 3), dtype=np.uint8))
    assert caught.value.code == "parser_checkpoint_invalid"
    assert parser._parser is None


def test_corrupt_parser_config_is_rejected_before_loading_model(tmp_path, monkeypatch):
    import ml.vton.parsing as parsing

    weights = b"isolated unit-test checkpoint"
    monkeypatch.setattr(parsing, "CHECKPOINT_SHA256", hashlib.sha256(weights).hexdigest())
    (tmp_path / "model.safetensors").write_bytes(weights)
    (tmp_path / "config.json").write_text("{}")
    (tmp_path / "download-manifest.json").write_text("{}")
    parser = FashnHumanParser(tmp_path)
    with pytest.raises(PipelineError, match="configuration checksum") as caught:
        parser.predict(np.zeros((32, 32, 3), dtype=np.uint8))
    assert caught.value.code == "parser_checkpoint_invalid"
    assert parser._parser is None


@pytest.mark.integration
def test_real_local_parser_runs_deterministically_with_expected_person_regions():
    parser = FashnHumanParser()
    person_path = ROOT / "data/raw/studio-person.jpg"
    if not parser.available() or not person_path.is_file():
        pytest.skip("Download the official parser and sample images first")
    image = np.array(Image.open(person_path).convert("RGB"))
    result = parser.predict(image)
    repeated = parser.predict(image)
    assert result.labels.shape == image.shape[:2]
    assert {0, 1, 2, 3, 6, 12, 13}.issubset(set(np.unique(result.labels)))
    np.testing.assert_array_equal(result.labels, repeated.labels)
    assert result.diagnostics["device"] == "cpu"
    assert "checkpointSha256" in result.diagnostics
