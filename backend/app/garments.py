"""Allowlisted real garment inputs. These images are never generated results."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from backend.app.config import ROOT

router = APIRouter(prefix="/api/garments", tags=["Garment catalog"])
GARMENTS = [
    ("sage-polo", "Sage pique polo", "t-shirt", "flat-lay", "sage-polo.jpg", "Structured collar · soft sage"),
    ("navy-blouse", "Navy broderie blouse", "blouse", "flat-lay", "fashn-samples/garment3.jpeg", "Textured cotton · flutter sleeves"),
    ("coral-dress", "Coral ruched dress", "dress", "model", "fashn-samples/garment1.jpeg", "Gathered silhouette · short sleeves"),
    ("navy-gown", "Midnight evening dress", "dress", "model", "fashn-samples/garment6.webp", "Embellished evening silhouette"),
    ("ivory-skirt", "Ivory tiered skirt", "skirt", "flat-lay", "fashn-samples/garment5.jpeg", "Soft tiers · delicate texture"),
]


@router.get("")
def list_garments():
    return {"items": [
        {"id": key, "name": name, "category": category, "photoType": photo_type,
         "imageUrl": f"/api/garments/{key}/image", "description": description}
        for key, name, category, photo_type, filename, description in GARMENTS
        if (ROOT / "data/raw" / filename).is_file()
    ]}


@router.get("/{garment_id}/image")
def garment_image(garment_id: str):
    row = next((item for item in GARMENTS if item[0] == garment_id), None)
    if row is None or not (ROOT / "data/raw" / row[4]).is_file():
        raise HTTPException(404, "This garment is not available. Upload a garment photo instead.")
    return FileResponse(ROOT / "data/raw" / row[4])
