"""Category-aware preservation for the cloud model's complete generated image."""
import cv2
import numpy as np

from ml.errors import PipelineError

LABELS = {"tops": (3,), "bottoms": (5, 6), "one-pieces": (3, 4, 5, 6)}
GENERATED_LABELS = {"tops": (3,), "bottoms": (5, 6), "one-pieces": (4, 3, 5, 6)}


def _top_hem_extension(old, new, source, feather, clothing_extension):
    """Allow a generated shirt to cover a small, connected part of a waistband.

    Keeping every source trouser pixel clips a longer generated top to the old
    shirt's hem. Only generated top pixels near a downward-facing source hem
    may replace pants, skirt or belt pixels. This is deliberately narrower than
    the general clothing extension radius used for nearby skin/background.
    """
    rows = np.nonzero(old)[0]
    height = int(rows.max() - rows.min() + 1)
    baseline_limit = max(feather * 2, round(height * .12))
    maximum_limit = max(baseline_limit, round(height * .35))
    # Lower-facing edges in the bottom 30% exclude sleeve ends and the collar.
    below = np.zeros_like(old)
    below[:-1] = old[1:]
    hem = old & ~below
    hem[:int(rows.min() + height * .70)] = False
    proximity = cv2.distanceTransform((~hem).astype(np.uint8), cv2.DIST_L2, 5)
    _, components = cv2.connectedComponents(new.astype(np.uint8), connectivity=8)
    touching = np.unique(components[old & new])
    touching = touching[touching != 0]
    connected_top = np.isin(components, touching)
    waistband = new & connected_top & np.isin(source, (5, 6, 7))
    # Follow the complete generated hem when it is modestly longer than the
    # original. Cutting it at an arbitrary 12% depth leaves jagged jean wedges.
    # An implausibly long or misparsed top must fail rather than be clipped into
    # an apparently successful result or overwrite most of the trouser legs.
    required_depth = float(proximity[waistband].max()) if waistband.any() else 0.
    if required_depth > maximum_limit:
        raise PipelineError("garment_length_changed",
                            "The generated top extends too far over the lower body. "
                            "Use a person photo wearing a top with similar coverage; this result was rejected.")
    limit = max(baseline_limit, int(np.ceil(required_depth)))
    extension = (
        waistband
        & (proximity <= limit)
    )
    # A target component can connect through pixels outside the allowed edit
    # area. Do not retain an isolated trouser patch after imposing the bound.
    support = old | clothing_extension | extension
    _, supported = cv2.connectedComponents(support.astype(np.uint8), connectivity=8)
    attached = np.unique(supported[old])
    extension &= np.isin(supported, attached[attached != 0])
    return extension, limit


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
    # Model clothing may cover bare arms/legs and surrounding background.
    # A dress may replace both top and bottom. A top may overlap only a bounded
    # waistband area; the rest of the lower-body clothing stays unchanged.
    eligible = np.isin(source, (0, 12, 14, 16))
    distance = cv2.distanceTransform((~old).astype(np.uint8), cv2.DIST_L2, 5)
    extension = new & eligible & (distance < min(source.shape) * .30)
    feather = max(2, round(min(source.shape) * .003))
    hem_extension = np.zeros_like(old)
    hem_limit = 0
    if category == "tops":
        hem_extension, hem_limit = _top_hem_extension(old, new, source, feather, extension)
        extension |= hem_extension
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
        "hemExtensionPixels": int(np.count_nonzero(hem_extension)),
        "hemExtensionLimitPixels": hem_limit,
        "compositor": "semantic-category-preservation-v3",
        "limitations": "Semantic parsing can mislabel seams and skin. Visual review is still required.",
    }
