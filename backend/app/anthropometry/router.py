import secrets
from functools import lru_cache
from pathlib import Path
from threading import BoundedSemaphore

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile

from backend.app.anthropometry.measurement_service import MeasurementService
from backend.app.anthropometry.pose_adapter import MediaPipePose
from backend.app.anthropometry.repository import MeasurementRepository, get_repository
from backend.app.anthropometry.schemas import (
    ChartCreate,
    ExtractionResponse,
    Gender,
    Identifier,
    SizingRequest,
    SizingResponse,
)
from backend.app.anthropometry.sizing_engine import recommend
from backend.app.config import settings
from ml.errors import PipelineError

router = APIRouter(prefix="/api/v1", tags=["Body measurements and brand sizing"])
measurement_capacity = BoundedSemaphore(1)


@lru_cache(maxsize=1)
def get_measurement_service() -> MeasurementService:
    return MeasurementService(
        MediaPipePose(settings.measurement_model_path),
        settings.measurement_output_root / "annotated",
    )


def chart_admin(x_admin_token: str = Header(default="")):
    if settings.admin_token and not secrets.compare_digest(settings.admin_token, x_admin_token):
        raise HTTPException(403, "Admin token required")


@router.post("/measurements/extract", response_model=ExtractionResponse)
def extract_measurements(
    image: UploadFile = File(),
    height_cm: float = Form(ge=80, le=250, allow_inf_nan=False),
    repo: MeasurementRepository = Depends(get_repository),
    service: MeasurementService = Depends(get_measurement_service),
):
    if not measurement_capacity.acquire(blocking=False):
        raise PipelineError("measurement_busy", "Another measurement is running; retry shortly.", 429)
    try:
        limit = settings.max_upload_mb * 1024 * 1024
        data = image.file.read(limit + 1)
        if len(data) > limit:
            raise PipelineError("upload_too_large", f"Image must be below {settings.max_upload_mb} MB.", 413)
        response = service.extract(data, height_cm)
        measurement_id = Path(response.annotated_image_url).stem
        try:
            repo.save_measurement(measurement_id, response)
        except PipelineError:
            # All three names originate in our UUID generator, never an upload name.
            for suffix in (".png", "_mask.png", ".json"):
                (service.output_root / f"{measurement_id}{suffix}").unlink(missing_ok=True)
            raise
        return response
    finally:
        measurement_capacity.release()


@router.post("/sizing/recommend", response_model=SizingResponse)
def recommend_size(data: SizingRequest, repo: MeasurementRepository = Depends(get_repository)):
    chart = repo.get_chart(data.brand_id, data.apparel_id, data.chart_version)
    return recommend(data.measurements, chart)


@router.get("/sizing/charts")
def list_charts(
    gender: Gender | None = None,
    market: str | None = Query(default=None, pattern=r"^(?:[A-Z]{2}|UNSPECIFIED)$"),
    brand_id: Identifier | None = None,
    repo: MeasurementRepository = Depends(get_repository),
):
    return repo.list_charts(gender=gender, market=market, brand_id=brand_id)


@router.get("/sizing/brands")
def list_brands(repo: MeasurementRepository = Depends(get_repository)):
    """Verified India coverage and explicit gaps; not a promise of brand-wide support."""
    return repo.list_brands()


@router.get("/sizing/charts/{brand_id}/{apparel_id}", response_model=ChartCreate)
def get_chart(
    brand_id: Identifier, apparel_id: Identifier,
    version: int | None = Query(default=None, ge=1),
    repo: MeasurementRepository = Depends(get_repository),
):
    return repo.get_chart(brand_id, apparel_id, version)


@router.post("/sizing/charts", status_code=201, response_model=ChartCreate, dependencies=[Depends(chart_admin)])
def create_chart(data: ChartCreate, repo: MeasurementRepository = Depends(get_repository)):
    return repo.create_chart(data)
