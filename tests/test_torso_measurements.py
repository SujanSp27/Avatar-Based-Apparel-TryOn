"""Torso ambiguity must not become either whole-scan failure or a fabricated size."""

import io
import json
from dataclasses import replace

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import ValidationError

from backend.app.anthropometry.measurement_service import (
    MeasurementService,
    estimate,
    intersects_arm,
)
from backend.app.anthropometry.pose_adapter import (
    decode_person,
    normalize_probabilities,
    refine_mask,
)
from backend.app.anthropometry.schemas import Measurements, PhotoMeasurements
from backend.app.main import app
from ml.errors import PipelineError

pytest_plugins = ["test_anthropometry"]


def upload():
    stream = io.BytesIO()
    Image.new("RGB", (600, 1000), "white").save(stream, format="PNG")
    return {"image": ("person.png", stream.getvalue(), "image/png")}


def test_adjacent_arm_with_visible_gap_does_not_change_width(observation):
    # The gap, not a distance-to-skeleton cut, is evidence of the body edge.
    observation.mask[300:490, 173:198] = True
    result, _ = estimate(observation, 160)
    assert result["measurements"]["chest_circumference"] == 98
    assert result["quality"]["requires_manual_review"] == []


def test_local_waist_band_recovers_real_gap_without_shifting_to_hips(observation):
    observation.mask[372:379, 150:450] = True
    result, _ = estimate(observation, 160)
    assert result["geometry"]["waist_torso_fraction"] == .48
    assert result["measurements"]["waist_circumference"] == 92


def test_overlap_returns_partial_measurements_not_arm_inclusive_circumferences(observation):
    observation.mask[300:500, 150:450] = True
    result, sections = estimate(observation, 160)
    assert result["measurements"]["shoulder_width"] == 40
    assert result["measurements"]["chest_circumference"] is None
    assert result["measurements"]["waist_circumference"] is None
    assert all(not name.startswith(("chest", "waist")) for name, _ in sections)
    assert set(result["quality"]["requires_manual_review"]) == {"chest_circumference", "waist_circumference"}
    PhotoMeasurements.model_validate(result["measurements"])
    with pytest.raises(ValidationError):
        Measurements.model_validate(result["measurements"])


def test_collinear_crossed_forearm_is_an_overlap(observation):
    points = observation.landmarks[:, :2] * [600, 1000]
    points[13], points[15] = [180, 375], [420, 375]
    assert intersects_arm((np.array([200, 375]), np.array([400, 375])), points, observation.landmarks[:, 3])


@pytest.mark.parametrize("index", [13, 14, 15, 16])
def test_unreliable_optional_arm_landmark_needs_review_not_pose_rejection(observation, index):
    observation.landmarks[index, 3] = .4
    result, _ = estimate(observation, 160)
    assert result["quality"]["metrics"]["chest_circumference"]["reason"] == "arm_landmarks_uncertain"
    assert result["measurements"]["chest_circumference"] is None
    assert result["measurements"]["shoulder_width"] == 40


def test_out_of_frame_arm_is_unknown_not_a_cut_through_torso(observation):
    observation.landmarks[15, 0] = -0.1
    result, _ = estimate(observation, 160)
    assert result["quality"]["metrics"]["chest_circumference"]["reason"] == "arm_landmarks_uncertain"


def widen_outline(observation):
    # Raised arms stay outside the observed torso. Width alone cannot identify
    # a body shape versus loose clothing, so retain the silhouette with review.
    observation.landmarks[[13, 14], :2] = np.array([[70, 230], [530, 230]]) / [600, 1000]
    observation.landmarks[[15, 16], :2] = np.array([[60, 220], [540, 220]]) / [600, 1000]
    observation.mask[280:490, 120:480] = True


def test_wide_or_layered_outline_is_uncertain_not_declared_body_measurement(observation):
    widen_outline(observation)
    result, _ = estimate(observation, 160)
    assert result["measurements"]["chest_circumference"] == 176.4
    info = result["quality"]["metrics"]["chest_circumference"]
    assert info["status"] == "review_required" and info["reason"] == "wide_clothing_outline"
    assert "body shape" in info["message"]


@pytest.mark.parametrize("kind,code", [("dimensions", "invalid_mask"), ("probabilities", "invalid_mask"),
                                      ("empty", "segmentation_missing"), ("central-hole", "torso_segmentation_failed")])
