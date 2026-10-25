from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from backend.app.config import settings
from backend.app.db import get_db
from backend.app.health import mongo_repository
from backend.app.main import app


@pytest.fixture
def health_client(monkeypatch, tmp_path):
    state = {"sql": True, "mongo": True, "remote": False, "sql_rollback_fails": False}

    class SQL:
        def execute(self, *args):
            if not state["sql"]:
                raise OperationalError("private sql", {}, RuntimeError("private connection secret"))

        def rollback(self):
            if state["sql_rollback_fails"]:
                raise OperationalError("private rollback", {}, RuntimeError("private connection secret"))

    class Mongo:
        def ping(self):
            return state["mongo"]

    checkpoint = tmp_path / "pose.task"
    checkpoint.write_bytes(b"existence probe only; not an inference fixture")
    monkeypatch.setattr(settings, "measurement_model_path", checkpoint)
    monkeypatch.setattr(app.state, "tryon_connection", SimpleNamespace(snapshot=lambda: {
        "available": state["remote"], "connectionState": "ready" if state["remote"] else "waiting",
        "reason": None if state["remote"] else "colab_unavailable",
        "private_worker_url": "must-not-be-returned",
    }))
    app.dependency_overrides[get_db] = SQL
    app.dependency_overrides[mongo_repository] = Mongo
    client = TestClient(app, raise_server_exceptions=False)
    try:
        yield client, state, checkpoint
    finally:
        client.close()
        app.dependency_overrides.clear()


def test_health_separates_measurements_from_unavailable_tryon(health_client):
    client, _, _ = health_client
    assert client.get("/api/v1/health/live").json() == {"status": "ok"}
    state = client.get("/api/v1/health").json()
    assert state["status"] == "degraded"
    assert state["capabilities"] == {"sizing": True, "measurements": True, "tryon": False}
    assert not state["local_gpu_used"]
    assert not state["components"]["pose_model"]["inference_validated"]
    assert "private_worker_url" not in str(state)
    for capability in ("sizing", "measurements"):
        response = client.get("/api/v1/health/ready", params={"capability": capability})
        assert response.status_code == 200 and response.json()["ready"]
    for capability in ("all", "tryon"):
        response = client.get("/api/v1/health/ready", params={"capability": capability})
        assert response.status_code == 503 and not response.json()["ready"]
        assert response.headers["Retry-After"] == "5"
    assert client.get("/api/v1/health/ready", params={"capability": "invalid"}).status_code == 422


@pytest.mark.parametrize("rollback_failure", [False, True])
def test_sql_failure_leaves_mongo_capabilities_usable(health_client, rollback_failure):
    client, state, _ = health_client
    state.update(sql=False, sql_rollback_fails=rollback_failure, remote=True)
    response = client.get("/api/v1/health/ready", params={"capability": "measurements"})
    assert response.status_code == 200
    assert response.json()["capabilities"] == {"sizing": True, "measurements": True, "tryon": False}
    assert "secret" not in response.text


def test_mongo_ownership_store_is_required_even_with_live_colab(health_client):
    client, state, checkpoint = health_client
    state.update(mongo=False, remote=True)
    response = client.get("/api/v1/health/ready", params={"capability": "tryon"})
    assert response.status_code == 503
    assert response.json()["components"]["colab"]["available"] is True
    assert response.json()["capabilities"] == {"sizing": False, "measurements": False, "tryon": False}
    state["mongo"] = True
    checkpoint.unlink()
    state = client.get("/api/v1/health").json()
    assert state["capabilities"] == {"sizing": True, "measurements": False, "tryon": True}


def test_database_exception_response_is_sanitized_and_identified(health_client):
    client, _, _ = health_client
    def failed_dependency():
        raise OperationalError("postgresql://private:secret@host", {}, RuntimeError("secret"))
    app.dependency_overrides[get_db] = failed_dependency
    response = client.get("/api/brands")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "database_unavailable"
    assert "private" not in response.text and "secret" not in response.text
    assert len(response.headers["X-Request-ID"]) == 32
    assert response.headers["Retry-After"] == "5"


def test_unexpected_exception_has_no_traceback_or_secret(health_client):
    client, _, _ = health_client
    def failed_dependency():
        raise RuntimeError("very-private-data")
    app.dependency_overrides[get_db] = failed_dependency
    response = client.get("/api/brands")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert response.headers["X-Request-ID"] == response.json()["error"]["request_id"]
    assert "very-private-data" not in response.text


def test_openapi_describes_all_new_routes_and_error_contracts(health_client):
    client, _, _ = health_client
    schema = client.get("/openapi.json").json()
    paths = schema["paths"]
    for path, method in (
        ("/api/v1/measurements/extract", "post"),
        ("/api/v1/measurements/extract-and-recommend", "post"),
        ("/api/v1/measurements", "get"),
        ("/api/v1/measurements/{measurement_id}", "get"),
        ("/api/v1/measurements/{measurement_id}", "delete"),
        ("/api/v1/measurements/{measurement_id}/annotation", "get"),
        ("/api/v1/sizing/brands", "post"),
        ("/api/v1/sizing/brands/{brand_id}", "patch"),
        ("/api/v1/sizing/charts/{brand_id}/{apparel_id}/versions", "get"),
        ("/api/v1/sizing/categories", "get"),
        ("/api/v1/health/ready", "get"),
    ):
        assert method in paths[path]
    sizing = paths["/api/v1/sizing/recommend"]["post"]
    assert {"200", "404", "409", "422", "503"}.issubset(sizing["responses"])
    request_ref = sizing["requestBody"]["content"]["application/json"]["schema"]["$ref"].rsplit("/", 1)[-1]
    assert "measurement_id" in schema["components"]["schemas"][request_ref]["properties"]


def test_cors_exposes_polling_and_request_headers(health_client):
    client, _, _ = health_client
    response = client.get("/api/v1/health/live", headers={"Origin": settings.cors_origins[0]})
    assert {"location", "x-request-id", "retry-after"}.issubset({
        value.strip().lower() for value in response.headers["access-control-expose-headers"].split(",")
    })
    options = client.options("/api/v1/sizing/brands/fixture", headers={
        "Origin": settings.cors_origins[0], "Access-Control-Request-Method": "PATCH",
        "Access-Control-Request-Headers": "X-Admin-Token,Content-Type",
    })
    assert options.status_code == 200
