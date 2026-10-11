"""Inference-mask contracts; these tests do not establish photographic realism."""

from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image

from ml.errors import PipelineError
from ml.vton.masking import NATIVE_SHAPE, PROTECTED_LABELS, build_replacement_mask


@pytest.fixture
def native_labels():
    labels = np.zeros(NATIVE_SHAPE, dtype=np.uint8)
    cv2.fillPoly(
        labels,
        [
            np.array(
                [
                    [100, 170],
                    [150, 150],
                    [220, 150],
                    [280, 170],
                    [300, 240],
                    [260, 250],
                    [250, 420],
                    [120, 420],
                    [110, 250],
                    [80, 240],
                ],
                dtype=np.int32,
            )
        ],
        3,
    )
    labels[100:145, 155:215] = 1
    labels[90:110, 150:220] = 2
    labels[240:330, 75:105] = 12
    labels[240:330, 275:305] = 12
    labels[330:345, 75:105] = 13
    labels[421:, 120:250] = 6
    return labels


def test_replacement_covers_every_old_shirt_pixel_without_a_rectangle(native_labels):
    result = build_replacement_mask(native_labels)
    assert result.dtype == np.uint8
    assert set(np.unique(result)) == {0, 255}
    assert np.all(result[native_labels == 3] == 255)
    ys, xs = np.where(result)
    assert not np.all(result[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1])


def test_only_narrow_adjacent_background_arm_and_torso_context_opens(native_labels):
    native_labels[165:180, 95:100] = 16
    result = build_replacement_mask(native_labels)
    extension = (result > 0) & (native_labels != 3)
    assert set(np.unique(native_labels[extension])) == {0, 12, 16}
    assert not np.any(result[:70])
    assert not np.any(result[:, :50])
    distance = cv2.distanceTransform((native_labels != 3).astype(np.uint8), cv2.DIST_L2, 5)
    # OpenCV's discrete elliptical kernel has subpixel radius approximation.
    assert float(distance[extension].max()) < 9


@pytest.mark.parametrize("protected_label", PROTECTED_LABELS)
def test_head_hands_other_clothes_and_lower_limbs_are_never_masked(protected_label):
    labels = np.zeros(NATIVE_SHAPE, dtype=np.uint8)
    labels[190:260, 130:220] = 3
    labels[190:260, 220:226] = protected_label
    result = build_replacement_mask(labels)
    assert np.all(result[labels == protected_label] == 0)
    assert np.all(result[labels == 3] == 255)


def test_head_guard_is_small_and_does_not_unmask_a_collar():
    labels = np.zeros(NATIVE_SHAPE, dtype=np.uint8)
    labels[150:200, 160:220] = 1
    labels[202:280, 160:220] = 3
    result = build_replacement_mask(labels)
    assert np.all(result[198:202, 160:220] == 0)
    assert np.all(result[202:280, 160:220] == 255)
    assert result[205, 157] == 255


def test_output_is_repeatable_and_does_not_mutate_labels(native_labels):
    before = native_labels.copy()
    first = build_replacement_mask(native_labels)
    second = build_replacement_mask(native_labels)
    np.testing.assert_array_equal(first, second)
    np.testing.assert_array_equal(before, native_labels)


def test_missing_shirt_fails_before_inference():
    with pytest.raises(PipelineError) as caught:
        build_replacement_mask(np.zeros(NATIVE_SHAPE, dtype=np.uint8))
    assert caught.value.code == "vton_clothing_not_found"


@pytest.mark.parametrize(
    "labels",
    [
        np.zeros((384, 512), np.uint8),
        np.zeros(NATIVE_SHAPE, float),
        np.full(NATIVE_SHAPE, 18, np.uint8),
        np.full(NATIVE_SHAPE, -1, np.int8),
    ],
)
def test_invalid_native_semantics_are_rejected(labels):
    with pytest.raises(ValueError):
        build_replacement_mask(labels)


def test_retained_reported_person_has_over_99_percent_latent_shirt_coverage():
    # Uses the retained parser output only: no parser/GPU/checkpoint is loaded.
    # These coordinates are the recorded crop for the reported regression input.
    root = Path(__file__).resolve().parents[1]
    path = root / "experiments/runs/catvton-initial/reported-striped-shirt/personParsing.png"
    if not path.is_file():
        pytest.skip("The private reported-person parsing fixture is not present")
    with Image.open(path) as source:
        if source.size != (1000, 1500):
            pytest.skip("The saved regression input has different crop coordinates")
        cropped = source.crop((230, 142, 756, 842))
        native = np.zeros(NATIVE_SHAPE, dtype=np.uint8)
        native[:511] = np.asarray(cropped.resize((384, 511), Image.Resampling.NEAREST))
    mask = build_replacement_mask(native) > 0
    # torch.interpolate(..., mode='nearest') samples the top-left of each 8x8 block.
    latent_coverage = mask[::8, ::8].repeat(8, axis=0).repeat(8, axis=1)
    old = native == 3
    assert np.mean(latent_coverage[old]) > 0.99
    assert np.all(mask[old])
    assert not np.any(mask[np.isin(native, PROTECTED_LABELS)])
