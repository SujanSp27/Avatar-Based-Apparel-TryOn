"""Conservative framing for a single product on a plain, pale background.

Only whitespace is cropped; colors, silhouette, holes and aspect ratio are kept.
Ambiguous backgrounds and model-worn references must retain their input framing.
"""
import cv2
import numpy as np
from PIL import Image


def frame_flat_lay(image: Image.Image, photo_type: str) -> tuple[Image.Image, dict]:
    rgb = image.convert("RGB")
    report = {"version": "plain-flat-lay-framing-v1", "applied": False,
              "inputSize": list(rgb.size), "cropBox": [0, 0, rgb.width, rgb.height]}
    if photo_type != 'flat-lay':
        return rgb, {**report, "reason": "model_reference_unchanged"}
    small = rgb.copy()
    small.thumbnail((800, 800), Image.Resampling.LANCZOS)
    values = np.asarray(small)
    edge = np.concatenate([values[0], values[-1], values[:, 0], values[:, -1]])
    background = np.median(edge, axis=0)
    if background.min() < 220 or np.ptp(background) > 15 or np.percentile(np.abs(edge - background), 95) > 12:
        return rgb, {**report, "reason": "background_not_plain_pale"}
    contrast = np.max(np.abs(values.astype(np.float32) - background), axis=2) > 45
    count, labels, stats, _ = cv2.connectedComponentsWithStats(contrast.astype(np.uint8))
    if count < 2:
        return rgb, {**report, "reason": "no_clear_product"}
    largest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    x, y, width, height, area = stats[largest]
    if (area < contrast.size * .03 or area < contrast.sum() * .95
            or x < 2 or y < 2 or x + width >= small.width - 2 or y + height >= small.height - 2):
        return rgb, {**report, "reason": "ambiguous_or_clipped_product"}
    # Any detached substantial product detail prevents cropping. Include all
    # high-contrast pixels so small, legitimate details cannot be cut off.
    ys, xs = np.nonzero(contrast)
    pad = round(max(width, height) * .08)
    left, top = max(0, int(xs.min()) - pad), max(0, int(ys.min()) - pad)
    right, bottom = min(small.width, int(xs.max()) + pad + 1), min(small.height, int(ys.max()) + pad + 1)
    if (right-left) * (bottom-top) > contrast.size * .85:
        return rgb, {**report, "reason": "already_framed"}
    sx, sy = rgb.width / small.width, rgb.height / small.height
    box = [int(left*sx), int(top*sy), min(rgb.width, int(np.ceil(right*sx))), min(rgb.height, int(np.ceil(bottom*sy)))]
    cropped = rgb.crop(box)
    if min(cropped.size) < 128:
        return rgb, {**report, "reason": "product_too_small"}
    return cropped, {**report, "applied": True, "reason": "removed_plain_background_margin",
                     "cropBox": box, "outputSize": list(cropped.size)}
