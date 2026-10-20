import io
import json
from pathlib import Path

import mongomock
import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import ValidationError

from backend.app.anthropometry.constants import METRICS, WEIGHTS
from backend.app.anthropometry.measurement_service import MeasurementService, estimate
from backend.app.anthropometry.pose_adapter import PoseObservation, decode_person
from backend.app.anthropometry.repository import MeasurementRepository, get_repository
from backend.app.anthropometry.router import get_measurement_service
from backend.app.anthropometry.schemas import ChartCreate
from backend.app.anthropometry.sizing_engine import recommend
from backend.app.config import ROOT, settings
from backend.app.main import app
from ml.errors import PipelineError


@pytest.fixture
def chart():
    return ChartCreate.model_validate(json.loads(
        (ROOT / "data/brandCharts/anthropometry-demo-v1.json").read_text()
    )[2])  # jumpsuit exercises all six exact weights


@pytest.fixture
def observation():
    # Anatomical geometry is deliberately simple enough to calculate by hand.
    points = np.zeros((33, 4), dtype=float)
    points[:, :2] = [300, 100]
    for index, xy in {
        11: (200, 250), 12: (400, 250), 23: (240, 500), 24: (360, 500),
        13: (160, 400), 14: (440, 400), 15: (140, 500), 16: (460, 500),
        25: (240, 700), 26: (360, 700), 27: (240, 900), 28: (360, 900),
        29: (240, 910), 30: (360, 910),
    }.items():
        points[index, :2] = xy
    points[:, :2] /= [600, 1000]
    points[:, 3] = 0.99
    mask = np.zeros((1000, 600), dtype=bool)
    mask[250:500, 200:400] = True
    mask[500:930, 210:270] = True
    mask[500:930, 330:390] = True
    return PoseObservation(np.full((1000, 600, 3), 255, dtype=np.uint8),
                           points, np.zeros((33, 3)), mask)


def test_exact_geometry_and_scaling(observation):
    result, _ = estimate(observation, 160)
    # Hpx = 900-100; S=.2. Widths shoulder=200, chest/waist=200,
    # hip joints=120, each thigh=60, mean inseam=sqrt(400**2+60**2).
    assert result["scale_factor"] == pytest.approx(0.2)
    assert result["measurements"] == pytest.approx({
        "shoulder_width": 40, "chest_circumference": 98,
        "waist_circumference": 92, "hip_circumference": 57.6,
        "thigh_circumference": 30, "inseam_length": 80.89,
    })
    larger, _ = estimate(observation, 200)
    assert larger["scale_factor"] == pytest.approx(.25)
    for key in METRICS:
        assert larger["measurements"][key] == pytest.approx(result["measurements"][key] * 1.25, abs=.02)


@pytest.mark.parametrize("landmark", [0, 11, 12, 23, 24, 25, 26, 27, 28, 29, 30])
def test_visibility_is_strictly_greater_than_threshold(observation, landmark):
    observation.landmarks[landmark, 3] = .65
    with pytest.raises(PipelineError, match="Visibility"):
        estimate(observation, 172)
    observation.landmarks[landmark, 3] = .6501
    estimate(observation, 172)


def test_scaling_uses_pixel_axes_not_normalized_distances(observation):
    # Non-square image, oblique shoulders: 200x40 pixels apart.
    observation.landmarks[12, 1] += 40 / 1000
    result, _ = estimate(observation, 160)
    assert result["measurements"]["shoulder_width"] == pytest.approx(round(np.hypot(200, 40) * .2, 2))


@pytest.mark.parametrize("height", [0, -172, 251, float("nan"), float("inf")])
def test_invalid_height(observation, height):
    with pytest.raises(PipelineError, match="height"):
        estimate(observation, height)


def test_partial_and_crossed_body_fail(observation):
    observation.landmarks[27, 1] = 1.1
    with pytest.raises(PipelineError) as error:
        estimate(observation, 172)
    assert error.value.code == "partial_body"
    observation.landmarks[27, 1] = .9
    observation.landmarks[[25, 26], 0] = observation.landmarks[[26, 25], 0]
    with pytest.raises(PipelineError) as error:
        estimate(observation, 172)
    assert error.value.code == "unsupported_pose"


def test_merged_thighs_do_not_measure_both_legs_as_one(observation):
    observation.mask[500:930, 210:390] = True
    with pytest.raises(PipelineError) as error:
        estimate(observation, 172)
    assert error.value.code == "ambiguous_thigh"


