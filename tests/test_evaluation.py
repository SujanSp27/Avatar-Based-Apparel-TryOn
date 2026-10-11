import json

import numpy as np
import pytest

from ml.evaluation.metrics import measurement_metrics, pose_metrics, size_metrics, validate_splits
from scripts import evaluate


def test_measurement_error_metrics():
    result = measurement_metrics([12, 18], [10, 20])
    assert result["mae"] == result["rmse"] == 2
    assert result["mape"] == pytest.approx(15)
    assert measurement_metrics([1], [0])["mape"] is None


def test_procrustes_recovers_scale_rotation_and_translation():
    actual = np.random.default_rng(7).normal(size=(17, 3))
    rotation = np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]])
    prediction = 2 * actual @ rotation + 10
    result = pose_metrics(prediction, actual)
    assert result["mpjpe"] > 1
    assert result["p_mpjpe"] < 1e-10


def test_size_metrics_and_leakage():
    result = size_metrics([["M", "S"], ["L", "M"]], ["M", "M"], ["S", "M", "L"])
    assert result["exactSizeAccuracy"] == 0.5
    assert result["top2Accuracy"] == result["adjacentSizeAccuracy"] == 1
    with pytest.raises(ValueError, match="leakage"):
        validate_splits(
            [
                {"personId": "a", "garmentId": "x", "split": "train"},
                {"personId": "a", "garmentId": "y", "split": "test"},
            ]
        )


def evaluate_runs(tmp_path, monkeypatch, records, truth=None):
    run_root = tmp_path / "runs"
    run_root.mkdir()
    for run_id, manifests in records.items():
        folder = run_root / run_id
        folder.mkdir()
        for name, value in manifests.items():
            (folder / f"{name}.json").write_text(json.dumps(value), encoding="utf-8")
    output = tmp_path / "report.json"
    arguments = ["evaluate.py", "--run-root", str(run_root), "--output", str(output)]
    if truth is not None:
        ground_truth = tmp_path / "truth.json"
        ground_truth.write_text(json.dumps(truth), encoding="utf-8")
        arguments += ["--ground-truth", str(ground_truth)]
    monkeypatch.setattr(evaluate.sys, "argv", arguments)
    evaluate.main()
    return json.loads(output.read_text(encoding="utf-8"))


def photo_record():
    return {
        "mode": "2d",
        "timingSeconds": 2,
        "memoryRssMB": 100,
        "measurements": None,
        "recommendedSize": None,
        "fitting": None,
        "candidates": [],
    }


def truth_record(run_id):
    return {
        "runId": run_id,
        "personId": f"person-{run_id}",
        "garmentId": f"garment-{run_id}",
        "split": "test",
        "measurements": {"chest": 90},
        "size": "M",
    }


def test_evaluation_mixed_modes_only_scores_actual_mesh_outputs(tmp_path, monkeypatch):
    report = evaluate_runs(
        tmp_path,
        monkeypatch,
        {
            "mesh": {
                "result": {
                    # Existing results predate the mode field and remain valid 3D records.
                    "timingSeconds": 10,
                    "memoryRssMB": 200,
                    "measurements": {"chest": 92},
                    "fitting": {"sampledPenetrationRate": 0.004},
                    "candidates": [{"sizeLabel": "M"}, {"sizeLabel": "L"}],
                }
            },
            "photo": {"result": photo_record()},
        },
        truth={
            "records": [truth_record("mesh"), truth_record("photo")],
            "sizeOrder": ["S", "M", "L"],
        },
    )
    assert report["runs"] == 2
    assert report["successful3dRuns"] == report["successful2dRuns"] == 1
    assert report["successRate"] == 1 and report["failureRate"] == 0
    assert report["meanLatencySeconds"] == 6
    assert report["meanSampledPenetrationRate"] == 0.004
    assert report["measurementAccuracy"]["n"] == 1
    assert report["measurementAccuracy"]["mae"] == 2
    assert report["sizeAccuracy"]["n"] == 1
    assert report["groundTruthRunsExcludedNo3dMeasurements"] == ["photo"]


def test_evaluation_2d_only_preserves_unavailable_statistics(tmp_path, monkeypatch):
    report = evaluate_runs(
        tmp_path,
        monkeypatch,
        {"photo": {"result": photo_record()}},
        truth={"records": [truth_record("photo")], "sizeOrder": ["S", "M", "L"]},
    )
    assert report["runs"] == report["successful2dRuns"] == 1
    assert report["successful3dRuns"] == 0
    assert report["meanSampledPenetrationRate"] is None
    assert report["measurementAccuracy"] is None
    assert report["sizeAccuracy"] is None
    assert report["poseAccuracy"] is None
    assert report["groundTruthRunsExcludedNo3dMeasurements"] == ["photo"]


def test_evaluation_failure_overrides_stale_success_and_ground_truth(tmp_path, monkeypatch):
    report = evaluate_runs(
        tmp_path,
        monkeypatch,
        {
            "failed": {
                "result": {
                    "mode": "3d",
                    "timingSeconds": 999,
                    "memoryRssMB": 999,
                    "measurements": {"chest": 999},
                    "fitting": {"sampledPenetrationRate": 1},
                    "candidates": [{"sizeLabel": "L"}],
                },
                "failure": {"timingSeconds": 4, "code": "internal_error"},
            },
            "photo": {"result": photo_record()},
            "processing": {"input": {"requestedMode": "auto"}},
        },
        truth={"records": [truth_record("failed")], "sizeOrder": ["S", "M", "L"]},
    )
    assert report["runs"] == 2
    assert report["successRate"] == report["failureRate"] == 0.5
    assert report["successful3dRuns"] == 0
    assert report["successful2dRuns"] == 1
    assert report["meanLatencySeconds"] == 3
    assert report["maxRecordedRssMB"] == 100
    assert report["meanSampledPenetrationRate"] is None
    assert report["measurementAccuracy"] is None
    assert report["sizeAccuracy"] is None
    assert report["groundTruthRunsExcludedFailed"] == ["failed"]


def test_evaluation_empty_run_directory_has_no_invented_metrics(tmp_path, monkeypatch):
    report = evaluate_runs(tmp_path, monkeypatch, {})
    assert report["runs"] == 0
    for key in (
        "successRate",
        "failureRate",
        "meanLatencySeconds",
        "maxRecordedRssMB",
        "meanSampledPenetrationRate",
        "measurementAccuracy",
        "sizeAccuracy",
        "poseAccuracy",
    ):
        assert report[key] is None
