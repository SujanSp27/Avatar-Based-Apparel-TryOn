"""Security and catalog integration tests; no external GPU or email deliveries."""

import io
from datetime import timedelta
from threading import BoundedSemaphore
from uuid import uuid4

import jwt
import mongomock
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app import main, private_data
from backend.app.accounts import lifecycle
from backend.app.accounts.security import ACCESS_COOKIE, digest, now, signing_key
from backend.app.anthropometry.repository import MeasurementRepository, get_repository
from backend.app.config import settings
from backend.app.db import Base, get_db
from backend.app.jobs import TryOnJobs
from backend.app.models import Run
from backend.app.storage import AssetStore

PASSWORD = "Vastra!Secure2026"


@pytest.fixture
def studio(tmp_path, monkeypatch):
    repo = MeasurementRepository(mongomock.MongoClient(tz_aware=True), "vastra_test")
    repo.db.command = lambda *a, **kw: {"ok": 1}
    repo.initialize()
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)

    def session():
        with factory() as db:
            yield db

    main.app.dependency_overrides[get_repository] = lambda: repo
    main.app.dependency_overrides[get_db] = session
    monkeypatch.setattr(main, "SessionLocal", factory)
    monkeypatch.setattr(private_data, "SessionLocal", factory)
    monkeypatch.setattr(settings, "asset_root", tmp_path / "results")
    monkeypatch.setattr(settings, "auth_secret", "isolated-test-signing-key" * 3)
    monkeypatch.setattr(settings, "auth_require_verification", False)
    monkeypatch.setattr(settings, "environment", "test")
    monkeypatch.setattr(settings, "admin_token", "")
    signing_key.cache_clear()
    store = AssetStore(settings.asset_root)
    jobs = TryOnJobs(tmp_path / "jobs", BoundedSemaphore(1))
    monkeypatch.setattr(main, "jobs", jobs)
    monkeypatch.setattr(main, "store", store)
    clients = [TestClient(main.app) for _ in range(3)]
    yield clients, repo.db, factory, store, jobs
    for c in clients:
        c.close()
    jobs.close()
    main.app.dependency_overrides.clear()
    signing_key.cache_clear()
    repo.close()
    engine.dispose()


def register(client, email="owner@example.com"):
    return client.post(
        "/api/v1/auth/signup",
        json={"name": "Vastra Owner", "email": email, "password": PASSWORD, "terms_accepted": True},
    )


def test_catalog_filters_actual_assets_and_idempotent_favorites(studio):
    (owner, stranger, _), db, *_ = studio
    assert register(owner).status_code == 201
    brands = owner.get("/api/v1/brands").json()
    assert len(brands) == 28 and all(not b["partnership"] for b in brands)
    page = owner.get("/api/v1/products?q=navy&sort=relevance&limit=2").json()
    assert len(page["items"]) == 2 and all("navy" in p["name"].lower() for p in page["items"])
    item = page["items"][0]
    assert owner.get(item["imageUrl"]).headers["content-type"].startswith("image/")
    assert owner.get("/api/v1/products?brand_id=nike").json()["total"] == 0
    sarees = owner.get("/api/v1/products?subcategory=saree").json()
    assert sarees["total"] == 1 and not sarees["items"][0]["tryon_supported"]
    assert owner.get("/api/v1/products?limit=1000").status_code == 422
    path = "/api/v1/favorites/" + item["id"]
    assert stranger.put(path).status_code == 401
    assert owner.put(path).status_code == owner.put(path).status_code == 204
    register(stranger, "other@example.com")
    assert stranger.get("/api/v1/favorites").json()["items"] == []
    assert stranger.delete(path).status_code == 204
    assert owner.get("/api/v1/favorites").json()["total"] == 1
    assert db.favorites.count_documents({}) == 1
    assert owner.delete(path).status_code == 204


