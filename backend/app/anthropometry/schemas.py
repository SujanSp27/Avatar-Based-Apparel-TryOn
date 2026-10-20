from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.app.anthropometry.constants import CATEGORY_METRICS
from ml.vton.categories import GarmentCategory

Metric = Literal[
    "shoulder_width", "chest_circumference", "waist_circumference",
    "hip_circumference", "thigh_circumference", "inseam_length",
]
Identifier = Annotated[str, Field(min_length=1, max_length=120, pattern=r"^[a-zA-Z0-9_-]+$")]
Centimeters = Annotated[float, Field(gt=0, le=400)]


class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Measurements(StrictSchema):
    shoulder_width: float = Field(gt=0, le=100)
    chest_circumference: Centimeters
    waist_circumference: Centimeters
    hip_circumference: Centimeters
    thigh_circumference: Centimeters
    inseam_length: float = Field(gt=0, le=200)


class ExtractionResponse(StrictSchema):
    scale_factor: float
    measurements: Measurements
    annotated_image_url: str
    quality: dict
    geometry: dict
    provenance: dict
    warnings: list[str]


class MeasurementRange(StrictSchema):
    lower: Centimeters
    upper: Centimeters

    @model_validator(mode="after")
    def ordered_bounds(self):
        if self.lower > self.upper:
            raise ValueError("lower must be less than or equal to upper")
        return self


class ChartSize(StrictSchema):
    size_label: str = Field(min_length=1, max_length=20)
    sort_order: int = Field(ge=0, le=100)
    bounds: dict[Metric, MeasurementRange]


class ChartCreate(StrictSchema):
    brand_id: Identifier
    brand_name: str = Field(min_length=1, max_length=120)
    apparel_id: Identifier
    category: GarmentCategory
    version: int = Field(ge=1)
    source: str = Field(min_length=3, max_length=500)
    is_demo: bool = False
    sizes: list[ChartSize] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def consistent_sizes(self):
        if len({r.size_label for r in self.sizes}) != len(self.sizes):
            raise ValueError("Size labels must be unique")
        if len({r.sort_order for r in self.sizes}) != len(self.sizes):
            raise ValueError("Sort orders must be unique")
        required = set(CATEGORY_METRICS[self.category.value])
        for row in self.sizes:
            if missing := required - row.bounds.keys():
                raise ValueError(f"{row.size_label} is missing category bounds: {sorted(missing)}")
        return self


class SizingRequest(StrictSchema):
    brand_id: Identifier
    apparel_id: Identifier
    measurements: dict[Metric, Centimeters] = Field(min_length=1)
    chart_version: int | None = Field(default=None, ge=1)


class SizeRanking(StrictSchema):
    size: str
    error: float
    deviations: dict[Metric, float]


class SizingResponse(StrictSchema):
    recommended_size: str
    minimum_error: float
    fit_confidence: float
    size_rankings: list[SizeRanking]
    chart_comparison: dict
    active_weights: dict[Metric, float]
    chart: dict
    score_meaning: str
