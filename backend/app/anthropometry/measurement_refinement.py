"""Conservative recovery of missing regions from image evidence, never body priors."""

from copy import deepcopy

import cv2
import numpy as np

from ml.errors import PipelineError

from .measurement_evidence import usable

RECOVERABLE_REASONS = {
    "arms_overlap_torso", "torso_segmentation_failed", "hip_outline_unavailable",
    "hand_overlaps_thigh", "ambiguous_thigh",
}
MASK_SUFFIXES = ("_native_mask.png", "_image_guided_mask.png")


def needs_refinement(result):
    return any(result["measurements"][key] is None and info["reason"] in RECOVERABLE_REASONS
               for key, info in result["quality"]["metrics"].items())


def guard_refined_mask(observation, candidate):
    """Require real exterior gaps and retain previously observed limb evidence.

    GrabCut can mistake a pale garment panel for background. Enclosed holes
    cannot establish an outer body edge, so retain the original foreground there.
    Reject a retry that erases visible joint or limb-axis evidence. This is a
    segmentation safeguard, not a learned accuracy/confidence estimate.
    """
    if (candidate.shape != observation.mask.shape or not np.isin(candidate, (0, 1)).all()
            or not candidate.any()):
        raise PipelineError("invalid_refined_mask", "Refined person outline is invalid.")
    candidate = candidate.astype(bool).copy()
    _, labels = cv2.connectedComponents((~candidate).astype(np.uint8), connectivity=4)
    exterior_labels = np.unique(np.concatenate((labels[0], labels[-1], labels[:, 0], labels[:, -1])))
    exterior = np.isin(labels, exterior_labels[exterior_labels != 0])
    candidate |= observation.mask & ~exterior
    points = observation.landmarks[:, :2] * observation.image.shape[1::-1]
    valid = usable(observation)
    evidence = [points[valid]]
    for first, second in ((11, 13), (13, 15), (12, 14), (14, 16), (15, 19), (16, 20),
                          (23, 25), (25, 27), (24, 26), (26, 28)):
        if valid[[first, second]].all():
            count = max(2, int(np.ceil(np.linalg.norm(points[first] - points[second]))) + 1)
            evidence.append(np.linspace(points[first], points[second], count))
    pixels = np.rint(np.concatenate(evidence)).astype(int)
    x, y = pixels.T
    if np.any(observation.mask[y, x] & ~candidate[y, x]):
        raise PipelineError("refinement_erased_pose_evidence", "Refinement removed an observed body region; keeping the original estimates.")
    return candidate


def merge_recovered(result, sections, candidate, candidate_sections, method):
    """Fill only previously missing regions; keep all existing values and scale."""
    merged = deepcopy(result)
    lines = list(sections)
    recovered = []
    if not np.isclose(result["scale_factor"], candidate["scale_factor"], rtol=0, atol=1e-12):
        raise PipelineError("refinement_scale_changed", "Refinement cannot change height calibration.")
    for key, value in candidate["measurements"].items():
        old = result["quality"]["metrics"][key]
        if (result["measurements"][key] is not None or value is None
                or old["reason"] not in RECOVERABLE_REASONS):
            continue
        region = key.removesuffix("_circumference")
        region_lines = [(name, segment) for name, segment in candidate_sections
                        if name == region or (region == "thigh" and name.startswith("thigh_"))]
        if not region_lines:
            continue
        info = deepcopy(candidate["quality"]["metrics"][key])
        existing_warning = info.get("message", "")
        info.update(status="review_required", requires_manual_review=True, confidence=None,
                    reason="image_refinement_estimate", baseline_reason=old["reason"],
                    refinement_method=method,
                    message=("Image-guided refinement found a visible outline. This approximate clothing-silhouette "
                             "estimate needs a tape measurement before sizing. " + existing_warning).strip())
        merged["measurements"][key] = value
        merged["quality"]["metrics"][key] = info
        merged["geometry"].setdefault("measurement_mask_sources", {})[key] = method
        if region in ("chest", "waist"):
            merged["geometry"][region + "_torso_fraction"] = candidate["geometry"][region + "_torso_fraction"]
        lines.extend(region_lines)
        recovered.append(key)
    review = [key for key, info in merged["quality"]["metrics"].items() if info["requires_manual_review"]]
    merged["quality"].update(status="review_required" if review else "estimated", requires_manual_review=review)
    return merged, lines, recovered
