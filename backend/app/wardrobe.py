"""Evidence-backed wardrobe publication, independent of broad model categories.

Publication is staged until twenty individually reviewed garments pass. Source
records and assets are never deleted. Changed images/metadata invalidate approval.
"""
import hashlib
import json
from functools import lru_cache
from pathlib import Path

from backend.app.config import ROOT
from ml.errors import PipelineError
from ml.vton.categories import MODEL_CATEGORIES

POLICY_PATH = ROOT / "data/catalog/wardrobe-approved-v1.json"


@lru_cache(maxsize=4)
def _read_policy(path: str, stamp: int):
    policy = json.loads(Path(path).read_text(encoding="utf-8"))
    entries = policy.get("garments", [])
    if (policy.get("version") != 1 or not isinstance(policy.get("enforced"), bool)
            or not isinstance(entries, list) or len({r["id"] for r in entries}) != len(entries)
            or (policy["enforced"] and len(entries) != 20)):
        raise ValueError("Invalid wardrobe publication")
    for row in entries:
        if (row.get("status") != "approved" or row.get("category") not in MODEL_CATEGORIES
                or row.get("photoType") not in {"model", "flat-lay"}
                or len(row.get("imageSha256", "")) != 64 or len(row.get("testedPeople", [])) < 2):
            raise ValueError("Incomplete garment approval")
    return policy


def policy():
    try:
        return _read_policy(str(POLICY_PATH), POLICY_PATH.stat().st_mtime_ns)
    except (OSError, ValueError, KeyError, TypeError):
        # A broken manifest must never silently republish unreviewed garments.
        return {"version": 1, "enforced": True, "garments": [], "error": "Wardrobe review data is unavailable."}


@lru_cache(maxsize=256)
def _source_hash(path: str, stamp: int, size: int):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def approval(row):
    data = policy()
    record = next((r for r in data["garments"] if r["id"] == row["_id"]), None)
    if row.get("category") not in MODEL_CATEGORIES:
        return {"status": "unsupported", "message": "This garment has no supported single-garment model mapping."}
    if not record:
        return {"status": "unreviewed", "message": "Individual garment quality has not yet passed the two-person evaluation."}
    root = (ROOT / "data/raw").resolve()
    path = (root / row["filename"]).resolve()
    try:
        stat = path.stat()
        valid = (path.is_relative_to(root) and row["category"] == record["category"]
                 and row["photoType"] == record["photoType"]
                 and _source_hash(str(path), stat.st_mtime_ns, stat.st_size) == record["imageSha256"])
    except OSError:
        valid = False
    if not valid:
        return {"status": "stale", "message": "The garment changed after review and must be retested."}
    return {"status": "approved", "message": "Passed the recorded test people; other poses and details may vary.",
            "testedPeople": record["testedPeople"], "maximumSeconds": record["maximumSeconds"]}


def validate_catalog_submission(db, product_id: str, garment: bytes, category: str, photo_type: str):
    row = db.products.find_one({"_id": product_id, "active": True})
    if not row:
        raise PipelineError("garment_unavailable", "This catalog garment is unavailable.", 404)
    data = policy()
    if row.get("category") not in MODEL_CATEGORIES or (data["enforced"] and approval(row)["status"] != "approved"):
        raise PipelineError("garment_not_approved", "This garment has not passed wardrobe review. Choose an approved garment.", 422)
    path = (ROOT / "data/raw" / row["filename"]).resolve()
    if not path.is_relative_to((ROOT / "data/raw").resolve()) or not path.is_file():
        raise PipelineError("garment_unavailable", "The catalog image is unavailable.", 404)
    if (category != row["category"] or photo_type != row["photoType"]
            or hashlib.sha256(garment).digest() != hashlib.sha256(path.read_bytes()).digest()):
        raise PipelineError("garment_input_mismatch", "The selected garment, photo type or category changed. Select the garment again.", 422)
