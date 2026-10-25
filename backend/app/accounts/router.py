import base64
import io
import secrets
import smtplib
import ssl
from datetime import timedelta
from email.message import EmailMessage
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from PIL import Image, UnidentifiedImageError
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from backend.app.accounts.schemas import (
    ForgotPassword,
    Login,
    ProfileUpdate,
    ResetPassword,
    SaveScan,
    Signup,
)
from backend.app.accounts.security import (
    ACCESS_COOKIE,
    ACCESS_SECONDS,
    COOKIE,
    access_token,
    csrf_guard,
    digest,
    dummy_hash,
    hasher,
    now,
    read_token,
    throttle,
    verify_password,
)
from backend.app.anthropometry.repository import get_repository
from backend.app.anthropometry.schemas import SizingRequest
from backend.app.anthropometry.sizing_engine import recommend
from backend.app.config import settings

router = APIRouter(prefix="/api/v1", tags=["Accounts and private profile"])


def account_db(repo=Depends(get_repository)):
    db = repo.db
    if db.account_schema.find_one({"_id": 2}):
        return db
    db.users.create_index("email", unique=True)
    db.auth_sessions.create_index("expires_at", expireAfterSeconds=0)
    db.auth_sessions.create_index("refresh_hash", unique=True)
    db.auth_limits.create_index("expires_at", expireAfterSeconds=0)
    db.password_resets.create_index("expires_at", expireAfterSeconds=0)
    db.saved_scans.create_index([("user_id", 1), ("created_at", -1)])
    db.saved_sizes.create_index([("user_id", 1), ("brand_id", 1), ("apparel_id", 1)], unique=True)
    db.email_verifications.create_index("expires_at", expireAfterSeconds=0)
    db.auth_sessions.create_index("user_id")
    db.auth_sessions.create_index("used_hashes")
    db.private_resources.create_index([("owner", 1), ("kind", 1)])
    db.private_resources.create_index("created_at")
    db.audit_events.create_index("expires_at", expireAfterSeconds=0)
    db.account_schema.update_one({"_id": 2}, {"$set": {"installed_at": now()}}, upsert=True)
    return db


def public_user(user):
    return {
        "id": user["_id"],
        "name": user["name"],
        "email": user["email"],
        "height_cm": user.get("height_cm"),
        "created_at": user["created_at"],
        "email_verified": user.get("email_verified", False),
        "measurement_unit": user.get("measurement_unit", "cm"),
    }


def current_user(request: Request, authorization: str = Header(default=""), db=Depends(account_db)):
    token = (
        authorization[7:]
        if authorization.startswith("Bearer ")
        else request.cookies.get(ACCESS_COOKIE)
    )
    if not token:
        raise HTTPException(401, "Sign in to access your saved results.")
    claims = read_token(token)
    session = db.auth_sessions.find_one(
        {
            "_id": claims["sid"],
            "user_id": claims["sub"],
            "revoked": False,
            "expires_at": {"$gt": now()},
        }
    )
    user = db.users.find_one({"_id": claims["sub"]})
    if not session or not user or user.get("deleting"):
        raise HTTPException(401, "Your session has ended. Please sign in again.")
    return user


def set_access_cookie(response, token):
    response.set_cookie(
        ACCESS_COOKIE,
        token,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="strict",
        path="/",
        max_age=ACCESS_SECONDS,
    )


def set_cookie(response: Response, raw: str, remember: bool, expires):
    response.set_cookie(
        COOKIE,
        raw,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="strict",
        path="/api/v1/auth",
        max_age=max(0, int((expires - now()).total_seconds())) if remember else None,
    )
    response.headers["Cache-Control"] = "no-store"


def session_response(response, db, user, remember=False):
    sid, raw = uuid4().hex, secrets.token_urlsafe(48)
    expires = now() + timedelta(days=30 if remember else 1)
    db.auth_sessions.insert_one(
        {
            "_id": sid,
            "user_id": user["_id"],
            "refresh_hash": digest(raw),
            "used_hashes": [],
            "expires_at": expires,
            "revoked": False,
            "remember": remember,
            "created_at": now(),
        }
    )
    set_cookie(response, raw, remember, expires)
    token = access_token(user["_id"], sid)
    set_access_cookie(response, token)
    return {
        "access_token": token,
        "expires_in": ACCESS_SECONDS,
        "user": public_user(user),
    }


