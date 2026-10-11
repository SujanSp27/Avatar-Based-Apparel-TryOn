import hashlib
import logging
import time
from uuid import uuid4

import psutil
import trimesh
from sqlalchemy.orm import Session

from backend.app.charts import chart_dict, latest_chart
from backend.app.config import settings
from backend.app.models import Brand, ChartVersion, Run
from backend.app.photo_tryon import photo_result
from backend.app.storage import AssetStore
from ml.errors import PipelineError
from ml.fitting.service import fit_garment
from ml.garment.templates import reconstruct_garment
from ml.human.hmr2 import HMR2Reconstructor
from ml.human.template import MediaPipeTemplateReconstructor
from ml.measurement.service import measure_body
from ml.preprocessing.images import ImageFeatures, PersonPreprocessor, preprocess_garment
from ml.preview import render_preview
from ml.sizing.engine import recommend

logger = logging.getLogger(__name__)

# Only known 3D limitations qualify for automatic fallback. Decode, person count,
# missing pose checkpoint, storage/database errors and programming bugs still fail.
FALLBACK_CODES = {
    "partial_body",
    "occluded_body",
    "extreme_pose",
    "low_resolution",
    "garment_background",
    "invalid_body_mesh",
    "missing_section",
    "open_section",
    "anatomical_section",
    "merged_chest_section",
    "fitting_failed",
    "template_union_failed",
    "hmr2_unavailable",
    "hmr2_not_validated",
}


