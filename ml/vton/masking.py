"""Semantic upper-body inpainting masks for CatVTON's supported input sizes.

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


def short_sleeve_support(labels: np.ndarray, landmarks: np.ndarray | None) -> np.ndarray:
    """Reserve upper-arm space using the existing MediaPipe pose, in source pixels.

    A dilation of a vest cannot admit T-shirt sleeves. Two pose-aligned corridors
    open the proximal upper arms and their immediate silhouette instead. This is
    permission for neural synthesis, never RGB warping or a predicted sleeve.
    The model still determines the actual garment boundary. Distal arms, hands,
    head and unrelated clothing stay protected. Missing/unreliable joints do not
    expand the mask. This conservative policy does not support long sleeves.
    """
    if (
        not isinstance(labels, np.ndarray) or labels.ndim != 2
        or not np.issubdtype(labels.dtype, np.integer)
        or np.any(labels < 0) or np.any(labels > 17)
    ):
        raise ValueError("Expected an HxW integer FASHN semantic map")
    support = np.zeros(labels.shape, dtype=bool)
    if landmarks is None:
        return support
    points = np.asarray(landmarks, dtype=float)
    if points.shape != (33, 4):
        raise ValueError("Expected 33 MediaPipe normalized x,y,z,visibility landmarks")
    if not np.isfinite(points[[11, 12, 13, 14]]).all():
        return support
    h, w = labels.shape
    xy = points[:, :2] * [w, h]
    shoulder_width = float(np.linalg.norm(xy[11] - xy[12]))
    if shoulder_width < min(h, w) * 0.08 or np.min(points[[11, 12], 3]) < 0.55:
        return support
    yy, xx = np.mgrid[:h, :w]
    eligible = np.isin(labels, (0, 3, 12, 16))
    for shoulder, elbow in ((11, 13), (12, 14)):
        if (
            np.min(points[[shoulder, elbow], 3]) < 0.55
            or np.any(points[[shoulder, elbow], :2] < 0)
            or np.any(points[[shoulder, elbow], :2] > 1)
        ):
            continue
        start = xy[shoulder]
        vector = xy[elbow] - start
        length = float(np.linalg.norm(vector))
        if not shoulder_width * 0.30 <= length <= shoulder_width * 1.5:
            continue
        dx, dy = xx - start[0], yy - start[1]
        along = (dx * vector[0] + dy * vector[1]) / length**2
        across = np.abs(dx * vector[1] - dy * vector[0]) / length
        # Stop before the elbow; do not open the whole arm or a torso rectangle.
        radius = min(shoulder_width * 0.18, length * 0.28)
        # A flat cutoff above the joint leaves a visible skin cap on a vest.
        # Include the round shoulder cap so the model can start a sleeve at the
        # shoulder silhouette. Keep the distal cutoff before the elbow.
        shoulder_cap = dx**2 + dy**2 <= radius**2
        corridor = ((along >= 0) & (along <= 0.72) & (across <= radius)) | shoulder_cap
        # Reject detached/implausible corridors caused by a bad pose or parser.
        if np.count_nonzero(corridor & (labels == 3)) < 16:
            continue
        support |= corridor & eligible
    return support


def binary_support(mask: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    """Validate optional shared inference/compositing support without coercing labels."""
    if not isinstance(mask, np.ndarray) or mask.shape != shape or mask.dtype != np.bool_:
        raise ValueError("Sleeve support must be a boolean mask matching the semantic map")
    return mask


def build_replacement_mask(
    labels_native: np.ndarray, *, sleeve_support: np.ndarray | None = None,
) -> np.ndarray:
    """Return a binary uint8 white-edit mask, expanded by one latent stride.

    Pass the native-size FASHN label map after applying exactly the same crop
    and nearest-neighbour padding as the person image. A radius-eight ellipse
    gives boundary latents shirt-free context without using a torso rectangle.
    Protected semantic classes take priority; the small head guard never
    removes any original shirt pixels from the replacement mask.
    """
    if not isinstance(labels_native, np.ndarray) or labels_native.shape not in {
        NATIVE_SHAPE, (1024, 768)
    }:
        raise ValueError("Expected a 512x384 or 1024x768 native semantic label map")
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
    scale = labels_native.shape[0] // NATIVE_SHAPE[0]
    seam_radius = VAE_STRIDE * scale
    seam_kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (2 * seam_radius + 1, 2 * seam_radius + 1)
    )
    expanded = cv2.dilate(old_shirt.astype(np.uint8), seam_kernel).astype(bool)
    if sleeve_support is not None:
        expanded |= binary_support(sleeve_support, labels_native.shape)
    protected = np.isin(labels_native, PROTECTED_LABELS)
    head = np.isin(labels_native, HEAD_LABELS).astype(np.uint8)
    head_kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (2 * HEAD_MARGIN * scale + 1, 2 * HEAD_MARGIN * scale + 1)
    )
    head_guard = cv2.dilate(head, head_kernel).astype(bool) & ~old_shirt
    expanded &= ~(protected | head_guard)
    # Every parsed shirt pixel must be regenerated; never feather old clothing
    # into the conditioning image or shrink it to protect a neighbouring guard.
    expanded[old_shirt] = True
    return expanded.astype(np.uint8) * 255