def test_connected_arm_is_not_included_in_chest_measurement(observation):
    # Deliberate mask bridge to the left upper arm; the first section is invalid,
    # the lower chest section remains separately measurable.
    observation.mask[300:325, 170:400] = True
    result, _ = estimate(observation, 160)
    assert result["geometry"]["chest_torso_fraction"] == .30
    assert result["measurements"]["chest_circumference"] == 98
    observation.mask[300:500, 150:450] = True
    with pytest.raises(PipelineError, match="includes arms"):
        estimate(observation, 160)


def test_mask_refinement_is_deterministic_and_uses_image_edges():
    from backend.app.anthropometry.pose_adapter import refine_mask
    # A dark torso and arm with a white gap incorrectly bridged by the coarse prior.
    image = np.full((200, 200, 3), 245, dtype=np.uint8)
    image[30:180, 65:125] = 40
    image[50:160, 145:165] = 40
    prior = np.zeros((200, 200), dtype=np.float32)
    prior[30:180, 65:125] = 1
    prior[50:160, 125:165] = .8
    mask = refine_mask(image, prior)
    assert mask[100, 95] and mask[100, 155]
    assert not mask[100, 135]
    assert np.array_equal(mask, refine_mask(image, prior))


def test_midpoint_error_confidence_and_ranking_exact(chart):
    # All measurements 10% above M -> E=.10 since weights sum to one.
    center = {key: (bounds.lower + bounds.upper) / 2 for key, bounds in chart.sizes[1].bounds.items()}
    single = chart.model_copy(update={"sizes": [chart.sizes[1]]})
    result = recommend({key: value * 1.1 for key, value in center.items()}, single)
    assert result.minimum_error == pytest.approx(.1)
    assert result.fit_confidence == pytest.approx(100 / 1.1)
    assert result.active_weights == WEIGHTS
    assert set(result.size_rankings[0].deviations) == set(METRICS)
    assert result.size_rankings[0].deviations == pytest.approx(dict.fromkeys(METRICS, .1))
    result = recommend(center, chart)
    assert result.recommended_size == "M"
    assert result.minimum_error == 0
    assert result.fit_confidence == 100
    assert [row.error for row in result.size_rankings] == sorted(row.error for row in result.size_rankings)


def test_nonuniform_errors_match_hand_calculation(chart):
    single = chart.model_copy(update={"sizes": [chart.sizes[1]]})
    # Deviations: .1,.2,.3,.4,.5,.6. E=.02+.05+.06+.08+.05+.03=.29.
    measurements = {
        key: ((bounds.lower + bounds.upper) / 2) * (1 + (i + 1) / 10)
        for i, (key, bounds) in enumerate(single.sizes[0].bounds.items())
    }
    result = recommend(measurements, single)
    assert result.minimum_error == pytest.approx(.29)
    assert result.fit_confidence == pytest.approx(100 / 1.29)
    # A measurement inside its interval still has nonzero error away from midpoint.
    center = {key: (bounds.lower + bounds.upper) / 2 for key, bounds in single.sizes[0].bounds.items()}
    center["shoulder_width"] += 1
    result = recommend(center, single)
    assert result.minimum_error == pytest.approx(.2 / 44)
    assert result.chart_comparison["M"]["shoulder_width"]["within_range"]


def test_category_subset_normalization_and_missing_measurements(chart):
    from ml.vton.categories import GarmentCategory
    chart.category = GarmentCategory.trouser
    measurements = {key: 100 for key in METRICS[2:]}
    result = recommend(measurements, chart)
    assert result.active_weights == pytest.approx({
        "waist_circumference": .20 / .55, "hip_circumference": .20 / .55,
        "thigh_circumference": .10 / .55, "inseam_length": .05 / .55,
    })
    with pytest.raises(PipelineError, match="inseam_length"):
        recommend({key: value for key, value in measurements.items() if key != "inseam_length"}, chart)


def test_invalid_and_incomplete_charts_fail_validation(chart):
    raw = chart.model_dump(mode="json")
    del raw["sizes"][0]["bounds"]["thigh_circumference"]
    with pytest.raises(ValidationError):
        ChartCreate.model_validate(raw)
    raw = chart.model_dump(mode="json")
    raw["sizes"][0]["bounds"]["shoulder_width"]["upper"] = 0
    with pytest.raises(ValidationError):
        ChartCreate.model_validate(raw)


@pytest.fixture
def repository():
    repo = MeasurementRepository(mongomock.MongoClient(), "test_anthropometry")
    # mongomock does not implement database command; no network is used.
    repo.db.command = lambda *args, **kwargs: {"ok": 1}
    repo.initialize()
    yield repo
    repo.close()


