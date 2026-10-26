import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.charts import seed_database
from backend.app.db import Base, get_db
from backend.app.main import app


@pytest.fixture
def client(monkeypatch):
    import mongomock

    from backend.app.anthropometry.repository import MeasurementRepository, get_repository
    from backend.app.config import settings
    repo = MeasurementRepository(mongomock.MongoClient(tz_aware=True), "sql_api_test")
    repo.db.command = lambda *a, **kw: {"ok": 1}
    app.dependency_overrides[get_repository] = lambda: repo
    monkeypatch.setattr(settings, "admin_token", "sql-api-admin")
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        seed_database(db)

    def session():
        with Session(engine, expire_on_commit=False) as db:
            yield db

    app.dependency_overrides[get_db] = session
    # No lifespan here: tests use an isolated database, not the running development database.
    client = TestClient(app, headers={"X-Admin-Token": "sql-api-admin"})
    registered = client.post("/api/v1/auth/signup", json={
        "name": "API Test", "email": "api@example.com", "password": "Api!Secure2026",
        "terms_accepted": True,
    })
    assert registered.status_code == 201, registered.text
    yield client
    client.close()
    app.dependency_overrides.clear()
    engine.dispose()


def test_brand_chart_version_crud_and_independent_sizing(client):
    brand = client.get("/api/brands").json()[0]
    path = f"/api/brands/{brand['id']}/charts"
    chart = client.get(path, params={"garmentCategory": "shirt"}).json()
    updated = {
        "version": 2,
        "garmentCategory": "shirt",
        "source": "Test fixture v2",
        "sizes": chart["sizes"],
    }
    assert client.post(path, json=updated).status_code == 201
    assert client.post(path, json=updated).status_code == 409
    assert client.get(path, params={"garmentCategory": "shirt"}).json()["version"] == 2
    assert (
        client.get(path, params={"garmentCategory": "shirt", "version": 1}).json()["version"] == 1
    )
    response = client.post(
        "/api/sizing/recommend",
        json={
            "brandId": brand["id"],
            "garmentCategory": "shirt",
            "fitPreference": "regular",
            "measurements": {"chest": 94, "waist": 78, "hip": 98, "shoulderWidth": 41},
        },
    )
    assert response.status_code == 200
    assert response.json()["recommendedSize"] == "M"
    assert response.json()["chartVersion"] == 2


def test_bad_chart_range_brand_duplicates_and_unknown_chart(client):
    spec = {"name": "Test Brand", "slug": "test-brand"}
    assert client.post("/api/brands", json=spec).status_code == 201
    assert client.post("/api/brands", json=spec).status_code == 409
    assert client.get("/api/brands/999/charts?garmentCategory=dress").status_code == 404
    chart = client.get("/api/brands/1/charts?garmentCategory=shirt").json()
    chart["sizes"][0]["chestMin"] = 200
    assert client.post("/api/brands/1/charts", json={**chart, "version": 2}).status_code == 422


def test_request_validation_and_asset_traversal(client):
    response = client.post(
        "/api/tryon",
        data={"brandId": 1, "garmentCategory": "spacesuit", "fitPreference": "regular"},
        files={"personImage": ("x.png", b"invalid"), "garmentImage": ("x.png", b"invalid")},
    )
    assert response.status_code == 422
    assert client.get("/assets/..%2F..%2F.env").status_code == 404
    assert client.delete("/api/runs/not-a-uuid").status_code == 422


def test_invalid_tryon_mode_is_rejected_before_pipeline(client, monkeypatch):
    from backend.app.main import pipeline

    def should_not_run(*args, **kwargs):
        raise AssertionError("Invalid mode must not reach image processing")

    monkeypatch.setattr(pipeline, "run", should_not_run)
    response = client.post(
        "/api/tryon",
        data={"brandId": 1, "garmentCategory": "shirt", "tryonMode": "unknown"},
        files={"personImage": ("x.png", b"invalid"), "garmentImage": ("x.png", b"invalid")},
    )
    assert response.status_code == 422


def test_failed_request_releases_pipeline_capacity(client, monkeypatch):
    from backend.app.main import pipeline
    from ml.errors import PipelineError

    calls = []

    def fail(*args, **kwargs):
        calls.append(True)
        raise PipelineError("invalid_image", "Invalid image fixture")

    monkeypatch.setattr(pipeline, "run", fail)
    monkeypatch.setattr(pipeline.worker, "availability", lambda **_: {"available": True})
    for _ in range(2):
        response = client.post(
            "/api/tryon",
            data={"brandId": 1, "garmentCategory": "shirt", "tryonMode": "2d"},
            files={"personImage": ("x.png", b"invalid"), "garmentImage": ("x.png", b"invalid")},
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "invalid_image"
    assert len(calls) == 2


def test_run_history_pagination_filtering_and_admin(client, monkeypatch):
    from datetime import datetime, timedelta, timezone
    from uuid import uuid4

    from backend.app.config import settings
    from backend.app.models import Run

    sessions = app.dependency_overrides[get_db]()
    db = next(sessions)
    try:
        now = datetime.now(timezone.utc)
        records = [Run(id=str(uuid4()), status=status, created_at=now + timedelta(seconds=index),
                       metadata_json={"private_diagnostic": "should-not-be-listed"})
                   for index, status in enumerate(("success", "failed", "processing"))]
        db.add_all(records)
        db.commit()
        page = client.get("/api/runs", params={"limit": 1, "offset": 1})
        assert page.status_code == 200 and "private_diagnostic" not in page.text
        assert page.json()["total"] == 3 and page.json()["items"][0]["id"] == records[1].id
        filtered = client.get("/api/runs", params={"status": "success"}).json()
        assert filtered["total"] == 1 and filtered["items"][0]["id"] == records[0].id
        assert client.get("/api/runs", params={"status": "unknown"}).status_code == 422
        assert client.get("/api/runs", params={"limit": 101}).status_code == 422
        monkeypatch.setattr(settings, "admin_token", "test-history-token")
        assert client.get("/api/runs").status_code == 403
        assert client.get("/api/runs", headers={"X-Admin-Token": "test-history-token"}).status_code == 200
    finally:
        sessions.close()
