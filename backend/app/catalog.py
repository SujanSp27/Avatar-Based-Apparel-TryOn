"""Database-backed discovery. Brand names are a directory, never invented inventory."""

import re
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from backend.app.accounts.router import account_db, current_user
from backend.app.accounts.security import require_admin
from backend.app.config import ROOT, settings
from backend.app.garments import GARMENTS

router = APIRouter(prefix="/api/v1", tags=["Catalog and favorites"])
BRANDS = [
    "Nike",
    "Adidas",
    "Puma",
    "Levi's",
    "H&M",
    "Zara",
    "Uniqlo",
    "US Polo Assn.",
    "Tommy Hilfiger",
    "Calvin Klein",
    "Ralph Lauren",
    "Under Armour",
    "Reebok",
    "New Balance",
    "Decathlon",
    "Allen Solly",
    "Peter England",
    "Van Heusen",
    "Louis Philippe",
    "Fabindia",
    "Biba",
    "W",
    "Aurelia",
]
TAXONOMY = [
    ("t-shirt", "T-shirts", "tops", "t-shirt"),
    ("polo", "Polo shirts", "tops", "t-shirt"),
    ("oversized-tee", "Oversized tees", "tops", "t-shirt"),
    ("shirt", "Shirts", "tops", "shirt"),
    ("formal-shirt", "Formal shirts", "tops", "shirt"),
    ("blouse", "Blouses", "tops", "blouse"),
    ("top", "Tops", "tops", "blouse"),
    ("hoodie", "Hoodies", "layers", "sweater"),
    ("sweatshirt", "Sweatshirts", "layers", "sweater"),
    ("sweater", "Sweaters", "layers", "sweater"),
    ("jacket", "Jackets", "layers", "jacket"),
    ("jeans", "Jeans", "bottoms", "jeans"),
    ("trouser", "Trousers", "bottoms", "trouser"),
    ("chino", "Chinos", "bottoms", "trouser"),
    ("shorts", "Shorts", "bottoms", "shorts"),
    ("skirt", "Skirts", "bottoms", "skirt"),
    ("dress", "Dresses", "one-pieces", "dress"),
    ("gown", "Gowns", "one-pieces", "dress"),
    ("jumpsuit", "Jumpsuits", "one-pieces", "jumpsuit"),
    ("kurta", "Kurtas & kurtis", "ethnic", None),
    ("salwar-suit", "Salwar suits", "ethnic", None),
    ("saree", "Sarees", "ethnic", None),
    ("traditional", "Traditional outfits", "ethnic", None),
    ("co-ord", "Co-ord sets", "sets", None),
]


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def initialize_catalog(db):
    db.products.create_index([("brand_id", 1), ("audience", 1), ("category", 1), ("name", 1)])
    db.products.create_index([("created_at", -1), ("_id", 1)])
    db.favorites.create_index([("user_id", 1), ("product_id", 1)], unique=True)
    for name in BRANDS:
        db.catalog_brands.update_one(
            {"_id": slug(name)}, {"$setOnInsert": {"name": name, "partnership": False}}, upsert=True
        )
    for key, name, group, model in TAXONOMY:
        db.categories.update_one(
            {"_id": key},
            {
                "$setOnInsert": {
                    "name": name,
                    "group": group,
                    "model_category": model,
                    "audiences": ["men", "women", "unisex"],
                    "support_note": "Single garment preview; fidelity varies."
                    if model
                    else "Multi-layer/draped outfits are not validated by this model. Upload a supported single garment instead.",
                }
            },
            upsert=True,
        )
    from scripts.download_samples import FASHN_REVISION, NAVY_URL, POLO_URL

    for key, name, category, photo, filename, description in GARMENTS:
        reference_url = (
            NAVY_URL
            if key == "navy-tee"
            else POLO_URL
            if key == "sage-polo"
            else (
                f"https://huggingface.co/spaces/fashn-ai/fashn-vton-1.5/blob/{FASHN_REVISION}/assets/examples/{filename.split('/')[-1]}"
            )
        )
        db.products.update_one(
            {"_id": key},
            {
                "$setOnInsert": {
                    "name": name,
                    "brand_id": "uniqlo" if key in {"navy-tee", "sage-polo"} else None,
                    "category": category,
                    "subcategory": "polo"
                    if key == "sage-polo"
                    else "gown"
                    if key == "navy-gown"
                    else category,
                    "audience": "unisex" if key in {"navy-tee", "sage-polo"} else "women",
                    "photoType": photo,
                    "filename": filename,
                    "description": description,
                    "colors": [
                        "sage"
                        if key == "sage-polo"
                        else "coral"
                        if key == "coral-dress"
                        else "ivory"
                        if key == "ivory-skirt"
                        else "navy"
                    ],
                    "sizes": [],
                    "size_note": "Size availability has not been verified for this research reference.",
                    "source_url": reference_url,
                    "license": "Research reference; commercial rights not established",
                    "commercial_use": False,
                    "created_at": datetime(2026, 10, 21, tzinfo=timezone.utc),
                    "seed_version": 1,
                    "active": (ROOT / "data/raw" / filename).is_file(),
                }
            },
            upsert=True,
        )


