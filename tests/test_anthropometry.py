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
        29: (240, 910), 30: (360, 910), 31: (245, 920), 32: (365, 920),
    }.items():
        points[index, :2] = xy
    points[:, :2] /= [600, 1000]
    points[:, 3] = 0.99
    mask = np.zeros((1000, 600), dtype=bool)
    mask[250:520, 200:400] = True
    mask[500:930, 210:270] = True
    mask[500:930, 330:390] = True
    return PoseObservation(np.full((1000, 600, 3), 255, dtype=np.uint8),
                           points, np.zeros((33, 3)), mask)


def test_exact_geometry_and_scaling(observation):
    result, _ = estimate(observation, 160)
    # Hpx = 900-100; S=.2. Widths shoulder=200, chest/waist=200,
    # hip outline=200, each thigh=60, mean inseam=sqrt(400**2+60**2).
    assert result["scale_factor"] == pytest.approx(0.2)
    assert result["measurements"] == pytest.approx({
        "shoulder_width": 40, "chest_circumference": 98,
        "waist_circumference": 92, "hip_circumference": 96,
        "thigh_circumference": 30, "inseam_length": 80.89,
    })
    larger, _ = estimate(observation, 200)
    assert larger["scale_factor"] == pytest.approx(.25)
    for key in METRICS:
        assert larger["measurements"][key] == pytest.approx(result["measurements"][key] * 1.25, abs=.02)


@pytest.mark.parametrize("landmark", [0, 11, 12, 23, 24, 25, 26, 27, 28, 29, 30])
def test_visibility_threshold_applies_to_dependencies_without_erasing_other_regions(observation, landmark):
    observation.landmarks[landmark, 3] = .65
    if landmark in (27, 28):
        with pytest.raises(PipelineError) as error:
            estimate(observation, 160)
        assert error.value.code == "scale_unavailable"
    else:
        result, _ = estimate(observation, 160)
        if landmark in (11, 12):
            assert result["measurements"]["shoulder_width"] is None
            assert result["measurements"]["chest_circumference"] is None
            assert result["measurements"]["thigh_circumference"] == 30
        elif landmark in (23, 24, 25, 26):
            assert result["measurements"]["thigh_circumference"] is None
            assert result["measurements"]["inseam_length"] is None
            assert result["measurements"]["shoulder_width"] == 40
        else:
            assert all(value is not None for value in result["measurements"].values())
        assert result["quality"]["minimum_key_landmark_visibility"] == .65
    observation.landmarks[landmark, 3] = .6501
    recovered, _ = estimate(observation, 160)
    assert all(value is not None for value in recovered["measurements"].values())


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
    result, _ = estimate(observation, 160)
    assert result["measurements"]["inseam_length"] is None
    assert result["measurements"]["chest_circumference"] == 98


def test_merged_thighs_do_not_measure_both_legs_as_one(observation):
    observation.mask[500:930, 210:390] = True
    result, _ = estimate(observation, 160)
    assert result["measurements"]["thigh_circumference"] is None
    assert result["quality"]["metrics"]["thigh_circumference"]["reason"] == "ambiguous_thigh"
    assert result["measurements"]["shoulder_width"] == 40
    assert result["measurements"]["chest_circumference"] == 98
    assert result["measurements"]["waist_circumference"] == 92


