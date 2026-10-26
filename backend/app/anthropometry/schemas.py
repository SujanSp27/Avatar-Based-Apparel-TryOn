from datetime import date, datetime
from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from backend.app.anthropometry.constants import CATEGORY_METRICS

# Size-chart coverage is independent of the image model's supported categories.
SizingCategory = Enum("SizingCategory", {key.replace("-", "_"): key for key in CATEGORY_METRICS}, type=str)

Metric = Literal[
    "shoulder_width", "chest_circumference", "waist_circumference",
    "hip_circumference", "thigh_circumference", "inseam_length",
]
Identifier = Annotated[str, Field(min_length=1, max_length=120, pattern=r"^[a-zA-Z0-9_-]+$")]
Centimeters = Annotated[float, Field(gt=0, le=400)]
Gender = Literal["men", "women", "unisex"]
MeasurementId = Annotated[str, Field(pattern=r"^pose_[0-9a-f]{32}$")]


class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class APIError(StrictSchema):
    code: str
    message: str


class ErrorResponse(StrictSchema):
    error: APIError


class CategoryMetrics(StrictSchema):
    category: SizingCategory
    default_metrics: list[Metric]
    default_weights: dict[Metric, float]


class Measurements(StrictSchema):
    shoulder_width: float = Field(gt=0, le=100)
    chest_circumference: Centimeters
    waist_circumference: Centimeters
    hip_circumference: Centimeters
    thigh_circumference: Centimeters
    inseam_length: float = Field(gt=0, le=200)


class PhotoMeasurements(Measurements):
    # Missing torso boundaries are unknown, never zero or an arm-inclusive width.
    # Manual/saved complete Measurements remain strictly positive and non-null.
    chest_circumference: Centimeters | None = None
    waist_circumference: Centimeters | None = None


class ExtractionResponse(StrictSchema):
    measurement_id: MeasurementId | None = None
    scale_factor: float
    measurements: PhotoMeasurements
    annotated_image_url: str
    quality: dict
    geometry: dict
    provenance: dict
    warnings: list[str]
    landmarks_normalized: list[list[float]] = Field(default_factory=list)


class StoredMeasurement(ExtractionResponse):
    measurement_id: MeasurementId
    created_at: datetime


class MeasurementPage(StrictSchema):
    items: list[StoredMeasurement]
    total: int
    limit: int
    offset: int


class BrandCreate(StrictSchema):
    brand_id: Identifier
    brand_name: str = Field(min_length=1, max_length=120)
    market: str = Field(default="IN", pattern=r"^[A-Z]{2}$")
    official_url: HttpUrl | None = None
    description: str = Field(default="", max_length=1000)


class BrandUpdate(StrictSchema):
    brand_name: str | None = Field(default=None, min_length=1, max_length=120)
    official_url: HttpUrl | None = None
    description: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def nonempty(self):
        if not self.model_fields_set or any(getattr(self, key) is None for key in self.model_fields_set):
            raise ValueError("Provide at least one non-null field to update")
        return self


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
    category: SizingCategory
    version: int = Field(ge=1)
    source: str = Field(min_length=3, max_length=500)
    is_demo: bool = False
    gender: Gender = "unisex"
    market: str = Field(default="UNSPECIFIED", pattern=r"^(?:[A-Z]{2}|UNSPECIFIED)$")
    source_url: HttpUrl | None = None
    checked_on: date | None = None
    source_unit: Literal["cm", "in"] = "cm"
    measurement_basis: Literal["body", "garment"] = "body"
    sizing_system: str = Field(default="Brand label (no regional conversion)", max_length=150)
    source_type: Literal["official", "retailer", "user-supplied", "demo"] = "user-supplied"
    verification_status: Literal["verified", "unverified", "user-supplied", "demo"] = "unverified"
    notes: list[str] = Field(default_factory=list, max_length=20)
    # Explicit subsets are needed for official charts that do not publish all
    # category dimensions. Never fabricate shoulder/thigh ranges to fill gaps.
    active_metrics: list[Metric] | None = Field(default=None, min_length=1, max_length=6)
    sizes: list[ChartSize] = Field(min_length=1, max_length=30)

    @property
    def metrics(self) -> tuple[str, ...]:
        return tuple(self.active_metrics or CATEGORY_METRICS[self.category.value])

    @model_validator(mode="after")
    def consistent_sizes(self):
        if self.verification_status == "verified" and (not self.source_url or not self.checked_on or self.is_demo):
            raise ValueError("Verified charts require a source URL, verification date and non-demo data")
        if len({r.size_label for r in self.sizes}) != len(self.sizes):
            raise ValueError("Size labels must be unique")
        if len({r.sort_order for r in self.sizes}) != len(self.sizes):
            raise ValueError("Sort orders must be unique")
        required = set(self.metrics)
        if len(required) != len(self.metrics):
            raise ValueError("Active metrics must be unique")
        if required - set(CATEGORY_METRICS[self.category.value]):
            raise ValueError("Active metrics must belong to the apparel category")
        for row in self.sizes:
            if missing := required - row.bounds.keys():
                raise ValueError(f"{row.size_label} is missing category bounds: {sorted(missing)}")
        return self


class SizingRequest(StrictSchema):
    brand_id: Identifier
    apparel_id: Identifier
    measurements: dict[Metric, Centimeters] | None = Field(default=None, min_length=1)
    measurement_id: MeasurementId | None = None
    chart_version: int | None = Field(default=None, ge=1)
    measurement_overrides: dict[Metric, Centimeters] = Field(default_factory=dict)

    @model_validator(mode="after")
    def one_measurement_source(self):
        if (self.measurements is None) == (self.measurement_id is None):
            raise ValueError("Provide exactly one of measurements or measurement_id")
        if self.measurement_overrides and not self.measurement_id:
            raise ValueError("Tape overrides require a measurement_id")
        return self


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
    warnings: list[str] = Field(default_factory=list)
    measurement_id: MeasurementId | None = None


class ExtractAndRecommendResponse(StrictSchema):
    extraction: ExtractionResponse
    recommendation: SizingResponse | None
    recommendation_error: APIError | None = None
