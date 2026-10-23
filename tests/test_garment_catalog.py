from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app import garments


def test_catalog_exposes_only_available_allowlisted_inputs(tmp_path, monkeypatch):
    monkeypatch.setattr(garments, "ROOT", tmp_path)
    app = FastAPI()
    app.include_router(garments.router)
    client = TestClient(app)
    assert client.get("/api/garments").json() == {"items": []}
    raw = tmp_path / "data/raw"
    raw.mkdir(parents=True)
    (raw / "navy-tee.jpg").write_bytes(b"test-image")
    items = client.get("/api/garments").json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == "navy-tee"
    assert items[0]["category"] == "t-shirt"
    assert items[0]["photoType"] == "model"
    image = client.get(items[0]["imageUrl"])
    assert image.content == b"test-image"
    assert image.headers["content-type"] == "image/jpeg"
    assert client.get("/api/garments/missing/image").status_code == 404
    assert client.get("/api/garments/sage-polo/image").status_code == 404
    assert client.get("/api/garments/%2e%2e%2f.env/image").status_code == 404


def test_catalog_categories_and_photo_types_match_real_inputs():
    items = {row[0]: row for row in garments.GARMENTS}
    assert items["navy-gown"][2:4] == ("dress", "model")
    assert items["coral-dress"][2:4] == ("dress", "model")
    assert items["ivory-skirt"][2:4] == ("skirt", "flat-lay")
    assert items["navy-blouse"][2:4] == ("blouse", "flat-lay")