def test_bad_segmentation_does_not_become_partial_success(observation, kind, code):
    if kind == "dimensions":
        observation.mask = observation.mask[::2]
    elif kind == "probabilities":
        observation.mask = observation.mask.astype(float) * .7
    elif kind == "empty":
        observation.mask[:] = False
    else:
        observation.mask[280:490, 290:310] = False
    if kind == "central-hole":
        result, _ = estimate(observation, 160)
        assert result["measurements"]["chest_circumference"] is None
        assert result["measurements"]["waist_circumference"] is None
        assert result["quality"]["metrics"]["chest_circumference"]["reason"] == code
        assert result["measurements"]["shoulder_width"] == 40
        assert result["measurements"]["thigh_circumference"] == 30
    else:
        with pytest.raises(PipelineError) as exc:
            estimate(observation, 160)
        assert exc.value.code == code


def test_probability_map_resize_does_not_transpose_axes_or_use_logits():
    prior = np.zeros((100, 60, 1), np.float32)
    prior[20:80, 20:40] = 1
    resized = normalize_probabilities(prior, (1000, 600))
    assert resized.shape == (1000, 600)
    assert resized[500, 300] == 1 and resized[50, 300] == 0
    for bad in [np.ones((3, 3)) * 255, np.full((3, 3), np.nan), np.ones(30)]:
        with pytest.raises(PipelineError):
            normalize_probabilities(bad, (100, 60))


def test_exif_orientation_and_downscale_use_same_pixel_space():
    source = Image.new("RGB", (2000, 1000), "white")
    exif = Image.Exif()
    exif[274] = 6
    encoded = io.BytesIO()
    source.save(encoded, format="JPEG", exif=exif)
    assert decode_person(encoded.getvalue()).shape == (1600, 800, 3)


def test_refinement_preserves_real_narrow_gap_and_output_dimensions():
    image = np.full((1200, 600, 3), 245, np.uint8)
    image[100:1000, 200:400] = 35
    image[300:800, 155:195] = 35
    prior = np.zeros((1200, 600), np.float32)
    prior[100:1000, 200:400] = 1
    prior[300:800, 155:200] = .8
    output = refine_mask(image, prior, max_edge=1600)
    assert output.shape == image.shape[:2]
    assert output[550, 180] and output[550, 300] and not output[550, 197]
    assert np.array_equal(output, refine_mask(image, prior, max_edge=1600))


def test_refinement_retry_only_accepts_observed_usable_boundaries(observation, tmp_path, monkeypatch):
    original_mask = observation.mask.copy()
    observation.mask[300:500, 150:450] = True
    observation.probabilities = original_mask.astype(np.float32)
    class Detector:
        model_sha256 = "test"
        def detect(self, image):
            return replace(observation, image=image)
    calls = []
    def refined(image, prior, *, max_edge):
        calls.append(max_edge)
        return original_mask
    monkeypatch.setattr("backend.app.anthropometry.measurement_service.refine_mask", refined)
    service = MeasurementService(Detector(), tmp_path)
    response = service.extract(upload()["image"][1], 160)
    assert calls == [1600] and response.measurements.chest_circumference == 98


def test_api_partial_scan_blocks_sizing_until_specific_tape_overrides(api, repository, observation):
    client, _ = api
    observation.mask[300:500, 150:450] = True
    response = client.post("/api/v1/measurements/extract", data={"height_cm": 160}, files=upload())
    assert response.status_code == 200, response.text
    scan = response.json()
    assert len(scan["landmarks_normalized"]) == 33 and scan["measurements"]["chest_circumference"] is None
    assert client.get(f"/api/v1/measurements/{scan['measurement_id']}/annotation").status_code == 200
    payload = {"brand_id": "brand_b", "apparel_id": "apparel_all", "measurement_id": scan["measurement_id"]}
    denied = client.post("/api/v1/sizing/recommend", json=payload)
    assert denied.status_code == 422 and denied.json()["error"]["code"] == "measurement_review_required"
    payload["measurement_overrides"] = {"chest_circumference": 98}
    assert client.post("/api/v1/sizing/recommend", json=payload).status_code == 422
    payload["measurement_overrides"]["waist_circumference"] = 92
    assert client.post("/api/v1/sizing/recommend", json=payload).status_code == 200
    stranger = TestClient(app)
    try:
        assert stranger.post("/api/v1/sizing/recommend", json=payload).status_code in (401, 404)
    finally:
        stranger.close()
    # Never mutate the stored image estimates to look confirmed.
    assert repository.get_measurement(scan["measurement_id"]).measurements.chest_circumference is None


