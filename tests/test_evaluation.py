import json

import pytest

from ml.evaluation.metrics import measurement_metrics, size_metrics, validate_splits
from scripts import evaluate


def test_measurement_error_metrics():
    result = measurement_metrics([12, 18], [10, 20])
    assert result["mae"] == result["rmse"] == 2
    assert result["mape"] == pytest.approx(15)
    assert measurement_metrics([1], [0])["mape"] is None


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


def test_actual_photo_runs_record_latency_and_failures(tmp_path, monkeypatch):
    report = evaluate_runs(tmp_path, monkeypatch, {
        "success": {"result": {"mode": "2d", "timingSeconds": 8}},
        "failed": {"result": {"mode": "2d", "timingSeconds": 1},
                   "failure": {"timingSeconds": 4}},
        "processing": {"input": {}},
    })
    assert report["runs"] == 2
    assert report["successRate"] == .5
    assert report["meanLatencySeconds"] == 6
    assert report["successful2dRuns"] == 1
    assert report["under10SecondsRate"] == 1


def test_empty_evaluation_does_not_invent_measurements(tmp_path, monkeypatch):
    report = evaluate_runs(tmp_path, monkeypatch, {})
    assert report["runs"] == 0
    assert report["meanLatencySeconds"] is None
    assert report["successRate"] is None
