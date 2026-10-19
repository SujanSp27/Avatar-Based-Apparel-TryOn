import numpy as np
import pytest

from ml.vton.region import inference_region, lower_body_visible


def labels():
    result = np.zeros((600, 400), dtype=np.uint8)
    result[50:100, 170:220] = 1
    result[100:310, 130:270] = 3
    result[200:340, 110:130] = 12
    result[340:360, 105:130] = 13
    result[310:540, 145:255] = 6
    result[540:570, 145:255] = 15
    return result


def test_top_crop_keeps_face_hands_and_space_below_hem():
    source = labels()
    left, top, right, bottom = inference_region(source, 'tops')
    selected = np.isin(source, (1, 3, 12, 13))
    inside = np.zeros_like(selected)
    inside[top:bottom, left:right] = True
    assert np.all(inside[selected])
    assert bottom > 360 and bottom < 540
    assert left < 105 and right > 270 and top < 50


@pytest.mark.parametrize('category', ['bottoms', 'one-pieces'])
def test_other_categories_keep_the_whole_person(category):
    source = labels()
    left, top, right, bottom = inference_region(source, category)
    inside = np.zeros_like(source, dtype=bool)
    inside[top:bottom, left:right] = True
    assert np.all(inside[source != 0])
    assert 0 <= left < right <= 400 and 0 <= top < bottom <= 600


def test_empty_and_frame_filling_maps_are_bounded():
    assert inference_region(np.zeros((200, 160), np.uint8), 'tops') == (0, 0, 160, 200)
    assert inference_region(np.full((200, 160), 3, np.uint8), 'tops') == (0, 0, 160, 200)


@pytest.mark.parametrize('lower_label', [4, 5, 6, 14])
def test_full_body_visibility_is_invariant_to_background_padding(lower_label):
    source = labels()
    source[source == 6] = lower_label
    assert lower_body_visible(source)
    padded = np.pad(source, ((600, 600), (500, 500)))
    # The old whole-image 8% threshold wrongly rejects this full-body photo.
    assert np.mean(np.isin(padded, (4, 5, 6, 14, 15))) < .08
    assert lower_body_visible(padded)


def test_portrait_or_tiny_lower_label_island_does_not_pass_visibility():
    portrait = labels()
    portrait[310:] = 0
    assert not lower_body_visible(portrait)
    portrait[290:295, 170:180] = 6
    assert not lower_body_visible(portrait)
    assert not lower_body_visible(np.zeros((200, 160), np.uint8))
