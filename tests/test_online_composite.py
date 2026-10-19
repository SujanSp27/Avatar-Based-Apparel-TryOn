"""Hem/preservation contracts on synthetic labels, not photographic fit claims."""

import cv2
import numpy as np
import pytest

from ml.errors import PipelineError
from ml.vton.online_composite import _align_shoulder_edge, preserve_regions


@pytest.fixture
def person():
    source = np.zeros((200, 160), dtype=np.uint8)
    source[10:35, 65:95] = 1
    source[45:125, 45:115] = 3
    source[125:195, 45:115] = 6
    source[116:139, 39:45] = 13
    source[195:, 45:115] = 15
    original = np.random.default_rng(17).integers(0, 256, (200, 160, 3), dtype=np.uint8)
    return original, 255 - original, source


@pytest.mark.parametrize("lower_label", [5, 6, 7])
def test_generated_top_can_cover_source_waistband_without_clipping(person, lower_label):
    original, generated, source = person
    source[source == 6] = lower_label
    target = source.copy()
    target[125:134, 45:115] = 3
    image, alpha, report = preserve_regions(original, generated, source, target, "tops")
    overlap = (source == lower_label) & (target == 3)
    assert overlap.any()
    assert np.all(alpha[overlap] > 0)
    assert np.all(alpha[127:131, 49:111] == 1)
    np.testing.assert_array_equal(image[127:131, 49:111], generated[127:131, 49:111])
    assert report["hemExtensionPixels"] == np.count_nonzero(overlap)
    assert report["hemExtensionLimitPixels"] == 10
    np.testing.assert_array_equal(image[140:], original[140:])


def test_excessive_generated_top_extension_does_not_replace_trouser_legs(person):
    original, generated, source = person
    target = source.copy()
    target[125:195, 45:115] = 3
    with pytest.raises(PipelineError) as failure:
        preserve_regions(original, generated, source, target, "tops")
    assert failure.value.code == "garment_length_changed"


def test_disconnected_target_top_island_cannot_overwrite_nearby_pants(person):
    original, generated, source = person
    target = source.copy()
    target[128:133, 60:90] = 3
    image, alpha, report = preserve_regions(original, generated, source, target, "tops")
    assert report["hemExtensionPixels"] == 0
    assert not alpha[source == 6].any()
    np.testing.assert_array_equal(image[source == 6], original[source == 6])


def test_oversized_connected_target_top_is_rejected_instead_of_leaving_pants_patch(person):
    original, generated, source = person
    target = source.copy()
    # Both strips are one target component, joined below the hem depth limit.
    # Clipping that distant join would leave isolated trouser patches. Reject
    # the distorted garment rather than presenting a partial result.
    target[125:175, 45:50] = 3
    target[170:175, 45:101] = 3
    target[128:175, 95:101] = 3
    with pytest.raises(PipelineError, match="extends too far"):
        preserve_regions(original, generated, source, target, "tops")


def test_hem_extension_requires_generated_clothing_and_preserves_protected_pixels(person):
    original, generated, source = person
    target = source.copy()
    target[125:134, 39:115] = 3
    target[130:134, 70:80] = 6  # A notch in the new hem remains trousers.
    target[source == 1] = 3  # A bad target label must never erase the face.
    image, alpha, report = preserve_regions(original, generated, source, target, "tops")
    protected = np.isin(source, (1, 13, 15))
    np.testing.assert_array_equal(image[protected], original[protected])
    assert not alpha[protected].any()
    assert not alpha[130:134, 70:80].any()
    assert np.all(alpha[source == 3] == 1)
    assert np.any((alpha > 0) & (alpha < 1))
    np.testing.assert_array_equal(image[alpha == 0], original[alpha == 0])
    assert report["identityPreservedExactly"]
    assert report["changedPixelsOutsideEditMask"] == 0


def test_sloping_source_hem_uses_local_contour_not_a_bounding_rectangle(person):
    original, generated, source = person
    # Raise the old hem on the left. A generated top spans its lower border,
    # but the local extension limit must still apply at each part of the hem.
    source[112:125, 45:70] = 6
    target = source.copy()
    target[110:139, 45:115] = 3
    image, alpha, report = preserve_regions(original, generated, source, target, "tops")
    old = source == 3
    below = np.zeros_like(old)
    below[:-1] = old[1:]
    hem = old & ~below
    proximity = cv2.distanceTransform((~hem).astype(np.uint8), cv2.DIST_L2, 5)
    lower_edit = (alpha > 0) & (source == 6)
    assert lower_edit[115, 50]
    assert lower_edit[125, 50]
    assert lower_edit[130, 100]
    assert np.all(proximity[lower_edit] <= report["hemExtensionLimitPixels"])
    np.testing.assert_array_equal(image[145:], original[145:])


def test_plausible_longer_top_keeps_its_complete_hem(person):
    original, generated, source = person
    target = source.copy()
    target[125:145, 45:115] = 3
    image, alpha, report = preserve_regions(original, generated, source, target, "tops")
    assert report["hemExtensionLimitPixels"] >= 20
    assert np.all(alpha[125:142, 49:111] == 1)
    np.testing.assert_array_equal(image[125:142, 49:111], generated[125:142, 49:111])
    np.testing.assert_array_equal(image[145:], original[145:])


def test_top_hem_policy_does_not_expand_a_bottom_into_source_top(person):
    original, generated, source = person
    target = source.copy()
    target[118:125, 45:115] = 6
    image, alpha, report = preserve_regions(original, generated, source, target, "bottoms")
    assert report["hemExtensionPixels"] == 0
    assert report["hemExtensionLimitPixels"] == 0
    assert not alpha[source == 3].any()
    np.testing.assert_array_equal(image[source == 3], original[source == 3])


def test_narrow_shoulder_gap_uses_neural_garment_and_preserves_other_pixels(person):
    original, generated, source = person
    source[65:95, 43:45] = 12
    target = source.copy()
    target[65:95, 43:45] = 0
    generated[source == 3] = (20, 50, 90)
    generated[target == 0] = 255
    before = generated.copy()
    image, alpha, report = preserve_regions(original, generated, source, target, "tops")
    assert report["shoulderProjectionPixels"] == 60
    assert np.all(image[65:95, 43:45] == (20, 50, 90))
    assert np.all(alpha[65:95, 43:45] == 1)
    np.testing.assert_array_equal(image[alpha == 0], original[alpha == 0])
    np.testing.assert_array_equal(generated, before)


@pytest.mark.parametrize("source_label,target_label", [(13, 0), (1, 0), (16, 0), (12, 12)])
def test_boundary_projection_cannot_paint_hands_head_neck_or_predicted_skin(person, source_label, target_label):
    _, generated, source = person
    source[65:95, 43:45] = source_label
    target = source.copy()
    target[65:95, 43:45] = target_label
    image, projected = _align_shoulder_edge(generated, source, target, target == 3, 2)
    assert not projected.any()
    np.testing.assert_array_equal(image, generated)


def test_projection_does_not_hide_a_broad_shrunken_arm(person):
    _, generated, source = person
    source[65:95, 30:45] = 12
    target = source.copy()
    target[source == 12] = 0
    image, projected = _align_shoulder_edge(generated, source, target, target == 3, 2)
    assert not projected.any()
    np.testing.assert_array_equal(image, generated)
