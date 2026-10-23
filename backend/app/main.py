import logging
import secrets
import time
from contextlib import asynccontextmanager
from threading import BoundedSemaphore
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pymongo.errors import PyMongoError
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.accounts.router import router as account_router
from backend.app.anthropometry.repository import repository as measurement_repository
from backend.app.anthropometry.router import get_measurement_service
from backend.app.anthropometry.router import router as measurement_router
from backend.app.charts import chart_dict, create_chart, latest_chart, seed_database
from backend.app.colab_connection import ColabConnection
from backend.app.config import ROOT, settings
from backend.app.db import SessionLocal, engine, get_db
from backend.app.health import router as health_router
from backend.app.garments import router as garment_router
from backend.app.jobs import TryOnJobs
from backend.app.models import Brand, ChartVersion, Run
from backend.app.online_vton import normalized_image
from backend.app.pipeline import TryOnPipeline
from backend.app.schemas import (
    BrandCreate,
    ChartCreate,
    RunPage,
    RunStatus,
    SizingRequest,
    TryOnMode,
)
from backend.app.storage import AssetStore
from ml.errors import PipelineError
from ml.sizing.engine import Category, Fit, recommend
from ml.vton.categories import GarmentCategory

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)
store = AssetStore(settings.asset_root)
pipeline = TryOnPipeline(store)
connection = ColabConnection(pipeline.worker)
capacity = BoundedSemaphore(1)
jobs = TryOnJobs(ROOT / ".runtime/tryon-jobs", capacity)


@asynccontextmanager
async def lifespan(app: FastAPI):
    jobs.recover_interrupted()
    try:
        with SessionLocal() as db:
            seed_database(db)
    except SQLAlchemyError:
        # The independent MongoDB APIs should remain usable during a SQL outage.
        logger.error("PostgreSQL startup check failed; legacy sizing and try-on are unavailable.")
    connection.start()
    try:
        yield
    finally:
        connection.close()
        jobs.close()
        if get_measurement_service.cache_info().currsize:
            get_measurement_service().detector.close()
            get_measurement_service.cache_clear()
        measurement_repository.close()


app = FastAPI(title="Form / Fit research API", version="0.2.0", lifespan=lifespan,
              description="Private Colab 2D try-on, CPU body estimates, and MongoDB-backed brand sizing. Single-process local prototype.")
app.state.tryon_connection = connection
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization", "X-Admin-Token", "Prefer", "Idempotency-Key"],
    expose_headers=["Location", "X-Request-ID", "Retry-After"],
)
app.mount("/assets", StaticFiles(directory=str(store.root)), name="assets")
annotation_root = settings.measurement_output_root / "annotated"
annotation_root.mkdir(parents=True, exist_ok=True)
app.mount("/static/annotated", StaticFiles(directory=str(annotation_root)), name="annotated")
app.include_router(measurement_router)
app.include_router(health_router)
app.include_router(garment_router)
app.include_router(account_router)


@app.middleware("http")
async def limit_request(request, call_next):
    length = request.headers.get("content-length")
    if request.url.path.startswith(("/api/v1/auth/", "/api/v1/profile")) and request.method in {"POST", "PATCH"}:
        if length and (not length.isdigit() or int(length) > 1024 * 1024):
            return JSONResponse(status_code=413, content={"error": {"code": "request_too_large", "message": "Account requests must be smaller than 1 MB."}})
    upload_paths = {"/api/tryon": 2, "/api/v1/measurements/extract": 1,
                    "/api/v1/measurements/extract-and-recommend": 1}
    if request.url.path in upload_paths and request.method == "POST":
        if not length:
            return JSONResponse(
                status_code=411,
                content={
                    "error": {
                        "code": "length_required",
                        "message": "Content-Length is required for image uploads.",
                    }
                },
            )
        if not length.isdigit() or int(length) > (
            settings.max_upload_mb * upload_paths[request.url.path] + 1
        ) * 1024 * 1024:
            return JSONResponse(
                status_code=413,
                content={
                    "error": {
                        "code": "upload_too_large",
                        "message": "Request exceeds the upload limit.",
                    }
                },
            )
    return await call_next(request)


@app.middleware("http")
async def request_metadata(request, call_next):
    request.state.request_id = uuid4().hex
    start = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    if request.url.path.startswith(("/api/v1/auth", "/api/v1/profile")):
        response.headers["Cache-Control"] = "no-store"
    if response.status_code in (429, 503):
        response.headers["Retry-After"] = "5"
    if request.url.path.startswith("/api/"):
        logger.info("request=%s method=%s status=%s seconds=%.3f", request.state.request_id,
                    request.method, response.status_code, time.perf_counter() - start)
    return response


