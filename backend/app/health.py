"""Capability-specific readiness without loading models or running inference."""

from typing import Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.anthropometry.repository import repository
from backend.app.config import settings
from backend.app.db import get_db

router = APIRouter(prefix="/api/v1/health", tags=["Health"])


def mongo_repository():
    # A failed MongoDB ping belongs in the health response, not an early dependency error.
    return repository


def component_status(request: Request, db: Session, repo) -> dict:
    try:
        db.execute(text("SELECT 1"))
        postgres = True
    except SQLAlchemyError:
        try:
            db.rollback()
        except SQLAlchemyError:
            pass  # A broken connection must not hide the other capability checks.
        postgres = False
    mongo = repo.ping()
    checkpoint = settings.measurement_model_path.is_file()
    remote = request.app.state.tryon_connection.snapshot()
    return {
        "status": "ok" if postgres and mongo and checkpoint and remote.get("available") else "degraded",
        "components": {
            "postgresql": {"available": postgres}, "mongodb": {"available": mongo},
            "pose_model": {"checkpoint_present": checkpoint, "device": "cpu", "inference_validated": False},
            "colab": {"available": bool(remote.get("available")), "state": remote.get("connectionState", "unknown"),
                      "reason": remote.get("reason")},
        },
        "capabilities": {"sizing": mongo, "measurements": mongo and checkpoint,
                         "tryon": postgres and bool(remote.get("available"))},
        "local_gpu_used": False,
    }


@router.get("/live")
def live():
    return {"status": "ok"}


@router.get("")
def health(request: Request, db: Session = Depends(get_db), repo=Depends(mongo_repository)):
    return component_status(request, db, repo)


@router.get("/ready")
def ready(request: Request, capability: Literal["sizing", "measurements", "tryon", "all"] = "all",
          db: Session = Depends(get_db), repo=Depends(mongo_repository)):
    state = component_status(request, db, repo)
    available = all(state["capabilities"].values()) if capability == "all" else state["capabilities"][capability]
    return JSONResponse({**state, "requested_capability": capability, "ready": available},
                        status_code=200 if available else 503)
