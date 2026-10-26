from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from ml.vton.garment_fidelity import assess_dark_reference, fabric_statistics


def fabric(color):
    image = np.full((240, 180, 3), 250, dtype=np.uint8)
    mask = np.zeros((240, 180), dtype=bool)
    mask[30:210, 25:155] = True
    image[mask] = color
    return image, mask


def test_dark_blouse_with_invented_white_layer_is_rejected():
    reference, mask = fabric([22, 29, 44])
    generated = reference.copy()
    generated[100:210, 25:155] = 235
    report = assess_dark_reference(reference, mask, generated, mask)
    assert report["status"] == "rejected"
    assert report["generated"]["paleFraction"] > .5


def test_background_hair_skin_and_bag_are_not_fabric():
    reference, mask = fabric([22, 29, 44])
    generated = reference.copy()
    generated[~mask] = 255
    report = assess_dark_reference(reference, mask, generated, mask)
    assert report["status"] == "not_rejected"
    assert report["generated"]["paleFraction"] == 0


@pytest.mark.parametrize("color", [[245, 245, 245], [200, 40, 40], [130, 150, 155]])
def test_guard_abstains_on_non_dark_references(color):
    reference, mask = fabric(color)
    generated, _ = fabric([240, 240, 240])
    assert assess_dark_reference(reference, mask, generated, mask)["status"] == "abstained"


def test_mixed_reference_and_normal_shadows_are_not_rejected():
    reference, mask = fabric([22, 29, 44])
    generated = reference.copy()
    generated[70:180, 40:90] = [60, 70, 90]
    assert assess_dark_reference(reference, mask, generated, mask)["status"] == "not_rejected"
    reference[30:100, 25:155] = 240
    assert assess_dark_reference(reference, mask, generated, mask)["status"] == "abstained"


def test_ambiguous_mask_abstains_and_semantic_map_is_rejected():
    reference, mask = fabric([22, 29, 44])
    assert assess_dark_reference(reference, np.zeros_like(mask), reference, mask)["status"] == "abstained"
    with pytest.raises(ValueError, match="binary garment mask"):
        fabric_statistics(reference, mask.astype(np.uint8) * 3)


def test_retained_real_blouse_failure_is_detected_without_inference():
    folder = Path(__file__).resolve().parents[1] / 'experiments/blouse-fidelity/masked20'
    def read(name):
        return np.array(Image.open(folder / name))
    reference, reference_labels = read('garment-input.png'), read('garment-labels.png')
    source, target = read('source-labels.png'), read('target-labels.png')
    protected = np.isin(source, (1, 2, 8, 9, 11, 13, 15, 17))
    report = assess_dark_reference(reference, reference_labels == 3, read('raw.png'), (target == 3) & ~protected)
    assert report['status'] == 'rejected'
    assert report['reference']['paleFraction'] < .02
    assert report['generated']['paleFraction'] > .50