def test_combined_endpoint_preserves_scan_when_sizing_needs_review(api, observation):
    client, _ = api
    widen_outline(observation)
    response = client.post("/api/v1/measurements/extract-and-recommend", data={
        "height_cm": 160, "brand_id": "brand_b", "apparel_id": "apparel_all",
    }, files=upload())
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["recommendation"] is None
    assert result["recommendation_error"]["code"] == "measurement_review_required"
    identifier = result["extraction"]["measurement_id"]
    assert client.get(f"/api/v1/measurements/{identifier}/annotation").status_code == 200


def test_saved_size_uses_same_quality_and_ownership_gate(api, observation):
    client, _ = api
    assert client.post("/api/v1/auth/signup", json={"name": "Torso Test", "email": "torso@example.com",
        "password": "Torso!Test12345", "terms_accepted": True}).status_code == 201
    widen_outline(observation)
    response = client.post("/api/v1/measurements/extract", data={"height_cm": 160}, files=upload())
    identifier = response.json()["measurement_id"]
    payload = {"brand_id": "brand_b", "apparel_id": "apparel_all", "measurement_id": identifier}
    assert client.post("/api/v1/profile/sizes", json=payload).status_code == 422
    payload["measurement_overrides"] = {"chest_circumference": 98, "waist_circumference": 92}
    saved = client.post("/api/v1/profile/sizes", json=payload)
    assert saved.status_code == 201, saved.text
    assert saved.json()["result"]["measurement_id"] == identifier
    stranger = TestClient(app)
    try:
        assert stranger.post("/api/v1/auth/signup", json={"name": "Other Test", "email": "other@example.com",
            "password": "Torso!Test12345", "terms_accepted": True}).status_code == 201
        assert stranger.post("/api/v1/profile/sizes", json=payload).status_code == 404
    finally:
        stranger.close()


@pytest.mark.integration
def test_real_fitted_shirt_across_resolutions_keeps_valid_torso(tmp_path):
    from backend.app.anthropometry.measurement_service import torso_sections, validate_pose
    from backend.app.anthropometry.pose_adapter import MediaPipePose
    from backend.app.config import ROOT, settings
    photo = ROOT / "data/raw/studio-person.jpg"
    if not settings.measurement_model_path.is_file() or not photo.is_file():
        pytest.skip("Local CPU pose checkpoint and credited sample required")
    service = MeasurementService(MediaPipePose(settings.measurement_model_path), tmp_path)
    try:
        for width in (400, 800):
            image = Image.open(photo).convert("RGB")
            image.thumbnail((width, width * 2))
            encoded = io.BytesIO()
            image.save(encoded, format="PNG")
            observation = service.detector.detect(decode_person(encoded.getvalue()))
            points = validate_pose(observation)
            widths, _, quality, _ = torso_sections(observation, points)
            scale = 172 / (points[[27, 28], 1].max() - points[:11, 1].min())
            assert len(observation.landmarks) == 33
            assert all(not q["requires_manual_review"] for q in quality.values())
            assert widths["chest"] * scale * 2.45 < 110
            assert widths["waist"] * scale * 2.3 < 100
            assert observation.mask.shape == observation.image.shape[:2]
    finally:
        service.detector.close()


def test_structured_diagnostics_omit_upload_content_and_failure_cause_is_logged(api, observation, caplog):
    caplog.set_level("INFO", logger="vastraview.measurements")
    client, _ = api
    assert client.post("/api/v1/measurements/extract", data={"height_cm": 160}, files=upload()).status_code == 200
    observation.landmarks[27, 3] = .5
    assert client.post("/api/v1/measurements/extract", data={"height_cm": 160}, files=upload()).status_code == 422
    rows = [json.loads(r.message) for r in caplog.records if r.name == "vastraview.measurements"]
    assert {"image_preprocessing", "pose_validation", "torso_sections", "measurement_completed", "measurement_failed"} <= {r["event"] for r in rows}
    failure = next(r for r in rows if r["event"] == "measurement_failed")
    assert failure["code"] == "scale_unavailable" and failure["duration_seconds"] >= 0
    assert all(word not in json.dumps(rows) for word in ["person.png", "base64", "token", "input_sha256"])
