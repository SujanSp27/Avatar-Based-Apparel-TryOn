"""Persist actual photo results from the online GPU; no local ML inference."""
import hashlib
import logging
import time
from uuid import uuid4

from sqlalchemy.orm import Session

from backend.app.models import Brand, Run
from backend.app.online_vton import OnlineTryOn
from backend.app.storage import AssetStore
from ml.errors import PipelineError

logger = logging.getLogger(__name__)


class TryOnPipeline:
    def __init__(self, asset_store: AssetStore, worker=None):
        self.store = asset_store
        self.worker = worker or OnlineTryOn()

    def run(self, db: Session, person_data: bytes, garment_data: bytes,
            brand_id: int | None, category: str, fit: str = "regular",
            photo_type: str = "flat-lay") -> dict:
        run_id = str(uuid4())
        folder = self.store.create(run_id)
        start = time.perf_counter()
        metadata = {
            "modelVersion": "FASHN VTON 1.5", "execution": "online-gpu-only",
            "inputSha256": {"person": hashlib.sha256(person_data).hexdigest(),
                            "garment": hashlib.sha256(garment_data).hexdigest()},
            "brandId": brand_id, "garmentCategory": category, "garmentPhotoType": photo_type,
            "fitPreference": fit,
        }
        record = Run(id=run_id, status="processing", chart_id=None, metadata_json=metadata)
        db.add(record)
        db.commit()
        try:
            (folder / "personInput.bin").write_bytes(person_data)
            (folder / "garmentInput.bin").write_bytes(garment_data)
            self.store.write_json(run_id, "input.json", metadata)
            diagnostics = self.worker.render(person_data, garment_data, category, photo_type, folder)
            brand = db.get(Brand, brand_id) if brand_id else None
            result = {
                "status": "success", "mode": "2d", "renderingMethod": "pretrained-vton",
                "runId": run_id, "brandId": brand_id, "brandName": brand.name if brand else None,
                "garmentCategory": category, "fit": fit, "recommendedSize": None,
                "measurements": None, "score": None, "explanation": {}, "candidates": [],
                "chartVersion": None, "previewUrl": self.store.url(run_id, "tryon-2d.png"),
                "originalUrl": self.store.url(run_id, "original-person.png"),
                "provenance": {"backend": "FASHN VTON 1.5", "execution": "online-gpu-only",
                               "localGpuUsed": False, "weights": diagnostics},
                "timingSeconds": round(time.perf_counter() - start, 3),
                "timings": {"remoteRoundTrip": diagnostics.get("remoteRoundTripSeconds"),
                            "gpuGeneration": diagnostics.get("inferenceSeconds")},
                "warnings": [
                    "Generated on your connected Colab GPU. Queue, network and cold model loading affect latency.",
                    "Inspect patterns, neckline, sleeves and hem. Clothing realism is not guaranteed for every outfit.",
                    "Face, hair and unrelated regions are restored using semantic masks; segmentation errors can affect boundaries.",
                    "Image generation does not determine physical fit or size. The separate size engine needs measured dimensions.",
                ],
                "artifacts": {name: self.store.url(run_id, name) for name in
                              ("tryon-2d.png", "original-person.png", "vton-diagnostics.json")},
            }
            result["artifacts"]["result"] = f"/assets/{run_id}/result.json"
            self.store.write_json(run_id, "result.json", result)
            record.status = "success"
            record.metadata_json = {**metadata, "result": result}
            db.commit()
            return result
        except Exception as exc:
            db.rollback()
            (folder / "result.json").unlink(missing_ok=True)
            failure = {"status": "failed", "runId": run_id,
                       "code": getattr(exc, "code", "internal_error"),
                       "message": str(exc) if isinstance(exc, PipelineError) else "Unexpected pipeline failure; inspect server logs.",
                       "model": metadata, "timingSeconds": round(time.perf_counter() - start, 3)}
            self.store.write_json(run_id, "failure.json", failure)
            record = db.get(Run, run_id)
            record.status = "failed"
            record.metadata_json = failure
            db.commit()
            logger.exception("Online try-on %s failed", run_id)
            if isinstance(exc, PipelineError):
                raise PipelineError(exc.code, f"{exc} (Run {run_id})", exc.status_code) from exc
            raise PipelineError("internal_error", f"Try-on failed. Run {run_id}; inspect server logs.", 500) from exc
