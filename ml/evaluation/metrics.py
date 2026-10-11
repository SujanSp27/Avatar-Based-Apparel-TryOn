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


def pose_metrics(predicted, actual) -> dict:
    p, a = np.asarray(predicted, dtype=float), np.asarray(actual, dtype=float)
    if (
        p.shape != a.shape
        or p.ndim != 2
        or p.shape[1] != 3
        or len(p) < 3
        or not np.isfinite(p).all()
        or not np.isfinite(a).all()
    ):
        raise ValueError("Expected matching finite Nx3 joints")
    pc, ac = p - p.mean(axis=0), a - a.mean(axis=0)
    if np.linalg.norm(pc) < 1e-8 or np.linalg.norm(ac) < 1e-8:
        raise ValueError("Degenerate pose")
    u, s, vt = np.linalg.svd(pc.T @ ac)
    correction = np.eye(3)
    correction[-1, -1] = np.linalg.det(u @ vt)
    rotation = u @ correction @ vt
    scale = np.sum(s * np.diag(correction)) / np.square(pc).sum()
    aligned = scale * pc @ rotation + a.mean(axis=0)
    return {
        "mpjpe": float(np.linalg.norm(p - a, axis=1).mean()),
        "p_mpjpe": float(np.linalg.norm(aligned - a, axis=1).mean()),
        "units": "same as input coordinates",
    }


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
