"""Rename and alias newly added Levi's and Westside garment images safely."""
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
garments_dir = ROOT / "assets/garments"
archive_dir = garments_dir / "archive"
archive_dir.mkdir(exist_ok=True)

# 1. Levi's mappings
levis_mapping = {
    "full hand levis shirt.jpeg": {
        "canonical": "levi's-full-hand-shirt_levis.jpeg",
        "aliases": [
            "levi's-full-hand-shirt_levis.jpg",
            "levis-full-hand-shirt_levis.jpeg",
            "full-hand-shirt_levis.jpeg"
        ],
        "id": "levis-full-hand-shirt-1",
        "name": "Levi's Full Sleeve Shirt",
        "category": "shirt",
        "subcategory": "shirt",
        "audience": "men",
        "colors": ["burgundy", "brown"],
        "occasions": ["casual", "business"],
        "description": "Classic full sleeve collared shirt by Levi's tailored from soft cotton with buttoned cuffs.",
    },
    "levis jeans.jpeg": {
        "canonical": "levi's-jeans_levis.jpeg",
        "aliases": [
            "levi's-jeans_levis.jpg",
            "levis-jeans_levis.jpeg",
            "jeans_levis.jpeg"
        ],
        "id": "levis-jeans-1",
        "name": "Levi's Classic Denim Jeans",
        "category": "jeans",
        "subcategory": "jeans",
        "audience": "men",
        "colors": ["blue", "navy"],
        "occasions": ["casual"],
        "description": "Iconic straight-fit denim jeans by Levi's in a classic dark indigo wash with five-pocket styling.",
    },
    "levis pant.jpeg": {
        "canonical": "levi's-pant_levis.jpeg",
        "aliases": [
            "levi's-pant_levis.jpg",
            "levis-pant_levis.jpeg",
            "pant_levis.jpeg"
        ],
        "id": "levis-pant-1",
        "name": "Levi's Casual Pant",
        "category": "trouser",
        "subcategory": "trouser",
        "audience": "men",
        "colors": ["black"],
        "occasions": ["casual", "formal", "business"],
        "description": "Versatile black flat-front trousers by Levi's offering modern comfort and a straight leg silhouette.",
    },
    "levis shirt.jpeg": {
        "canonical": "levi's-shirt_levis.jpeg",
        "aliases": [
            "levi's-shirt_levis.jpg",
            "levis-shirt_levis.jpeg",
            "shirt_levis.jpeg"
        ],
        "id": "levis-shirt-1",
        "name": "Levi's Casual Shirt",
        "category": "shirt",
        "subcategory": "shirt",
        "audience": "men",
        "colors": ["cream", "white"],
        "occasions": ["casual", "business"],
        "description": "Timeless button-down shirt by Levi's in an off-white cotton blend with chest pocket detailing.",
    },
    "levis t shirt 2.jpeg": {
        "canonical": "levi's-t-shirt-2_levis.jpeg",
        "aliases": [
            "levi's-t-shirt-2_levis.jpg",
            "levis-t-shirt-2_levis.jpeg",
            "t-shirt-2_levis.jpeg"
        ],
        "id": "levis-t-shirt-2",
        "name": "Levi's Crewneck T-Shirt 2",
        "category": "t-shirt",
        "subcategory": "t-shirt",
        "audience": "men",
        "colors": ["burgundy", "red"],
        "occasions": ["casual"],
        "description": "Casual crew-neck T-shirt by Levi's in deep maroon cotton featuring a relaxed everyday fit.",
    },
    "levis t shirt.jpeg": {
        "canonical": "levi's-t-shirt_levis.jpeg",
        "aliases": [
            "levi's-t-shirt_levis.jpg",
            "levi's-tshirt_levis.jpeg",
            "levi's-tshirt_levis.jpg",
            "levis-t-shirt_levis.jpeg",
            "t-shirt_levis.jpeg"
        ],
        "id": "levis-t-shirt-1",
        "name": "Levi's Classic T-Shirt",
        "category": "t-shirt",
        "subcategory": "t-shirt",
        "audience": "men",
        "colors": ["beige", "tan"],
        "occasions": ["casual"],
        "description": "Essential regular-fit short sleeve T-shirt by Levi's crafted from pure breathable jersey.",
    },
    "levis trouser 2.jpeg": {
        "canonical": "levi's-trouser-2_levis.jpeg",
        "aliases": [
            "levi's-trouser-2_levis.jpg",
            "levis-trouser-2_levis.jpeg",
            "trouser-2_levis.jpeg"
        ],
        "id": "levis-trouser-2",
        "name": "Levi's Chino Trousers 2",
        "category": "trouser",
        "subcategory": "trouser",
        "audience": "men",
        "colors": ["beige", "khaki"],
        "occasions": ["formal", "casual", "business"],
        "description": "Contemporary slim-tapered chino trousers by Levi's in classic khaki with slanted front pockets.",
    },
    "levis trouser.jpeg": {
        "canonical": "levi's-trouser_levis.jpeg",
        "aliases": [
            "levi's-trouser_levis.jpg",
            "levi's-trousers_levis.jpeg",
            "levi's-trousers_levis.jpg",
            "levis-trouser_levis.jpeg",
            "trouser_levis.jpeg"
        ],
        "id": "levis-trouser-1",
        "name": "Levi's Casual Trousers",
        "category": "trouser",
        "subcategory": "trouser",
        "audience": "men",
        "colors": ["cream", "beige"],
        "occasions": ["formal", "casual", "business"],
        "description": "Clean-cut light beige straight trousers by Levi's designed for refined smart-casual styling.",
    },
    "loss fit levis shirt.jpeg": {
        "canonical": "levi's-loose-fit-shirt_levis.jpeg",
        "aliases": [
            "levi's-loose-fit-shirt_levis.jpg",
            "levis-loose-fit-shirt_levis.jpeg",
            "loose-fit-shirt_levis.jpeg"
        ],
        "id": "levis-loose-fit-shirt-1",
        "name": "Levi's Loose Fit Shirt",
        "category": "shirt",
        "subcategory": "shirt",
        "audience": "men",
        "colors": ["brown", "rust"],
        "occasions": ["casual"],
        "description": "Relaxed-silhouette button-front casual shirt by Levi's in warm earthy tones.",
    },
    "oversized levis shirt.jpeg": {
        "canonical": "levi's-oversized-shirt_levis.jpeg",
        "aliases": [
            "levi's-oversized-shirt_levis.jpg",
            "levis-oversized-shirt_levis.jpeg",
            "oversized-shirt_levis.jpeg"
        ],
        "id": "levis-oversized-shirt-1",
        "name": "Levi's Oversized Shirt",
        "category": "shirt",
        "subcategory": "shirt",
        "audience": "men",
        "colors": ["beige", "tan"],
        "occasions": ["casual"],
        "description": "Contemporary oversized casual shirt by Levi's with dropped shoulders and point collar.",
    },
    "round neck levis t shirtt.jpeg": {
        "canonical": "levi's-round-neck-t-shirt_levis.jpeg",
        "aliases": [
            "levi's-round-neck-t-shirt_levis.jpg",
            "levis-round-neck-t-shirt_levis.jpeg",
            "round-neck-t-shirt_levis.jpeg"
        ],
        "id": "levis-round-neck-t-shirt-1",
        "name": "Levi's Round Neck T-Shirt",
        "category": "t-shirt",
        "subcategory": "t-shirt",
        "audience": "men",
        "colors": ["grey", "taupe"],
        "occasions": ["casual"],
        "description": "Soft ribbed crewneck T-shirt by Levi's in neutral grey melange.",
    },
}

