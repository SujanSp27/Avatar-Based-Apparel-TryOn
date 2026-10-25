from functools import lru_cache
from pathlib import Path
from threading import BoundedSemaphore

from fastapi import APIRouter, Depends, File, Form, Header, Query, Request, UploadFile
from fastapi.responses import FileResponse
from pymongo.errors import PyMongoError

from backend.app.accounts.security import now, require_admin, throttle
from backend.app.anthropometry.constants import CATEGORY_METRICS, WEIGHTS
from backend.app.anthropometry.measurement_service import MeasurementService
from backend.app.anthropometry.pose_adapter import MediaPipePose
from backend.app.anthropometry.repository import MeasurementRepository, get_repository
from backend.app.anthropometry.schemas import (
    BrandCreate,
    BrandUpdate,
    CategoryMetrics,
    ChartCreate,
    ErrorResponse,
    ExtractAndRecommendResponse,
    ExtractionResponse,
    Gender,
    Identifier,
    MeasurementId,
    MeasurementPage,
    SizingRequest,
    SizingResponse,
    StoredMeasurement,
)
from backend.app.anthropometry.sizing_engine import recommend
from backend.app.config import settings
from backend.app.private_data import check_measurement, principal
from ml.errors import PipelineError
from ml.vton.categories import GarmentCategory

router = APIRouter(prefix="/api/v1", tags=["Body measurements and brand sizing"], responses={
    404: {"model": ErrorResponse, "description": "Requested record or chart does not exist"},
    409: {"model": ErrorResponse, "description": "Brand or immutable chart version conflicts"},
    413: {"model": ErrorResponse, "description": "Image upload exceeds the configured limit"},
    429: {"model": ErrorResponse, "description": "Measurement processor is busy; retry later"},
    503: {"model": ErrorResponse, "description": "Required database, model or storage is unavailable"},
})
measurement_capacity = BoundedSemaphore(1)


@lru_cache(maxsize=1)
def get_measurement_service() -> MeasurementService:
    return MeasurementService(
        MediaPipePose(settings.measurement_model_path),
        settings.measurement_output_root / "annotated",
    )


def chart_admin(x_admin_token: str = Header(default="")):
    require_admin(x_admin_token)


def extract_and_save(image: UploadFile, height_cm: float, repo: MeasurementRepository,
                     service: MeasurementService, owner: str | None = None) -> ExtractionResponse:
    if not measurement_capacity.acquire(blocking=False):
        raise PipelineError("measurement_busy", "Another measurement is running; retry shortly.", 429)
    try:
        limit = settings.max_upload_mb * 1024 * 1024
        data = image.file.read(limit + 1)
        if len(data) > limit:
            raise PipelineError("upload_too_large", f"Image must be below {settings.max_upload_mb} MB.", 413)
        response = service.extract(data, height_cm)
        measurement_id = Path(response.annotated_image_url).stem
        response.measurement_id = measurement_id
        try:
            repo.save_measurement(measurement_id, response)
            if owner:
                repo.db.private_resources.insert_one({"_id": "measurement:" + measurement_id,
                    "owner": owner, "kind": "measurement", "resource_id": measurement_id, "created_at": now()})
        except (PipelineError, PyMongoError):
            service.remove_artifacts(measurement_id)
            repo.measurements.delete_one({"measurement_id": measurement_id})
            raise
        return response
    finally:
        measurement_capacity.release()


@router.post("/measurements/extract", response_model=ExtractionResponse)
def extract_measurements(
    request: Request,
    image: UploadFile = File(),
    height_cm: float = Form(ge=80, le=250, allow_inf_nan=False),
    repo: MeasurementRepository = Depends(get_repository),
    service: MeasurementService = Depends(get_measurement_service),
    owner: str = Depends(principal),
):
    throttle(repo.db, request, "measurement-extraction", owner, maximum=12)
    return extract_and_save(image, height_cm, repo, service, owner)


@router.post("/measurements/extract-and-recommend", response_model=ExtractAndRecommendResponse)
def extract_and_recommend(
    request: Request,
    image: UploadFile = File(), height_cm: float = Form(ge=80, le=250, allow_inf_nan=False),
    brand_id: Identifier = Form(), apparel_id: Identifier = Form(),
    chart_version: int | None = Form(default=None, ge=1),
    repo: MeasurementRepository = Depends(get_repository),
    service: MeasurementService = Depends(get_measurement_service),
    owner: str = Depends(principal),
):
    throttle(repo.db, request, "measurement-extraction", owner, maximum=12)
    chart = repo.get_chart(brand_id, apparel_id, chart_version)
    if chart.measurement_basis != "body":
        raise PipelineError("chart_basis_unsupported", "A body-size chart is required; garment dimensions cannot score body measurements.")
    extraction = extract_and_save(image, height_cm, repo, service, owner)
    result = recommend(extraction.measurements.model_dump(), chart)
    result.measurement_id = extraction.measurement_id
    result.warnings.extend(extraction.warnings)
    return ExtractAndRecommendResponse(extraction=extraction, recommendation=result)


