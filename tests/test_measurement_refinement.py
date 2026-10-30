"""Real colour refinement with synthetic geometry; no anthropometric accuracy claims."""

import io
import json
from copy import deepcopy
from dataclasses import replace

import cv2
import numpy as np
import pytest
from PIL import Image

from backend.app.anthropometry.measurement_refinement import guard_refined_mask, merge_recovered
from backend.app.anthropometry.measurement_service import MeasurementService, estimate
from backend.app.anthropometry.pose_adapter import refine_mask
from backend.app.anthropometry.router import get_measurement_service
from backend.app.main import app
from ml.errors import PipelineError

pytest_plugins = ["test_anthropometry"]


def bridged_observation(observation):
    mask = observation.mask.astype(np.uint8)
    points = np.rint(observation.landmarks[:, :2] * [600, 1000]).astype(int)
    for a, b in ((11, 13), (13, 15), (12, 14), (14, 16)):
        cv2.line(mask, points[a], points[b], 1, 9)
    observation.landmarks[17:23, 3] = 0
    clean = mask.astype(bool)
    observation.image[:] = 245
    observation.image[clean] = 35
    observation.mask = clean.copy()
    observation.mask[300:500, 150:450] = True
    observation.probabilities = observation.mask.astype(np.float32)
    return observation, clean


def encode(image):
    stream = io.BytesIO()
    Image.fromarray(image).save(stream, format="PNG")
    return stream.getvalue()


def service_for(observation, tmp_path):
    class Detector:
        model_sha256 = "synthetic-geometry-only"
        def detect(self, image):
            return replace(observation, image=image)
    return MeasurementService(Detector(), tmp_path)


def test_confident_false_bridge_can_be_reclassified_by_real_image_evidence(observation):
    observation, clean = bridged_observation(observation)
    locked = refine_mask(observation.image, observation.probabilities, max_edge=1600)
    recovered = refine_mask(observation.image, observation.probabilities, max_edge=1600, reconsider_foreground=True)
    assert locked[400, 180] and not clean[400, 180]
    assert not recovered[400, 180] and recovered[400, 160] and recovered[400, 300]
    guarded = guard_refined_mask(observation, recovered)
    result, _ = estimate(replace(observation, mask=guarded), 160)
    assert result["measurements"]["chest_circumference"] == 98
    assert result["measurements"]["waist_circumference"] == 92


@pytest.mark.parametrize("small", [False, True])
def test_recovery_is_per_metric_reviewed_and_auditable(observation, tmp_path, small):
    observation, _ = bridged_observation(observation)
    if small:
        observation.image = cv2.resize(observation.image, (420, 700), interpolation=cv2.INTER_NEAREST)
        observation.mask = cv2.resize(observation.mask.astype(np.uint8), (420, 700), interpolation=cv2.INTER_NEAREST).astype(bool)
        observation.probabilities = observation.mask.astype(np.float32)
    baseline, _ = estimate(observation, 160)
    service = service_for(observation, tmp_path)
    response = service.extract(encode(observation.image), 160)
    for key, old in baseline["measurements"].items():
        if old is not None:
            assert getattr(response.measurements, key) == old
            assert response.quality["metrics"][key] == baseline["quality"]["metrics"][key]
    for key in ("chest_circumference", "waist_circumference"):
        assert baseline["measurements"][key] is None
        assert getattr(response.measurements, key) is not None
        info = response.quality["metrics"][key]
        assert info["reason"] == "image_refinement_estimate" and info["requires_manual_review"]
        assert info["confidence"] is None
        assert response.geometry["measurement_mask_sources"][key] == "image_guided"
    assert response.scale_factor == baseline["scale_factor"]
    assert not any("Chest circumference is unavailable" in message for message in response.warnings)
    artifacts = json.loads(service.artifact_path(response.measurement_id, ".json").read_text())
    assert artifacts["geometry"]["refinement_attempts"][-1]["recovered"]
    assert np.array_equal(np.array(Image.open(service.artifact_path(response.measurement_id, "_mask.png"))) > 0,
                          observation.mask)
    assert service.artifact_path(response.measurement_id, "_image_guided_mask.png").is_file()
    service.remove_artifacts(response.measurement_id)
    assert not list(tmp_path.iterdir())


def test_true_touching_region_does_not_become_an_invented_gap(observation, tmp_path):
    observation, _ = bridged_observation(observation)
    observation.image[observation.mask] = 35  # Actual foreground covers the bridge.
    response = service_for(observation, tmp_path).extract(encode(observation.image), 160)
    assert response.measurements.chest_circumference is None
    assert response.measurements.waist_circumference is None
    assert response.measurements.shoulder_width == 40
    assert not list(tmp_path.glob("*_image_guided_mask.png"))


def test_refinement_cannot_erase_an_observed_arm_to_make_a_clean_torso(observation):
    observation, clean = bridged_observation(observation)
    erased = clean.copy()
    erased[350:450, :190] = False
    with pytest.raises(PipelineError) as exc:
        guard_refined_mask(observation, erased)
    assert exc.value.code == "refinement_erased_pose_evidence"


