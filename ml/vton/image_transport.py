"""Lossless image transport; imports no model, Torch or local GPU runtime."""
import io

from PIL import Image, ImageChops


def encode_changed_pixels(original: Image.Image, result: Image.Image) -> tuple[bytes, dict]:
    """Return an exact RGBA patch instead of retransmitting unchanged pixels."""
    if original.size != result.size or original.mode != "RGB" or result.mode != "RGB":
        raise ValueError("Expected matching RGB images")
    channels = ImageChops.difference(original, result).split()
    delta = ImageChops.lighter(ImageChops.lighter(channels[0], channels[1]), channels[2])
    box = delta.getbbox()
    if box is None:
        raise ValueError("Generated result does not change the person image")
    changed = delta.crop(box).point(lambda value: 255 if value else 0)
    patch = Image.new("RGBA", (box[2] - box[0], box[3] - box[1]))
    patch.paste(result.crop(box), (0, 0), changed)
    output = io.BytesIO()
    patch.save(output, format="WEBP", lossless=True, quality=0, method=0)
    return output.getvalue(), {"patchBox": list(box), "canvasSize": list(original.size)}


def restore_changed_pixels(original: Image.Image, patch: Image.Image, box, canvas_size) -> Image.Image:
    """Validate bounds and exact replacement alpha before applying a patch."""
    if (not isinstance(box, list) or len(box) != 4
            or any(type(value) is not int for value in box)
            or not isinstance(canvas_size, list) or len(canvas_size) != 2
            or any(type(value) is not int for value in canvas_size)
            or canvas_size != list(original.size)):
        raise ValueError("Invalid generated patch coordinates")
    left, top, right, bottom = box
    if not (0 <= left < right <= original.width and 0 <= top < bottom <= original.height):
        raise ValueError("Generated patch is outside the original image")
    if patch.size != (right - left, bottom - top) or patch.mode not in {"RGB", "RGBA"}:
        raise ValueError("Generated patch dimensions or mode are invalid")
    # WebP decoders may omit the alpha channel for a fully opaque rectangle.
    alpha = patch.getchannel("A") if patch.mode == "RGBA" else Image.new("L", patch.size, 255)
    histogram = alpha.histogram()
    if any(histogram[1:255]) or not histogram[255]:
        raise ValueError("Generated patch must use exact binary replacement alpha")
    output = original.convert("RGB")
    output.paste(patch.convert("RGB"), (left, top), alpha)
    return output
