import numpy as np


def measurement_metrics(predicted, actual) -> dict:
    p, a = np.asarray(predicted, dtype=float), np.asarray(actual, dtype=float)
    if p.shape != a.shape or p.size == 0 or not np.isfinite(p).all() or not np.isfinite(a).all():
        raise ValueError(
            "Paired finite, nonempty measurement arrays of the same shape are required"
        )
    error = p - a
    nonzero = np.abs(a) > 1e-8
    return {
        "mae": float(np.abs(error).mean()),
        "rmse": float(np.sqrt(np.square(error).mean())),
        "mape": float((np.abs(error[nonzero] / a[nonzero])).mean() * 100)
        if nonzero.any()
        else None,
        "mapeExcludedZeros": int((~nonzero).sum()),
        "n": int(p.size),
    }


def silhouette_iou(predicted, actual) -> float:
    p, a = np.asarray(predicted, dtype=bool), np.asarray(actual, dtype=bool)
    if p.shape != a.shape:
        raise ValueError("Masks must have the same shape")
    union = np.logical_or(p, a).sum()
    return float(np.logical_and(p, a).sum() / union) if union else 1.0


def size_metrics(predictions: list[list[str]], actual: list[str], size_order: list[str]) -> dict:
    if not actual or len(predictions) != len(actual) or any(not p for p in predictions):
        raise ValueError("Nonempty paired rankings and labels required")
    order = {label: i for i, label in enumerate(size_order)}
    return {
        "exactSizeAccuracy": float(np.mean([p[0] == a for p, a in zip(predictions, actual)])),
        "adjacentSizeAccuracy": float(
            np.mean([abs(order[p[0]] - order[a]) <= 1 for p, a in zip(predictions, actual)])
        ),
        "top2Accuracy": float(np.mean([a in p[:2] for p, a in zip(predictions, actual)])),
        "n": len(actual),
    }


def validate_splits(records: list[dict]) -> dict:
    seen_people, seen_garments = {}, {}
    counts = {"train": 0, "validation": 0, "test": 0}
    for record in records:
        split = record["split"]
        if split not in counts:
            raise ValueError("Unknown split")
        counts[split] += 1
        for key, seen in (("personId", seen_people), ("garmentId", seen_garments)):
            identity = record[key]
            if identity in seen and seen[identity] != split:
                raise ValueError(f"{key} leakage: {identity} appears in multiple splits")
            seen[identity] = split
    return counts