@app.exception_handler(PipelineError)
async def pipeline_error(_, exc: PipelineError):
    return JSONResponse(
        status_code=exc.status_code, content={"error": {"code": exc.code, "message": str(exc)}}
    )


@app.exception_handler(IntegrityError)
async def integrity_error(_, exc):
    return JSONResponse(
        status_code=409,
        content={
            "error": {
                "code": "conflict",
                "message": "A brand or chart version with these identifiers already exists.",
            }
        },
    )


@app.exception_handler(SQLAlchemyError)
async def database_error(_, exc):
    logger.error("PostgreSQL request failed (%s)", type(exc).__name__)
    return JSONResponse(status_code=503, content={"error": {
        "code": "database_unavailable", "message": "The application database is unavailable; retry when it is running."}})


@app.exception_handler(PyMongoError)
async def account_database_error(_, exc):
    logger.error("Account database request failed (%s)", type(exc).__name__)
    return JSONResponse(status_code=503, content={"error": {
        "code": "account_database_unavailable", "message": "The account database is unavailable. Please retry shortly."}})


@app.exception_handler(Exception)
async def unexpected_error(request, exc):
    request_id = getattr(request.state, "request_id", uuid4().hex)
    logger.error("Unexpected API error request=%s type=%s", request_id, type(exc).__name__)
    return JSONResponse(status_code=500, headers={"X-Request-ID": request_id}, content={"error": {
        "code": "internal_error", "message": "An unexpected error occurred. Use the request ID to locate the server log.",
        "request_id": request_id}})


def admin(x_admin_token: str = Header(default="")):
    if settings.admin_token and not secrets.compare_digest(x_admin_token, settings.admin_token):
        raise HTTPException(403, "Admin token required")


@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {
        "status": "ok",
        "database": engine.dialect.name,
        "tryonModes": ["2d"],
        "vton2d": connection.snapshot(),
        "scope": "Online GPU photo try-on; independent measured-input brand sizing",
    }


@app.get("/api/brands")
def brands(db: Session = Depends(get_db)):
    return [
        {"id": b.id, "name": b.name, "slug": b.slug, "isDemo": b.is_demo}
        for b in db.scalars(select(Brand).order_by(Brand.id))
    ]


@app.get("/api/tryon/availability")
def tryon_availability():
    # Independent from PostgreSQL and the inference queue, always fast.
    return connection.snapshot()


@app.post("/api/tryon/retry", status_code=202)
def retry_tryon_connection():
    return connection.retry()


@app.post("/api/brands", status_code=201, dependencies=[Depends(admin)])
def add_brand(data: BrandCreate, db: Session = Depends(get_db)):
    brand = Brand(name=data.name, slug=data.slug, is_demo=data.isDemo)
    db.add(brand)
    db.commit()
    return {"id": brand.id, **data.model_dump()}


@app.get("/api/brands/{brand_id}/charts")
def get_chart(
    brand_id: int,
    garmentCategory: Category,
    version: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
):
    return chart_dict(latest_chart(db, brand_id, garmentCategory.value, version))


@app.get("/api/brands/{brand_id}/chart-versions")
def versions(brand_id: int, garmentCategory: Category, db: Session = Depends(get_db)):
    return [
        {"version": c.version, "source": c.source, "createdAt": c.created_at.isoformat()}
        for c in db.scalars(
            select(ChartVersion)
            .where(
                ChartVersion.brand_id == brand_id,
                ChartVersion.garment_category == garmentCategory.value,
            )
            .order_by(ChartVersion.version.desc())
        )
    ]


@app.post("/api/brands/{brand_id}/charts", status_code=201, dependencies=[Depends(admin)])
@app.put("/api/brands/{brand_id}/charts", status_code=201, dependencies=[Depends(admin)])
def add_chart(brand_id: int, data: ChartCreate, db: Session = Depends(get_db)):
    chart = create_chart(db, brand_id, data)
    db.commit()
    return chart_dict(chart)


@app.post("/api/sizing/recommend")
def sizing(data: SizingRequest, db: Session = Depends(get_db)):
    chart = latest_chart(db, data.brandId, data.garmentCategory.value)
    result = recommend(
        data.measurements.model_dump(exclude_none=True),
        chart_dict(chart)["sizes"],
        data.garmentCategory.value,
        data.fitPreference.value,
    )
    return {**result, "chartVersion": chart.version, "chartSource": chart.source}