def catalog_db(db=Depends(account_db)):
    # Seed uses setOnInsert: never overwrite operator-curated product metadata.
    if not db.catalog_versions.find_one({"_id": 1}):
        initialize_catalog(db)
        db.catalog_versions.update_one({"_id": 1}, {"$set": {"installed": True}}, upsert=True)
    return db


def image_path(row):
    root = (ROOT / "data/raw").resolve()
    path = (root / row["filename"]).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise HTTPException(404, "Catalog image is unavailable.")
    return path


def visible_query():
    return {
        "active": True,
        **({"commercial_use": True} if settings.environment == "production" else {}),
    }


def public_product(row, db):
    brand = db.catalog_brands.find_one({"_id": row.get("brand_id")})
    return {
        **{k: v for k, v in row.items() if k not in {"_id", "filename"}},
        "id": row["_id"],
        "brand_name": brand["name"] if brand else "Independent reference",
        "imageUrl": f"/api/v1/products/{row['_id']}/image",
    }


@router.get("/products")
def products(
    q: str = Query("", max_length=100),
    category: str | None = None,
    subcategory: str | None = None,
    audience: Literal["men", "women", "unisex"] | None = None,
    brand_id: str | None = None,
    sort: Literal["name", "newest", "relevance"] = "relevance",
    limit: int = Query(12, ge=1, le=48),
    offset: int = Query(0, ge=0, le=10000),
    db=Depends(catalog_db),
):
    query = visible_query()
    for key, value in {
        "category": category,
        "subcategory": subcategory,
        "audience": audience,
        "brand_id": brand_id,
    }.items():
        if value:
            query[key] = value
    if q.strip():
        pattern = re.escape(q.strip())
        brand_ids = [
            b["_id"] for b in db.catalog_brands.find({"name": {"$regex": pattern, "$options": "i"}})
        ]
        query["$or"] = [
            {"name": {"$regex": pattern, "$options": "i"}},
            {"brand_id": {"$in": brand_ids}},
        ]
    order = [("created_at", -1), ("_id", 1)] if sort == "newest" else [("name", 1), ("_id", 1)]
    # Missing assets are excluded at seed/publication time; the image endpoint fails closed.
    if q.strip() and sort == "relevance":
        # Exact product names rank first, then prefix matches, then substring/brand matches.
        rows = list(
            db.products.aggregate(
                [
                    {"$match": query},
                    {
                        "$addFields": {
                            "_rank": {
                                "$cond": [
                                    {"$eq": [{"$toLower": "$name"}, q.strip().lower()]},
                                    2,
                                    {
                                        "$cond": [
                                            {
                                                "$regexMatch": {
                                                    "input": "$name",
                                                    "regex": "^" + re.escape(q.strip()),
                                                    "options": "i",
                                                }
                                            },
                                            1,
                                            0,
                                        ]
                                    },
                                ]
                            }
                        }
                    },
                    {"$sort": {"_rank": -1, "name": 1, "_id": 1}},
                    {"$skip": offset},
                    {"$limit": limit},
                    {"$project": {"_rank": 0}},
                ]
            )
        )
    else:
        rows = list(db.products.find(query).sort(order).skip(offset).limit(limit))
    return {
        "items": [public_product(r, db) for r in rows],
        "total": db.products.count_documents(query),
        "offset": offset,
        "limit": limit,
    }


@router.get("/products/{product_id}")
def product(product_id: str, db=Depends(catalog_db)):
    row = db.products.find_one({"_id": product_id, **visible_query()})
    if not row:
        raise HTTPException(404, "Product is unavailable.")
    return public_product(row, db)


