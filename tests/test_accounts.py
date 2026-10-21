import base64
import io
from datetime import timedelta
from uuid import uuid4

import mongomock
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.app.accounts import router as account_module
from backend.app.accounts.security import COOKIE, digest, now
from backend.app.anthropometry.repository import MeasurementRepository, get_repository
from backend.app.config import settings
from backend.app.main import app

PASSWORD = "Studio!Measurements82"


@pytest.fixture
def accounts(monkeypatch):
    repo = MeasurementRepository(mongomock.MongoClient(tz_aware=True), "account_tests")
    repo.db.command = lambda *a, **kw: {"ok": 1}
    repo.initialize()
    app.dependency_overrides[get_repository] = lambda: repo
    monkeypatch.setattr(settings, "auth_secret", "test-only-signing-key-" * 4)
    monkeypatch.setattr(settings, "smtp_host", "")
    from backend.app.accounts.security import signing_key

    signing_key.cache_clear()
    client = TestClient(app)
    try:
        yield client, repo
    finally:
        client.close()
        repo.close()
        app.dependency_overrides.clear()
        signing_key.cache_clear()


def signup(client, email="owner@example.com"):
    response = client.post(
        "/api/v1/auth/signup",
        json={
            "name": "Studio Owner",
            "email": email,
            "password": PASSWORD,
            "terms_accepted": True,
        },
    )
    assert response.status_code == 201, response.text
    return response


def auth(response):
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def test_signup_real_hash_cookie_profile_and_logout(accounts):
    client, repo = accounts
    response = signup(client)
    user = repo.db.users.find_one({"email": "owner@example.com"})
    assert user["password_hash"].startswith("$argon2id$") and PASSWORD not in user["password_hash"]
    assert "password_hash" not in response.text
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=strict" in cookie and "Max-Age" not in cookie
    assert response.headers["cache-control"] == "no-store"
    profile = client.get("/api/v1/profile", headers=auth(response))
    assert profile.status_code == 200 and profile.json()["email"] == "owner@example.com"
    updated = client.patch(
        "/api/v1/profile", headers=auth(response), json={"name": "New Name", "height_cm": 172.5}
    )
    assert updated.status_code == 200 and updated.json()["height_cm"] == 172.5
    assert client.post("/api/v1/auth/logout").status_code == 204
    assert client.get("/api/v1/profile", headers=auth(response)).status_code == 401
    assert client.post("/api/v1/auth/refresh").status_code == 401


def test_refresh_rotation_replay_revokes_session(accounts):
    client, repo = accounts
    response = signup(client)
    original = client.cookies.get(COOKIE)
    refreshed = client.post("/api/v1/auth/refresh")
    assert refreshed.status_code == 200
    assert client.cookies.get(COOKIE) != original
    assert client.get("/api/v1/profile", headers=auth(refreshed)).status_code == 200
    assert not repo.db.auth_sessions.find_one({"refresh_hash": digest(original)})
    attacker = TestClient(app)
    attacker.cookies.set(COOKIE, original, path="/api/v1/auth")
    try:
        assert attacker.post("/api/v1/auth/refresh").status_code == 401
    finally:
        attacker.close()
    assert client.get("/api/v1/profile", headers=auth(response)).status_code == 401
    assert client.post("/api/v1/auth/refresh").status_code == 401


def test_bad_credentials_duplicate_and_remember_me(accounts):
    client, _ = accounts
    signup(client)
    assert (
        client.post(
            "/api/v1/auth/signup",
            json={
                "name": "Owner",
                "email": "owner@example.com",
                "password": PASSWORD,
                "terms_accepted": True,
            },
        ).status_code
        == 409
    )
    for email, password in (("owner@example.com", "wrong"), ("nobody@example.com", PASSWORD)):
        response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
        assert (
            response.status_code == 401
            and response.json()["detail"] == "Email or password is incorrect."
        )
    good = client.post(
        "/api/v1/auth/login",
        json={"email": "OWNER@example.com", "password": PASSWORD, "remember": True},
    )
    assert good.status_code == 200 and "Max-Age=" in good.headers["set-cookie"]


@pytest.mark.parametrize(
    "change", [{"password": "weak"}, {"terms_accepted": False}, {"email": "bad"}, {"name": " "}]
)
def test_signup_validation(accounts, change):
    client, _ = accounts
    response = client.post(
        "/api/v1/auth/signup",
        json={
            "name": "Owner",
            "email": "owner@example.com",
            "password": PASSWORD,
            "terms_accepted": True,
            **change,
        },
    )
    assert response.status_code == 422


def test_csrf_origin_and_throttling(accounts):
    client, _ = accounts
    response = client.post(
        "/api/v1/auth/login",
        headers={"Origin": "https://untrusted.example"},
        json={"email": "owner@example.com", "password": PASSWORD},
    )
    assert response.status_code == 403
    for _ in range(12):
        assert (
            client.post(
                "/api/v1/auth/login", json={"email": "owner@example.com", "password": PASSWORD}
            ).status_code
            == 401
        )
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": "owner@example.com", "password": PASSWORD}
        ).status_code
        == 429
    )


def thumbnail_bytes():
    stream = io.BytesIO()
    Image.new("RGB", (32, 48), "green").save(stream, format="PNG")
    return base64.b64encode(stream.getvalue()).decode()


