"""Regional evidence regressions, independent of gender labels or generated bodies."""
import copy

import numpy as np
import pytest

from backend.app.anthropometry.measurement_service import estimate
from backend.app.anthropometry.schemas import PhotoMeasurements
from ml.errors import PipelineError

pytest_plugins = ["test_anthropometry"]


@pytest.mark.parametrize("weak", [(29,), (30,), (29, 30), (29, 30, 31, 32)])
def test_uncertain_heels_use_observed_foot_evidence_without_coordinate_substitution(observation, weak):
    baseline, _ = estimate(observation, 160)
    observation.landmarks[list(weak), 3] = .1
    before = observation.landmarks.copy()
    result, _ = estimate(observation, 160)
    assert result["measurements"] == baseline["measurements"]
    assert result["scale_factor"] == baseline["scale_factor"]
    assert np.array_equal(before, observation.landmarks)
    assert result["quality"]["minimum_key_landmark_visibility"] == .1
    assert len(result["geometry"]["foot_evidence"]) == 2


@pytest.mark.parametrize("side", [0, 1])
def test_cropped_foot_mask_is_not_rescued_by_hallucinated_visible_heel(observation, side):
    x = 240 if side == 0 else 360
    observation.mask[900:, x - 30:x + 30] = True
    with pytest.raises(PipelineError) as exc:
        estimate(observation, 160)
    assert exc.value.code == "partial_body"


def test_short_occluded_foot_outline_cannot_calibrate(observation):
    observation.mask[902:, :] = False
    observation.landmarks[[29, 30, 31, 32], 3] = .1
    with pytest.raises(PipelineError) as exc:
        estimate(observation, 160)
    assert exc.value.code == "scale_unavailable"


@pytest.mark.parametrize("index", [25, 26, 11, 12, 23, 24])
def test_presence_is_used_without_modifying_visibility(observation, index):
    observation.presence = np.full(33, .99)
    observation.presence[index] = .1
    result, _ = estimate(observation, 160)
    affected = [q for q in result["quality"]["metrics"].values() if index in q["landmark_indices"]]
    assert all(q["requires_manual_review"] for q in affected)
    assert all(q["landmark_presence_min"] == .1 for q in affected)
    assert observation.landmarks[index, 3] == .99
    assert any(value is not None for value in result["measurements"].values())


@pytest.mark.parametrize("mode", ["merged", "dress", "missing-left", "narrow-gap", "local-touch"])
def test_thigh_geometry_is_local_and_does_not_erase_torso(observation, mode):
    if mode in ("merged", "dress"):
        observation.mask[530:700, 210:390] = True
    elif mode == "missing-left":
        observation.mask[560:610, 210:270] = False
    elif mode == "narrow-gap":
        observation.mask[530:650, 270:299] = True
        observation.mask[530:650, 301:330] = True
    else:
        observation.mask[577:584, 210:390] = True
    result, lines = estimate(observation, 160)
    assert result["measurements"]["chest_circumference"] == 98
    assert result["measurements"]["waist_circumference"] == 92
    info = result["quality"]["metrics"]["thigh_circumference"]
    if mode in ("merged", "dress"):
        assert result["measurements"]["thigh_circumference"] is None
        assert info["status"] == "unavailable"
        assert not any(name.startswith("thigh") for name, _ in lines)
    elif mode == "missing-left":
        assert result["measurements"]["thigh_circumference"] == 30
        assert info["status"] == "review_required"
        assert sum(s["status"] == "estimated" for s in info["sides"]) == 1
    else:
        assert result["measurements"]["thigh_circumference"] > 0
        assert info["status"] == "estimated"
        if mode == "local-touch":
            assert all(s["fraction"] == .38 for s in info["sides"])


@pytest.mark.parametrize("index", [15, 16])
def test_unknown_wrist_requires_actual_disconnected_arm_mask(observation, index):
    observation.landmarks[index, 3] = .2
    no_evidence, _ = estimate(observation, 160)
    assert no_evidence["measurements"]["chest_circumference"] is None
    # Real observed arm component is separate below the chest section.
    x = 160 if index == 15 else 440
    observation.mask[330:550, x - 8:x + 9] = True
    result, _ = estimate(observation, 160)
    assert result["measurements"]["chest_circumference"] == 98
    assert result["measurements"]["waist_circumference"] == 92
    # A touching forearm has no verified gap. Never cut an invented body contour.
    observation.mask[380:405, min(x, 300):max(x, 300) + 1] = True
    joined, _ = estimate(observation, 160)
    assert joined["measurements"]["chest_circumference"] is None


def test_hip_uses_visible_outer_edges_not_skeletal_joint_spacing(observation):
    result, _ = estimate(observation, 160)
    assert result["measurements"]["hip_circumference"] == 96
    assert result["measurements"]["hip_circumference"] != 57.6
    observation.mask[495:510, 290:310] = False
    partial, _ = estimate(observation, 160)
    assert partial["measurements"]["hip_circumference"] is None
    assert partial["measurements"]["shoulder_width"] == 40


@pytest.mark.parametrize("height,width_factor", [(145, .8), (172, 1), (200, 1.2)])
def test_body_proportions_share_geometry_without_gender_classifier(observation, height, width_factor):
    original = copy.deepcopy(observation)
    observation.landmarks[[11, 12], 0] = .5 + (observation.landmarks[[11, 12], 0] - .5) * width_factor
    result, _ = estimate(observation, height)
    assert result["measurements"]["shoulder_width"] == pytest.approx(200 * width_factor * height / 800, abs=.01)
    assert np.array_equal(original.mask, observation.mask)
    assert all(q["confidence"] is None for q in result["quality"]["metrics"].values())
    PhotoMeasurements.model_validate(result["measurements"])


