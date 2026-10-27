"""Publication/security gates. Synthetic fixtures never become catalog approvals."""
import io

import httpx
import numpy as np
import pytest
from PIL import Image

from backend.app import catalog, wardrobe
from backend.app.config import ROOT
from ml.errors import PipelineError
from scripts import curate_wardrobe as curate
from scripts.evaluate_wardrobe import (
    catalog_rows,
    digest,
    inspect_source,
    save,
    submit_trial,
    validate_output,
)
from tests.test_vastraview import register

pytest_plugins = ["test_vastraview"]


def png(array):
    stream = io.BytesIO()
    Image.fromarray(array).save(stream, "PNG")
    return stream.getvalue()


def test_output_validation_requires_changed_pixels_and_matching_frame():
    a = np.zeros((128, 128, 3), dtype=np.uint8)
    assert not validate_output(png(a), png(a))["nonEmptyEdit"]
    b = a.copy()
    b[32:96, 32:96] = 120
    assert validate_output(png(a), png(b))["nonEmptyEdit"]
    assert not validate_output(png(a), png(b[:64]))["matchingDimensions"]
    with pytest.raises(OSError):
        validate_output(png(a), b"not an image")


def test_source_audit_uses_actual_decoder_and_supported_category():
    row = next(r for r in catalog_rows() if r["id"] == "edit-a59f077d")
    report = inspect_source(row)
    assert report["validImage"] and report["modelCategory"] == "tops"
    assert report["inferenceStatus"] == "not_tested"
    assert report["visualStatus"] == "not_reviewed"
    assert inspect_source({**row, "category": None})["technicalStatus"] == "unsupported"
    with pytest.raises(ValueError):
        inspect_source({**row, "filename": "../../.env"})


@pytest.mark.parametrize("status", [401, 429, 503])
def test_preflight_failure_preserves_key_and_does_not_start_another_job(tmp_path, status):
    transport = httpx.MockTransport(lambda request: httpx.Response(status, json={"detail": "blocked"}))
    state = {"jobId": "same-key", "status": "submitting"}
    row = {"category": "t-shirt", "photoType": "flat-lay", "filename": "shirt.jpg"}
    with httpx.Client(base_url="http://localhost", transport=transport) as client:
        assert not submit_trial(client, row, state, tmp_path / "trial.json", b"person", b"garment")
    assert state["status"] == "prepared" and state["jobId"] == "same-key"


def test_missing_inference_cannot_be_approved_or_published(tmp_path):
    source = {"sha256": "unused"}
    assert curate.assess_trial(tmp_path, source, "studio")["status"] == "pending"
    destination = tmp_path / "published.json"
    with pytest.raises(ValueError, match="Only 0 garments passed"):
        curate.publish(tmp_path, destination)
    assert not destination.exists()


def test_failed_api_job_keeps_structured_error_readable_in_report(tmp_path):
    case = tmp_path / "cases/edit-a59f077d/studio"
    save(case / "trial.json", {"status": "failed", "jobId": "saved-failure",
        "error": {"code": "online_gpu_connection", "message": "The GPU connection expired."}})
    report = curate.report(tmp_path)
    entry = next(row for row in report["garments"] if row["id"] == "edit-a59f077d")
    assert entry["trials"]["studio"]["reasons"] == ["The GPU connection expired."]
    assert "The GPU connection expired." in (tmp_path / "report.md").read_text(encoding="utf-8")