def test_immutable_mongodb_versions_and_exact_apparel_selection(repository, chart):
    original = repository.get_chart("brand_b", "apparel_a")
    update = original.model_copy(update={"version": 2})
    repository.create_chart(update)
    assert repository.get_chart("brand_b", "apparel_a").version == 2
    assert repository.get_chart("brand_b", "apparel_a", 1).version == 1
    assert repository.get_chart("brand_b", "apparel_all").version == 1
    with pytest.raises(PipelineError) as exc:
        repository.create_chart(update)
    assert exc.value.status_code == 409
    with pytest.raises(PipelineError) as exc:
        repository.get_chart("missing", "apparel_a")
    assert exc.value.status_code == 404
    repository._ready = False
    repository.initialize()
    assert repository.get_chart("brand_b", "apparel_a").version == 2


@pytest.fixture
def api(repository, observation, tmp_path):
    class Detector:
        model_sha256 = "test-double"

        def detect(self, image):
            return PoseObservation(image, observation.landmarks, observation.world_landmarks, observation.mask)

    # Use the mounted directory, isolated per test via static route replacement.
    service = MeasurementService(Detector(), tmp_path)
    app.dependency_overrides[get_repository] = lambda: repository
    app.dependency_overrides[get_measurement_service] = lambda: service
    client = TestClient(app, raise_server_exceptions=True)
    try:
        yield client, service
    finally:
        client.close()
        app.dependency_overrides.clear()


def image_bytes(format="PNG"):
    stream = io.BytesIO()
    Image.new("RGB", (600, 1000), "white").save(stream, format=format)
    return stream.getvalue()


def test_api_extract_persists_real_artifacts_and_uses_engine(api, repository):
    client, service = api
    response = client.post("/api/v1/measurements/extract", data={"height_cm": 160},
                           files={"image": ("person.png", image_bytes(), "image/png")})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["scale_factor"] == pytest.approx(.2)
    filename = Path(result["annotated_image_url"]).name
    with Image.open(service.output_root / filename) as annotated:
        assert annotated.size == (600, 1000)
    assert repository.measurements.count_documents({}) == 1
    sized = client.post("/api/v1/sizing/recommend", json={
        "brand_id": "brand_b", "apparel_id": "apparel_all", "measurements": result["measurements"],
    })
    assert sized.status_code == 200, sized.text
    expected = recommend(result["measurements"], repository.get_chart("brand_b", "apparel_all"))
    assert sized.json()["minimum_error"] == pytest.approx(expected.minimum_error)


def test_api_limits_invalid_images_and_height(api, monkeypatch):
    client, _ = api
    for height in ("nan", "inf", "-1", "0", "251"):
        response = client.post("/api/v1/measurements/extract", data={"height_cm": height},
                               files={"image": ("x.png", b"invalid")})
        assert response.status_code == 422
    response = client.post("/api/v1/measurements/extract", data={"height_cm": 172},
                           files={"image": ("x.png", b"invalid")})
    assert response.status_code == 422
    monkeypatch.setattr(settings, "max_upload_mb", 1)
    response = client.post("/api/v1/measurements/extract", data={"height_cm": 172},
                           files={"image": ("x.png", b"x" * (1024 * 1024 + 1))})
    assert response.status_code == 413
    with pytest.raises(PipelineError):
        decode_person(image_bytes("WEBP"))


def test_api_chart_auth_and_unknown_apparel(api, monkeypatch, chart):
    client, _ = api
    monkeypatch.setattr(settings, "admin_token", "test-secret")
    payload = chart.model_dump(mode="json")
    payload["version"] = 2
    assert client.post("/api/v1/sizing/charts", json=payload).status_code == 403
    assert client.post("/api/v1/sizing/charts", json=payload,
                       headers={"X-Admin-Token": "test-secret"}).status_code == 201
    assert client.get("/api/v1/sizing/charts/brand_b/apparel_all").json()["version"] == 2
    assert client.post("/api/v1/sizing/recommend", json={
        "brand_id": "unknown", "apparel_id": "apparel_all",
        "measurements": dict.fromkeys(METRICS, 100),
    }).status_code == 404


def test_official_india_charts_match_published_inch_values(repository):
    source = json.loads((ROOT / "data/brandCharts/india-chart-sources-v1.json").read_text())
    for record in source:
        brand_id = record["apparel_id"].split("-")[0]
        chart = repository.get_chart(brand_id, record["apparel_id"])
        assert chart.market == "IN" and chart.gender in ("men", "women")
        assert chart.measurement_basis == "body" and not chart.is_demo
        assert chart.source_url and chart.checked_on
        for row, size in zip(record["source_rows"], chart.sizes, strict=True):
            assert row[0] == size.size_label
            for key, (lo, hi) in zip(record["metrics"], row[1:], strict=True):
                assert size.bounds[key].lower == pytest.approx(lo * 2.54)
                assert size.bounds[key].upper == pytest.approx(hi * 2.54)
    nike = repository.get_chart("nike", "nike-in-hv4188-013")
    result = recommend({
        "chest_circumference": 37 * 2.54,
        "waist_circumference": 32.25 * 2.54,
        "hip_circumference": 37 * 2.54,
    }, nike)
    assert result.recommended_size == "M"
    assert result.minimum_error == pytest.approx(0, abs=1e-12)
    assert result.active_weights == pytest.approx({
        "chest_circumference": .25 / .65, "waist_circumference": .2 / .65,
        "hip_circumference": .2 / .65,
    })
    assert any("shoulder_width" in warning for warning in result.warnings)


