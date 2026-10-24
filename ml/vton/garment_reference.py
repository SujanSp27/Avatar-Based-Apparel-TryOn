"""Prepare confidently segmented dark flat-lay tops for FASHN conditioning.

Use FASHN's neutral mask value (127), without altering reference fabric, pose,
framing or aspect ratio. Ambiguous and worn references keep the official path.
"""
import numpy as np
from PIL import Image

from ml.vton.garment_fidelity import fabric_statistics


def prepare_reference(
    image: Image.Image, labels: np.ndarray, category: str, photo_type: str,
) -> tuple[Image.Image, dict[str, object]]:
    rgb = np.asarray(image.convert('RGB'))
    if labels.shape != rgb.shape[:2]:
        raise ValueError('Reference labels must match reference image dimensions')
    report = {'version': 'dark-flat-lay-neutral-background-v1', 'applied': False,
              'category': category, 'photoType': photo_type, 'maskValue': 127}
    if category != 'tops' or photo_type != 'flat-lay':
        return image, {**report, 'reason': 'outside_validated_reference_scope'}
    mask = labels == 3
    stats = fabric_statistics(rgb, mask)
    if (not stats['usable'] or stats['luminanceP90'] >= 115
            or stats['brightestChannelP90'] >= 140 or stats['paleFraction'] >= .02):
        return image, {**report, 'reason': 'not_a_confident_dark_fabric_reference'}
    border = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]]).astype(float)
    background = np.median(border, axis=0)
    if (background.min() < 220 or np.ptp(background) > 15
            or np.percentile(np.abs(border - background), 95) > 12):
        return image, {**report, 'reason': 'background_not_plain_pale'}
    # The photographed shadow is darker than the backdrop but is not fabric.
    # This path is already limited to dark garments: validate that the parser
    # covers their dark pixels, rather than treating grey shadows as omissions.
    contrast = (
        (np.max(np.abs(rgb.astype(float) - background), axis=2) > 60)
        & (rgb.max(axis=2) < 140)
    )
    # A clipped garment or incomplete parsing is not safe to background-mask.
    border_mask = np.concatenate([mask[0], mask[-1], mask[:, 0], mask[:, -1]])
    coverage = float(np.count_nonzero(contrast & mask) / max(1, contrast.sum()))
    if mask.mean() < .03 or border_mask.any() or coverage < .95:
        return image, {**report, 'reason': 'ambiguous_or_clipped_reference',
                       'contrastCoverage': coverage}
    prepared = rgb.copy()
    prepared[~mask] = 127
    return Image.fromarray(prepared), {**report, 'applied': True,
        'reason': 'removed_pale_background_conditioning',
        'referenceFabricPreservedExactly': bool(np.array_equal(prepared[mask], rgb[mask])),
        'foregroundPixels': int(mask.sum()), 'contrastCoverage': coverage}
