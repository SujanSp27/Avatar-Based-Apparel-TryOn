import logging
import secrets
from contextlib import asynccontextmanager
from threading import BoundedSemaphore
from uuid import UUID

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.charts import chart_dict, create_chart, latest_chart, seed_database
from backend.app.config import ROOT, settings
from backend.app.db import SessionLocal, engine, get_db
from backend.app.jobs import TryOnJobs
from backend.app.models import Brand, ChartVersion, Run
from backend.app.photo_tryon import get_vton
from backend.app.pipeline import TryOnPipeline
from backend.app.schemas import BrandCreate, ChartCreate, SizingRequest, TryOnMode
from backend.app.storage import AssetStore
from ml.errors import PipelineError
from ml.sizing.engine import Category, Fit, recommend

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
store = AssetStore(settings.asset_root)
pipeline = TryOnPipeline(store)
capacity = BoundedSemaphore(1)
jobs = TryOnJobs(ROOT / ".runtime/tryon-jobs", capacity)


@asynccontextmanager
async def lifespan(app: FastAPI):
    jobs.recover_interrupted()
    with SessionLocal() as db:
        seed_database(db)
    yield
    jobs.close()


app = FastAPI(title="Form / Fit research API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "X-Admin-Token", "Prefer", "Idempotency-Key"],
)
app.mount("/assets", StaticFiles(directory=str(store.root)), name="assets")


@app.middleware("http")
async def limit_request(request, call_next):
    length = request.headers.get("content-length")
    if request.url.path == "/api/tryon" and request.method == "POST":
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
        if not length.isdigit() or int(length) > (settings.max_upload_mb * 2 + 1) * 1024 * 1024:
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


def admin(x_admin_token: str = Header(default="")):
    if settings.admin_token and not secrets.compare_digest(x_admin_token, settings.admin_token):
        raise HTTPException(403, "Admin token required")


@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {
        "status": "ok",
        "database": engine.dialect.name,
        "humanBackend": settings.human_backend,
        "poseModelAvailable": settings.model_path.is_file(),
        "hmr2Available": False,
        "tryonModes": ["auto", "3d", "2d"],
        "vton2d": get_vton().availability(),
        "scope": "approximate 3D template and pretrained 2D virtual try-on research prototype",
    }


@app.get("/api/brands")
def brands(db: Session = Depends(get_db)):
    return [
        {"id": b.id, "name": b.name, "slug": b.slug, "isDemo": b.is_demo}
        for b in db.scalars(select(Brand).order_by(Brand.id))
    ]


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


@app.post("/api/tryon")
def tryon(
    personImage: UploadFile = File(),
    garmentImage: UploadFile = File(),
    brandId: int = Form(gt=0),
    garmentCategory: Category = Form(),
    fitPreference: Fit = Form(Fit.regular),
    heightCm: float | None = Form(default=None, ge=120, le=220),
    garmentLengthCm: float | None = Form(default=None, ge=20, le=180),
    garmentWidthCm: float | None = Form(default=None, ge=20, le=100),
    tryonMode: TryOnMode = Form(TryOnMode.auto),
    prefer: str = Header(default=""),
    idempotency_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    dimensions = {
        k: v for k, v in {"lengthCm": garmentLengthCm, "widthCm": garmentWidthCm}.items()
        if v is not None
    }
    if prefer == "respond-async":
        # Check chart/category before occupying the only inference slot.
        latest_chart(db, brandId, garmentCategory.value)
        person_data, garment_data = upload_bytes(personImage), upload_bytes(garmentImage)
        parameters = {
            "brand_id": brandId, "category": garmentCategory.value, "fit": fitPreference.value,
            "height_cm": heightCm, "dimensions": dimensions, "mode": tryonMode.value,
        }

        def work():
            # A request-scoped database session cannot cross into the worker thread.
            with SessionLocal() as worker_db:
                return pipeline.run(worker_db, person_data, garment_data, **parameters)

        state = jobs.submit(person_data, garment_data, parameters, work, idempotency_key)
        return JSONResponse(status_code=202, content=state, headers={"Location": state["statusUrl"]})
    if not capacity.acquire(blocking=False):
        raise PipelineError("busy", "Another try-on is running. Retry after it finishes.", 429)
    try:
        dimensions = {
            k: v
            for k, v in {"lengthCm": garmentLengthCm, "widthCm": garmentWidthCm}.items()
            if v is not None
        }
        return pipeline.run(
            db,
            upload_bytes(personImage),
            upload_bytes(garmentImage),
            brandId,
            garmentCategory.value,
            fitPreference.value,
            heightCm,
            dimensions,
            mode=tryonMode.value,
        )
    finally:
        capacity.release()


@app.get("/api/tryon/jobs/{job_id}")
def job_status(job_id: UUID):
    return jobs.get(job_id)


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
    files = {"person": "studio-person.jpg", "garment": "garment-demo.png"}
    if kind not in files or not (ROOT / "data/raw" / files[kind]).is_file():
        raise HTTPException(404, "Sample not available")
    return FileResponse(
        ROOT / "data/raw" / files[kind],
        media_type="image/jpeg" if kind == "person" else "image/png",
    )
