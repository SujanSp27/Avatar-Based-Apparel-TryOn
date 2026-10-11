import pytest

from ml.errors import PipelineError
from ml.human.hmr2 import HMR2Reconstructor
from ml.human.template import MediaPipeTemplateReconstructor
from ml.measurement.service import measure_body


def test_missing_research_model_never_silently_falls_back():
    model = HMR2Reconstructor("", "", "")
    with pytest.raises(PipelineError) as error:
        model.reconstruct(None, 172)
    assert error.value.status_code == 503
    assert "SMPL_MODEL_PATH" in str(error.value)


@pytest.mark.integration
def test_height_calibration_scales_mesh_and_measurements(person_features, body):
    small = MediaPipeTemplateReconstructor().reconstruct(person_features, 155)
    actual = measure_body(small.mesh, small.landmarks)
    baseline = measure_body(body.mesh, body.landmarks)
    assert actual["height"] == 155
    assert actual["chest"] == pytest.approx(baseline["chest"] * 155 / 172, abs=0.3)


def test_storage_deletion_refuses_non_uuid(tmp_path):
    from backend.app.storage import AssetStore

    store = AssetStore(tmp_path)
    with pytest.raises(ValueError):
        store.delete("../something")