def test_enclosed_background_coloured_fabric_cannot_make_an_outer_body_edge(observation):
    candidate = observation.mask.copy()
    candidate[300:400, 210:270] = False
    restored = guard_refined_mask(observation, candidate)
    assert np.array_equal(restored, observation.mask)


@pytest.mark.parametrize("bad", ["shape", "empty", "nan"])
def test_invalid_refinement_does_not_enter_measurements(observation, bad):
    candidate = (observation.mask[:200] if bad == "shape" else np.zeros_like(observation.mask)
                 if bad == "empty" else np.full(observation.mask.shape, np.nan))
    with pytest.raises(PipelineError, match="invalid"):
        guard_refined_mask(observation, candidate)


def test_merge_keeps_valid_hip_even_when_candidate_hip_is_worse(observation):
    original, original_lines = estimate(observation, 160)
    bridged, _ = bridged_observation(observation)
    baseline, lines = estimate(bridged, 160)
    candidate = deepcopy(original)
    candidate["measurements"]["hip_circumference"] = None
    merged, _, recovered = merge_recovered(baseline, lines, candidate, original_lines, "image_guided")
    assert recovered == ["chest_circumference", "waist_circumference"]
    assert merged["measurements"]["hip_circumference"] == baseline["measurements"]["hip_circumference"]
    assert merged["quality"]["metrics"]["hip_circumference"] == baseline["quality"]["metrics"]["hip_circumference"]
    assert baseline["measurements"]["chest_circumference"] is None  # No in-place edits.


def test_refinement_cannot_change_calibration(observation):
    baseline, lines = estimate(observation, 160)
    candidate = deepcopy(baseline)
    candidate["scale_factor"] *= 1.1
    with pytest.raises(PipelineError, match="calibration"):
        merge_recovered(baseline, lines, candidate, lines, "image_guided")


def test_recovered_values_still_require_explicit_tape_overrides(api, observation, tmp_path):
    client, _ = api
    observation, _ = bridged_observation(observation)
    previous = app.dependency_overrides[get_measurement_service]
    app.dependency_overrides[get_measurement_service] = lambda: service_for(observation, tmp_path)
    try:
        response = client.post("/api/v1/measurements/extract", data={"height_cm": 160},
                               files={"image": ("fixture.png", encode(observation.image), "image/png")})
        assert response.status_code == 200, response.text
        scan = response.json()
        assert scan["measurements"]["chest_circumference"] == 98
        payload = {"brand_id": "brand_b", "apparel_id": "apparel_all", "measurement_id": scan["measurement_id"]}
        denied = client.post("/api/v1/sizing/recommend", json=payload)
        assert denied.status_code == 422
        assert denied.json()["error"]["code"] == "measurement_review_required"
        payload["measurement_overrides"] = {"chest_circumference": 98, "waist_circumference": 92}
        assert client.post("/api/v1/sizing/recommend", json=payload).status_code == 200
        assert client.delete(f"/api/v1/measurements/{scan['measurement_id']}").status_code == 204
        assert not list(tmp_path.iterdir())
    finally:
        app.dependency_overrides[get_measurement_service] = previous


def test_failed_refinement_is_bounded_and_keeps_partial_results(observation, tmp_path, monkeypatch):
    observation, _ = bridged_observation(observation)
    baseline, _ = estimate(observation, 160)
    calls = []
    def failed(*args, **kwargs):
        calls.append(kwargs)
        raise PipelineError("segmentation_failed", "No reliable colour separation")
    monkeypatch.setattr("backend.app.anthropometry.measurement_service.refine_mask", failed)
    response = service_for(observation, tmp_path).extract(encode(observation.image), 160)
    assert response.measurements.model_dump() == baseline["measurements"]
    assert len(calls) == 2
    assert all(attempt["code"] == "segmentation_failed" for attempt in response.geometry["refinement_attempts"])


@pytest.mark.parametrize("region", ["hip", "thigh"])
def test_lower_region_retry_does_not_depend_on_a_chest_failure(observation, tmp_path, region):
    observation, clean = bridged_observation(observation)
    observation.mask = clean.copy()
    if region == "hip":
        observation.mask[490:505, 130:470] = True
    else:
        observation.mask[555:610, 210:390] = True
    observation.probabilities = observation.mask.astype(np.float32)
    baseline, _ = estimate(observation, 160)
    key = region + "_circumference"
    assert baseline["measurements"][key] is None
    assert baseline["measurements"]["chest_circumference"] == 98
    response = service_for(observation, tmp_path).extract(encode(observation.image), 160)
    assert getattr(response.measurements, key) == (96 if region == "hip" else 30)
    assert response.quality["metrics"][key]["requires_manual_review"]
    for other, value in baseline["measurements"].items():
        if other != key:
            assert getattr(response.measurements, other) == value
