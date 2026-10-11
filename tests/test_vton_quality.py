"""Catastrophic texture-loss checks, not proof of perceptual try-on quality."""

import json
from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image

from ml.vton.quality import assess_garment_fidelity


def fabric(*, stripe=True, warp=False, vertical=False, low_contrast=False):
    height, width = 320, 240
    y, x = np.indices((height, width), dtype=np.float32)
    coordinate = x if vertical else y
    if warp:
        coordinate = y * 1.15 + 12 * np.sin(x / 55) + 0.12 * x
    bands = ((coordinate % 26) < 7) if stripe else np.zeros((height, width), bool)
    dark = np.array([45, 96, 92], dtype=np.float32)
    light = dark + 12 if low_contrast else np.array([220, 225, 204], dtype=np.float32)
    rgb = np.where(bands[:, :, None], light, dark).astype(np.float32)
    if warp:
        rgb = rgb * (0.55 + 0.20 * np.cos(x[:, :, None] / 80))
    return rgb.clip(0, 255).astype(np.uint8), np.ones((height, width), dtype=bool)


def test_regular_pronounced_stripes_becoming_flat_are_rejected():
    source, mask = fabric()
    target, target_mask = fabric(stripe=False)
    result = assess_garment_fidelity(source, mask, target, target_mask)
    assert result.rejected
    assert result.reason == "pronounced_stripes_disappeared"
    assert result.reference["pronouncedHorizontalStripes"]
    assert result.generated["localLuminanceContrast"] < 1
    json.dumps(result.as_dict(), allow_nan=False)


@pytest.mark.parametrize("warp", [False, True])
def test_kept_stripes_with_different_spacing_curves_and_lighting_are_not_rejected(warp):
    source, mask = fabric()
    target, target_mask = fabric(warp=warp)
    result = assess_garment_fidelity(source, mask, target, target_mask)
    assert result.status == "not_rejected"
    assert not result.rejected


def test_generated_tilted_stripes_are_not_rejected():
    source, mask = fabric()
    rotation = cv2.getRotationMatrix2D((120, 160), 28, 1)
    target = cv2.warpAffine(source, rotation, (240, 320), borderMode=cv2.BORDER_REFLECT)
    result = assess_garment_fidelity(source, mask, target, mask)
    assert not result.rejected


@pytest.mark.parametrize("warp", [False, True])
def test_low_exposure_does_not_make_retained_stripes_fail(warp):
    source, mask = fabric()
    target, target_mask = fabric(warp=warp)
    target = (target.astype(float) * 0.12).astype(np.uint8)
    result = assess_garment_fidelity(source, mask, target, target_mask)
    assert not result.rejected
    assert result.generated["possibleRetainedStripeStructure"]


@pytest.mark.parametrize(
    "kind", ["solid", "vertical", "low_contrast", "random_texture", "checkerboard", "gradient"]
)
def test_unsupported_or_ambiguous_reference_textures_abstain(kind):
    source, mask = fabric(
        stripe=kind != "solid", vertical=kind == "vertical", low_contrast=kind == "low_contrast"
    )
    if kind == "random_texture":
        source = np.random.default_rng(21).integers(0, 256, source.shape, dtype=np.uint8)
    elif kind == "checkerboard":
        y, x = np.indices(mask.shape)
        source = np.repeat((30 + ((x // 12 + y // 12) % 2) * 180)[:, :, None], 3, axis=2).astype(
            np.uint8
        )
    elif kind == "gradient":
        source = np.broadcast_to(
            np.linspace(40, 225, source.shape[0], dtype=np.uint8)[:, None, None], source.shape
        ).copy()
    target, _ = fabric(stripe=False)
    result = assess_garment_fidelity(source, mask, target, mask)
    assert result.status == "abstained"
    assert not result.rejected


def test_textured_output_does_not_claim_to_have_matched_the_reference():
    source, mask = fabric()
    target = np.random.default_rng(7).integers(0, 256, source.shape, dtype=np.uint8)
    result = assess_garment_fidelity(source, mask, target, mask)
    assert result.status == "not_rejected"
    assert "passed" not in result.as_dict().values()


@pytest.mark.parametrize("which", ["reference", "generated"])
def test_unclear_semantic_crop_abstains(which):
    source, mask = fabric()
    target, target_mask = fabric(stripe=False)
    selected_mask = mask if which == "reference" else target_mask
    selected_mask[90:180, 100:130] = False
    result = assess_garment_fidelity(source, mask, target, target_mask)
    assert result.status == "abstained"
    assert result.reason == "insufficient_clear_fabric"


def test_empty_garment_mask_abstains():
    source, mask = fabric()
    result = assess_garment_fidelity(source, np.zeros_like(mask), source, mask)
    assert result.status == "abstained"


def test_different_input_resolutions_are_supported_without_pixel_alignment():
    source, mask = fabric()
    target, target_mask = fabric(warp=True)
    target = cv2.resize(target, (180, 256), interpolation=cv2.INTER_AREA)
    target_mask = cv2.resize(
        target_mask.astype(np.uint8), (180, 256), interpolation=cv2.INTER_NEAREST
    )
    result = assess_garment_fidelity(source, mask, target, target_mask)
    assert result.status == "not_rejected"


def test_reproducible_and_input_arrays_unchanged():
    source, mask = fabric()
    target, target_mask = fabric(stripe=False)
    originals = [a.copy() for a in (source, mask, target, target_mask)]
    first = assess_garment_fidelity(source, mask, target, target_mask).as_dict()
    assert first == assess_garment_fidelity(source, mask, target, target_mask).as_dict()
    for original, current in zip(originals, (source, mask, target, target_mask)):
        np.testing.assert_array_equal(original, current)


@pytest.mark.parametrize(
    "invalid", ["float_image", "wrong_mask_shape", "semantic_labels", "float_mask"]
)
def test_invalid_api_inputs_are_not_silently_interpreted(invalid):
    source, mask = fabric()
    if invalid == "float_image":
        source = source.astype(np.float32)
    elif invalid == "wrong_mask_shape":
        mask = mask[:100]
    elif invalid == "semantic_labels":
        mask = np.full_like(mask, 3, dtype=np.uint8)
    elif invalid == "float_mask":
        mask = mask.astype(np.float32)
    with pytest.raises(ValueError):
        assess_garment_fidelity(source, mask, source, mask)


def test_actual_retained_catvton_plain_shirt_is_rejected():
    # Private optional regression artifacts; no model/checkpoint loading or
    # sample-specific image hashes/coordinates occur in the quality algorithm.
    folder = (
        Path(__file__).resolve().parents[1]
        / "experiments/runs/catvton-initial/reported-striped-shirt"
    )
    names = [
        "vton-garment-input.png",
        "vton-garment-mask.png",
        "tryon-2d.png",
        "generatedParsing.png",
    ]
    if not all((folder / name).is_file() for name in names):
        pytest.skip("The retained private CatVTON regression artifacts are unavailable")
    source, source_mask, target, target_parse = [
        np.asarray(Image.open(folder / name)) for name in names
    ]
    result = assess_garment_fidelity(source, source_mask, target, target_parse == 3)
    assert result.rejected, result.as_dict()
