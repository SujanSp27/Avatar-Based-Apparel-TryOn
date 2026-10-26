"""Enforce photo quality before scoring; raw manual input remains a separate path."""

from backend.app.anthropometry.schemas import ChartCreate, ExtractionResponse
from ml.errors import PipelineError


def reviewed_measurements(record: ExtractionResponse, chart: ChartCreate, overrides: dict | None = None) -> dict:
    overrides = overrides or {}
    values = record.measurements.model_dump(exclude_none=True)
    review = set(record.quality.get("requires_manual_review", []))
    missing = (set(chart.metrics) & (review | (set(chart.metrics) - values.keys()))) - overrides.keys()
    if missing:
        raise PipelineError("measurement_review_required", "Enter or confirm tape measurements before sizing: "
                            + ", ".join(sorted(name.replace("_", " ") for name in missing)) + ".")
    return {**values, **overrides}