def test_connected_arm_is_not_included_in_chest_measurement(observation):
    # Deliberate mask bridge to the left upper arm; the first section is invalid,
    # the lower chest section remains separately measurable.
    observation.mask[300:325, 170:400] = True
    result, _ = estimate(observation, 160)
    assert result["geometry"]["chest_torso_fraction"] == .30
    assert result["measurements"]["chest_circumference"] == 98
    observation.mask[300:500, 150:450] = True
    uncertain, _ = estimate(observation, 160)
    assert uncertain["measurements"]["chest_circumference"] is None
    assert uncertain["measurements"]["waist_circumference"] is None
    assert uncertain["quality"]["metrics"]["chest_circumference"]["reason"] == "arms_overlap_torso"


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
    repo = MeasurementRepository(mongomock.MongoClient(tz_aware=True), "test_anthropometry")
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
def api(repository, observation, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "measurement-test-admin")
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
    assert {"nike", "puma", "adidas", "allen-solly", "us-polo-assn", "manyavar", "levi-s", "h-m", "libas", "biba", "raymond"} <= {b["brand_id"] for b in brands}
    for brand in brands:
        if brand["coverage"]:
            assert {c["gender"] for c in brand["coverage"]} == {"men", "women"}
        if brand["brand_id"] not in ("nike", "puma"):
            assert all(not c["apparel_ids"] for c in brand["coverage"])
    for gender in ("men", "women"):
        charts = client.get("/api/v1/sizing/charts", params={"market": "IN", "gender": gender}).json()
        assert {c["brand_id"] for c in charts} == ({"nike", "puma", "manyavar"} if gender == "men" else {"nike", "puma"})
        assert all(c["gender"] == gender and not c["is_demo"] for c in charts)
    us = client.get("/api/v1/sizing/charts", params={"market": "US"}).json()
    assert us and all(c["brand_id"] == "levi-s" and c["market"] == "US" for c in us)


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


def extract_fixture(client, endpoint="/api/v1/measurements/extract", **data):
    response = client.post(endpoint, data={"height_cm": 160, **data},
                           files={"image": ("person.png", image_bytes(), "image/png")})
    assert response.status_code == 200, response.text
    return response.json()


def test_saved_measurement_lifecycle_and_reference_sizing(api):
    client, service = api
    client.headers["X-Admin-Token"] = "measurement-test-admin"
    result = extract_fixture(client)
    identifier = result["measurement_id"]
    fetched = client.get(f"/api/v1/measurements/{identifier}")
    assert fetched.status_code == 200
    assert fetched.json()["measurements"] == result["measurements"]
    assert fetched.json()["created_at"].endswith("Z")
    page = client.get("/api/v1/measurements", params={"limit": 1}).json()
    assert page["total"] == 1 and page["items"][0]["measurement_id"] == identifier
    assert client.get("/api/v1/measurements", params={"offset": 1}).json()["items"] == []
    png = client.get(f"/api/v1/measurements/{identifier}/annotation")
    assert png.status_code == 200 and png.headers["content-type"] == "image/png"
    assert png.content == service.artifact_path(identifier).read_bytes()
    base = {"brand_id": "brand_b", "apparel_id": "apparel_all"}
    stored = client.post("/api/v1/sizing/recommend", json={**base, "measurement_id": identifier})
    manual = client.post("/api/v1/sizing/recommend", json={**base, "measurements": result["measurements"]})
    assert stored.status_code == manual.status_code == 200
    for key in ("minimum_error", "recommended_size", "fit_confidence", "size_rankings"):
        assert stored.json()[key] == manual.json()[key]
    assert stored.json()["measurement_id"] == identifier
    assert set(result["warnings"]).issubset(stored.json()["warnings"])
    deleted = client.delete(f"/api/v1/measurements/{identifier}")
    assert deleted.status_code == 204 and not deleted.content
    assert not list(service.output_root.glob(f"{identifier}*"))
    assert client.get(f"/api/v1/measurements/{identifier}").status_code == 404
    assert client.get(f"/api/v1/measurements/{identifier}/annotation").status_code == 404
    assert client.delete(f"/api/v1/measurements/{identifier}").status_code == 404
    assert client.post("/api/v1/sizing/recommend", json={**base, "measurement_id": identifier}).status_code == 404


def test_combined_extraction_uses_same_chart_and_preserves_warning(api, repository):
    client, _ = api
    result = extract_fixture(client, "/api/v1/measurements/extract-and-recommend",
                             brand_id="brand_b", apparel_id="apparel_all", chart_version=1)
    extraction, recommendation = result["extraction"], result["recommendation"]
    expected = recommend(extraction["measurements"], repository.get_chart("brand_b", "apparel_all", 1))
    assert recommendation["minimum_error"] == expected.minimum_error
    assert recommendation["measurement_id"] == extraction["measurement_id"]
    assert set(extraction["warnings"]).issubset(recommendation["warnings"])
    assert repository.measurements.count_documents({}) == 1


