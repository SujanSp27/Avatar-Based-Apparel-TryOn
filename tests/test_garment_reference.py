from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from ml.vton.garment_reference import prepare_reference


@pytest.fixture
def reference():
    folder = Path(__file__).resolve().parents[1] / 'experiments/blouse-fidelity/masked20'
    return Image.open(folder / 'garment-input.png'), np.array(Image.open(folder / 'garment-labels.png'))


def test_exact_reported_blouse_keeps_all_fabric_pixels_and_dimensions(reference):
    image, labels = reference
    prepared, report = prepare_reference(image, labels, 'tops', 'flat-lay')
    assert report['applied']
    assert prepared.size == image.size
    np.testing.assert_array_equal(np.array(prepared)[labels == 3], np.array(image)[labels == 3])
    assert np.all(np.array(prepared)[labels != 3] == 127)


@pytest.mark.parametrize('category,photo_type', [('tops', 'model'), ('bottoms', 'flat-lay'), ('one-pieces', 'flat-lay')])
def test_other_reference_paths_are_unchanged(reference, category, photo_type):
    image, labels = reference
    prepared, report = prepare_reference(image, labels, category, photo_type)
    assert not report['applied']
    assert prepared is image


def test_white_garment_and_incomplete_parser_are_unchanged(reference):
    image, labels = reference
    white = Image.new('RGB', image.size, 'white')
    assert not prepare_reference(white, labels, 'tops', 'flat-lay')[1]['applied']
    incomplete = labels.copy()
    incomplete[500:] = 0
    assert not prepare_reference(image, incomplete, 'tops', 'flat-lay')[1]['applied']


def test_complex_background_is_not_masked(reference):
    image, labels = reference
    pixels = np.array(image)
    pixels[0] = [30, 100, 50]
    prepared, report = prepare_reference(Image.fromarray(pixels), labels, 'tops', 'flat-lay')
    assert not report['applied']
    np.testing.assert_array_equal(np.array(prepared), pixels)


def test_photographed_shadow_is_background_but_missing_dark_fabric_is_not():
    pixels = np.full((240, 180, 3), 249, dtype=np.uint8)
    pixels[30:220, 20:160] = [165, 164, 158]  # Product shadow outside the fabric.
    labels = np.zeros((240, 180), dtype=np.uint8)
    labels[40:190, 30:150] = 3
    pixels[labels == 3] = [30, 35, 55]
    image = Image.fromarray(pixels)
    prepared, report = prepare_reference(image, labels, 'tops', 'flat-lay')
    assert report['applied']
    np.testing.assert_array_equal(np.asarray(prepared)[labels == 3], pixels[labels == 3])
    assert np.all(np.asarray(prepared)[labels == 0] == 127)
    incomplete = labels.copy()
    incomplete[40:80] = 0
    unchanged, report = prepare_reference(image, incomplete, 'tops', 'flat-lay')
    assert not report['applied']
    assert unchanged is image


def test_clipped_fabric_is_not_background_masked():
    pixels = np.full((240, 180, 3), 249, dtype=np.uint8)
    labels = np.zeros((240, 180), dtype=np.uint8)
    labels[40:240, 30:150] = 3
    pixels[labels == 3] = [30, 35, 55]
    image = Image.fromarray(pixels)
    assert not prepare_reference(image, labels, 'tops', 'flat-lay')[1]['applied']