def test_out_of_frame_shoulder_does_not_become_numeric_success(observation):
    observation.landmarks[11, 0] = -.1
    result, _ = estimate(observation, 160)
    assert result["measurements"]["shoulder_width"] is None
    assert result["measurements"]["chest_circumference"] is None
    assert result["measurements"]["thigh_circumference"] == 30
    chest_warning = next(w for w in result["warnings"] if w.startswith("Chest circumference is unavailable"))
    assert "Shoulders or hips" in chest_warning
    assert "separated from the arms" not in chest_warning


def test_partial_scan_contract_rejects_zero_and_exposes_all_six_keys():
    values = PhotoMeasurements()
    assert len(values.model_dump()) == 6
    with pytest.raises(ValueError):
        PhotoMeasurements(thigh_circumference=0)


@pytest.mark.parametrize("separation", [80, 160])
def test_separated_and_wider_stances_keep_observed_thigh_boundaries(observation, separation):
    # Move complete vertical leg fixtures; never synthesize missing inner edges.
    observation.mask[530:] = False
    for sign, ids in ((-1, [23, 25, 27, 29, 31]), (1, [24, 26, 28, 30, 32])):
        x = 300 + sign * separation / 2
        observation.landmarks[ids, 0] = x / 600
        observation.mask[530:930, int(x) - 30:int(x) + 30] = True
    result, _ = estimate(observation, 160)
    assert result["measurements"]["thigh_circumference"] == 30
    assert result["quality"]["metrics"]["thigh_circumference"]["status"] == "estimated"


def test_thigh_rejection_cannot_be_used_as_a_saved_complete_measurement(api, observation):
    from test_torso_measurements import upload
    client, _ = api
    observation.mask[530:650, 210:390] = True
    response = client.post("/api/v1/measurements/extract", data={"height_cm": 160}, files=upload())
    assert response.status_code == 200
    scan = response.json()
    assert scan["measurements"]["thigh_circumference"] is None
    assert scan["measurements"]["chest_circumference"] == 98
    payload = {"brand_id": "brand_b", "apparel_id": "apparel_all", "measurement_id": scan["measurement_id"]}
    denied = client.post("/api/v1/sizing/recommend", json=payload)
    assert denied.status_code == 422
    assert denied.json()["error"]["code"] == "measurement_review_required"
    payload["measurement_overrides"] = {"thigh_circumference": 52}
    assert client.post("/api/v1/sizing/recommend", json=payload).status_code == 200


@pytest.mark.parametrize("kind", ["missing-face", "invalid-presence", "cropped-head"])
def test_invalid_calibration_evidence_is_not_a_partial_success(observation, kind):
    if kind == "missing-face":
        observation.landmarks[:11, 3] = .1
        code = "scale_unavailable"
    elif kind == "invalid-presence":
        observation.presence = np.full(33, np.nan)
        code = "invalid_pose"
    else:
        observation.mask[:300, 290:310] = True
        code = "partial_body"
    with pytest.raises(PipelineError) as exc:
        estimate(observation, 160)
    assert exc.value.code == code


def test_unconnected_mask_speck_at_top_does_not_invalidate_calibration(observation):
    observation.mask[0, 0] = True
    result, _ = estimate(observation, 160)
    assert result["scale_factor"] == .2
    assert result["measurements"]["shoulder_width"] == 40


@pytest.mark.integration
def test_existing_female_mirror_photos_keep_region_limits_and_heel_fallback(tmp_path):
    from backend.app.anthropometry.measurement_service import MeasurementService
    from backend.app.anthropometry.pose_adapter import MediaPipePose
    from backend.app.config import ROOT, settings
    root = ROOT / "data/raw/fashn-samples"
    if not settings.measurement_model_path.is_file() or not all((root / name).is_file() for name in ("person1.png", "person5.png")):
        pytest.skip("Pinned official demonstration photos and CPU pose checkpoint required")
    service = MeasurementService(MediaPipePose(settings.measurement_model_path), tmp_path)
    try:
        # Two public upstream examples, local evaluation only. See their existing
        # source/rights manifest; neither has tape-measure ground truth.
        scan = service.extract((root / "person5.png").read_bytes(), 172)
        assert scan.quality["minimum_key_landmark_visibility"] < .65
        assert scan.measurements.shoulder_width > 0
        assert scan.measurements.hip_circumference > 0
        assert scan.measurements.inseam_length > 0
        assert scan.measurements.chest_circumference is None  # Raised arms cross torso.
        assert scan.measurements.waist_circumference is None
        assert scan.measurements.thigh_circumference is None  # No inner thigh gap.
        assert set(scan.quality["requires_manual_review"]) == {
            "chest_circumference", "waist_circumference", "thigh_circumference"}
        assert scan.provenance["local_gpu_used"] is False
        assert len(scan.landmark_presence) == 33
        with pytest.raises(PipelineError) as exc:
            service.extract((root / "person1.png").read_bytes(), 172)
        assert exc.value.code == "scale_unavailable"  # Dress/boot occlusion, uncertain ankle.
    finally:
        service.detector.close()
