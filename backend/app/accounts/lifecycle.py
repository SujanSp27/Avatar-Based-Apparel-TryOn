"""Email verification, session control and retryable account deletion."""

import secrets
import smtplib
import ssl
from datetime import timedelta
from email.message import EmailMessage

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from backend.app.accounts.router import account_db, current_user
from backend.app.accounts.schemas import ForgotPassword
from backend.app.accounts.security import (
    ACCESS_COOKIE,
    COOKIE,
    csrf_guard,
    digest,
    now,
    read_token,
    throttle,
    verify_password,
)
from backend.app.config import settings

router = APIRouter(prefix="/api/v1", tags=["Account lifecycle"])


def audit(db, event, user_id):
    db.audit_events.insert_one(
        {
            "event": event,
            "user_id": user_id,
            "created_at": now(),
            "expires_at": now() + timedelta(days=90),
        }
    )


def send_verification(db, user):
    if not settings.smtp_host or not settings.smtp_from:
        raise HTTPException(503, "Email delivery is not configured. Contact the administrator.")
    raw = secrets.token_urlsafe(48)
    db.email_verifications.insert_one(
        {"_id": digest(raw), "user_id": user["_id"], "expires_at": now() + timedelta(hours=1)}
    )
    email = EmailMessage()
    email["From"], email["To"], email["Subject"] = (
        settings.smtp_from,
        user["email"],
        "Verify your VastraView email",
    )
    email.set_content(
        f"Verify your email within one hour:\n{settings.app_public_url.rstrip('/')}/verify-email#token={raw}\n\nIgnore this if you did not register."
    )
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(email)
    except (OSError, smtplib.SMTPException) as exc:
        db.email_verifications.delete_one({"_id": digest(raw)})
        raise HTTPException(503, "Email could not be sent. Request a new link later.") from exc


class Verification(BaseModel):
    token: str = Field(min_length=32, max_length=128)


@router.post("/auth/request-verification", dependencies=[Depends(csrf_guard)])
def request_verification(data: ForgotPassword, request: Request, db=Depends(account_db)):
    throttle(db, request, "verify", str(data.email), maximum=3)
    if not settings.smtp_host or not settings.smtp_from:
        raise HTTPException(503, "Email delivery is not configured. Contact the administrator.")
    user = db.users.find_one({"email": str(data.email).lower(), "deleting": {"$ne": True}})
    if user and not user.get("email_verified"):
        send_verification(db, user)
    return {"message": "If this account needs verification, an email will arrive shortly."}


@router.post("/auth/verify-email", dependencies=[Depends(csrf_guard)])
def verify_email(data: Verification, request: Request, db=Depends(account_db)):
    throttle(db, request, "verify-confirm", maximum=8)
    token = db.email_verifications.find_one_and_delete(
        {"_id": digest(data.token), "expires_at": {"$gt": now()}}
    )
    if not token:
        raise HTTPException(400, "Verification link expired or already used.")
    db.users.update_one({"_id": token["user_id"]}, {"$set": {"email_verified": True}})
    db.email_verifications.delete_many({"user_id": token["user_id"]})
    audit(db, "email_verified", token["user_id"])
    return {"message": "Email verified. You can sign in."}


@router.get("/profile/sessions")
def sessions(request: Request, user=Depends(current_user), db=Depends(account_db)):
    raw = request.headers.get("authorization", "").removeprefix("Bearer ") or request.cookies.get(
        ACCESS_COOKIE, ""
    )
    sid = read_token(raw)["sid"]
    return [
        {
            "id": s["_id"],
            "created_at": s.get("created_at"),
            "expires_at": s["expires_at"],
            "current": s["_id"] == sid,
        }
        for s in db.auth_sessions.find(
            {"user_id": user["_id"], "revoked": False, "expires_at": {"$gt": now()}}
        ).limit(100)
    ]


@router.delete("/profile/sessions/{session_id}", status_code=204)
def revoke_session(session_id: str, user=Depends(current_user), db=Depends(account_db)):
    db.auth_sessions.update_one(
        {"_id": session_id, "user_id": user["_id"]}, {"$set": {"revoked": True}}
    )
    audit(db, "session_revoked", user["_id"])


class DeleteAccount(BaseModel):
    password: str = Field(min_length=1, max_length=128)


@router.delete("/profile", status_code=204)
def delete_account(
    data: DeleteAccount,
    request: Request,
    response: Response,
    user=Depends(current_user),
    db=Depends(account_db),
):
    throttle(db, request, "delete-account", user["_id"], maximum=5)
    if not verify_password(user["password_hash"], data.password):
        raise HTTPException(403, "Password is incorrect.")
    # Refuse while work is active. Keep the account if cleanup fails so it can be retried.
    from pymongo import ReturnDocument

    from backend.app.private_data import delete_owned_resources

    marked = db.users.find_one_and_update(
        {"_id": user["_id"], "deleting": {"$ne": True}},
        {"$set": {"deleting": True}},
        return_document=ReturnDocument.AFTER,
    )
    if not marked:
        raise HTTPException(409, "Account deletion is already in progress.")
    try:
        delete_owned_resources(user["_id"], db)
        for name in ("saved_scans", "saved_sizes", "favorites", "password_resets", "email_verifications"):
            db[name].delete_many({"user_id": user["_id"]})
        # Keep the user/session until content cleanup completes, making failures
        # retryable. Once the user is removed all remaining tokens fail closed.
        db.users.delete_one({"_id": user["_id"]})
        db.auth_sessions.delete_many({"user_id": user["_id"]})
        audit(db, "account_deleted", user["_id"])
    except Exception:
        db.users.update_one({"_id": user["_id"]}, {"$set": {"deleting": False}})
        raise
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(COOKIE, path="/api/v1/auth")
