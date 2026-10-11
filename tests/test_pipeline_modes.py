import copy
from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.app.charts import seed_database
from backend.app.db import Base
from backend.app.models import Run
from backend.app.pipeline import TryOnPipeline
from backend.app.storage import AssetStore
from ml.errors import PipelineError
from ml.preprocessing.images import save_features

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def mode_pipeline(tmp_path, monkeypatch, person_features):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    pipeline = TryOnPipeline(AssetStore(tmp_path / "assets"))
    portrait = copy.deepcopy(person_features)
    portrait.landmarks[[27, 28, 31, 32], 1] = 1.5
    portrait.landmarks[[27, 28, 31, 32], 3] = 0.01

    def detect(_, folder):
        save_features(portrait, folder, "person")
        return portrait

    monkeypatch.setattr(pipeline.person, "detect", detect)

    # Isolate orchestration/persistence from expensive pretrained inference.
    # Actual model quality is tested by scripts/validate_pretrained_vton.py.
    def neural_response(store, run_id, person, garment_data, category, fit, reason):
        Image.new("RGB", (16, 16), "blue").save(store.folder(run_id) / "tryon-2d.png")
        return {
            "mode": "2d",
            "renderingMethod": "pretrained-vton",
            "fit": fit,
            "fallbackReason": reason,
            "recommendedSize": None,
            "measurements": None,
            "avatarUrl": None,
            "bodyUrl": None,
            "garmentUrl": None,
            "score": None,
            "fitting": None,
            "provenance": {"backend": "unit-test-double"},
            "artifacts": {},
        }

    monkeypatch.setattr("backend.app.pipeline.photo_result", neural_response)
    with Session(engine, expire_on_commit=False) as db:
        seed_database(db)
        yield pipeline, db, tmp_path
    engine.dispose()


def run(pipeline, db, **kwargs):
    return pipeline.run(
        db,
        b"injected pose fixture",
        (ROOT / "data/raw/garment-demo.png").read_bytes(),
        1,
        "t-shirt",
        "regular",
        172,
        **kwargs,
    )


@pytest.mark.integration
def test_auto_fallback_persists_neural_response_without_fake_size_or_mesh(mode_pipeline):
    pipeline, db, _ = mode_pipeline
    result = run(pipeline, db)
    assert result["mode"] == "2d"
    assert result["renderingMethod"] == "pretrained-vton"
    assert result["fallbackReason"]["code"] == "partial_body"
    assert result["recommendedSize"] is None and result["measurements"] is None
    assert result["avatarUrl"] is None and result["bodyUrl"] is None
    assert result["score"] is None and result["fitting"] is None
    folder = pipeline.store.folder(result["runId"])
    assert (folder / "tryon-2d.png").read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert not (folder / "body.glb").exists()
    assert db.get(Run, result["runId"]).status == "success"


@pytest.mark.integration
def test_explicit_3d_keeps_strict_full_body_validation(mode_pipeline):
    pipeline, db, _ = mode_pipeline
    with pytest.raises(PipelineError) as error:
        run(pipeline, db, mode="3d")
    assert error.value.code == "partial_body"
    assert list(pipeline.store.root.glob("*/failure.json"))
    assert not list(pipeline.store.root.glob("*/tryon-2d.png"))


@pytest.mark.integration
def test_explicit_2d_has_no_failed_3d_claim(mode_pipeline):
    pipeline, db, _ = mode_pipeline
    result = run(pipeline, db, mode="2d")
    assert result["mode"] == "2d" and result["fallbackReason"] is None
    assert result["requestedMode"] == "2d"


@pytest.mark.integration
def test_auto_does_not_hide_unexpected_errors(mode_pipeline, monkeypatch):
    pipeline, db, _ = mode_pipeline

    def broken(_):
        raise RuntimeError("Unexpected defect")

    monkeypatch.setattr(pipeline.person, "validate_pose", broken)
    with pytest.raises(PipelineError) as error:
        run(pipeline, db)
    assert error.value.code == "internal_error"
    assert not list(pipeline.store.root.glob("*/tryon-2d.png"))


@pytest.mark.integration
def test_input_write_failure_does_not_leave_run_processing(mode_pipeline, monkeypatch):
    pipeline, db, _ = mode_pipeline
    original = Path.write_bytes

    def fail_input(path, data):
        if path.name == "personInput.bin":
            raise OSError("Input write failed")
        return original(path, data)

    monkeypatch.setattr(Path, "write_bytes", fail_input)
    with pytest.raises(PipelineError) as error:
        run(pipeline, db)
    assert error.value.code == "internal_error"
    record = db.scalar(select(Run))
    assert record.status == "failed"
    assert (pipeline.store.folder(record.id) / "failure.json").is_file()


@pytest.mark.integration
def test_final_commit_failure_removes_success_manifest(mode_pipeline, monkeypatch):
    pipeline, db, _ = mode_pipeline
    original = db.commit
    count = 0

    def commit():
        nonlocal count
        count += 1
        if count == 2:
            raise RuntimeError("Final commit failed")
        return original()

    monkeypatch.setattr(db, "commit", commit)
    with pytest.raises(PipelineError) as error:
        run(pipeline, db, mode="2d")
    assert error.value.code == "internal_error"
    record = db.scalar(select(Run))
    assert record.status == "failed"
    folder = pipeline.store.folder(record.id)
    assert (folder / "failure.json").is_file()
    assert not (folder / "result.json").exists()


@pytest.mark.integration
def test_pretrained_failure_never_invokes_legacy_overlay(mode_pipeline, monkeypatch):
    pipeline, db, _ = mode_pipeline

    def unavailable(*args, **kwargs):
        raise PipelineError(
            "vton_model_unavailable", "Checkpoint missing; no overlay allowed.", 503
        )

    def forbidden(*args, **kwargs):
        pytest.fail("An overlay must never replace failed pretrained inference")

    monkeypatch.setattr("backend.app.pipeline.photo_result", unavailable)
    monkeypatch.setattr("ml.tryon2d.service.render_tryon_2d", forbidden)
    with pytest.raises(PipelineError) as error:
        run(pipeline, db, mode="auto")
    assert error.value.code == "vton_model_unavailable"
    assert error.value.status_code == 503
    assert not list(pipeline.store.root.glob("*/tryon-2d.png"))
    assert db.scalar(select(Run)).status == "failed"
