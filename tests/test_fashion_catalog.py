"""Sourced catalog, exact chart arithmetic and region/category regression checks."""

import hashlib
import json

import pytest
from PIL import Image

from backend.app.anthropometry.schemas import ChartCreate
from backend.app.anthropometry.sizing_engine import recommend
from backend.app.catalog import TAXONOMY, initialize_catalog
from backend.app.config import ROOT

pytest_plugins = ["test_vastraview"]


def test_catalog_manifest_distinct_images_and_model_support():
    rows = json.loads((ROOT / "data/catalog/garments-v2.json").read_text())
    assert len(rows) == len({r["id"] for r in rows}) == len({r["image_sha256"] for r in rows}) == 14
    for row in rows:
        path = ROOT / row["filename"]
        assert row["brand_id"] == "h-m"
        assert row["sizes"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row["image_sha256"]
        with Image.open(path) as photo:
            assert photo.size == (row["image_width"], row["image_height"])
            photo.verify()


def test_catalog_filters_pagination_no_duplication_and_seed_preserves_edits(studio):
    (client, *_), db, *_ = studio
    first = client.get("/api/v1/products?limit=12").json()
    second = client.get("/api/v1/products?limit=12&offset=12").json()
    assert first["total"] == 16
    assert not {p["id"] for p in first["items"]} & {p["id"] for p in second["items"]}
    hm_res = client.get("/api/v1/products?brand_id=h-m&limit=20").json()
    assert hm_res["total"] == 14 and len(hm_res["items"]) == 14 and all(p["brand_id"] == "h-m" for p in hm_res["items"])
    tops = client.get("/api/v1/products?tryon_supported=true&category=t-shirt").json()["items"]
    assert tops and all(p["category"] == "t-shirt" for p in tops)
    facets = client.get("/api/v1/catalog/facets").json()
    assert "casual" in facets["occasions"]
    key = first["items"][0]["id"]
    db.products.update_one({"_id": key}, {"$set": {"description": "Operator revision"}})
    initialize_catalog(db)
    assert db.products.find_one({"_id": key})["description"] == "Operator revision"


def test_real_chart_points_regions_and_units():
    raw = json.loads((ROOT / "data/brandCharts/sourced-body-charts-v2.json").read_text())
    charts = {r["apparel_id"]: ChartCreate.model_validate(r) for r in raw}
    adidas = charts["adidas-gb-men-t-shirt"]
    assert adidas.market == "GB" and adidas.verification_status == "verified"
    result = recommend({"chest_circumference": 96.5, "waist_circumference": 84.5, "hip_circumference": 95.5}, adidas)
    assert result.recommended_size == "M" and result.minimum_error == 0
    assert result.fit_confidence == 100 and sum(result.active_weights.values()) == pytest.approx(1)
    jeans = charts["levis-us-women-jeans"]
    point = jeans.sizes[0].bounds["waist_circumference"]
    assert point.lower == point.upper == pytest.approx(25.25 * 2.54)
    assert "inseam_length" not in jeans.metrics
    kurta = charts["manyavar-in-M218838-kurta"]
    values = {k: v.lower for k, v in kurta.sizes[0].bounds.items()}
    assert recommend(values, kurta).recommended_size == "36/S"
    assert kurta.sizes[0].bounds["chest_circumference"].lower == 91  # body, not garment chest 102
    assert all(c.source_url and c.checked_on for c in charts.values())


def test_chart_market_and_category_are_not_substituted(studio):
    client = studio[0][0]
    assert client.get("/api/v1/sizing/charts?brand_id=adidas&market=IN").json() == []
    valid = client.get("/api/v1/sizing/charts?brand_id=adidas&market=GB&category=trouser&latest_only=true").json()
    assert len(valid) == 2 and {c["gender"] for c in valid} == {"men", "women"}
    assert client.get("/api/v1/sizing/charts?brand_id=manyavar&category=kurta").json()
    assert client.get("/api/v1/sizing/charts?brand_id=manyavar&category=jeans").json() == []