def test_completed_image_alone_never_passes_visual_or_mask_review(tmp_path):
    row = next(r for r in catalog_rows() if r["id"] == "edit-a59f077d")
    source = inspect_source(row)
    output = png(np.zeros((128, 128, 3), dtype=np.uint8))
    (tmp_path / "after.png").write_bytes(output)
    save(tmp_path / "trial.json", {
        "status": "generated", "jobId": "fixture", "inputs": {"garmentSha256": source["sha256"],
        "personSha256": digest((ROOT / curate.PEOPLE["studio"]).read_bytes())},
        "outputSha256": digest(output), "outputChecks": {"readable": True, "matchingDimensions": True, "nonEmptyEdit": True},
        "timingTargetMet": True, "observedEndToEndSeconds": 20,
        "diagnostics": {"modelRevision": curate.MODEL, "sourceCommit": curate.SOURCE, "device": "cuda",
                        "inputAudit": {"garment": {"rgbSha256": source["normalizedRgbSha256"]},
                                       "category": "tops", "garmentPhotoType": "flat-lay"}},
    })
    review = curate.assess_trial(tmp_path, source, "studio")
    assert review["status"] == "needs_review"
    assert "Full-resolution visual review pending" in review["reasons"]
    assert "Worker masks/conditioning not retrieved for inspection" in review["reasons"]
    # A rejected review never becomes an approval merely because all numeric
    # scores were entered as four. Explicit visual acceptance is mandatory.
    save(tmp_path / "visual-review.json", {
        "outputSha256": digest(output), "reviewer": "test reviewer", "reviewedAt": "2026-10-27",
        "fullResolutionInspected": True, "majorArtifacts": False, "decision": "failed",
        "ratings": dict.fromkeys(curate.RATINGS, 4), "notes": "Wrong garment construction",
    })
    assert curate.assess_trial(tmp_path, source, "studio")["status"] == "failed"


def test_policy_malformed_fails_closed(tmp_path, monkeypatch):
    manifest = tmp_path / "policy.json"
    manifest.write_text('{"version":1,"enforced":true,"garments":[]}')
    monkeypatch.setattr(wardrobe, "POLICY_PATH", manifest)
    assert wardrobe.policy()["enforced"] and wardrobe.policy()["error"]


def test_catalog_preserved_before_verified_publication(studio):
    client = studio[0][0]
    quality = client.get("/api/v1/catalog/quality").json()
    assert quality["approvedCount"] == 0 and not quality["enforced"]
    result = client.get("/api/v1/products?limit=48").json()
    assert result["total"] == 57
    assert all(p["qualityReview"]["status"] != "approved" for p in result["items"])


def test_catalog_payload_rejects_changed_image_category_and_unsupported(studio, monkeypatch):
    (client, *_), db, *_ = studio
    register(client)
    client.get("/api/v1/products")
    row = db.products.find_one({"_id": "edit-a59f077d"})
    actual = (ROOT / "data/raw" / row["filename"]).read_bytes()
    wardrobe.validate_catalog_submission(db, row["_id"], actual, "t-shirt", "flat-lay")
    for image, category, photo in ((b"different", "t-shirt", "flat-lay"), (actual, "dress", "flat-lay"), (actual, "t-shirt", "model")):
        with pytest.raises(PipelineError, match="changed"):
            wardrobe.validate_catalog_submission(db, row["_id"], image, category, photo)
    response = client.post("/api/tryon", data={"productId": row["_id"], "garmentCategory": "dress"},
                           files={"personImage": ("person.jpg", actual), "garmentImage": ("garment.webp", actual)})
    assert response.status_code == 422 and response.json()["error"]["code"] == "garment_input_mismatch"
    monkeypatch.setattr(wardrobe, "policy", lambda: {"enforced": True, "garments": []})
    monkeypatch.setattr(catalog, "policy", wardrobe.policy)
    with pytest.raises(PipelineError, match="not passed"):
        wardrobe.validate_catalog_submission(db, row["_id"], actual, "t-shirt", "flat-lay")
    assert client.get("/api/v1/products").json()["total"] == 0
    assert client.get("/api/v1/products/unknown").status_code == 404


def test_source_change_invalidates_approval(studio, monkeypatch):
    client, db = studio[0][0], studio[1]
    client.get("/api/v1/products")
    row = db.products.find_one({"_id": "edit-a59f077d"})
    record = {"id": row["_id"], "category": row["category"], "photoType": row["photoType"],
              "imageSha256": "0" * 64, "testedPeople": ["studio", "mirror"], "maximumSeconds": 25}
    monkeypatch.setattr(wardrobe, "policy", lambda: {"enforced": True, "garments": [record]})
    assert wardrobe.approval(row)["status"] == "stale"


