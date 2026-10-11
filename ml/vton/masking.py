"""Semantic upper-body inpainting masks for CatVTON's 384 by 512 input.

The inference mask needs a small amount of context outside the old shirt so
the VAE can remove its edge. It is deliberately distinct from the final RGB
compositing mask: opening context here does not authorize changing identity,
limbs or background in the published image.
"""

import cv2
import numpy as np

from ml.errors import PipelineError

NATIVE_SHAPE = (512, 384)
VAE_STRIDE = 8
HEAD_MARGIN = 2
HEAD_LABELS = (1, 2, 9, 11)
# FASHN labels: retain head, other clothes, accessories, hands and lower limbs.
# Only background (0), original top (3), arms (12), and torso (16) can supply
# narrow seam context. In particular, exposed hands are never inpainted.
PROTECTED_LABELS = (1, 2, 4, 5, 6, 7, 8, 9, 10, 11, 13, 14, 15, 17)


def build_replacement_mask(labels_native: np.ndarray) -> np.ndarray:
    """Return a binary uint8 white-edit mask, expanded by one latent stride.

    Pass the native-size FASHN label map after applying exactly the same crop
    and nearest-neighbour padding as the person image. A radius-eight ellipse
    gives boundary latents shirt-free context without using a torso rectangle.
    Protected semantic classes take priority; the small head guard never
    removes any original shirt pixels from the replacement mask.
    """
    if not isinstance(labels_native, np.ndarray) or labels_native.shape != NATIVE_SHAPE:
        raise ValueError("Expected a 512x384 native semantic label map")
    if (
        not np.issubdtype(labels_native.dtype, np.integer)
        or np.any(labels_native < 0)
        or np.any(labels_native > 17)
    ):
        raise ValueError("Expected integer FASHN label IDs from 0 through 17")
    old_shirt = labels_native == 3
    if not old_shirt.any():
        raise PipelineError(
            "vton_clothing_not_found",
            "No upper-body clothing remains in the prepared model input.",
        )
    seam_kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (2 * VAE_STRIDE + 1, 2 * VAE_STRIDE + 1)
    )
    expanded = cv2.dilate(old_shirt.astype(np.uint8), seam_kernel).astype(bool)
    protected = np.isin(labels_native, PROTECTED_LABELS)
    head = np.isin(labels_native, HEAD_LABELS).astype(np.uint8)
    head_kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (2 * HEAD_MARGIN + 1, 2 * HEAD_MARGIN + 1)
    )
    head_guard = cv2.dilate(head, head_kernel).astype(bool) & ~old_shirt
    expanded &= ~(protected | head_guard)
    # Every parsed shirt pixel must be regenerated; never feather old clothing
    # into the conditioning image or shrink it to protect a neighbouring guard.
    expanded[old_shirt] = True
    return expanded.astype(np.uint8) * 255