def test_chart_subset_is_explicit_and_validated(chart):
    raw = chart.model_dump(mode="json")
    raw["active_metrics"] = ["chest_circumference", "chest_circumference"]
    with pytest.raises(ValidationError):
        ChartCreate.model_validate(raw)
    raw["category"] = "t-shirt"
    raw["active_metrics"] = ["inseam_length"]
    with pytest.raises(ValidationError):
        ChartCreate.model_validate(raw)
    raw["active_metrics"] = []
    with pytest.raises(ValidationError):
        ChartCreate.model_validate(raw)


def test_garment_dimensions_cannot_be_used_as_body_bounds(chart):
    chart.measurement_basis = "garment"
    with pytest.raises(PipelineError) as error:
        recommend(dict.fromkeys(METRICS, 100), chart)
    assert error.value.code == "chart_basis_unsupported"


def test_brand_api_exposes_verified_coverage_and_filters(api):
    client, _ = api
    brands = client.get("/api/v1/sizing/brands").json()
    assert {b["brand_id"] for b in brands} == {"nike", "puma", "adidas", "allen-solly", "us-polo-assn"}
    for brand in brands:
        assert {c["gender"] for c in brand["coverage"]} == {"men", "women"}
        if brand["brand_id"] not in ("nike", "puma"):
            assert all(not c["apparel_ids"] for c in brand["coverage"])
    for gender in ("men", "women"):
        charts = client.get("/api/v1/sizing/charts", params={"market": "IN", "gender": gender}).json()
        assert {c["brand_id"] for c in charts} == {"nike", "puma"}
        assert all(c["gender"] == gender and not c["is_demo"] for c in charts)
    assert client.get("/api/v1/sizing/charts", params={"market": "US"}).json() == []


def test_chart_versions_cannot_change_gender_or_market(repository):
    original = repository.get_chart("nike", "nike-in-hv4188-013")
    for update in ({"gender": "women"}, {"market": "US"}):
        with pytest.raises(PipelineError) as error:
            repository.create_chart(original.model_copy(update={"version": 2, **update}))
        assert error.value.status_code == 409


def test_database_failure_is_explicit_without_connection_secrets(api, monkeypatch, repository):
    from pymongo.errors import ServerSelectionTimeoutError

    def broken(*args, **kwargs):
        raise ServerSelectionTimeoutError("mongodb://secret-user:secret-pass@private-host")

    monkeypatch.setattr(repository.charts, "find_one", broken)
    client, _ = api
    result = client.post("/api/v1/sizing/recommend", json={
        "brand_id": "brand_b", "apparel_id": "apparel_all", "measurements": dict.fromkeys(METRICS, 100),
    })
    assert result.status_code == 503
    assert "measurement_database_unavailable" in result.text
    assert "secret" not in result.text and "private-host" not in result.text


@pytest.mark.integration
def test_real_cpu_pose_and_repeated_measurements(tmp_path):
    from backend.app.anthropometry.pose_adapter import MediaPipePose
    if not settings.measurement_model_path.exists():
        pytest.skip("MediaPipe checkpoint is not installed")
    photo = ROOT / "data/raw/studio-person.jpg"
    if not photo.exists():
        pytest.skip("Credited sample photo is not installed")
    service = MeasurementService(MediaPipePose(settings.measurement_model_path), tmp_path)
    try:
        first = service.extract(photo.read_bytes(), 172)
        second = service.extract(photo.read_bytes(), 172)
        assert first.measurements == second.measurements
        assert first.scale_factor == second.scale_factor
        assert first.provenance["device"] == "cpu"
        assert not first.provenance["local_gpu_used"]
        assert first.measurements.chest_circumference < 110  # Old arm-inclusive section was 134.7.
        assert first.measurements.waist_circumference < 100  # Old mask bridge yielded 110.65.
        with Image.open(photo) as image:
            partial = io.BytesIO()
            image.crop((0, 0, image.width, int(image.height * .55))).save(partial, format="PNG")
        with pytest.raises(PipelineError):
            service.extract(partial.getvalue(), 172)
    finally:
        service.detector.close()
