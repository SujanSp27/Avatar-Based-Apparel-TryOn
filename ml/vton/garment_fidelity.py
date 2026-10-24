"""Conservative diagnostics for invented pale fabric on a dark reference.

These measurements do not certify fit, sleeve shape, texture, or identity. They
use garment-only masks, never a whole rectangular crop or the source edit mask.
"""
from __future__ import annotations

import cv2
import numpy as np


def fabric_statistics(rgb: np.ndarray, mask: np.ndarray) -> dict:
    if rgb.dtype != np.uint8 or rgb.ndim != 3 or rgb.shape[2] != 3:
        raise ValueError("Expected uint8 RGB image")
    if mask.shape != rgb.shape[:2] or mask.dtype != np.bool_:
        raise ValueError("Expected a matching binary garment mask")
    # Ignore antialiased outlines and small parser boundary errors.
    radius = max(1, round(min(mask.shape) * .003))
    interior = cv2.erode(mask.astype(np.uint8), np.ones((radius * 2 + 1,) * 2, np.uint8)).astype(bool)
    count = int(interior.sum())
    if count < 256:
        return {"usable": False, "pixels": count}
    values = rgb[interior].astype(np.float32)
    luminance = values @ np.array([.2126, .7152, .0722], dtype=np.float32)
    pale = (rgb.min(axis=2) > 180) & (np.ptp(rgb.astype(np.int16), axis=2) < 40) & interior
    components, _, stats, _ = cv2.connectedComponentsWithStats(pale.astype(np.uint8))
    largest = int(stats[1:, cv2.CC_STAT_AREA].max()) if components > 1 else 0
    return {"usable": True, "pixels": count, "medianRgb": np.median(values, axis=0).tolist(),
            "luminanceP90": round(float(np.percentile(luminance, 90)), 3),
            "brightestChannelP90": round(float(np.percentile(values.max(axis=1), 90)), 3),
            "paleFraction": round(float(pale.sum() / count), 5),
            "largestPaleComponentFraction": round(largest / count, 5)}


def assess_dark_reference(reference, reference_mask, generated, generated_mask) -> dict:
    source = fabric_statistics(reference, reference_mask)
    target = fabric_statistics(generated, generated_mask)
    scope = (source["usable"] and target["usable"]
             and source["luminanceP90"] < 115 and source["brightestChannelP90"] < 140
             and source["paleFraction"] < .02)
    rejected = bool(scope and target["paleFraction"] > .20
                    and target["largestPaleComponentFraction"] > .10)
    return {"version": "dark-reference-pale-layer-v1",
            "status": "rejected" if rejected else "not_rejected" if scope else "abstained",
            "reason": "unrequested_pale_fabric" if rejected else "no_decision_on_overall_quality",
            "reference": source, "generated": target,
            "limitations": "Uncalibrated catastrophic color-change check; does not validate garment construction or fitting."}
