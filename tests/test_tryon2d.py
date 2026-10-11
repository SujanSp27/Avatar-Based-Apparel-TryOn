import copy
import io
from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image

from ml.errors import PipelineError
from ml.preprocessing.images import (
    ImageFeatures,
    PersonPreprocessor,
    decode_image,
    preprocess_garment,
)
from ml.tryon2d import render_tryon_2d
from ml.tryon2d.service import _skin


@pytest.fixture
def portrait_and_garment():
    person = np.full((400, 400, 3), 225, dtype=np.uint8)
    mask = np.zeros((400, 400), dtype=np.uint8)
    cv2.ellipse(mask, (200, 105), (49, 74), 0, 0, 360, 255, -1)
    cv2.rectangle(mask, (91, 186), (309, 399), 255, -1)
    person[mask > 0] = [25, 45, 65]
    person[30:174, 161:240] = [180, 125, 95]
    points = np.zeros((33, 4))
    points[:, 1] = 1.5
    points[0] = [0.5, 0.25, 0, 0.99]
    points[11] = [0.74, 0.51, 0, 0.99]
    points[12] = [0.26, 0.51, 0, 0.99]
    features = ImageFeatures(person, mask, person, (91, 30, 310, 400), points)
    garment = np.zeros((240, 240, 4), dtype=np.uint8)
    polygon = np.array(
        [
            [85, 10],
            [105, 28],
            [135, 28],
            [155, 10],
            [225, 60],
            [205, 103],
            [177, 92],
            [177, 239],
            [63, 239],
            [63, 92],
            [35, 103],
            [15, 60],
        ]
    )
    cv2.fillPoly(garment, [polygon], (80, 130, 210, 255))
    garment[70:110, 80:160] = [210, 205, 60, 255]
    source = ImageFeatures(garment[:, :, :3], garment[:, :, 3], garment, (0, 0, 240, 240))
    return features, source


def test_portrait_overlay_preserves_head_and_background_and_is_repeatable(
    portrait_and_garment, tmp_path
):
    person, garment = portrait_and_garment
    result = render_tryon_2d(person, garment, "t-shirt", "regular", tmp_path / "first")
    repeated = render_tryon_2d(person, garment, "t-shirt", "regular", tmp_path / "second")
    image = np.array(Image.open(tmp_path / "first/tryon-2d.png"))
    assert np.array_equal(image[:150], person.image[:150])
    assert np.array_equal(image[person.mask == 0], person.image[person.mask == 0])
    assert np.count_nonzero(np.any(image != person.image, axis=2)) > 10_000
    assert (tmp_path / "first/tryon-2d.png").read_bytes() == (
        tmp_path / "second/tryon-2d.png"
    ).read_bytes()
    assert result == repeated
    assert result["visibleRegion"] == "upper_body"
    assert result["diagnostics"]["physicalSizingAvailable"] is False
    assert "measurements" not in result and "recommendedSize" not in result
    assert (tmp_path / "first/overlay-diagnostics.json").is_file()
    assert np.array_equal(
        np.array(Image.open(tmp_path / "first/original-person.png")), person.image
    )


def test_beige_clothing_is_overlaid_while_face_and_pose_located_hand_are_preserved(
    portrait_and_garment, tmp_path
):
    person, garment = portrait_and_garment
    person.image[210:400, 91:310] = [190, 148, 116]
    assert np.all(_skin(person.image[230:310, 170:230]))
    person.landmarks[15] = [0.52, 0.8, 0, 0.95]
    person.landmarks[19] = [0.48, 0.77, 0, 0.95]
    person.image[306:318, 187:202] = [180, 125, 95]
    render_tryon_2d(person, garment, "t-shirt", "regular", tmp_path)
    output = np.array(Image.open(tmp_path / "tryon-2d.png"))
    assert np.array_equal(output[:150], person.image[:150])
    assert np.array_equal(output[306:318, 187:202], person.image[306:318, 187:202])
    chest = np.any(output[230:280, 170:230] != person.image[230:280, 170:230], axis=2)
    assert np.count_nonzero(chest) > 2500