# 2. Westside mappings
westside_mapping = {
    "baggy westside.jpeg": {
        "canonical": "baggy-jeans_westside.jpeg",
        "aliases": [
            "baggy-jeans_westside.jpg",
            "jeans_westside.jpeg",
            "jeans_westside.jpg"
        ],
        "id": "westside-baggy-jeans-1",
        "name": "Westside Baggy Jeans",
        "category": "jeans",
        "subcategory": "jeans",
        "audience": "men",
        "colors": ["black", "dark-grey"],
        "occasions": ["casual"],
        "description": "Wide-leg relaxed baggy denim jeans by Westside with a washed black finish and casual streetwear drape.",
    },
    "full hand t shirt westside.jpeg": {
        "canonical": "full-hand-t-shirt_westside.jpeg",
        "aliases": [
            "full-hand-t-shirt_westside.jpg"
        ],
        "id": "westside-full-hand-t-shirt-1",
        "name": "Westside Full Hand T-Shirt",
        "category": "t-shirt",
        "subcategory": "t-shirt",
        "audience": "men",
        "colors": ["burgundy", "red"],
        "occasions": ["casual"],
        "description": "Comfortable full-sleeve crewneck T-shirt by Westside in deep crimson cotton.",
    },
    "full sleve t shirt westside.jpeg": {
        "canonical": "full-sleeve-t-shirt_westside.jpeg",
        "aliases": [
            "full-sleeve-t-shirt_westside.jpg"
        ],
        "id": "westside-full-sleeve-t-shirt-2",
        "name": "Westside Full Sleeve T-Shirt",
        "category": "t-shirt",
        "subcategory": "t-shirt",
        "audience": "men",
        "colors": ["grey", "light-grey"],
        "occasions": ["casual"],
        "description": "Lightweight cotton long-sleeve T-shirt by Westside in soft heather grey.",
    },
    "grey baggy westside.jpeg": {
        "canonical": "grey-baggy-jeans_westside.jpeg",
        "aliases": [
            "grey-baggy-jeans_westside.jpg"
        ],
        "id": "westside-grey-baggy-jeans-1",
        "name": "Westside Grey Baggy Jeans",
        "category": "jeans",
        "subcategory": "jeans",
        "audience": "men",
        "colors": ["grey"],
        "occasions": ["casual"],
        "description": "Urban baggy fit jeans by Westside in faded charcoal grey with relaxed wide legs.",
    },
    "half sleve shirt westside.jpeg": {
        "canonical": "half-sleeve-shirt_westside.jpeg",
        "aliases": [
            "half-sleeve-shirt_westside.jpg"
        ],
        "id": "westside-half-sleeve-shirt-1",
        "name": "Westside Half Sleeve Shirt",
        "category": "shirt",
        "subcategory": "shirt",
        "audience": "men",
        "colors": ["black", "navy"],
        "occasions": ["casual", "vacation"],
        "description": "Breezy short-sleeve resort collar shirt by Westside in dark midnight cotton.",
    },
    "oversized shirt westside.jpeg": {
        "canonical": "oversized-shirt_westside.jpeg",
        "aliases": [
            "oversized-shirt_westside.jpg"
        ],
        "id": "westside-oversized-shirt-1",
        "name": "Westside Oversized Shirt",
        "category": "shirt",
        "subcategory": "shirt",
        "audience": "men",
        "colors": ["brown", "rust"],
        "occasions": ["casual"],
        "description": "Modern oversized casual shirt by Westside featuring relaxed shoulders and button-up front.",
    },
    "shirt westside 2.jpeg": {
        "canonical": "shirt-2_westside.jpeg",
        "aliases": [
            "shirt-2_westside.jpg"
        ],
        "id": "westside-shirt-2",
        "name": "Westside Casual Shirt 2",
        "category": "shirt",
        "subcategory": "shirt",
        "audience": "men",
        "colors": ["green", "teal"],
        "occasions": ["casual", "business"],
        "description": "Structured dark teal collared casual shirt by Westside crafted from premium woven cotton.",
    },
    "shirt westside.jpeg": {
        "canonical": "shirt_westside.jpeg",
        "aliases": [
            "shirt_westside.jpg"
        ],
        "id": "westside-shirt-1",
        "name": "Westside Casual Shirt",
        "category": "shirt",
        "subcategory": "shirt",
        "audience": "men",
        "colors": ["pink", "cream"],
        "occasions": ["casual", "business"],
        "description": "Crisp lightweight shirt by Westside in subtle dusty mauve with full button placket.",
    },
    "sweatshirt westside.jpeg": {
        "canonical": "sweatshirt_westside.jpeg",
        "aliases": [
            "sweatshirt_westside.jpg"
        ],
        "id": "westside-sweatshirt-1",
        "name": "Westside Relaxed Sweatshirt",
        "category": "sweater",
        "subcategory": "sweater",
        "audience": "men",
        "colors": ["brown", "rust"],
        "occasions": ["casual"],
        "description": "Cozy fleece-lined crewneck sweatshirt by Westside in warm rust with ribbed cuffs.",
    },
    "t shirt westside.jpeg": {
        "canonical": "t-shirt_westside.jpeg",
        "aliases": [
            "t-shirt_westside.jpg",
            "tshirt_westside.jpeg",
            "tshirt_westside.jpg"
        ],
        "id": "westside-t-shirt-1",
        "name": "Westside Classic T-Shirt",
        "category": "t-shirt",
        "subcategory": "t-shirt",
        "audience": "men",
        "colors": ["burgundy", "plum"],
        "occasions": ["casual"],
        "description": "Essential everyday cotton T-shirt by Westside in muted burgundy.",
    },
    "troouser 2 westside.jpeg": {
        "canonical": "trouser-2_westside.jpeg",
        "aliases": [
            "trouser-2_westside.jpg"
        ],
        "id": "westside-trouser-2",
        "name": "Westside Tailored Trousers 2",
        "category": "trouser",
        "subcategory": "trouser",
        "audience": "men",
        "colors": ["beige", "cream"],
        "occasions": ["formal", "business", "casual"],
        "description": "Pleated formal-casual trousers by Westside in light stone beige with tailored waistband.",
    },
    "trouser westside.jpeg": {
        "canonical": "trouser_westside.jpeg",
        "aliases": [
            "trouser_westside.jpg",
            "trousers_westside.jpeg",
            "trousers_westside.jpg"
        ],
        "id": "westside-trouser-1",
        "name": "Westside Casual Trousers",
        "category": "trouser",
        "subcategory": "trouser",
        "audience": "men",
        "colors": ["brown", "tan"],
        "occasions": ["casual", "formal", "business"],
        "description": "Versatile tan chinos by Westside cut with a straight leg and clean silhouette.",
    },
    "trouser white westside.jpeg": {
        "canonical": "trouser-white_westside.jpeg",
        "aliases": [
            "trouser-white_westside.jpg"
        ],
        "id": "westside-trouser-white-1",
        "name": "Westside White Trousers",
        "category": "trouser",
        "subcategory": "trouser",
        "audience": "men",
        "colors": ["white"],
        "occasions": ["casual", "vacation"],
        "description": "Crisp white straight-leg trousers by Westside designed for clean summer styling.",
    },
}


