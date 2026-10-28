"""Allowlisted real garment inputs. These images are never generated results."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from backend.app.config import ROOT, settings

router = APIRouter(prefix="/api/garments", tags=["Garment catalog"])
GARMENTS = [
    ("navy-tee", "Navy crew-neck T-shirt", "t-shirt", "model", "navy-tee.jpg", "Clean neckline · deep navy"),
    ("sage-polo", "Sage pique polo", "t-shirt", "flat-lay", "sage-polo.jpg", "Structured collar · soft sage"),
    ("navy-blouse", "Navy broderie blouse", "blouse", "flat-lay", "fashn-samples/garment3.jpeg", "Textured cotton · flutter sleeves"),
    ("coral-dress", "Coral ruched dress", "dress", "model", "fashn-samples/garment1.jpeg", "Gathered silhouette · short sleeves"),
    ("navy-gown", "Midnight evening dress", "dress", "model", "fashn-samples/garment6.webp", "Embellished evening silhouette"),
    ("ivory-skirt", "Ivory tiered skirt", "skirt", "flat-lay", "fashn-samples/garment5.jpeg", "Soft tiers · delicate texture"),
]


def visible_legacy(row):
    # The old route must not republish references excluded by wardrobe review.
    from backend.app.wardrobe import approval, policy
    if settings.environment == "production":
        return False
    return (ROOT / "data/raw" / row[4]).is_file() and (
        not policy()["enforced"] or approval({"_id": row[0], "category": row[2],
            "photoType": row[3], "filename": row[4]})["status"] == "approved")


@router.get("")
def list_garments():
    if settings.environment == "production":
        return {"items": []}  # Only the licensed, database-backed catalog is published.
    return {"items": [
        {"id": key, "name": name, "category": category, "photoType": photo_type,
         "imageUrl": f"/api/garments/{key}/image", "description": description}
        for key, name, category, photo_type, filename, description in GARMENTS
        if visible_legacy((key, name, category, photo_type, filename, description))
    ]}


@router.get("/{garment_id}/image")
def garment_image(garment_id: str):
    if settings.environment == "production":
        raise HTTPException(404, "Research garment references are not published in production.")
    row = next((item for item in GARMENTS if item[0] == garment_id), None)
    if row is None or not visible_legacy(row):
        raise HTTPException(404, "This garment is not available. Upload a garment photo instead.")
    return FileResponse(ROOT / "data/raw" / row[4], headers={"Cache-Control": "no-cache, must-revalidate"})
