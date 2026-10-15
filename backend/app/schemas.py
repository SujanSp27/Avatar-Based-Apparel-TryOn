from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ml.sizing.engine import Category, Fit


class TryOnMode(str, Enum):
    two_d = "2d"


class BrandCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=120)
    isDemo: bool = False


class SizeCreate(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    sizeLabel: str = Field(min_length=1, max_length=20)
    sortOrder: int = Field(ge=0, le=100)
    chestMin: float = Field(gt=0, le=300)
    chestMax: float = Field(gt=0, le=300)
    waistMin: float = Field(gt=0, le=300)
    waistMax: float = Field(gt=0, le=300)
    hipMin: float = Field(gt=0, le=300)
    hipMax: float = Field(gt=0, le=300)
    shoulderMin: float | None = Field(default=None, gt=0, le=100)
    shoulderMax: float | None = Field(default=None, gt=0, le=100)

    @model_validator(mode="after")
    def ranges(self):
        for name in ("chest", "waist", "hip", "shoulder"):
            lo, hi = getattr(self, name + "Min"), getattr(self, name + "Max")
            if (lo is None) != (hi is None) or (lo is not None and hi < lo):
                raise ValueError(f"{name}Min must be <= {name}Max and both must be present")
        return self


class ChartCreate(BaseModel):
    garmentCategory: Category
    version: int = Field(ge=1)
    source: str = Field(min_length=3, max_length=500)
    sizes: list[SizeCreate] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def unique_sizes(self):
        if len({s.sizeLabel for s in self.sizes}) != len(self.sizes) or len(
            {s.sortOrder for s in self.sizes}
        ) != len(self.sizes):
            raise ValueError("Size labels and sort orders must be unique within a version")
        return self


class MeasurementsInput(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    chest: float = Field(gt=0, le=300)
    waist: float = Field(gt=0, le=300)
    hip: float = Field(gt=0, le=300)
    shoulderWidth: float | None = Field(default=None, gt=0, le=100)


class SizingRequest(BaseModel):
    brandId: int = Field(gt=0)
    garmentCategory: Category
    fitPreference: Fit = Fit.regular
    measurements: MeasurementsInput