def test_production_hides_unlicensed_catalog(studio, monkeypatch):
    client = studio[0][0]
    assert client.get("/api/v1/products").json()["total"] > 0
    monkeypatch.setattr(settings, "environment", "production")
    published = client.get("/api/v1/products").json()
    assert published["total"] == 51 and all(p["commercial_use"] for p in published["items"])
    assert client.get("/api/v1/products/navy-tee/image").status_code == 404


def test_private_images_job_metadata_and_history_cannot_cross_accounts(studio):
    (owner, other, anonymous), _, factory, store, jobs = studio
    uid = register(owner).json()["user"]["id"]
    register(other, "other@example.com")
    rid = str(uuid4())
    folder = store.create(rid)
    Image.new("RGB", (64, 64), "navy").save(folder / "tryon-2d.png")
    result = {"runId": rid, "previewUrl": f"/assets/{rid}/tryon-2d.png"}
    with factory() as db:
        db.add(Run(id=rid, status="success", metadata_json={"owner": uid, "result": result}))
        db.commit()
    jid = str(uuid4())
    jobs._save(
        {
            "jobId": jid,
            "status": "success",
            "createdAt": 1,
            "requestHash": "secret-hash",
            "owner": uid,
            "result": result,
        }
    )
    for path in (result["previewUrl"], f"/api/runs/{rid}", f"/api/tryon/jobs/{jid}"):
        response = owner.get(path)
        assert response.status_code == 200, response.text
        assert "no-store" in response.headers["cache-control"]
        assert anonymous.get(path).status_code == 401
        assert other.get(path).status_code == 404
    assert owner.get(f"/assets/{rid}/personInput.bin").status_code == 404
    (folder / "garment-reference.png").write_bytes((folder / "tryon-2d.png").read_bytes())
    reference_url = f"/assets/{rid}/garment-reference.png"
    assert owner.get(reference_url).status_code == 200
    assert anonymous.get(reference_url).status_code == 401
    assert other.get(reference_url).status_code == 404
    assert "owner" not in owner.get(f"/api/tryon/jobs/{jid}").json()
    assert other.get("/api/v1/history").json()["items"] == []
    assert len(owner.get("/api/v1/history").json()["items"]) == 1
    assert other.delete(f"/api/v1/history/{rid}").status_code == 404
    assert owner.delete(f"/api/v1/history/{rid}").status_code == 204
    assert not folder.exists() and not jobs._path(jid).exists()


def test_new_submission_requires_account_and_retains_job_ownership(studio, monkeypatch):
    (guest, stranger, _), _, _, _, jobs = studio
    monkeypatch.setattr(main, "require_tryon_ready", lambda: None)
    monkeypatch.setattr(
        main.pipeline, "run", lambda *a, **kw: {"status": "success", "owner_received": kw["owner"]}
    )
    image = io.BytesIO()
    Image.new("RGB", (512, 768), "white").save(image, format="PNG")
    def submit():
        return guest.post(
        "/api/tryon",
        headers={"Prefer": "respond-async"},
        data={"garmentCategory": "blouse"},
        files={
            "personImage": ("p.png", image.getvalue()),
            "garmentImage": ("g.png", image.getvalue()),
        },
    )
    assert submit().status_code == 401
    assert register(guest).status_code == 201
    response = submit()
    assert response.status_code == 202, response.text
    path = response.json()["statusUrl"]
    assert guest.get(path).status_code == 200
    assert stranger.get(path).status_code == 401
    register(stranger, "second@example.com")
    assert stranger.get(path).status_code == 404