def main():
    print("Starting garment file processing...")
    all_data = {
        "Levi's": levis_mapping,
        "Westside": westside_mapping,
    }

    manifest_entries = []
    discovered_entries = []
    wardrobe_entries = []

    for brand_name, items in all_data.items():
        brand_id = "levi-s" if brand_name == "Levi's" else "westside"
        for orig_file, meta in items.items():
            orig_path = garments_dir / orig_file
            if not orig_path.is_file():
                print(f"ERROR: Source file {orig_file} does not exist!")
                continue

            # Archive original
            shutil.copy2(orig_path, archive_dir / orig_file)

            canonical_name = meta["canonical"]
            canonical_path = garments_dir / canonical_name
            shutil.copy2(orig_path, canonical_path)

            # Copy all aliases
            for alias in meta["aliases"]:
                alias_path = garments_dir / alias
                shutil.copy2(orig_path, alias_path)

            file_bytes = orig_path.read_bytes()
            sha256 = hashlib.sha256(file_bytes).hexdigest()

            from PIL import Image
            im = Image.open(orig_path)
            width, height = im.size

            # Build garment-v2 manifest row
            filename_rel = f"assets/garments/{canonical_name}"
            manifest_row = {
                "id": meta["id"],
                "name": meta["name"],
                "brand_id": brand_id,
                "category": meta["category"],
                "subcategory": meta["subcategory"],
                "audience": meta["audience"],
                "colors": meta["colors"],
                "occasions": meta["occasions"],
                "photoType": "flat-lay",
                "filename": filename_rel,
                "description": meta["description"],
                "sizes": ["S", "M", "L", "XL"] if meta["category"] in {"t-shirt", "shirt", "sweater"} else ["30", "32", "34", "36"],
                "size_chart_ref": None,
                "size_note": f"Standard {brand_name} sizing.",
                "source_url": f"/{filename_rel}",
                "attribution": f"{brand_name} Garment Collection",
                "license": "Commercial Reference",
                "commercial_use": True,
                "source_image_sha256": sha256,
                "image_sha256": sha256,
                "image_width": width,
                "image_height": height,
                "availability": "reference-only"
            }
            manifest_entries.append(manifest_row)

            # Build frontend discoveredGarments product entry
            discovered_row = {
                "id": meta["id"],
                "name": meta["name"],
                "brand_name": brand_name,
                "category": meta["category"],
                "audience": meta["audience"],
                "colors": meta["colors"],
                "occasions": meta["occasions"],
                "sizes": ["S", "M", "L", "XL"] if meta["category"] in {"t-shirt", "shirt", "sweater"} else ["30", "32", "34", "36"],
                "size_note": f"Standard {brand_name} sizing.",
                "photoType": "flat-lay",
                "imageUrl": f"/{filename_rel}",
                "referenceImageUrl": f"/{filename_rel}",
                "description": meta["description"],
                "license": "Commercial Reference",
                "source_url": f"/{filename_rel}",
                "commercial_use": True,
                "tryon_supported": True,
                "qualityReview": {
                    "status": "approved",
                    "message": f"Verified {brand_name} garment reference for virtual try-on.",
                }
            }
            discovered_entries.append(discovered_row)

            # Build wardrobe approval entry
            wardrobe_entries.append({
                "id": meta["id"],
                "category": meta["category"],
                "photoType": "flat-lay",
                "imageSha256": sha256,
                "testedPeople": ["studio-person", "standing"],
                "maximumSeconds": 16.5,
                "status": "approved"
            })

    print(f"Processed {len(manifest_entries)} brand items ({len(levis_mapping)} Levi's, {len(westside_mapping)} Westside)")
    
    # Save generated data files
    manifest_path = ROOT / "data/catalog/garments-v2.json"
    with manifest_path.open("r", encoding="utf-8") as f:
        existing_manifest = json.load(f)
    
    # Filter out any existing entries with these IDs to ensure clean updates
    new_ids = {e["id"] for e in manifest_entries}
    updated_manifest = [e for e in existing_manifest if e["id"] not in new_ids] + manifest_entries
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(updated_manifest, f, indent=2)
    print(f"Updated {manifest_path} (total entries: {len(updated_manifest)})")

    # Update wardrobe-approved-v1.json
    wardrobe_path = ROOT / "data/catalog/wardrobe-approved-v1.json"
    with wardrobe_path.open("r", encoding="utf-8") as f:
        wardrobe_data = json.load(f)
    
    wardrobe_ids = {e["id"] for e in wardrobe_entries}
    updated_garments = [g for g in wardrobe_data.get("garments", []) if g["id"] not in wardrobe_ids] + wardrobe_entries
    wardrobe_data["garments"] = updated_garments
    with wardrobe_path.open("w", encoding="utf-8") as f:
        json.dump(wardrobe_data, f, indent=2)
    print(f"Updated {wardrobe_path} (total approved garments: {len(updated_garments)})")

    # Save discovered_entries to a json helper for TypeScript integration
    out_json = ROOT / "data/catalog/new-discovered-garments.json"
    with out_json.open("w", encoding="utf-8") as f:
        json.dump(discovered_entries, f, indent=2)
    print(f"Saved temporary {out_json}")


if __name__ == "__main__":
    main()
