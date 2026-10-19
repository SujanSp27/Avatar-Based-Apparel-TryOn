"""Exact pixel transport, using local CPU fixtures only."""
import io

import numpy as np
import pytest
from PIL import Image

from ml.vton.image_transport import encode_changed_pixels, restore_changed_pixels


@pytest.mark.parametrize("opaque_rectangle", [False, True])
def test_changed_pixel_transport_matches_entire_output_exactly(opaque_rectangle):
    pixels = np.random.default_rng(7).integers(0, 256, (200, 160, 3), dtype=np.uint8)
    original = Image.fromarray(pixels)
    generated = pixels.copy()
    generated[60:120, 40:110] = [70, 90, 100]
    if not opaque_rectangle:
        generated[80:100, 55:75] = pixels[80:100, 55:75]
    expected = Image.fromarray(generated)
    encoded, metadata = encode_changed_pixels(original, expected)
    with Image.open(io.BytesIO(encoded)) as patch:
        actual = restore_changed_pixels(original, patch, metadata["patchBox"], metadata["canvasSize"])
    assert actual.tobytes() == expected.tobytes()
    assert original.tobytes() == pixels.tobytes()
    assert metadata["patchBox"] == [40, 60, 110, 120]
    assert len(encoded) < len(pixels.tobytes()) * .1


@pytest.mark.parametrize("box,canvas", [
    ([-1, 0, 4, 4], [16, 20]), ([0, 0, 17, 4], [16, 20]),
    ([0, 0, 0, 4], [16, 20]), ([False, 0, 4, 4], [16, 20]),
    ([0, 0, 4, 4], [16, 21]), ([0, 0, 4, 4], None),
    (None, [16, 20]), ([0., 0, 4, 4], [16, 20]),
])
def test_patch_bounds_and_canvas_are_validated(box, canvas):
    with pytest.raises(ValueError):
        restore_changed_pixels(Image.new("RGB", (16, 20)), Image.new("RGBA", (4, 4)), box, canvas)


@pytest.mark.parametrize("alpha", [0, 128, 254])
def test_empty_or_blending_alpha_is_rejected(alpha):
    with pytest.raises(ValueError, match="binary"):
        restore_changed_pixels(Image.new("RGB", (16, 20)),
                               Image.new("RGBA", (4, 4), (10, 20, 30, alpha)),
                               [0, 0, 4, 4], [16, 20])


def test_unchanged_generated_result_is_not_encoded_as_success():
    image = Image.new("RGB", (16, 20))
    with pytest.raises(ValueError, match="does not change"):
        encode_changed_pixels(image, image)
