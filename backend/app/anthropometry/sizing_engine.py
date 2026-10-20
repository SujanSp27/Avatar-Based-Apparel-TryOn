"""Exact midpoint-relative weighted error; independent of images and physical ease."""

import math

from backend.app.anthropometry.constants import CATEGORY_METRICS, WEIGHTS
from backend.app.anthropometry.schemas import ChartCreate, SizingResponse
from ml.errors import PipelineError


def recommend(measurements: dict[str, float], chart: ChartCreate) -> SizingResponse:
    active = CATEGORY_METRICS[chart.category.value]
    if missing := set(active) - measurements.keys():
        raise PipelineError("missing_measurement", f"This apparel requires: {', '.join(sorted(missing))}.")
    for name in active:
        if not math.isfinite(measurements[name]) or measurements[name] <= 0:
            raise PipelineError("invalid_measurement", f"{name} must be a positive finite value in cm.")
    total = math.fsum(WEIGHTS[key] for key in active)
    weights = {key: WEIGHTS[key] / total for key in active}
    candidates = []
    comparisons = {}
    for size in chart.sizes:
        details = {}
        for key in active:
            bounds = size.bounds[key]
            center = (bounds.lower + bounds.upper) / 2
            deviation = abs(measurements[key] - center) / center
            details[key] = {
                "measurement": measurements[key], "lower": bounds.lower, "upper": bounds.upper,
                "midpoint": center, "deviation": deviation,
                "weighted_error": weights[key] * deviation,
                "within_range": bounds.lower <= measurements[key] <= bounds.upper,
            }
        error = math.fsum(item["weighted_error"] for item in details.values())
        # Rank on full precision. Published chart order breaks exact ties.
        candidates.append((error, size.sort_order, size.size_label, details))
        comparisons[size.size_label] = details
    candidates.sort(key=lambda candidate: (candidate[0], candidate[1], candidate[2]))
    best_error, _, best_size, _ = candidates[0]
    return SizingResponse(
        recommended_size=best_size,
        minimum_error=best_error,
        fit_confidence=100 / (1 + best_error),
        size_rankings=[
            {"size": label, "error": error,
             "deviations": {key: item["deviation"] for key, item in details.items()}}
            for error, _, label, details in candidates
        ],
        active_weights=weights,
        chart_comparison=comparisons,
        chart={"brand_id": chart.brand_id, "brand_name": chart.brand_name,
               "apparel_id": chart.apparel_id, "category": chart.category.value,
               "version": chart.version, "source": chart.source, "is_demo": chart.is_demo,
               "units": "cm"},
        score_meaning="100/(1+weighted midpoint-relative error); a heuristic fit score, not a calibrated probability.",
    )