MEASUREMENTS = {
    "shoulder_width": 44,
    "chest_circumference": 94,
    "waist_circumference": 82,
    "hip_circumference": 96,
    "thigh_circumference": 54,
    "inseam_length": 78,
}


def test_private_scans_and_sizes_cannot_be_read_or_deleted_by_other_account(accounts):
    client, _ = accounts
    owner = signup(client)
    saved = client.post(
        "/api/v1/profile/scans",
        headers=auth(owner),
        json={
            "height_cm": 172,
            "measurements": MEASUREMENTS,
            "source": "manual",
            "thumbnail_base64": thumbnail_bytes(),
        },
    )
    assert saved.status_code == 201
    scan_id = saved.json()["id"]
    png = f"/api/v1/profile/scans/{scan_id}/thumbnail"
    assert client.get(png).status_code == 401
    assert client.get(png, headers=auth(owner)).headers["content-type"] == "image/jpeg"
    payload = {"brand_id": "nike", "apparel_id": "nike-in-hv4188-013", "measurements": MEASUREMENTS}
    size = client.post("/api/v1/profile/sizes", headers=auth(owner), json=payload)
    assert size.status_code == 201
    assert size.json()["result"]["recommended_size"] == "M"
    again = client.post("/api/v1/profile/sizes", headers=auth(owner), json=payload)
    assert again.json()["id"] == size.json()["id"]
    other = signup(client, "other@example.com")
    assert client.get("/api/v1/profile/scans", headers=auth(other)).json()["items"] == []
    assert client.get("/api/v1/profile/sizes", headers=auth(other)).json() == []
    assert client.get(png, headers=auth(other)).status_code == 404
    assert client.delete(f"/api/v1/profile/scans/{scan_id}", headers=auth(other)).status_code == 404
    assert (
        client.delete(f"/api/v1/profile/sizes/{size.json()['id']}", headers=auth(other)).status_code
        == 404
    )
    assert client.delete(f"/api/v1/profile/scans/{scan_id}", headers=auth(owner)).status_code == 204
    assert client.get(png, headers=auth(owner)).status_code == 404
    assert (
        client.delete(f"/api/v1/profile/sizes/{size.json()['id']}", headers=auth(owner)).status_code
        == 204
    )


def test_missing_mail_service_is_honest_and_reset_is_single_use(accounts):
    client, repo = accounts
    response = signup(client)
    unavailable = client.post("/api/v1/auth/forgot-password", json={"email": "owner@example.com"})
    assert unavailable.status_code == 503 and "not configured" in unavailable.text
    raw = uuid4().hex + uuid4().hex
    repo.db.password_resets.insert_one(
        {
            "_id": digest(raw),
            "user_id": response.json()["user"]["id"],
            "expires_at": now() + timedelta(minutes=20),
        }
    )
    reset = client.post(
        "/api/v1/auth/reset-password", json={"token": raw, "password": "New!StudioPassword22"}
    )
    assert reset.status_code == 200
    assert client.get("/api/v1/profile", headers=auth(response)).status_code == 401
    assert (
        client.post(
            "/api/v1/auth/reset-password", json={"token": raw, "password": PASSWORD}
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": "owner@example.com", "password": "New!StudioPassword22"},
        ).status_code
        == 200
    )


def test_expired_reset_and_access_token_are_rejected(accounts):
    import jwt

    from backend.app.accounts.security import signing_key

    client, repo = accounts
    user = signup(client).json()["user"]["id"]
    raw = uuid4().hex
    repo.db.password_resets.insert_one(
        {"_id": digest(raw), "user_id": user, "expires_at": now() - timedelta(seconds=1)}
    )
    assert (
        client.post(
            "/api/v1/auth/reset-password", json={"token": raw, "password": PASSWORD}
        ).status_code
        == 400
    )
    token = jwt.encode(
        {
            "sub": user,
            "sid": "unknown",
            "iat": now() - timedelta(hours=1),
            "exp": now() - timedelta(minutes=1),
            "iss": "formfit-studio",
            "aud": "formfit-web",
        },
        signing_key(),
        algorithm="HS256",
    )
    assert (
        client.get("/api/v1/profile", headers={"Authorization": "Bearer " + token}).status_code
        == 401
    )


def test_password_email_delivery_uses_expiring_fragment_token(accounts, monkeypatch):
    client, repo = accounts
    signup(client)
    monkeypatch.setattr(settings, "smtp_host", "mail.example.com")
    monkeypatch.setattr(settings, "smtp_from", "studio@example.com")
    sent = []

    class SMTP:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def starttls(self, **kwargs):
            pass

        def send_message(self, message):
            sent.append(message)

    monkeypatch.setattr(account_module.smtplib, "SMTP", SMTP)
    response = client.post("/api/v1/auth/forgot-password", json={"email": "owner@example.com"})
    assert response.status_code == 200 and "token" not in response.text
    assert len(sent) == 1 and "/reset-password#token=" in sent[0].get_content()
    assert repo.db.password_resets.count_documents({}) == 1
    unknown = client.post("/api/v1/auth/forgot-password", json={"email": "unknown@example.com"})
    assert unknown.json() == response.json() and len(sent) == 1
