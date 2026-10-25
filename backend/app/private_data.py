"""Browser-scoped guest uploads and authenticated, owner-scoped private assets."""

from datetime import timedelta
from pathlib import Path
from uuid import UUID, uuid4

import jwt
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy import select

from backend.app.accounts.router import account_db, current_user
from backend.app.accounts.security import ACCESS_COOKIE, now, signing_key
from backend.app.config import settings
from backend.app.db import SessionLocal
from backend.app.models import Run
from backend.app.storage import AssetStore

router = APIRouter(tags=["Private images and history"])
GUEST_COOKIE = "vastraview_guest"


def authenticated_owner(user=Depends(current_user)):
    """New try-on jobs require an account; historical assets retain ownership."""
    return user["_id"]


def principal(request: Request, db=Depends(account_db)):
    authorization = request.headers.get("authorization", "")
    if authorization or request.cookies.get(ACCESS_COOKIE):
        return current_user(request, authorization, db)["_id"]
    token = request.cookies.get(GUEST_COOKIE, "")
    if token:
        try:
            claims = jwt.decode(
                token,
                signing_key(),
                algorithms=["HS256"],
                issuer="vastraview",
                audience="private-guest",
                options={"require": ["sub", "exp", "iat"]},
            )
            return claims["sub"]
        except jwt.InvalidTokenError:
            pass
    # Only creation requests may establish a guest. UUID knowledge never grants access.
    if request.method == "POST" and request.url.path in {
        "/api/v1/measurements/extract",
        "/api/v1/measurements/extract-and-recommend",
    }:
        owner = "guest:" + uuid4().hex
        request.state.guest_token = jwt.encode(
            {
                "sub": owner,
                "iss": "vastraview",
                "aud": "private-guest",
                "iat": now(),
                "exp": now() + timedelta(hours=settings.guest_retention_hours),
            },
            signing_key(),
            algorithm="HS256",
        )
        return owner
    raise HTTPException(401, "Sign in or use the browser session that created this result.")


def check_measurement(db, measurement_id, owner):
    if not db.private_resources.find_one({"_id": "measurement:" + measurement_id, "owner": owner}):
        raise HTTPException(404, "Measurement not found in your session.")


def owned_run(db, run_id, owner):
    row = db.get(Run, str(run_id))
    if not row or row.metadata_json.get("owner") != owner:
        raise HTTPException(404, "Result not found in your session.")
    return row


@router.get("/assets/{run_id}/{filename}")
def image(run_id: UUID, filename: str, owner=Depends(principal)):
    # Never expose raw inputs, masks, checkpoints, arbitrary paths or diagnostic logs.
    if filename not in {"tryon-2d.png", "original-person.png", "result.json"}:
        raise HTTPException(404, "Asset not found.")
    with SessionLocal() as db:
        row = owned_run(db, run_id, owner)
        if row.status != "success":
            raise HTTPException(404, "Result has not completed.")
    path = (settings.asset_root / str(run_id) / filename).resolve()
    if not path.is_relative_to(settings.asset_root.resolve()) or not path.is_file():
        raise HTTPException(404, "Asset is no longer available.")
    return FileResponse(path, headers={"Cache-Control": "private, no-store"})


@router.get("/static/annotated/{filename}")
def annotation_image(filename: str, owner=Depends(principal), db=Depends(account_db)):
    if Path(filename).name != filename or not filename.endswith(".png"):
        raise HTTPException(404, "Annotation not found.")
    check_measurement(db, Path(filename).stem, owner)
    root = (settings.measurement_output_root / "annotated").resolve()
    path = (root / filename).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise HTTPException(404, "Annotation not found.")
    return FileResponse(
        path, media_type="image/png", headers={"Cache-Control": "private, no-store"}
    )


@router.get("/api/v1/history")
def history(
    limit: int = Query(12, ge=1, le=48),
    offset: int = Query(0, ge=0, le=10000),
    user=Depends(current_user),
):
    with SessionLocal() as db:
        rows = db.scalars(
            select(Run)
            .where(Run.metadata_json["owner"].as_string() == user["_id"])
            .order_by(Run.created_at.desc(), Run.id)
            .offset(offset)
            .limit(limit + 1)
        ).all()
        return {
            "items": [
                {
                    "id": row.id,
                    "status": row.status,
                    "created_at": row.created_at,
                    "result": row.metadata_json.get("result"),
                }
                for row in rows[:limit]
            ],
            "has_more": len(rows) > limit,
            "offset": offset,
            "limit": limit,
        }


def delete_run_files(db, row):
    if row.status == "processing":
        raise HTTPException(409, "Wait for the current try-on to finish before deleting it.")
    AssetStore(settings.asset_root).delete(row.id)
    # Remove persisted job results pointing to the deleted assets, preserving unrelated jobs.
    from backend.app.main import jobs

    with jobs.lock:
        for path in jobs.directory.glob("*.json"):
            data = jobs._read(path.stem)
            if data.get("result", {}).get("runId") == row.id:
                path.unlink()
    db.delete(row)
    db.commit()


@router.delete("/api/v1/history/{run_id}", status_code=204)
def delete_history(run_id: UUID, user=Depends(current_user)):
    with SessionLocal() as db:
        delete_run_files(db, owned_run(db, run_id, user["_id"]))


def delete_owned_resources(owner, accounts):
    from backend.app.main import jobs

    with jobs.lock:
        for path in jobs.directory.glob("*.json"):
            data = jobs._read(path.stem)
            if data.get("owner") == owner and data["status"] in {"queued", "processing"}:
                raise HTTPException(
                    409, "Wait for your try-on to finish before deleting your account."
                )
        with SessionLocal() as db:
            rows = db.scalars(
                select(Run).where(Run.metadata_json["owner"].as_string() == owner)
            ).all()
            if any(row.status == "processing" for row in rows):
                raise HTTPException(
                    409, "Wait for your try-on to finish before deleting your account."
                )
            for row in rows:
                delete_run_files(db, row)
        for resource in accounts.private_resources.find({"owner": owner, "kind": "measurement"}):
            mid = resource["resource_id"]
            # Artifact deletion does not need to load the MediaPipe checkpoint.
            from backend.app.anthropometry.measurement_service import MeasurementService

            MeasurementService(
                None, settings.measurement_output_root / "annotated"
            ).remove_artifacts(mid)
            accounts.body_measurements.delete_one({"measurement_id": mid})
            accounts.private_resources.delete_one({"_id": resource["_id"]})
        for path in jobs.directory.glob("*.json"):
            if jobs._read(path.stem).get("owner") == owner:
                path.unlink()
