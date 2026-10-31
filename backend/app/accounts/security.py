import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from functools import lru_cache

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import HTTPException, Request
from pymongo import ReturnDocument

from backend.app.config import ROOT, settings

hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
COOKIE = "formfit_refresh"
ACCESS_COOKIE = "vastraview_access"
ACCESS_SECONDS = 900


def now():
    return datetime.now(timezone.utc)


def digest(value: str):
    return hashlib.sha256(value.encode()).hexdigest()


@lru_cache(maxsize=1)
def signing_key():
    if settings.auth_secret:
        if len(settings.auth_secret) < 32:
            raise RuntimeError("AUTH_SECRET must contain at least 32 characters")
        return settings.auth_secret
    # Development only: persistent, generated key outside the public asset tree.
    path = ROOT / ".runtime/auth-signing.key"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="ascii") as stream:
            stream.write(secrets.token_urlsafe(64))
    except FileExistsError:
        pass
    return path.read_text(encoding="ascii")


def verify_password(encoded: str, password: str):
    try:
        return hasher.verify(encoded, password)
    except VerificationError:
        return False


@lru_cache(maxsize=1)
def dummy_hash():
    return hasher.hash(secrets.token_urlsafe(32))


def csrf_guard(request: Request):
    origin = request.headers.get("origin")
    if request.headers.get("sec-fetch-site") == "cross-site" or (
        origin and origin not in {*settings.cors_origins, settings.app_public_url.rstrip("/")}
    ):
        raise HTTPException(403, "This request origin is not allowed.")


def throttle(db, request: Request, action: str, email: str = "", maximum: int = 20):
    # Atomic fixed windows; shared by processes using this MongoDB.
    window = int(now().timestamp()) // 900
    ip = request.client.host if request.client else "unknown"
    for subject, ceiling in (
        (f"{ip}:{action}", maximum * 3),
        (f"{ip}:{email.lower()}:{action}", maximum),
    ):
        row = db.auth_limits.find_one_and_update(
            {"_id": digest(f"{subject}:{window}")},
            {"$inc": {"count": 1}, "$setOnInsert": {"expires_at": now() + timedelta(minutes=30)}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        if row["count"] > ceiling:
            raise HTTPException(429, "Too many attempts. Please try again in 15 minutes.")


def access_token(user_id: str, session_id: str):
    issued = now()
    return jwt.encode(
        {
            "sub": user_id,
            "sid": session_id,
            "iat": issued,
            "exp": issued + timedelta(seconds=ACCESS_SECONDS),
            "iss": "formfit-studio",
            "aud": "formfit-web",
        },
        signing_key(),
        algorithm="HS256",
    )


def read_token(token: str):
    try:
        return jwt.decode(
            token,
            signing_key(),
            algorithms=["HS256"],
            issuer="formfit-studio",
            audience="formfit-web",
            options={"require": ["sub", "sid", "iat", "exp"]},
        )
    except jwt.InvalidTokenError as exc:
        raise HTTPException(401, "Your session has expired. Please sign in again.") from exc


def require_admin(x_admin_token: str = ""):
    if not settings.admin_token or not secrets.compare_digest(settings.admin_token, x_admin_token):
        raise HTTPException(403, "Administrative access is not configured or not authorized.")