@router.get("/products/{product_id}/image")
def product_image(product_id: str, db=Depends(catalog_db)):
    row = db.products.find_one({"_id": product_id, **visible_query()})
    if not row:
        raise HTTPException(404, "Product is unavailable.")
    return FileResponse(image_path(row), headers={"Cache-Control": "public, max-age=3600"})


@router.get("/categories")
def categories(db=Depends(catalog_db)):
    return [{"id": r.pop("_id"), **r} for r in db.categories.find().sort("name", 1)]


@router.get("/brands")
def brands(db=Depends(catalog_db)):
    return [
        {
            "id": r["_id"],
            "name": r["name"],
            "partnership": False,
            "product_count": db.products.count_documents({"brand_id": r["_id"], **visible_query()}),
            "chart_count": db.brand_size_charts.count_documents({"brand_id": r["_id"]}),
        }
        for r in db.catalog_brands.find().sort("name", 1)
    ]


@router.put("/favorites/{product_id}", status_code=204)
def favorite(product_id: str, user=Depends(current_user), db=Depends(catalog_db)):
    product(product_id, db)
    db.favorites.update_one(
        {"user_id": user["_id"], "product_id": product_id},
        {"$setOnInsert": {"created_at": datetime.now(timezone.utc)}},
        upsert=True,
    )


@router.delete("/favorites/{product_id}", status_code=204)
def unfavorite(product_id: str, user=Depends(current_user), db=Depends(catalog_db)):
    db.favorites.delete_one({"user_id": user["_id"], "product_id": product_id})


@router.get("/favorites")
def favorites(
    limit: int = Query(12, ge=1, le=48),
    offset: int = Query(0, ge=0, le=10000),
    user=Depends(current_user),
    db=Depends(catalog_db),
):
    stages = [
        {"$match": {"user_id": user["_id"]}},
        {
            "$lookup": {
                "from": "products",
                "localField": "product_id",
                "foreignField": "_id",
                "as": "product",
            }
        },
        {"$unwind": "$product"},
        {"$match": {"product." + k: v for k, v in visible_query().items()}},
    ]
    total = list(db.favorites.aggregate(stages + [{"$count": "total"}]))
    rows = db.favorites.aggregate(
        stages
        + [{"$sort": {"created_at": -1, "product_id": 1}}, {"$skip": offset}, {"$limit": limit}]
    )
    return {
        "items": [public_product(r["product"], db) for r in rows],
        "total": total[0]["total"] if total else 0,
        "limit": limit,
        "offset": offset,
    }


class ProductPublication(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,79}$")
    name: str = Field(min_length=3, max_length=120)
    brand_id: str | None = None
    subcategory: str
    audience: Literal["men", "women", "unisex"]
    filename: str = Field(min_length=1, max_length=200)
    photoType: Literal["model", "flat-lay"]
    description: str = Field(min_length=3, max_length=1000)
    colors: list[str] = Field(min_length=1, max_length=20)
    sizes: list[str] = Field(default_factory=list, max_length=30)
    source_url: HttpUrl
    license: str = Field(min_length=5, max_length=500)
    commercial_use: bool = False
    active: bool = True


@router.put("/products/{product_id}")
def publish_product(
    product_id: str,
    data: ProductPublication,
    x_admin_token: str = Header(""),
    db=Depends(catalog_db),
):
    require_admin(x_admin_token)
    if product_id != data.id:
        raise HTTPException(422, "Product ID does not match its path.")
    category = db.categories.find_one({"_id": data.subcategory})
    if not category or not category["model_category"]:
        raise HTTPException(422, "This garment type is not supported for try-on.")
    if data.brand_id and not db.catalog_brands.find_one({"_id": data.brand_id}):
        raise HTTPException(422, "Unknown catalog brand.")
    row = data.model_dump(mode="json", exclude={"id"})
    from backend.app.online_vton import normalized_image

    path = image_path(row)
    if path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise HTTPException(422, "Catalog images must use JPEG, PNG or WebP filenames.")
    if path.stat().st_size > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, "Catalog image exceeds the upload limit.")
    normalized_image(path.read_bytes())
    row.update(
        category=category["model_category"], size_note="Consult the product's original size guide."
    )
    db.products.update_one(
        {"_id": product_id},
        {"$set": row, "$setOnInsert": {"created_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    return public_product(db.products.find_one({"_id": product_id}), db)
