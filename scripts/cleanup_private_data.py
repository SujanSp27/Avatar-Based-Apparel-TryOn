"""Remove expired owned processing artifacts; dry-run unless --apply is supplied.

Run with the API stopped (single-process deployment). Unowned legacy artifacts
are deliberately retained for an operator migration/review, never reassigned.
"""

import argparse
import json
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select

from backend.app.anthropometry.repository import get_repository
from backend.app.config import ROOT, settings
from backend.app.db import SessionLocal
from backend.app.models import Run
from backend.app.storage import AssetStore


def expired(owner, created, at):
    if not owner or not created:
        return False
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    age = (
        timedelta(hours=settings.guest_retention_hours)
        if owner.startswith("guest:")
        else timedelta(days=settings.private_retention_days)
    )
    return created + age < at


def cleanup(apply=False):
    at = datetime.now(timezone.utc)
    counts = {"runs": 0, "measurements": 0, "jobs": 0}
    with SessionLocal() as db:
        rows = db.scalars(select(Run).where(Run.status != "processing")).yield_per(100)
        for row in rows:
            if expired(row.metadata_json.get("owner"), row.created_at, at):
                counts["runs"] += 1
                if apply:
                    AssetStore(settings.asset_root).delete(str(UUID(row.id)))
                    db.delete(row)
        if apply:
            db.commit()
    repo = get_repository()
    root = (settings.measurement_output_root / "annotated").resolve()
    for item in repo.db.private_resources.find({"kind": "measurement"}).batch_size(100):
        if not expired(item.get("owner"), item.get("created_at"), at):
            continue
        from pydantic import TypeAdapter

        from backend.app.anthropometry.schemas import MeasurementId

        mid = TypeAdapter(MeasurementId).validate_python(item["resource_id"])
        counts["measurements"] += 1
        if apply:
            for path in root.glob(mid + "*"):
                if path.is_file() and path.resolve().is_relative_to(root):
                    path.unlink()
            repo.measurements.delete_one({"measurement_id": mid})
            repo.db.private_resources.delete_one({"_id": item["_id"]})
    for path in (ROOT / ".runtime/tryon-jobs").glob("*.json"):
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
            created = datetime.fromtimestamp(item["createdAt"], tz=timezone.utc)
            if item["status"] in {"success", "failed"} and expired(item.get("owner"), created, at):
                counts["jobs"] += 1
                if apply:
                    path.unlink()
        except (ValueError, KeyError, OSError):
            continue  # Preserve malformed records for operator review.
    print(json.dumps({"applied": apply, "expired": counts}))
    return counts


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    cleanup(parser.parse_args().apply)