@router.post("/auth/signup", status_code=201, dependencies=[Depends(csrf_guard)])
def signup(data: Signup, request: Request, response: Response, db=Depends(account_db)):
    throttle(db, request, "signup", str(data.email), maximum=5)
    if len(data.name.strip()) < 2:
        raise HTTPException(422, "Enter your name.")
    user = {
        "_id": uuid4().hex,
        "email": str(data.email).lower(),
        "name": data.name.strip(),
        "password_hash": hasher.hash(data.password),
        "created_at": now(),
        "height_cm": None,
        "email_verified": False,
        "terms_version": "2026-10-21",
        "terms_accepted_at": now(),
    }
    if settings.auth_require_verification:
        from backend.app.accounts.lifecycle import send_verification

        # Same response for existing accounts; never reveal registration state.
        existing = db.users.find_one({"email": user["email"]})
        if not existing:
            try:
                db.users.insert_one(user)
            except DuplicateKeyError:
                pass
            else:
                send_verification(db, user)
        return {
            "message": "Check your email to verify your account. If you already registered, sign in or request a new verification link.",
            "verification_required": True,
        }
    if len(user["name"]) < 2:
        raise HTTPException(422, "Enter your name.")
    try:
        db.users.insert_one(user)
    except DuplicateKeyError as exc:
        raise HTTPException(
            409, "An account already exists. Sign in or reset your password."
        ) from exc
    return session_response(response, db, user)


@router.post("/auth/login", dependencies=[Depends(csrf_guard)])
def login(data: Login, request: Request, response: Response, db=Depends(account_db)):
    throttle(db, request, "login", str(data.email))
    user = db.users.find_one({"email": str(data.email).lower()})
    valid = verify_password(user["password_hash"] if user else dummy_hash(), data.password)
    if not user or not valid:
        raise HTTPException(401, "Email or password is incorrect.")
    if user.get("deleting"):
        raise HTTPException(401, "Account is unavailable.")
    if settings.auth_require_verification and not user.get("email_verified"):
        raise HTTPException(
            403, "Verify your email before signing in. Request a new verification link if needed."
        )
    if hasher.check_needs_rehash(user["password_hash"]):
        db.users.update_one(
            {"_id": user["_id"]}, {"$set": {"password_hash": hasher.hash(data.password)}}
        )
    return session_response(response, db, user, data.remember)


@router.post("/auth/refresh", dependencies=[Depends(csrf_guard)])
def refresh(request: Request, response: Response, db=Depends(account_db)):
    raw = request.cookies.get(COOKIE, "")
    if not raw:
        raise HTTPException(401, "No saved session.")
    old_hash, next_raw = digest(raw), secrets.token_urlsafe(48)
    session = db.auth_sessions.find_one_and_update(
        {"refresh_hash": old_hash, "revoked": False, "expires_at": {"$gt": now()}},
        {"$set": {"refresh_hash": digest(next_raw)}, "$push": {"used_hashes": old_hash}},
        return_document=ReturnDocument.AFTER,
    )
    if not session:
        db.auth_sessions.update_many({"used_hashes": old_hash}, {"$set": {"revoked": True}})
        raise HTTPException(401, "Your saved session has expired. Please sign in again.")
    user = db.users.find_one({"_id": session["user_id"]})
    if (
        not user
        or user.get("deleting")
        or (settings.auth_require_verification and not user.get("email_verified"))
    ):
        raise HTTPException(401, "Account unavailable.")
    set_cookie(response, next_raw, session["remember"], session["expires_at"])
    token = access_token(user["_id"], session["_id"])
    set_access_cookie(response, token)
    return {
        "access_token": token,
        "expires_in": ACCESS_SECONDS,
        "user": public_user(user),
    }


