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
    maximum_limit = max(baseline_limit, round(height * .40))
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


def _align_shoulder_edge(generated, source, target, clothing, feather):
    """Project tiny neural-clothing boundary gaps onto the original arm outline.

    A model can shrink a sleeve edge by a few pixels, leaving an exposed strip
    of the original upper arm after identity preservation. Only complete, narrow
    source-arm / generated-background components adjacent to generated clothing
    qualify. Broader limb changes, bare-skin predictions and hands never qualify.
    Colours come from the nearest interior of the generated garment, not from
    the uploaded flat-lay or a fabricated skin colour.
    """
    radius = max(2, round(min(source.shape) * .008))
    distance = cv2.distanceTransform((~clothing).astype(np.uint8), cv2.DIST_L2, 5)
    gaps = (source == 12) & (target == 0)
    count, components, stats, _ = cv2.connectedComponentsWithStats(gaps.astype(np.uint8))
    projected = np.zeros_like(clothing)
    area_limit = max(16, round(np.count_nonzero(clothing) * .015))
    for component in range(1, count):
        if stats[component, cv2.CC_STAT_AREA] > area_limit:
            continue
        region = components == component
        if distance[region].max() <= radius and distance[region].min() <= 1.5:
            projected |= region
    if not projected.any():
        return generated, projected
    # Parsing can leave one-pixel background gaps between the arm contour and
    # shirt. Join only this narrow boundary band; never retain isolated dots.
    joined = cv2.morphologyEx(
        (clothing | projected).astype(np.uint8), cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (radius * 2 + 1,) * 2),
    ).astype(bool)
    projected |= joined & ~clothing & np.isin(source, (0, 12)) & (target == 0) & (distance <= radius)
    # Avoid sampling the anti-aliased clothing/background boundary itself.
    interior = cv2.distanceTransform(clothing.astype(np.uint8), cv2.DIST_L2, 5) > feather
    if not interior.any():
        return generated, np.zeros_like(clothing)
    _, nearest = cv2.distanceTransformWithLabels(
        (~interior).astype(np.uint8), cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL,
    )
    coordinates = np.argwhere(interior)
    y, x = coordinates[nearest[projected] - 1].T
    aligned = generated.copy()
    aligned[projected] = generated[y, x]
    return aligned, projected


def _revealed_region_transitions(alpha, old, source, target, category):
    """Blend newly exposed material into the same material in the source.

    A lower neckline or shorter hem exposes pixels that did not exist in the
    source photo. Keeping the source up to its old clothing edge creates a skin
    or denim stripe even when the raw neural output is continuous. Extend only
    those seams into an adjacent, agreeing semantic region, with a smooth fade.
    Never blend through clothing, a disconnected region, the face or hands.
    """
    rows = np.nonzero(old)[0]
    radius = min(max(4, round(min(source.shape) * .04)),
                 max(4, round((rows.max() - rows.min() + 1) * .10)))
    core = max(1, radius * .16)
    labels = (12, 14, 16, 5, 6) if category == "tops" else (12, 14, 16)
    adjusted = np.zeros_like(old)
    for label in labels:
        revealed = old & (target == label)
        if not revealed.any():
            continue
        agreement = (source == label) & (target == label)
        _, components = cv2.connectedComponents((revealed | agreement).astype(np.uint8))
        touching = np.unique(components[revealed])
        connected = np.isin(components, touching[touching != 0])
        distance = cv2.distanceTransform((~revealed).astype(np.uint8), cv2.DIST_L2, 5)
        band = agreement & connected & (distance < radius)
        fade = np.clip((radius - distance) / (radius - core), 0., 1.)
        fade = fade * fade * (3. - 2. * fade)
        adjusted |= band & (fade > alpha)
        alpha[band] = np.maximum(alpha[band], fade[band])
    return adjusted


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
    # A short outfit cannot faithfully reveal a large amount of anatomy hidden
    # by a long source outfit. Do not present invented limbs/background as an
    # identity-preserving success. This conservative gate is not a quality score.
    revealed_skin = old & np.isin(target, (12, 14, 16))
    if np.count_nonzero(revealed_skin) > np.count_nonzero(old) * .20:
        raise PipelineError(
            "coverage_change_too_large",
            "This outfit would expose too much skin hidden by the original clothing. "
            "Use a person photo with similar sleeve and hem coverage; the generated result was rejected.",
        )
    # Model clothing may cover bare arms/legs and surrounding background.
    # A dress may replace both top and bottom. A top may overlap only a bounded
    # waistband area; the rest of the lower-body clothing stays unchanged.
    feather = max(2, round(min(source.shape) * .003))
    projected = np.zeros_like(old)
    if category == "tops":
        _, components = cv2.connectedComponents(new.astype(np.uint8), connectivity=8)
        touching = np.unique(components[new & old])
        connected_top = new & np.isin(components, touching[touching != 0])
        generated, projected = _align_shoulder_edge(generated, source, target, connected_top, feather)
        new |= projected
    eligible = np.isin(source, (0, 12, 14, 16))
    distance = cv2.distanceTransform((~old).astype(np.uint8), cv2.DIST_L2, 5)
    extension = new & eligible & (distance < min(source.shape) * .30)
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
    alpha[projected] = 1.
    transitions = _revealed_region_transitions(alpha, old, source, target, category)
    alpha[protected] = 0.
    output = np.rint(generated * alpha[..., None] + original * (1 - alpha[..., None])).clip(0, 255).astype(np.uint8)
    return output, alpha, {
        "identityPreservedExactly": bool(np.array_equal(output[protected], original[protected])),
        "changedPixelsOutsideEditMask": int(np.count_nonzero(np.any(output != original, axis=2) & (alpha == 0))),
        "oldClothingMinimumAlpha": float(alpha[old & ~protected].min()),
        "editedPixels": int(np.count_nonzero(alpha)),
        "hemExtensionPixels": int(np.count_nonzero(hem_extension)),
        "hemExtensionLimitPixels": hem_limit,
        "shoulderProjectionPixels": int(np.count_nonzero(projected)),
        "revealedRegionTransitionPixels": int(np.count_nonzero(transitions & ~protected)),
        "compositor": "semantic-category-preservation-v7",
        "limitations": "Semantic parsing can mislabel seams and skin. Visual review is still required.",
    }
