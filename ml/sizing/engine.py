from enum import Enum

from ml.errors import PipelineError


class Category(str, Enum):
    tshirt = "t-shirt"
    shirt = "shirt"
    dress = "dress"
    trouser = "trouser"


class Fit(str, Enum):
    tight = "tight"
    regular = "regular"
    loose = "loose"


WEIGHTS = {
    "t-shirt": {"chest": 0.60, "waist": 0.25, "hip": 0.05, "shoulderWidth": 0.10},
    "shirt": {"chest": 0.50, "waist": 0.25, "hip": 0.10, "shoulderWidth": 0.15},
    "dress": {"chest": 0.35, "waist": 0.30, "hip": 0.30, "shoulderWidth": 0.05},
    "trouser": {"waist": 0.45, "hip": 0.55},
}
EASE = {"tight": -2.0, "regular": 0.0, "loose": 4.0}


def recommend(measurements: dict, rows: list[dict], category: str, fit: str) -> dict:
    category, fit = Category(category).value, Fit(fit).value
    if not rows:
        raise PipelineError(
            "chart_missing", "No size chart is available for this brand and category.", 404
        )
    weights = WEIGHTS[category]
    candidates = []
    for row in rows:
        errors, explanation, weighted, total_weight, midpoint = {}, {}, 0.0, 0.0, 0.0
        for measurement, weight in weights.items():
            prefix = "shoulder" if measurement == "shoulderWidth" else measurement
            low, high = row.get(prefix + "Min"), row.get(prefix + "Max")
            if low is None or high is None:
                continue
            if measurement not in measurements:
                raise PipelineError("missing_measurement", f"Sizing requires {measurement} in cm.")
            actual = float(measurements[measurement])
            if not 0 < actual < 400:
                raise PipelineError("invalid_measurement", f"Invalid {measurement} value.")
            target = actual + EASE[fit] * (0.25 if measurement == "shoulderWidth" else 1)
            width = max(high - low, 1.0)
            distance = max(low - target, 0.0, target - high)
            normalized = distance / width
            weighted += weight * normalized
            midpoint += weight * abs(target - (low + high) / 2) / width
            total_weight += weight
            errors[measurement] = round(normalized, 4)
            explanation[measurement] = (
                "Good"
                if distance == 0
                else ("Slightly loose" if target < low else "Slightly tight")
                if distance <= 3
                else ("Too loose" if target < low else "Too tight")
            )
        if not total_weight:
            raise PipelineError(
                "chart_invalid", "The chart has no measurements relevant to this category."
            )
        candidates.append(
            {
                "sizeLabel": row["sizeLabel"],
                "score": round(weighted / total_weight, 4),
                "explanation": explanation,
                "measurementErrors": errors,
                "order": row["sortOrder"],
                "midpointDistance": midpoint / total_weight,
            }
        )
    candidates.sort(key=lambda c: (c["score"], c["midpointDistance"], c["order"]))
    best = candidates[0]
    return {
        "recommendedSize": best["sizeLabel"],
        "fit": fit,
        "score": best["score"],
        "explanation": best["explanation"],
        "candidates": candidates,
        "outOfRange": any(v > 0 for v in best["measurementErrors"].values()),
        "targetEaseCm": EASE[fit],
        "scoreMeaning": "weighted normalized interval distance; not a probability",
    }