def test_combined_rejects_missing_or_garment_chart_before_inference(api, repository, monkeypatch):
    client, service = api
    def must_not_infer(*args, **kwargs):
        pytest.fail("invalid chart should be rejected before image processing")
    monkeypatch.setattr(service, "extract", must_not_infer)
    for brand, apparel, status in (("missing", "unknown", 404), ("brand_b", "apparel_all", 422)):
        repository.charts.update_many({"brand_id": "brand_b"}, {"$set": {"measurement_basis": "garment"}})
        response = client.post("/api/v1/measurements/extract-and-recommend", data={
            "height_cm": 160, "brand_id": brand, "apparel_id": apparel,
        }, files={"image": ("person.png", image_bytes(), "image/png")})
        assert response.status_code == status, response.text
    assert repository.measurements.count_documents({}) == 0


def test_measurement_reference_and_pagination_validation(api):
    client, _ = api
    client.headers["X-Admin-Token"] = "measurement-test-admin"
    extract_fixture(client)  # Establish the owner session before private-path validation.
    base = {"brand_id": "brand_b", "apparel_id": "apparel_all"}
    for extra in ({}, {"measurements": dict.fromkeys(METRICS, 100), "measurement_id": "pose_" + "a" * 32},
                  {"measurement_id": "../../secrets"}, {"measurements": {"unknown": 100}}):
        assert client.post("/api/v1/sizing/recommend", json={**base, **extra}).status_code == 422
    assert client.get("/api/v1/measurements/invalid").status_code == 422
    for params in ({"limit": 0}, {"limit": 101}, {"offset": -1}):
        assert client.get("/api/v1/measurements", params=params).status_code == 422


def test_admin_protects_record_list_delete_and_brand_mutations(api, monkeypatch):
    client, _ = api
    identifier = extract_fixture(client)["measurement_id"]
    monkeypatch.setattr(settings, "admin_token", "admin-fixture")
    for method, url, kwargs in (
        ("get", "/api/v1/measurements", {}),
        ("post", "/api/v1/sizing/brands", {"json": {"brand_id": "example", "brand_name": "Example"}}),
        ("patch", "/api/v1/sizing/brands/nike", {"json": {"description": "fixture"}}),
    ):
        assert getattr(client, method)(url, **kwargs).status_code == 403
        assert getattr(client, method)(url, headers={"X-Admin-Token": "admin-fixture"}, **kwargs).status_code in (200, 201, 204)
    # Owners may delete their own data without an administrative credential.
    assert client.delete(f"/api/v1/measurements/{identifier}").status_code == 204


def test_storage_cleanup_on_mongo_failure_and_retry_after_header(api, repository, monkeypatch):
    from pymongo.errors import ServerSelectionTimeoutError
    client, service = api
    def broken(*args, **kwargs):
        raise ServerSelectionTimeoutError("private-database-secret")
    monkeypatch.setattr(repository.measurements, "insert_one", broken)
    response = client.post("/api/v1/measurements/extract", data={"height_cm": 160},
                           files={"image": ("person.png", image_bytes(), "image/png")})
    assert response.status_code == 503 and response.headers["Retry-After"] == "5"
    assert "private-database-secret" not in response.text
    assert not list(service.output_root.glob("pose_*"))
    assert repository.measurements.count_documents({}) == 0


def test_delete_preserves_metadata_when_artifact_cleanup_fails(api, repository, monkeypatch):
    client, service = api
    identifier = extract_fixture(client)["measurement_id"]
    def broken(*args, **kwargs):
        raise PipelineError("measurement_storage_unavailable", "Cleanup could not finish.", 503)
    monkeypatch.setattr(service, "remove_artifacts", broken)
    assert client.delete(f"/api/v1/measurements/{identifier}").status_code == 503
    assert repository.get_measurement(identifier).measurement_id == identifier


def test_artifact_paths_reject_traversal_and_missing_annotation(api):
    client, service = api
    identifier = extract_fixture(client)["measurement_id"]
    service.artifact_path(identifier).unlink()
    assert client.get(f"/api/v1/measurements/{identifier}/annotation").status_code == 404
    for invalid in ("../outside", "pose_" + "f" * 32 + "/../outside", "POSE_" + "f" * 32):
        with pytest.raises(PipelineError):
            service.artifact_path(invalid)
    with pytest.raises(PipelineError):
        service.artifact_path(identifier, "/../.env")


