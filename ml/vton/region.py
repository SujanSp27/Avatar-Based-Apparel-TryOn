"""Keep the relevant person region detailed at a limited inference resolution."""
import numpy as np


def lower_body_visible(labels: np.ndarray) -> bool:
    """Check lower-body evidence relative to the person, not the background.

    Large studio margins and mirror selfies must not invalidate an otherwise
    visible skirt or legs. This is a parsing sanity check, not a pose-quality
    guarantee; small isolated lower-body labels cannot qualify a portrait.
    """
    if labels.ndim != 2:
        raise ValueError("Expected a semantic label map")
    person = np.isin(labels, tuple(range(1, 18)))
    rows = np.nonzero(person)[0]
    if rows.size < 64:
        return False
    lower = np.isin(labels, (4, 5, 6, 14, 15))
    lower_rows = np.nonzero(lower)[0]
    if lower_rows.size < max(64, rows.size * .06):
        return False
    person_height = int(rows.max() - rows.min() + 1)
    lower_height = int(lower_rows.max() - lower_rows.min() + 1)
    return lower_height >= person_height * .18 and float(np.median(lower_rows)) > rows.min() + person_height * .4


def inference_region(labels: np.ndarray, category: str) -> tuple[int, int, int, int]:
    """Return a padded PIL crop; no generated pixels or geometry warping.

    Upper-body inference retains head, clothing, arms and hands. Other categories
    retain the full person. Clothing replacement still uses semantic masks after
    mapping the generated crop back into the original photograph.
    """
    if labels.ndim != 2 or category not in {"tops", "bottoms", "one-pieces"}:
        raise ValueError("Expected a semantic label map and supported category")
    height, width = labels.shape
    selected = np.isin(labels, (1, 2, 3, 7, 9, 10, 11, 12, 13, 16, 17)) if category == "tops" else labels != 0
    rows, columns = np.nonzero(selected)
    if rows.size < max(16, labels.size * .003):
        return 0, 0, width, height
    left, right, top, bottom = int(columns.min()), int(columns.max()) + 1, int(rows.min()), int(rows.max()) + 1
    pad_x = max(12, round((right - left) * .15))
    pad_y = max(12, round((bottom - top) * .08))
    return max(0, left - pad_x), max(0, top - pad_y), min(width, right + pad_x), min(height, bottom + pad_y)
