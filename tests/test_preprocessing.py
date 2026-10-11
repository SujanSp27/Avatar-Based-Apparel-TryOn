from pathlib import Path

import numpy as np
import pytest

from ml.errors import PipelineError
from ml.preprocessing.images import ImageFeatures, PersonPreprocessor, preprocess_garment

ROOT = Path(__file__).resolve().parents[1]


def test_cropped_portrait_is_reported_before_low_joint_visibility():
    # Pose detectors extrapolate missing legs below the edge of an upper-body photo.
    points = np.full((33, 4), 0.5)
    points[:, 3] = 1.0
    points[[23, 24, 25, 26, 27, 28, 31, 32], 1] = 1.5
    points[[23, 24, 25, 26, 27, 28, 31, 32], 3] = 0.01
    image = np.zeros((256, 256, 3), dtype=np.uint8)
    features = ImageFeatures(
        image, np.zeros((256, 256), dtype=np.uint8), image, (10, 10, 245, 245), points
    )
    with pytest.raises(PipelineError) as error:
        PersonPreprocessor.validate_pose(features)
    assert error.value.code == "partial_body"
    assert "head-to-toe" in str(error.value)
    assert "Portraits and waist-up photos are not supported" in str(error.value)


@pytest.mark.integration
def test_preprocessing_is_repeatable(processor, person_features):
    repeated = processor.process((ROOT / "data/raw/studio-person.jpg").read_bytes())
    assert np.array_equal(person_features.mask, repeated.mask)
    assert np.array_equal(person_features.landmarks, repeated.landmarks)


@pytest.mark.integration
@pytest.mark.parametrize("name", ["coco-241.jpg", "coco-294.jpg", "coco-328.jpg", "yoga.jpg"])
def test_multiple_cropped_and_extreme_poses_rejected(processor, name):
    path = ROOT / "data/raw" / name
    if not path.exists():
        pytest.skip("Optional rejection sample missing")
    with pytest.raises(PipelineError):
        processor.process(path.read_bytes())


def test_light_fabric_stripes_do_not_split_garment():
    path = ROOT / "data/raw/garment-demo.png"
    if not path.exists():
        pytest.skip("Run scripts/create_demo_garment.py")
    features = preprocess_garment(path.read_bytes())
    assert features.crop.shape[0] > 400
    assert features.mask.sum() > 25_000_000
    light_fabric = np.all(features.image[:, :, :3] == [217, 223, 201], axis=2)
    assert light_fabric.any()
    assert np.all(features.mask[light_fabric] == 255)
    assert not np.any(features.mask[:20])
