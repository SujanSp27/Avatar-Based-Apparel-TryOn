"""Publication/access contracts; fixture approvals never become real catalog evidence."""
import json

import pytest

from backend.app import wardrobe
from backend.app.config import ROOT
from ml.errors import PipelineError
from scripts import curate_wardrobe as curate
from scripts.evaluate_wardrobe import digest, save
from tests.test_vastraview import register

pytest_plugins = ["test_vastraview"]


def install(records, *, status="published"):
    save(wardrobe.POLICY_PATH, {"version": 1, "enforced": True, "status": status,
                              "targetCount": 20, "garments": records})


def records_for(rows):
    return [{"id": r["_id"], "category": r["category"], "photoType": r["photoType"],
             "status": "approved", "imageSha256": digest((ROOT / "data/raw" / r["filename"]).read_bytes()),
             "testedPeople": ["studio", "mirror"], "maximumSeconds": 29} for r in rows]


def test_exactly_twenty_filters_all_routes_favorites_facets_and_submission(studio):
    client, db = studio[0][0], studio[1]
    register(client)
    client.get("/api/v1/products")
    rows = list(db.products.find({"commercial_use": True, "category": {"$ne": None}}).sort("_id", 1))
    chosen, rejected = rows[:20], rows[20]
    for r in [chosen[0], rejected]:
        assert client.put(f"/api/v1/favorites/{r['_id']}").status_code == 204
    install(records_for(chosen))
    keys = {r["_id"] for r in chosen}
    for query in ("", "?sort=name", "?sort=newest", "?tryon_supported=true"):
        result = client.get("/api/v1/products" + (query + "&" if query else "?") + "limit=48").json()
        assert result["total"] == 20 and {r["id"] for r in result["items"]} == keys
    assert client.get("/api/v1/products?offset=20").json()["items"] == []
    assert client.get("/api/v1/products", params={"q": rejected["name"]}).json()["total"] == 0
    assert client.get("/api/v1/catalog/quality").json()["approvedCount"] == 20
    for suffix in ("", "/image"):
        assert client.get(f"/api/v1/products/{rejected['_id']}{suffix}").status_code == 404
    assert client.put(f"/api/v1/favorites/{rejected['_id']}").status_code == 404
    assert [r["id"] for r in client.get("/api/v1/favorites").json()["items"]] == [chosen[0]["_id"]]
    assert db.favorites.count_documents({}) == 2
    assert db.products.count_documents({}) == 57
    assert client.get("/api/garments").json()["items"] == []
    assert client.get("/api/garments/sage-polo/image").status_code == 404
    categories = client.get("/api/v1/categories").json()
    assert {c["id"] for c in categories} == {r["subcategory"] for r in chosen}
    assert sum(c["product_count"] for c in categories) == 20
    facets = client.get("/api/v1/catalog/facets").json()
    assert set(facets["colors"]) == {color for row in chosen for color in row["colors"]}
    for brand in client.get("/api/v1/brands").json():
        assert brand["product_count"] == sum(r.get("brand_id") == brand["id"] for r in chosen)
    for row in chosen:
        actual = (ROOT / "data/raw" / row["filename"]).read_bytes()
        wardrobe.validate_catalog_submission(db, row["_id"], actual, row["category"], row["photoType"])
    actual = (ROOT / "data/raw" / rejected["filename"]).read_bytes()
    with pytest.raises(PipelineError) as error:
        wardrobe.validate_catalog_submission(db, rejected["_id"], actual, rejected["category"], rejected["photoType"])
    assert error.value.code == "garment_not_approved"
    response = client.post("/api/tryon", data={"productId": rejected["_id"], "garmentCategory": rejected["category"]},
                           files={"personImage": ("p.jpg", actual), "garmentImage": ("g.jpg", actual)})
    assert response.status_code == 422 and response.json()["error"]["code"] == "garment_not_approved"


def test_explicit_shortfall_hides_unapproved_without_deleting_inventory(studio):
    client, db = studio[0][0], studio[1]
    register(client)
    client.get("/api/v1/products")
    client.put("/api/v1/favorites/sage-polo")
    install([], status="quality_shortfall")
    assert "error" not in wardrobe.policy()
    for route in ("products", "favorites"):
        assert client.get(f"/api/v1/{route}").json()["total"] == 0
    assert client.get("/api/v1/categories").json() == []
    assert client.get("/api/v1/catalog/facets").json() == {"colors": [], "occasions": []}
    assert client.get("/api/v1/catalog/quality").json()["status"] == "quality_shortfall"
    assert client.get("/api/garments/sage-polo/image").status_code == 404
    assert db.products.count_documents({}) == 57 and db.favorites.count_documents({}) == 1
    assert client.get("/api/v1/sizing/charts?brand_id=nike").json()


def test_stale_approval_is_removed_from_reported_count_and_routes(studio):
    client, db = studio[0][0], studio[1]
    client.get("/api/v1/products")
    row = db.products.find_one({"_id": "edit-a59f077d"})
    records = records_for([row])
    install(records, status="quality_shortfall")
    assert client.get("/api/v1/catalog/quality").json()["approvedCount"] == 1
    records[0]["imageSha256"] = "0" * 64
    install(records, status="quality_shortfall")
    assert client.get("/api/v1/catalog/quality").json()["approvedCount"] == 0
    assert client.get(f"/api/v1/products/{row['_id']}/image").status_code == 404


def test_more_than_twenty_or_boolean_timing_fails_closed(studio):
    client, db = studio[0][0], studio[1]
    client.get("/api/v1/products")
    rows = list(db.products.find({"commercial_use": True, "category": {"$ne": None}}))
    install(records_for(rows[:21]))
    assert wardrobe.policy().get("error")
    records = records_for(rows[:20])
    records[0]["maximumSeconds"] = True
    install(records)
    assert wardrobe.policy().get("error")


def test_shortfall_publication_archives_previous_policy_and_reasons_first(tmp_path, monkeypatch):
    data = {"generatedAt": "2026-10-28", "garments": [{"id": "rejected", "status": "not_approved",
            "trials": {"studio": {"status": "failed", "reasons": ["Invented sleeves"]}}}]}
    monkeypatch.setattr(curate, "report", lambda folder: data)
    monkeypatch.setattr(curate, "catalog_rows", lambda: [{"id": "rejected", "filename": "retained.png"}])
    output = tmp_path / "publication.json"
    save(output, {"version": 1, "enforced": False, "garments": []})
    curate.publish(tmp_path, output, allow_shortfall=True)
    published = json.loads(output.read_text())
    assert published["status"] == "quality_shortfall" and published["enforced"] and not published["garments"]
    archive = json.loads(next(tmp_path.glob("catalog-archive-*.json")).read_text())
    assert archive["evaluation"] == data and not archive["previousPublication"]["enforced"]
    assert archive["sourceRecords"][0]["filename"] == "retained.png"
    before = output.read_bytes()
    monkeypatch.setattr(curate, "save", lambda *args: (_ for _ in ()).throw(OSError("Archive disk full")))
    with pytest.raises(OSError, match="Archive disk full"):
        curate.publish(tmp_path, output, allow_shortfall=True)
    assert output.read_bytes() == before