def test_inference_rejects_invalid_expired_and_revoked_tokens(studio, monkeypatch):
    (client, _, _), *_ = studio
    monkeypatch.setattr(main, "require_tryon_ready", lambda: pytest.fail("Unauthorized inference reached model"))
    token = register(client).json()["access_token"]
    claims = jwt.decode(token, options={"verify_signature": False})
    expired = jwt.encode({**claims, "exp": now() - timedelta(seconds=1)}, signing_key(), algorithm="HS256")
    for candidate in ("invalid.jwt.value", expired):
        response = client.post("/api/tryon", headers={"Authorization": f"Bearer {candidate}"},
            data={"garmentCategory": "t-shirt"}, files={"personImage": ("p.png", b"p"), "garmentImage": ("g.png", b"g")})
        assert response.status_code == 401
    assert client.post("/api/v1/auth/logout").status_code in (200, 204)
    response = client.post("/api/tryon", headers={"Authorization": f"Bearer {token}"},
        data={"garmentCategory": "t-shirt"}, files={"personImage": ("p.png", b"p"), "garmentImage": ("g.png", b"g")})
    assert response.status_code == 401
    assert client.post("/api/tryon/retry").status_code == 401


def test_admin_fail_closed_and_cookie_csrf(studio):
    (owner, _, _), *_ = studio
    register(owner)
    assert owner.post("/api/brands", json={"name": "Unsafe", "slug": "unsafe"}).status_code == 403
    assert (
        owner.patch(
            "/api/v1/profile",
            headers={"Origin": "https://evil.example"},
            json={"name": "Bad actor"},
        ).status_code
        == 403
    )
    assert (
        owner.request(
            "DELETE", "/api/v1/profile", headers={"Sec-Fetch-Site": "cross-site"}, json={}
        ).status_code
        == 403
    )


def test_verify_email_expiry_single_use_and_session_revocation(studio, monkeypatch):
    (owner, other, _), db, *_ = studio
    monkeypatch.setattr(settings, "auth_require_verification", True)
    monkeypatch.setattr(settings, "smtp_host", "test.invalid")
    monkeypatch.setattr(settings, "smtp_from", "noreply@example.com")
    delivered = []

    class Mail:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def starttls(self, **kw):
            pass

        def send_message(self, message):
            delivered.append(message.get_content())

    monkeypatch.setattr(lifecycle.smtplib, "SMTP", Mail)
    assert register(owner).json()["verification_required"] is True
    assert "access_token" not in register(owner).json()
    payload = {"email": "owner@example.com", "password": PASSWORD}
    assert owner.post("/api/v1/auth/login", json=payload).status_code == 403
    token = delivered[0].split("#token=")[1].split()[0]
    db.email_verifications.insert_one(
        {"_id": digest("z" * 48), "user_id": "unused", "expires_at": now() - timedelta(seconds=1)}
    )
    assert owner.post("/api/v1/auth/verify-email", json={"token": "z" * 48}).status_code == 400
    assert owner.post("/api/v1/auth/verify-email", json={"token": token}).status_code == 200
    assert owner.post("/api/v1/auth/verify-email", json={"token": token}).status_code == 400
    assert owner.post("/api/v1/auth/login", json=payload).status_code == 200
    assert other.post("/api/v1/auth/login", json=payload).status_code == 200
    sessions = owner.get("/api/v1/profile/sessions").json()
    remote = next(s for s in sessions if not s["current"])
    assert owner.delete("/api/v1/profile/sessions/" + remote["id"]).status_code == 204
    assert other.get("/api/v1/profile").status_code == 401
    assert owner.cookies.get(ACCESS_COOKIE)


def test_account_deletion_password_and_cleanup(studio):
    (owner, _, _), db, *_ = studio
    uid = register(owner).json()["user"]["id"]
    db.favorites.insert_one({"user_id": uid, "product_id": "navy-tee"})
    assert owner.request("DELETE", "/api/v1/profile", json={"password": "wrong"}).status_code == 403
    assert (
        owner.request("DELETE", "/api/v1/profile", json={"password": PASSWORD}).status_code == 204
    )
    assert (
        db.users.count_documents({"_id": uid})
        == db.auth_sessions.count_documents({"user_id": uid})
        == db.favorites.count_documents({"user_id": uid})
        == 0
    )
    assert owner.get("/api/v1/profile").status_code == 401
