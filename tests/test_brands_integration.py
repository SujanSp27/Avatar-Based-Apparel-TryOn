"""Integration tests for Levi's and Westside brand collections in VastraView."""
import json
import urllib.request
import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "http://127.0.0.1:8000"


def get_json(endpoint: str):
    req = urllib.request.Request(f"{BASE_URL}{endpoint}")
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.load(r)


def get_status(endpoint: str):
    req = urllib.request.Request(f"{BASE_URL}{endpoint}")
    with urllib.request.urlopen(req, timeout=5) as r:
        return r.status


def test_brands_endpoint():
    brands = get_json("/api/v1/brands")
    brand_dict = {b["id"]: b for b in brands}
    
    assert "h-m" in brand_dict, "H&M brand must exist in /api/v1/brands"
    assert "levi-s" in brand_dict, "Levi's brand must exist in /api/v1/brands"
    assert "westside" in brand_dict, "Westside brand must exist in /api/v1/brands"

    assert brand_dict["h-m"]["name"] == "H&M"
    assert brand_dict["levi-s"]["name"] == "Levi's"
    assert brand_dict["westside"]["name"] == "Westside"


def test_hm_collection():
    data = get_json("/api/v1/products?brand_id=h-m&limit=48")
    items = data.get("items", [])
    assert len(items) == 14, f"Expected 14 H&M products, got {len(items)}"
    for item in items:
        assert item["brand_name"] == "H&M"
        assert get_status(item["imageUrl"]) == 200


def test_levis_collection():
    data = get_json("/api/v1/products?brand_id=levi-s&limit=48")
    items = data.get("items", [])
    assert len(items) == 11, f"Expected 11 Levi's products, got {len(items)}"
    for item in items:
        assert item["brand_name"] == "Levi's"
        assert item["tryon_supported"] is True
        assert get_status(item["imageUrl"]) == 200


def test_westside_collection():
    data = get_json("/api/v1/products?brand_id=westside&limit=48")
    items = data.get("items", [])
    assert len(items) == 13, f"Expected 13 Westside products, got {len(items)}"
    for item in items:
        assert item["brand_name"] == "Westside"
        assert item["tryon_supported"] is True
        assert get_status(item["imageUrl"]) == 200


def test_all_categories_accessible():
    for brand_id in ["levi-s", "westside"]:
        data = get_json(f"/api/v1/products?brand_id={brand_id}&limit=48")
        for item in data.get("items", []):
            assert item["category"] in {"shirt", "t-shirt", "jeans", "trouser", "sweater", "jacket"}
