import hashlib

import numpy as np
import torch
from PIL import Image

from ml.vton.input_audit import image_record, save_conditioning


def test_audit_captures_actual_sampler_conditioning_without_mutation(tmp_path):
    pixels = np.random.default_rng(5).integers(0, 256, (32, 24, 3), dtype=np.uint8)
    tensor = (torch.from_numpy(pixels).permute(2, 0, 1).float() / 127.5 - 1)[None]
    keys = ["ca_images", "garment_images", "person_poses", "garment_poses"]
    before = tensor.clone()
    report = save_conditioning(tmp_path, dict.fromkeys(keys, tensor))
    assert torch.equal(tensor, before)
    assert set(report) == set(keys)
    assert report["garment_images"]["shape"] == [32, 24, 3]
    np.testing.assert_array_equal(np.asarray(Image.open(tmp_path / "garment-conditioning.png")), pixels)
    assert (tmp_path / "conditioning.json").is_file()
    assert image_record(Image.fromarray(pixels)) == {
        "size": [24, 32], "rgbSha256": hashlib.sha256(pixels.tobytes()).hexdigest(),
    }
