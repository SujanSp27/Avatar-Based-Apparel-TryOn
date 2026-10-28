"""Display changes must not swap inference inputs or bypass garment approval."""

import hashlib
import json

import pytest
from PIL import Image

from backend.app import catalog, wardrobe
from backend.app.config import settings
from ml.errors import PipelineError

pytest_plugins = ["test_vastraview"]


@pytest.fixture
def photographs(studio, tmp_path, monkeypatch):
    client, db = studio[0][0], studio[1]
    client.get("/api/v1/products")  # Finish source inventory seeding before isolating assets.
    root = tmp_path / "data/raw"
    root.mkdir(parents=True)
    for name, color in (("display.png", "white"), ("reference.png", "navy")):
        Image.new("RGB", (512, 768), color).save(root / name)
    monkeypatch.setattr(catalog, "ROOT", tmp_path)
    monkeypatch.setattr(wardrobe, "ROOT", tmp_path)
    reference = (root / "reference.png").read_bytes()
    display = (root / "display.png").read_bytes()
    metadata = dict(filename="display.png", photoType="model", source_url="https://example.com/product",
                    license="CC BY 2.0", license_url="https://creativecommons.org/licenses/by/2.0/",
                    attribution="Test photographer", attribution_url=None, commercial_use=True,
                    sha256=hashlib.sha256(display).hexdigest(),
                    identity_note="Test fixture: two views of the same garment, not a real catalog approval.")
    db.products.update_one({"_id": "navy-tee"}, {"$set": {
        "filename": "reference.png", "photoType": "flat-lay", "display_image": metadata, "commercial_use": True}})
    return client, db, root, reference, display, metadata


def test_display_reference_and_favorites_keep_distinct_bytes(photographs):
    client, db, _, reference, display, _ = photographs
    product = client.get("/api/v1/products/navy-tee").json()
    assert client.get(product["imageUrl"]).content == display
    assert client.get(product["referenceImageUrl"]).content == reference
    assert "filename" not in product and "filename" not in product["displayImage"]
    wardrobe.validate_catalog_submission(db, "navy-tee", reference, "t-shirt", "flat-lay")
    with pytest.raises(PipelineError, match="changed"):
        wardrobe.validate_catalog_submission(db, "navy-tee", display, "t-shirt", "flat-lay")
    from test_vastraview import register
    assert register(client).status_code == 201
    assert client.put("/api/v1/favorites/navy-tee").status_code == 204
    favorite = client.get("/api/v1/favorites").json()["items"][0]
    assert favorite["imageUrl"] == product["imageUrl"]
    assert favorite["referenceImageUrl"] == product["referenceImageUrl"]


def test_reference_fallback_preserves_old_records(photographs):
    client, db, _, reference, _, _ = photographs
    db.products.update_one({"_id": "navy-tee"}, {"$unset": {"display_image": ""}})
    product = client.get("/api/v1/products/navy-tee").json()
    assert product["displayImage"] is None
    assert client.get(product["imageUrl"]).content == reference
    assert client.get(product["referenceImageUrl"]).content == reference


def test_display_change_preserves_review_reference_change_invalidates_it(photographs):
    client, db, _, reference, _, _ = photographs
    wardrobe.POLICY_PATH.write_text(json.dumps({"version": 1, "enforced": True, "status": "quality_shortfall", "garments": [{
        "id": "navy-tee", "category": "t-shirt", "photoType": "flat-lay",
        "imageSha256": hashlib.sha256(reference).hexdigest(), "testedPeople": ["fixture-a", "fixture-b"],
        "maximumSeconds": 25, "status": "approved",
    }]}))
    assert client.get("/api/v1/products/navy-tee").json()["qualityReview"]["status"] == "approved"
    db.products.update_one({"_id": "navy-tee"}, {"$set": {"display_image.filename": "reference.png"}})
    assert wardrobe.approval(db.products.find_one({"_id": "navy-tee"}))["status"] == "approved"
    assert client.get("/api/v1/products/navy-tee/image").status_code == 404
    assert client.get("/api/v1/products/navy-tee/reference-image").content == reference
    db.products.update_one({"_id": "navy-tee"}, {"$set": {"filename": "display.png"}})
    assert wardrobe.approval(db.products.find_one({"_id": "navy-tee"}))["status"] == "stale"
    for tail in ("", "/image", "/reference-image"):
        assert client.get("/api/v1/products/navy-tee" + tail).status_code == 404


def test_display_license_and_paths_fail_closed(photographs, monkeypatch):
    client, db, *_ = photographs
    db.products.update_one({"_id": "navy-tee"}, {"$set": {"display_image.filename": "../../secret.png"}})
    assert client.get("/api/v1/products/navy-tee/image").status_code == 404
    db.products.update_one({"_id": "navy-tee"}, {"$set": {"display_image.commercial_use": False}})
    monkeypatch.setattr(settings, "environment", "production")
    for tail in ("", "/image", "/reference-image"):
        assert client.get("/api/v1/products/navy-tee" + tail).status_code == 404


def test_admin_display_update_validates_content_and_keeps_ids(photographs, monkeypatch):
    client, db, _, _, _, metadata = photographs
    monkeypatch.setattr(settings, "admin_token", "test-admin-image-token")
    headers = {"X-Admin-Token": settings.admin_token}
    payload = dict(id="navy-tee", name="Navy crew-neck T-shirt", brand_id="uniqlo", subcategory="t-shirt",
                   audience="unisex", filename="reference.png", photoType="flat-lay", description="Test reference",
                   colors=["navy"], source_url="https://example.com/reference", license="CC BY 2.0",
                   commercial_use=True, display_image=metadata)
    assert client.put("/api/v1/products/navy-tee", json=payload).status_code == 403
    assert client.put("/api/v1/products/navy-tee", json=payload, headers=headers).status_code == 200
    payload.pop("display_image")
    assert client.put("/api/v1/products/navy-tee", json=payload, headers=headers).status_code == 200
    assert db.products.find_one({"_id": "navy-tee"})["display_image"] == metadata
    payload["display_image"] = {**metadata, "sha256": "0" * 64}
    assert client.put("/api/v1/products/navy-tee", json=payload, headers=headers).status_code == 422
    payload["display_image"] = {**metadata, "filename": "../../secret.png"}
    assert client.put("/api/v1/products/navy-tee", json=payload, headers=headers).status_code == 404
    payload["display_image"] = None
    assert client.put("/api/v1/products/navy-tee", json=payload, headers=headers).status_code == 200
    assert db.products.find_one({"_id": "navy-tee"})["display_image"] is None
