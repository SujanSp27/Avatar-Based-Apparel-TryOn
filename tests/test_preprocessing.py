from pathlib import Path

import numpy as np
import pytest

from ml.preprocessing.images import preprocess_garment

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.integration
def test_preprocessing_is_repeatable(processor, person_features):
    repeated = processor.process((ROOT / "data/raw/studio-person.jpg").read_bytes())
    assert np.array_equal(person_features.mask, repeated.mask)
    assert np.array_equal(person_features.landmarks, repeated.landmarks)


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