def test_brand_creation_immutable_history_and_chart_discovery(api, chart):
    client, _ = api
    client.headers["X-Admin-Token"] = "measurement-test-admin"
    created = client.post("/api/v1/sizing/brands", json={
        "brand_id": "fixture", "brand_name": "Fixture", "official_url": "https://example.com/",
    })
    assert created.status_code == 201
    assert not created.json()["recommendation_available"]
    assert client.post("/api/v1/sizing/brands", json={"brand_id": "fixture", "brand_name": "Other"}).status_code == 409
    payload = chart.model_dump(mode="json")
    payload.update(brand_id="fixture", brand_name="Wrong", is_demo=False, market="IN")
    assert client.post("/api/v1/sizing/charts", json=payload).status_code == 409
    payload["brand_name"] = "Fixture"
    assert client.post("/api/v1/sizing/charts", json=payload).status_code == 201
    updated = client.patch("/api/v1/sizing/brands/fixture", json={"brand_name": "Fixture Renamed"})
    assert updated.status_code == 200 and updated.json()["recommendation_available"]
    payload.update(version=2, brand_name="Fixture Renamed")
    assert client.post("/api/v1/sizing/charts", json=payload).status_code == 201
    path = "/api/v1/sizing/charts/fixture/apparel_all"
    assert client.get(path, params={"version": 1}).json()["brand_name"] == "Fixture"
    versions = client.get(path + "/versions").json()
    assert [v["version"] for v in versions] == [2, 1]
    latest = client.get("/api/v1/sizing/charts", params={"brand_id": "fixture", "latest_only": True}).json()
    assert len(latest) == 1 and latest[0]["version"] == 2 and "sizes" not in latest[0]
    page = client.get("/api/v1/sizing/charts", params={"brand_id": "fixture", "limit": 1, "offset": 1}).json()
    assert page[0]["version"] == 1
    assert client.patch("/api/v1/sizing/brands/fixture", json={}).status_code == 422
    assert client.get("/api/v1/sizing/brands/missing").status_code == 404
    assert client.patch("/api/v1/sizing/brands/missing", json={"description": "no"}).status_code == 404
    assert client.get("/api/v1/sizing/charts/missing/apparel/versions").status_code == 404
    default = client.get("/api/v1/sizing/brands").json()
    assert "brand_b" not in {b["brand_id"] for b in default}
    demos = client.get("/api/v1/sizing/brands", params={"include_demo": True}).json()
    assert "brand_b" in {b["brand_id"] for b in demos}


def test_categories_expose_normalized_weights_and_explicit_subsets(api):
    from backend.app.anthropometry.constants import CATEGORY_METRICS
    client, _ = api
    records = client.get("/api/v1/sizing/categories").json()
    assert {record["category"] for record in records} == set(CATEGORY_METRICS)
    for record in records:
        assert sum(record["default_weights"].values()) == pytest.approx(1)
        assert set(record["default_weights"]) == set(record["default_metrics"])
    assert next(r for r in records if r["category"] == "jumpsuit")["default_weights"] == WEIGHTS


def test_corrupt_record_reports_typed_error(api, repository):
    client, _ = api
    client.headers["X-Admin-Token"] = "measurement-test-admin"
    identifier = extract_fixture(client)["measurement_id"]
    repository.measurements.replace_one({"measurement_id": identifier}, {"measurement_id": identifier, "private_field": "do-not-expose"})
    response = client.get(f"/api/v1/measurements/{identifier}")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "measurement_record_invalid"
    assert "private_field" not in response.text
    assert client.get("/api/v1/measurements").json()["error"]["code"] == "measurement_record_invalid"


def test_owned_mongo_client_reopens_after_lifespan_shutdown(monkeypatch):
    clients = []
    def new_client():
        client = mongomock.MongoClient(tz_aware=True)
        client["reopen"].command = lambda *args, **kwargs: {"ok": 1}
        clients.append(client)
        return client
    monkeypatch.setattr(MeasurementRepository, "_new_client", staticmethod(new_client))
    repo = MeasurementRepository(database="reopen")
    repo.initialize()
    repo.close()
    assert repo.ping() and len(clients) == 2
    assert repo.get_chart("brand_b", "apparel_a").version == 1
    repo.close()


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