def test_published_catalog_filters_favorites_and_invalidated_sources(studio, monkeypatch):
    client, db = studio[0][0], studio[1]
    register(client)
    client.get("/api/v1/products")
    ids = ["edit-a59f077d", "edit-1b2a7169"]
    for product_id in ids:
        assert client.put(f"/api/v1/favorites/{product_id}").status_code == 204
    records = []
    for row in db.products.find({"_id": {"$in": ids}}):
        records.append({"id": row["_id"], "category": row["category"], "photoType": row["photoType"],
                        "imageSha256": digest((ROOT / "data/raw" / row["filename"]).read_bytes()),
                        "testedPeople": ["studio", "mirror"], "maximumSeconds": 25})
    published = {"enforced": True, "garments": records}
    monkeypatch.setattr(wardrobe, "policy", lambda: published)
    monkeypatch.setattr(catalog, "policy", wardrobe.policy)
    assert client.get("/api/v1/favorites").json()["total"] == 2
    assert client.get("/api/v1/products/unknown").status_code == 404
    records[0]["imageSha256"] = "0" * 64
    remaining = records[1]["id"]
    for endpoint in ("products", "favorites"):
        response = client.get(f"/api/v1/{endpoint}")
        assert response.status_code == 200
        assert [r["id"] for r in response.json()["items"]] == [remaining]
    assert db.favorites.count_documents({}) == 2  # Archived references survive publication.
    assert client.get(f"/api/v1/products/{records[0]['id']}/image").status_code == 404
    assert client.get("/api/v1/products?category=t-shirt&tryon_supported=false").json()["total"] == 0


def test_catalog_collar_correction_is_repeatable_and_preserves_operator_edits(studio):
    client, db = studio[0][0], studio[1]
    client.get("/api/v1/products")
    key = "edit-4758e641"
    db.catalog_versions.delete_one({"_id": 3})
    db.products.update_one({"_id": key}, {"$set": {"name": "Olive mandarin-collar shirt", "description": "Operator description"}})
    catalog.catalog_db(db)
    row = db.products.find_one({"_id": key})
    assert row["name"] == "Olive short-sleeve shirt" and row["description"] == "Operator description"
    db.products.update_one({"_id": key}, {"$set": {"name": "Operator name"}})
    catalog.catalog_db(db)
    assert db.products.find_one({"_id": key})["name"] == "Operator name"


def test_background_experiment_preserves_fabric_and_rejects_clipped_mask(tmp_path):
    from scripts.prepare_wardrobe_reference import prepare
    pixels = np.full((240, 180, 3), [160, 40, 50], dtype=np.uint8)
    mask = np.zeros((240, 180), dtype=np.uint8)
    mask[40:200, 35:145] = 3
    pixels[mask == 3] = [20, 100, 60]
    (tmp_path / "garment-input.png").write_bytes(png(pixels))
    (tmp_path / "garment-labels.png").write_bytes(png(mask))
    save(tmp_path / "trial.json", {"productId": "test", "inputs": {"photoType": "flat-lay", "garmentSha256": "a" * 64},
                                    "diagnostics": {"category": "tops"}})
    prepare(tmp_path, tmp_path / "prepared")
    result = np.asarray(Image.open(tmp_path / "prepared/test.png"))
    np.testing.assert_array_equal(result[mask == 3], pixels[mask == 3])
    assert (result[mask == 0] == 127).all()
    mask[:40, 35:145] = 3
    (tmp_path / "garment-labels.png").write_bytes(png(mask))
    with pytest.raises(ValueError, match="border"):
        prepare(tmp_path, tmp_path / "clipped")


def test_reference_mask_uses_actual_parser_label_numbers(tmp_path):
    image = np.zeros((128, 128, 3), dtype=np.uint8)
    for name in ("person-input.png", "garment-input.png"):
        (tmp_path / name).write_bytes(png(image))
    mask = np.zeros((128, 128), dtype=np.uint8)
    mask[20:90, 20:90] = 5  # Actual skirt label, not 7 (belt).
    for name in ("source-labels.png", "target-labels.png", "garment-labels.png", "edit-mask.png"):
        (tmp_path / name).write_bytes(png(mask))
    save(tmp_path / "conditioning.json", {key: {"shape": [864, 576, 1 if key.endswith("poses") else 3], "float32Sha256": "a" * 64}
         for key in ("ca_images", "garment_images", "person_poses", "garment_poses")})
    assert not curate.artifact_checks(tmp_path, {"category": "bottoms", "modelResolution": [576, 864]})
    assert "Reference parser found too little category-specific garment" in curate.artifact_checks(
        tmp_path, {"category": "one-pieces", "modelResolution": [576, 864]})