class TryOnPipeline:
    def __init__(self, asset_store: AssetStore):
        self.store = asset_store
        self.person = PersonPreprocessor(settings.model_path)
        if settings.human_backend == "mediapipe_template":
            self.human = MediaPipeTemplateReconstructor()
        elif settings.human_backend == "hmr2":
            self.human = HMR2Reconstructor(
                settings.hmr2_root, settings.hmr2_checkpoint, settings.smpl_model_path
            )
        else:
            raise ValueError(f"Unknown HUMAN_BACKEND {settings.human_backend}")

    def run(
        self,
        db: Session,
        person_data: bytes,
        garment_data: bytes,
        brand_id: int,
        category: str,
        fit: str,
        height_cm: float | None,
        dimensions: dict | None = None,
        mode: str = "auto",
    ) -> dict:
        if mode not in {"auto", "3d", "2d"}:
            raise PipelineError("tryon_mode", "Choose auto, 3d or 2d mode.")
        chart = latest_chart(db, brand_id, category)
        chart_data = chart_dict(chart)
        run_id = str(uuid4())
        folder = self.store.create(run_id)
        start = time.perf_counter()
        stage = "preprocessing"
        timings = {}
        metadata = {
            "modelVersion": getattr(self.human, "version", settings.human_backend),
            "checkpoint": str(settings.model_path),
            "checkpointSha256": hashlib.sha256(settings.model_path.read_bytes()).hexdigest()
            if settings.model_path.is_file()
            else None,
            "inputSha256": {
                "person": hashlib.sha256(person_data).hexdigest(),
                "garment": hashlib.sha256(garment_data).hexdigest(),
            },
            "brandId": brand_id,
            "garmentCategory": category,
            "fitPreference": fit,
            "heightCm": height_cm or 170.0,
            "heightAssumed": height_cm is None,
            "chart": chart_data,
            "requestedMode": mode,
        }
        record = Run(id=run_id, status="processing", chart_id=chart.id, metadata_json=metadata)
        db.add(record)
        db.commit()
        person = None
        try:
            (folder / "personInput.bin").write_bytes(person_data)
            (folder / "garmentInput.bin").write_bytes(garment_data)
            self.store.write_json(run_id, "input.json", metadata)
            tick = time.perf_counter()
            person = self.person.detect(person_data, folder)
            if mode == "2d":
                timings[stage] = time.perf_counter() - tick
                stage = "2d_pretrained_tryon"
                return self._photo_result(
                    db,
                    record,
                    metadata,
                    person,
                    garment_data,
                    category,
                    fit,
                    chart,
                    timings,
                    start,
                    None,
                )
            self.person.validate_pose(person)
            garment_features = preprocess_garment(garment_data, folder)
            timings[stage] = time.perf_counter() - tick
            stage, tick = "human_reconstruction", time.perf_counter()
            body = self.human.reconstruct(person, height_cm or 170.0)
            for extension in ("obj", "ply", "glb"):
                body.mesh.export(folder / f"body.{extension}")
            self.store.write_json(run_id, "bodyParameters.json", body.parameters)
            timings[stage] = time.perf_counter() - tick
            stage, tick = "measurements_and_sizing", time.perf_counter()
            measurements = measure_body(body.mesh, body.landmarks)
            sizing = recommend(measurements, chart_data["sizes"], category, fit)
            self.store.write_json(run_id, "measurements.json", measurements)
            selected = next(
                r for r in chart_data["sizes"] if r["sizeLabel"] == sizing["recommendedSize"]
            )
            timings[stage] = time.perf_counter() - tick
            stage, tick = "garment_reconstruction", time.perf_counter()
            garment = reconstruct_garment(
                garment_features, category, body, measurements, selected, fit, dimensions
            )
            garment.mesh.export(folder / "garment-template.glb")
            self.store.write_json(run_id, "garmentParameters.json", garment.parameters)
            timings[stage] = time.perf_counter() - tick
            stage, tick = "fitting_and_deformation", time.perf_counter()
            fitted, fitting = fit_garment(body.mesh, garment)
            fitted.export(folder / "garment.glb")
            self.store.write_json(run_id, "fitting.json", fitting)
            timings[stage] = time.perf_counter() - tick
            stage, tick = "export_and_preview", time.perf_counter()
            scene = trimesh.Scene()
            scene.add_geometry(body.mesh, node_name="body", geom_name="body")
            scene.add_geometry(fitted, node_name="garment", geom_name="garment")
            scene.export(folder / "dressed.glb")
            loaded = trimesh.load(folder / "dressed.glb", force="scene")
            if len(loaded.geometry) < 2:
                raise PipelineError(
                    "export_failed", "GLB reload failed; no result was published.", 500
                )
            for view in ("front", "side", "back"):
                render_preview([body.mesh, fitted], folder / f"preview-{view}.png", view)
            timings[stage] = time.perf_counter() - tick
            warnings = person.warnings + [
                "Approximate pose-conditioned body template; not a recovered SMPL body or validated measurement.",
                "Depth is assumed from template proportions; single-image circumferences can be inaccurate.",
                "Back garment texture repeats front fabric. Seams and cloth material physics are not reconstructed.",
            ]
            if height_cm is None:
                warnings.append(
                    "Height was not supplied; 170 cm was assumed for every physical dimension."
                )
            if sizing["outOfRange"]:
                warnings.append(
                    "The closest size does not contain all target measurements; check the chart before choosing clothing."
                )
            if fitting["remainingPenetrationSamples"]:
                warnings.append(
                    "Small residual garment/body intersections remain in sampled collision checks."
                )
            names = [
                "body.obj",
                "body.ply",
                "bodyParameters.json",
                "measurements.json",
                "garmentParameters.json",
                "fitting.json",
                "personMask.png",
                "personCrop.png",
                "garmentMask.png",
                "garmentCrop.png",
                "poseKeypoints.json",
                "preview-front.png",
                "preview-side.png",
                "preview-back.png",
            ]
            result = {
                "status": "success",
                "mode": "3d",
                "requestedMode": mode,
                "fallbackReason": None,
                "runId": run_id,
                "brandId": brand_id,
                "brandName": db.get(Brand, brand_id).name,
                "garmentCategory": category,
                **sizing,
                "measurements": measurements,
                "avatarUrl": self.store.url(run_id, "dressed.glb"),
                "bodyUrl": self.store.url(run_id, "body.glb"),
                "garmentUrl": self.store.url(run_id, "garment.glb"),
                "previewUrl": self.store.url(run_id, "preview-front.png"),
                "chartVersion": chart.version,
                "chartSource": chart.source,
                "provenance": body.provenance,
                "warnings": warnings,
                "fitting": fitting,
                "timingSeconds": round(time.perf_counter() - start, 3),
                "timings": timings,
                "memoryRssMB": round(psutil.Process().memory_info().rss / 1024**2, 1),
                "artifacts": {name: self.store.url(run_id, name) for name in names},
            }
            result["artifacts"]["result"] = f"/assets/{run_id}/result.json"
            self.store.write_json(run_id, "result.json", result)
            record.status = "success"
            record.metadata_json = {**metadata, "result": result}
            db.commit()
            return result
        except Exception as exc:
            if (
                mode == "auto"
                and person is not None
                and isinstance(exc, PipelineError)
                and exc.code in FALLBACK_CODES
            ):
                reason = {"code": exc.code, "message": str(exc), "stage": stage}
                timings.setdefault(stage, time.perf_counter() - tick)
                logger.info("Run %s switching from 3D to 2D: %s", run_id, exc.code)
                metadata["fallbackReason"] = reason
                stage = "2d_pretrained_tryon"
                try:
                    return self._photo_result(
                        db,
                        record,
                        metadata,
                        person,
                        garment_data,
                        category,
                        fit,
                        chart,
                        timings,
                        start,
                        reason,
                    )
                except Exception as fallback_error:
                    exc = fallback_error
            db.rollback()
            error = {
                "status": "failed",
                "runId": run_id,
                "stage": stage,
                "code": getattr(exc, "code", "internal_error"),
                "message": str(exc)
                if isinstance(exc, PipelineError)
                else "Unexpected pipeline failure; inspect local server log.",
                "model": metadata,
                "timings": timings,
                "timingSeconds": round(time.perf_counter() - start, 3),
            }
            try:
                # A failed final DB commit must not leave a published success manifest.
                (folder / "result.json").unlink(missing_ok=True)
                self.store.write_json(run_id, "failure.json", error)
            except OSError:
                logger.exception("Could not save failure artifacts for %s", run_id)
            record = db.get(Run, run_id)
            record.status = "failed"
            record.metadata_json = error
            db.commit()
            logger.error(
                "Pipeline run %s failed at %s",
                run_id,
                stage,
                exc_info=(type(exc), exc, exc.__traceback__),
            )
            if isinstance(exc, PipelineError):
                raise PipelineError(exc.code, f"{exc} (Run {run_id})", exc.status_code) from exc
            raise PipelineError(
                "internal_error", f"Pipeline failed at {stage}. Run {run_id}; see local logs.", 500
            ) from exc

    def _photo_result(
        self,
        db: Session,
        record: Run,
        metadata: dict,
        person: ImageFeatures,
        garment_data: bytes,
        category: str,
        fit: str,
        chart: ChartVersion,
        timings: dict,
        start: float,
        fallback_reason: dict | None,
    ) -> dict:
        tick = time.perf_counter()
        result = photo_result(
            self.store, record.id, person, garment_data, category, fit, fallback_reason
        )
        timings["2d_pretrained_tryon"] = time.perf_counter() - tick
        result.update(
            {
                "status": "success",
                "runId": record.id,
                "requestedMode": metadata["requestedMode"],
                "brandId": metadata["brandId"],
                "brandName": db.get(Brand, metadata["brandId"]).name,
                "garmentCategory": category,
                "chartVersion": chart.version,
                "chartSource": chart.source,
                "timings": timings,
                "timingSeconds": round(time.perf_counter() - start, 3),
                "memoryRssMB": round(psutil.Process().memory_info().rss / 1024**2, 1),
            }
        )
        result["artifacts"]["result"] = f"/assets/{record.id}/result.json"
        metadata["configuredHumanModelVersion"] = metadata["modelVersion"]
        metadata["modelVersion"] = result["provenance"]["backend"]
        metadata["outputMode"] = "2d"
        self.store.write_json(record.id, "input.json", metadata)
        self.store.write_json(record.id, "result.json", result)
        record.status = "success"
        record.metadata_json = {**metadata, "result": result}
        db.commit()
        return result