@router.post("/auth/logout", status_code=204, dependencies=[Depends(csrf_guard)])
def logout(request: Request, response: Response, db=Depends(account_db)):
    response.delete_cookie(
        ACCESS_COOKIE,
        path="/",
        secure=settings.auth_cookie_secure,
        httponly=True,
        samesite="strict",
    )
    raw = request.cookies.get(COOKIE)
    access = request.headers.get("authorization", "").removeprefix(
        "Bearer "
    ) or request.cookies.get(ACCESS_COOKIE)
    if access:
        try:
            claims = read_token(access)
            db.auth_sessions.update_one(
                {"_id": claims["sid"], "user_id": claims["sub"]}, {"$set": {"revoked": True}}
            )
        except HTTPException:
            pass  # Logout is idempotent even after an expired access token.
    if raw:
        db.auth_sessions.update_many(
            {"$or": [{"refresh_hash": digest(raw)}, {"used_hashes": digest(raw)}]},
            {"$set": {"revoked": True}},
        )
    response.delete_cookie(
        COOKIE,
        path="/api/v1/auth",
        secure=settings.auth_cookie_secure,
        httponly=True,
        samesite="strict",
    )


@router.post("/auth/forgot-password", dependencies=[Depends(csrf_guard)])
def forgot_password(data: ForgotPassword, request: Request, db=Depends(account_db)):
    throttle(db, request, "reset", str(data.email), maximum=3)
    if not settings.smtp_host or not settings.smtp_from:
        raise HTTPException(
            503, "Password reset email is not configured. Contact the studio administrator."
        )
    user = db.users.find_one({"email": str(data.email).lower()})
    if user:
        raw = secrets.token_urlsafe(48)
        db.password_resets.insert_one(
            {
                "_id": digest(raw),
                "user_id": user["_id"],
                "expires_at": now() + timedelta(minutes=20),
            }
        )
        email = EmailMessage()
        email["From"], email["To"], email["Subject"] = (
            settings.smtp_from,
            user["email"],
            "Reset your VastraView password",
        )
        email.set_content(
            f"Reset your password within 20 minutes:\n{settings.app_public_url.rstrip('/')}/reset-password#token={raw}\n\nIf you did not request this, ignore this email."
        )
        try:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
                smtp.starttls(context=ssl.create_default_context())
                if settings.smtp_user:
                    smtp.login(settings.smtp_user, settings.smtp_password)
                smtp.send_message(email)
        except (OSError, smtplib.SMTPException) as exc:
            db.password_resets.delete_one({"_id": digest(raw)})
            raise HTTPException(
                503, "Password reset email could not be sent. Please retry later."
            ) from exc
    return {"message": "If this email has an account, a reset link will arrive shortly."}


@router.post("/auth/reset-password", dependencies=[Depends(csrf_guard)])
def reset_password(data: ResetPassword, request: Request, db=Depends(account_db)):
    throttle(db, request, "reset-confirm", maximum=8)
    encoded = hasher.hash(data.password)
    token = db.password_resets.find_one_and_delete(
        {"_id": digest(data.token), "expires_at": {"$gt": now()}}
    )
    if not token:
        raise HTTPException(400, "This reset link has expired or was already used.")
    db.users.update_one({"_id": token["user_id"]}, {"$set": {"password_hash": encoded}})
    db.auth_sessions.update_many({"user_id": token["user_id"]}, {"$set": {"revoked": True}})
    db.password_resets.delete_many({"user_id": token["user_id"]})
    return {"message": "Password changed. Sign in with your new password."}


@router.get("/profile")
def profile(user=Depends(current_user)):
    return public_user(user)


@router.patch("/profile")
def update_profile(data: ProfileUpdate, user=Depends(current_user), db=Depends(account_db)):
    if len(data.name.strip()) < 2:
        raise HTTPException(422, "Enter your name.")
    db.users.update_one(
        {"_id": user["_id"]}, {"$set": {**data.model_dump(), "name": data.name.strip()}}
    )
    return public_user(db.users.find_one({"_id": user["_id"]}))