def test_beige_uploaded_fabric_is_not_removed_as_exposed_skin(portrait_and_garment, tmp_path):
    person, garment = portrait_and_garment
    garment.crop[garment.crop[:, :, 3] > 0, :3] = [190, 148, 116]
    result = render_tryon_2d(person, garment, "t-shirt", "regular", tmp_path)
    assert result["diagnostics"]["overlaidPixels"] > 10_000
    output = np.array(Image.open(tmp_path / "tryon-2d.png"))
    assert np.array_equal(output[250, 200], [190, 148, 116])


@pytest.mark.parametrize("index", [11, 12])
def test_missing_shoulder_rejected(portrait_and_garment, tmp_path, index):
    person, garment = portrait_and_garment
    person.landmarks[index, 3] = 0.3
    with pytest.raises(PipelineError) as error:
        render_tryon_2d(person, garment, "shirt", "regular", tmp_path)
    assert error.value.code == "upper_body_not_visible"
    assert not (tmp_path / "tryon-2d.png").exists()


def test_face_only_crop_rejected(portrait_and_garment, tmp_path):
    person, garment = portrait_and_garment
    person.landmarks[[11, 12], 1] = 0.92
    with pytest.raises(PipelineError) as error:
        render_tryon_2d(person, garment, "shirt", "regular", tmp_path)
    assert error.value.code == "upper_body_not_visible"


def test_trousers_require_visible_lower_body(portrait_and_garment, tmp_path):
    person, garment = portrait_and_garment
    with pytest.raises(PipelineError) as error:
        render_tryon_2d(person, garment, "trouser", "regular", tmp_path)
    assert error.value.code == "lower_body_not_visible"
    assert "hips and knees" in str(error.value)


def test_cropped_dress_is_labeled_without_fabricating_lower_body(portrait_and_garment, tmp_path):
    person, garment = portrait_and_garment
    result = render_tryon_2d(person, garment, "dress", "loose", tmp_path)
    assert result["diagnostics"]["croppedBody"]
    assert any("skirt length" in warning for warning in result["warnings"])
    assert Image.open(tmp_path / "tryon-2d.png").size == (400, 400)


def test_three_dimensional_pose_validation_remains_strict(portrait_and_garment):
    person, _ = portrait_and_garment
    with pytest.raises(PipelineError) as error:
        PersonPreprocessor.validate_pose(copy.deepcopy(person))
    assert error.value.code == "partial_body"


def test_small_images_require_explicit_two_dimensional_relaxation():
    buffer = io.BytesIO()
    Image.new("RGB", (171, 191), "white").save(buffer, format="PNG")
    with pytest.raises(PipelineError) as error:
        decode_image(buffer.getvalue())
    assert error.value.code == "low_resolution"
    assert decode_image(buffer.getvalue(), min_dimension=128).shape == (191, 171, 4)


@pytest.mark.integration
def test_reported_portrait_and_small_worn_garment_render(tmp_path):
    root = Path(__file__).resolve().parents[1]
    failed = root / "data/processed/4fd1db83-60cb-460f-9887-985eb1ffb82f"
    if not (failed / "personInput.bin").exists():
        pytest.skip("Local user-upload regression fixture is not distributed")
    processor = PersonPreprocessor(root / "assets/bodyModels/pose_landmarker_full.task")
    person = processor.detect((failed / "personInput.bin").read_bytes())
    garment = preprocess_garment(
        (failed / "garmentInput.bin").read_bytes(), min_dimension=128, allow_worn=True
    )
    result = render_tryon_2d(person, garment, "t-shirt", "regular", tmp_path)
    assert result["diagnostics"]["overlaidPixels"] > 15_000
    assert any("small garment" in warning for warning in result["warnings"])
    with pytest.raises(PipelineError):
        processor.validate_pose(person)