def upload_bytes(upload: UploadFile) -> bytes:
    limit = settings.max_upload_mb * 1024 * 1024
    data = upload.file.read(limit + 1)
    if len(data) > limit:
        raise PipelineError(
            "upload_too_large", f"Each image must be below {settings.max_upload_mb} MB.", 413
        )
    return data


def require_tryon_ready():
    status = pipeline.worker.availability(check_connection=True)
    if not status['available']:
        connection.retry()
        raise PipelineError('online_gpu_unavailable', connection.snapshot()['reason'] or
                            'The Colab model is unavailable. Recovery has been requested; retry shortly.', 503)


@app.post("/api/tryon")
def tryon(
    personImage: UploadFile = File(),
    garmentImage: UploadFile = File(),
    brandId: int | None = Form(default=None, gt=0),
    garmentCategory: GarmentCategory = Form(),
    fitPreference: Fit = Form(Fit.regular),
    tryonMode: TryOnMode = Form(TryOnMode.two_d),
    garmentPhotoType: str = Form(default="flat-lay", pattern="^(flat-lay|model)$"),
    prefer: str = Header(default=""),
    idempotency_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    if brandId is not None and db.get(Brand, brandId) is None:
        raise PipelineError("brand_missing", "The selected brand does not exist.", 404)
    if prefer == "respond-async":
        # Image generation is independent of available sizing charts.
        person_data, garment_data = upload_bytes(personImage), upload_bytes(garmentImage)
        parameters = {
            "brand_id": brandId, "category": garmentCategory.value, "fit": fitPreference.value,
            "photo_type": garmentPhotoType,
        }

        def work():
            # A request-scoped database session cannot cross into the worker thread.
            with SessionLocal() as worker_db:
                return pipeline.run(worker_db, person_data, garment_data, **parameters)

        def preflight():
            normalized_image(person_data)
            normalized_image(garment_data)
            require_tryon_ready()

        state = jobs.submit(person_data, garment_data, parameters, work, idempotency_key, preflight=preflight)
        return JSONResponse(status_code=202, content=state, headers={"Location": state["statusUrl"]})
    if not capacity.acquire(blocking=False):
        raise PipelineError("busy", "Another try-on is running. Retry after it finishes.", 429)
    try:
        require_tryon_ready()
        return pipeline.run(
            db,
            upload_bytes(personImage),
            upload_bytes(garmentImage),
            brandId,
            garmentCategory.value,
            fitPreference.value,
            photo_type=garmentPhotoType,
        )
    finally:
        capacity.release()


@app.get("/api/tryon/jobs/{job_id}")
def job_status(job_id: UUID):
    return jobs.get(job_id)


@app.get("/api/runs", response_model=RunPage, dependencies=[Depends(admin)])
def list_runs(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
              status: RunStatus | None = None, db: Session = Depends(get_db)):
    query = select(Run)
    count = select(func.count()).select_from(Run)
    if status is not None:
        query = query.where(Run.status == status)
        count = count.where(Run.status == status)
    rows = db.scalars(query.order_by(Run.created_at.desc(), Run.id).offset(offset).limit(limit))
    return {"items": [{"id": row.id, "status": row.status, "created_at": row.created_at} for row in rows],
            "total": db.scalar(count), "limit": limit, "offset": offset}


@app.get("/api/runs/{run_id}")
def get_run(run_id: UUID, db: Session = Depends(get_db)):
    run = db.get(Run, str(run_id))
    if not run:
        raise HTTPException(404, "Run not found")
    return {"id": run.id, "status": run.status, "metadata": run.metadata_json}


@app.delete("/api/runs/{run_id}", status_code=204, dependencies=[Depends(admin)])
def delete_run(run_id: UUID, db: Session = Depends(get_db)):
    run = db.get(Run, str(run_id))
    if not run:
        raise HTTPException(404, "Run not found")
    if run.status == "processing":
        raise HTTPException(409, "Cannot delete a running job")
    store.delete(str(run_id))
    db.delete(run)
    db.commit()


@app.get("/api/samples/{kind}")
def sample(kind: str):
    files = {"person": "studio-person.jpg", "garment": "garment-demo.png", "polo": "sage-polo.jpg"}
    if kind not in files or not (ROOT / "data/raw" / files[kind]).is_file():
        raise HTTPException(404, "Sample not available")
    return FileResponse(
        ROOT / "data/raw" / files[kind],
        media_type="image/png" if kind == "garment" else "image/jpeg",
    )
