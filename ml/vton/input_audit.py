"""Record actual model conditioning for reproducible garment-fidelity review.

No models, GPU, image edits or inference are started by this module.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image


def image_record(image: Image.Image) -> dict:
    rgb = image.convert("RGB")
    return {"size": list(rgb.size), "rgbSha256": hashlib.sha256(rgb.tobytes()).hexdigest()}


def save_conditioning(folder: Path, tensors: dict) -> dict:
    """Capture the tensors passed to the pinned sampler, not a parallel preview.

    RGB/pose tensors use the official [-1, 1] normalization. Float32 byte hashes
    identify their exact values after conversion from the inference dtype; PNGs
    are inspection aids rounded back to uint8, not re-fed into the model.
    """
    records = {}
    for key, name in (
        ("ca_images", "person-conditioning"),
        ("garment_images", "garment-conditioning"),
        ("person_poses", "person-pose"),
        ("garment_poses", "garment-pose"),
    ):
        tensor = tensors[key][0].detach().float().cpu()
        array = np.ascontiguousarray(tensor.permute(1, 2, 0).numpy())
        if array.ndim != 3 or array.shape[2] not in {1, 3} or not np.isfinite(array).all():
            raise ValueError("Invalid model conditioning tensor")
        pixels = np.rint((array + 1) * 127.5).clip(0, 255).astype(np.uint8)
        if pixels.shape[2] == 1:
            pixels = pixels[:, :, 0]
        Image.fromarray(pixels).save(folder / f"{name}.png")
        records[key] = {"shape": list(array.shape),
                        "float32Sha256": hashlib.sha256(array.tobytes()).hexdigest()}
    (folder / "conditioning.json").write_text(json.dumps(records, indent=2))
    return records
