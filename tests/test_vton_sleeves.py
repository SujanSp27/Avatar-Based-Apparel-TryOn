"""Pose mask/compositing regressions; no new neural inference is executed."""

import cv2
import numpy as np
import pytest

from ml.vton.masking import PROTECTED_LABELS, build_replacement_mask, short_sleeve_support
from ml.vton.parsing import compose_preserving_identity


@pytest.fixture
def vest():
    labels = np.zeros((512, 384), np.uint8)
    labels[140:350, 120:260] = 3
    labels[150:320, 85:120] = 12
    labels[150:320, 260:295] = 12
    labels[320:355, 85:120] = 13
    labels[350:, 120:260] = 6
    labels[50:130, 155:220] = 1
    labels[40:60, 150:220] = 2
    points = np.zeros((33, 4), float)
    for index, xy in {11: (120, 150), 12: (260, 150), 13: (95, 270), 14: (285, 270)}.items():
        points[index, :2] = np.array(xy) / [384, 512]
        points[index, 3] = 0.99
    return labels, points


def test_vest_to_short_sleeves_opens_both_upper_arms_without_forearms(vest):
    labels, points = vest
    support = short_sleeve_support(labels, points)
    before = build_replacement_mask(labels)
    after = build_replacement_mask(labels, sleeve_support=support)
    for y, x in ((210, 102), (210, 278)):
        assert labels[y, x] == 12
        assert before[y, x] == 0  # the recovered job's old dilation cannot edit here
        assert after[y, x] == 255
    assert not support[270:].any()
    assert np.all(after[labels == 3] == 255)
    assert not np.any(after[np.isin(labels, PROTECTED_LABELS)])
    assert not after[:, :70].any()


def test_pose_support_is_deterministic_and_scales_with_source_resolution(vest):
    labels, points = vest
    original, original_points = labels.copy(), points.copy()
    support = short_sleeve_support(labels, points)
    doubled = cv2.resize(labels, (768, 1024), interpolation=cv2.INTER_NEAREST)
    np.testing.assert_array_equal(support, short_sleeve_support(doubled, points)[::2, ::2])
    np.testing.assert_array_equal(labels, original)
    np.testing.assert_array_equal(points, original_points)


def test_sleeve_can_cover_the_skin_cap_above_the_shoulder_joint(vest):
    labels, points = vest
    # The pose joint is inside the shoulder, below its visible upper boundary.
    labels[127:150, 110:130] = 12
    labels[127:150, 250:270] = 12
    support = short_sleeve_support(labels, points)
    assert support[130, 120] and support[130, 260]
    assert not support[110, 120]  # bounded cap, not a whole-shoulder rectangle
    assert not support[270:].any()  # elbow/forearm preservation is unchanged


@pytest.mark.parametrize("bad", ["missing", "low_visibility", "outside", "nan", "detached"])
def test_unreliable_pose_cannot_expand_onto_an_unrelated_region(vest, bad):
    labels, points = vest
    if bad == "missing":
        points = None
    elif bad == "low_visibility":
        points[[13, 14], 3] = 0.1
    elif bad == "outside":
        points[[13, 14], 0] = 2
    elif bad == "nan":
        points[11, 0] = np.nan
    else:
        points[[11, 12, 13, 14], 1] -= 0.25
    assert not short_sleeve_support(labels, points).any()


def test_shared_sleeve_support_admits_only_neural_clothing_preserving_skin(vest):
    labels, points = vest
    support = short_sleeve_support(labels, points)
    rng = np.random.default_rng(40)
    original = rng.integers(0, 256, (*labels.shape, 3), dtype=np.uint8)
    generated = np.full_like(original, (40, 50, 70))
    target = labels.copy()
    target[support] = 3
    # Even a bad generated parser must not allow face/hair/hands/lower-clothes changes.
    target[np.isin(labels, PROTECTED_LABELS)] = 3
    result = compose_preserving_identity(
        original, generated, labels, target, sleeve_support=support,
    )
    for y, x in ((210, 102), (210, 278)):
        np.testing.assert_array_equal(result.image[y, x], generated[y, x])
    protected = np.isin(labels, PROTECTED_LABELS)
    np.testing.assert_array_equal(result.image[protected], original[protected])
    np.testing.assert_array_equal(result.image[280:310, 85:110], original[280:310, 85:110])
    result_without_sleeves = compose_preserving_identity(
        original, generated, labels, labels, sleeve_support=support,
    )
    np.testing.assert_array_equal(
        result_without_sleeves.image[labels == 12], original[labels == 12],
    )


def test_invalid_support_is_not_silently_converted_from_semantic_labels(vest):
    labels, _ = vest
    with pytest.raises(ValueError, match="boolean"):
        build_replacement_mask(labels, sleeve_support=labels)


def test_protected_regions_override_pose_corridors(vest):
    labels, points = vest
    for label in PROTECTED_LABELS:
        modified = labels.copy()
        modified[200:220, 90:115] = label
        support = short_sleeve_support(modified, points)
        assert not support[200:220, 90:115].any()