@router.get("/measurements", response_model=MeasurementPage, dependencies=[Depends(chart_admin)])
def list_measurements(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
                      repo: MeasurementRepository = Depends(get_repository)):
    return repo.list_measurements(limit, offset)


@router.get("/measurements/{measurement_id}", response_model=StoredMeasurement)
def get_measurement(measurement_id: MeasurementId, repo: MeasurementRepository = Depends(get_repository), owner=Depends(principal)):
    check_measurement(repo.db, measurement_id, owner)
    return repo.get_measurement(measurement_id)


@router.get("/measurements/{measurement_id}/annotation", response_class=FileResponse)
def annotation(measurement_id: MeasurementId, repo: MeasurementRepository = Depends(get_repository),
               service: MeasurementService = Depends(get_measurement_service), owner=Depends(principal)):
    check_measurement(repo.db, measurement_id, owner)
    repo.get_measurement(measurement_id)
    path = service.artifact_path(measurement_id)
    if not path.is_file():
        raise PipelineError("artifact_missing", "The annotation file is unavailable.", 404)
    return FileResponse(path, media_type="image/png")


@router.delete("/measurements/{measurement_id}", status_code=204)
def delete_measurement(measurement_id: MeasurementId, repo: MeasurementRepository = Depends(get_repository),
                       service: MeasurementService = Depends(get_measurement_service), owner=Depends(principal)):
    check_measurement(repo.db, measurement_id, owner)
    repo.get_measurement(measurement_id)
    # Keep metadata if filesystem cleanup fails, so deletion can be retried.
    service.remove_artifacts(measurement_id)
    repo.delete_measurement(measurement_id)
    repo.db.private_resources.delete_one({"_id": "measurement:" + measurement_id, "owner": owner})


@router.post("/sizing/recommend", response_model=SizingResponse)
def recommend_size(data: SizingRequest, request: Request, repo: MeasurementRepository = Depends(get_repository)):
    if data.measurement_id:
        check_measurement(repo.db, data.measurement_id, principal(request, repo.db))
    chart = repo.get_chart(data.brand_id, data.apparel_id, data.chart_version)
    record = repo.get_measurement(data.measurement_id) if data.measurement_id else None
    measurements = record.measurements.model_dump() if record else data.measurements
    result = recommend(measurements, chart)
    if record:
        result.measurement_id = record.measurement_id
        result.warnings.extend(record.warnings)
    return result


@router.get("/sizing/categories", response_model=list[CategoryMetrics])
def sizing_categories():
    """Default sizing dimensions; each sourced chart may declare a smaller explicit subset."""
    return [CategoryMetrics(category=category, default_metrics=list(metrics), default_weights={
        key: WEIGHTS[key] / sum(WEIGHTS[name] for name in metrics) for key in metrics
    }) for category, metrics in CATEGORY_METRICS.items()]


@router.get("/sizing/charts", response_model=list[dict])
def list_charts(
    gender: Gender | None = None,
    market: str | None = Query(default=None, pattern=r"^(?:[A-Z]{2}|UNSPECIFIED)$"),
    brand_id: Identifier | None = None,
    category: GarmentCategory | None = None,
    limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
    latest_only: bool = False,
    repo: MeasurementRepository = Depends(get_repository),
):
    return repo.list_charts(gender=gender, market=market, brand_id=brand_id,
                            category=category.value if category else None,
                            limit=limit, offset=offset, latest_only=latest_only)


@router.get("/sizing/brands")
def list_brands(include_demo: bool = False, repo: MeasurementRepository = Depends(get_repository)):
    """Verified India coverage and explicit gaps; not a promise of brand-wide support."""
    return repo.list_brands(include_demo=include_demo)


@router.post("/sizing/brands", status_code=201, dependencies=[Depends(chart_admin)])
def create_brand(data: BrandCreate, repo: MeasurementRepository = Depends(get_repository)):
    return repo.create_brand(data)


@router.get("/sizing/brands/{brand_id}")
def get_brand(brand_id: Identifier, repo: MeasurementRepository = Depends(get_repository)):
    return repo.get_brand(brand_id)


@router.patch("/sizing/brands/{brand_id}", dependencies=[Depends(chart_admin)])
def update_brand(brand_id: Identifier, data: BrandUpdate, repo: MeasurementRepository = Depends(get_repository)):
    return repo.update_brand(brand_id, data)


@router.get("/sizing/charts/{brand_id}/{apparel_id}/versions")
def chart_versions(brand_id: Identifier, apparel_id: Identifier,
                   repo: MeasurementRepository = Depends(get_repository)):
    return repo.list_versions(brand_id, apparel_id)


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