def scan_public(row):
    return {
        **{k: v for k, v in row.items() if k not in {"_id", "user_id", "thumbnail"}},
        "id": row["_id"],
        "has_thumbnail": bool(row.get("thumbnail")),
        "thumbnail_url": f"/api/v1/profile/scans/{row['_id']}/thumbnail"
        if row.get("thumbnail")
        else None,
    }


@router.post("/profile/scans", status_code=201)
def save_scan(data: SaveScan, user=Depends(current_user), db=Depends(account_db)):
    thumbnail = None
    if data.thumbnail_base64:
        try:
            binary = base64.b64decode(data.thumbnail_base64, validate=True)
            with Image.open(io.BytesIO(binary)) as image:
                if image.width * image.height > 512 * 768 or image.format not in {"JPEG", "PNG"}:
                    raise ValueError("thumbnail size or format")
                buffer = io.BytesIO()
                image.convert("RGB").save(buffer, format="JPEG", quality=85)
                thumbnail = buffer.getvalue()
        except (ValueError, OSError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
            raise HTTPException(
                422, "Invalid thumbnail. Use a JPEG or PNG below 512 × 768 pixels."
            ) from exc
    row = {
        **data.model_dump(exclude={"thumbnail_base64"}),
        "_id": str(uuid4()),
        "user_id": user["_id"],
        "created_at": now(),
        "consented_at": now(),
        "consent_method": "explicit-save-action",
        "thumbnail": thumbnail,
    }
    db.saved_scans.insert_one(row)
    return scan_public(row)


@router.get("/profile/scans")
def scans(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user=Depends(current_user),
    db=Depends(account_db),
):
    query = {"user_id": user["_id"]}
    return {
        "items": [
            scan_public(row)
            for row in db.saved_scans.find(query).sort("created_at", -1).skip(offset).limit(limit)
        ],
        "total": db.saved_scans.count_documents(query),
        "limit": limit,
        "offset": offset,
    }


@router.get("/profile/scans/{scan_id}/thumbnail")
def thumbnail(scan_id: UUID, user=Depends(current_user), db=Depends(account_db)):
    row = db.saved_scans.find_one({"_id": str(scan_id), "user_id": user["_id"]})
    if not row or not row.get("thumbnail"):
        raise HTTPException(404, "Thumbnail not found.")
    return Response(
        row["thumbnail"], media_type="image/jpeg", headers={"Cache-Control": "private, no-store"}
    )


@router.delete("/profile/scans/{scan_id}", status_code=204)
def delete_scan(scan_id: UUID, user=Depends(current_user), db=Depends(account_db)):
    if not db.saved_scans.delete_one({"_id": str(scan_id), "user_id": user["_id"]}).deleted_count:
        raise HTTPException(404, "Saved scan not found.")


@router.post("/profile/sizes", status_code=201)
def save_size(
    data: SizingRequest,
    user=Depends(current_user),
    db=Depends(account_db),
    repo=Depends(get_repository),
):
    if data.measurements is None:
        raise HTTPException(422, "Supply your measurements to save a recommendation.")
    chart = repo.get_chart(data.brand_id, data.apparel_id, data.chart_version)
    result = recommend(data.measurements, chart)
    row = {"brand_id": data.brand_id, "apparel_id": data.apparel_id, "user_id": user["_id"]}
    saved = db.saved_sizes.find_one_and_update(
        row,
        {
            "$set": {"result": result.model_dump(mode="json"), "updated_at": now()},
            "$setOnInsert": {"_id": str(uuid4())},
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return {"id": saved["_id"], "result": saved["result"], "updated_at": saved["updated_at"]}


@router.get("/profile/sizes")
def saved_sizes(user=Depends(current_user), db=Depends(account_db)):
    return [
        {"id": row["_id"], "result": row["result"], "updated_at": row["updated_at"]}
        for row in db.saved_sizes.find({"user_id": user["_id"]}).sort("updated_at", -1).limit(100)
    ]


@router.delete("/profile/sizes/{size_id}", status_code=204)
def delete_size(size_id: UUID, user=Depends(current_user), db=Depends(account_db)):
    if not db.saved_sizes.delete_one({"_id": str(size_id), "user_id": user["_id"]}).deleted_count:
        raise HTTPException(404, "Saved size not found.")
