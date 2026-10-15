"""Category-aware preservation for the cloud model's complete generated image."""
import cv2
import numpy as np

from ml.errors import PipelineError

LABELS = {"tops": (3,), "bottoms": (5, 6), "one-pieces": (3, 4, 5, 6)}
GENERATED_LABELS = {"tops": (3,), "bottoms": (5, 6), "one-pieces": (4, 3, 5, 6)}


def preserve_regions(original, generated, source, target, category):
    if category not in LABELS:
        raise ValueError("Unknown garment category")
    if original.shape != generated.shape or source.shape != original.shape[:2] or target.shape != source.shape:
        raise ValueError("Images and label maps must have matching dimensions")
    old = np.isin(source, LABELS[category])
    new = np.isin(target, GENERATED_LABELS[category])
    head = np.isin(source, (1, 2, 9, 11))
    if np.count_nonzero(head) < source.size * .001:
        raise PipelineError("face_not_visible", "Use a clear photo with the person's face and hair visible.")
    if np.count_nonzero(old) < source.size * .003 or np.count_nonzero(new) < source.size * .003:
        raise PipelineError("clothing_not_visible", "The selected clothing region is not clearly visible in the input or generated image.")
    # Model clothing may cover bare arms/legs and surrounding background, while
    # unrelated clothing is retained. A dress may replace both top and bottom.
    eligible = np.isin(source, (0, 12, 14, 16))
    distance = cv2.distanceTransform((~old).astype(np.uint8), cv2.DIST_L2, 5)
    extension = new & eligible & (distance < min(source.shape) * .30)
    feather = max(2, round(min(source.shape) * .003))
    support = old | extension
    edge = cv2.dilate(support.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (feather * 2 + 1,) * 2)).astype(bool)
    support |= edge & eligible & (distance <= feather)
    protected = head | np.isin(source, (13, 15, 8, 17))
    # Shrinking a real limb is not fixed by deleting skin or accepting a white gap.
    skin = np.isin(source, (12, 14))
    interior = cv2.distanceTransform(skin.astype(np.uint8), cv2.DIST_L2, 5) > feather * 2
    missing_skin = interior & (target == 0) & (distance < min(source.shape) * .06)
    if np.count_nonzero(missing_skin) > max(96, np.count_nonzero(skin) * .04):
        raise PipelineError("body_shape_changed", "The generated outfit distorted an exposed arm or leg. Try a clearer frontal photo; this result was rejected.")
    alpha = np.minimum(cv2.distanceTransform(support.astype(np.uint8), cv2.DIST_L2, 5) / feather, 1.)
    alpha[old] = 1.
    alpha[protected] = 0.
    output = np.rint(generated * alpha[..., None] + original * (1 - alpha[..., None])).clip(0, 255).astype(np.uint8)
    return output, alpha, {
        "identityPreservedExactly": bool(np.array_equal(output[protected], original[protected])),
        "changedPixelsOutsideEditMask": int(np.count_nonzero(np.any(output != original, axis=2) & (alpha == 0))),
        "oldClothingMinimumAlpha": float(alpha[old & ~protected].min()),
        "editedPixels": int(np.count_nonzero(alpha)),
        "compositor": "semantic-category-preservation-v1",
        "limitations": "Semantic parsing can mislabel seams and skin. Visual review is still required.",
    }
