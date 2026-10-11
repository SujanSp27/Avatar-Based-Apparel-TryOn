"""Evaluate recorded ground truth or summarize actual run artifacts; never invent labels."""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ml.evaluation.metrics import measurement_metrics, pose_metrics, size_metrics, validate_splits


def load_run_records(run_root: Path) -> tuple[dict[str, dict], dict[str, dict]]:
    """Read one terminal record per run; a failed publication overrides stale success."""
    successes, failures = {}, {}
    for folder in sorted(run_root.glob("*")):
        failure = folder / "failure.json"
        result = folder / "result.json"
        if failure.is_file():
            failures[folder.name] = json.loads(failure.read_text(encoding="utf-8"))
        elif result.is_file():
            successes[folder.name] = json.loads(result.read_text(encoding="utf-8"))
    return successes, failures


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ground-truth", type=Path)
    parser.add_argument("--run-root", type=Path, default=ROOT / "data/processed")
    parser.add_argument("--output", type=Path, default=ROOT / "experiments/evaluation-report.json")
    args = parser.parse_args()
    success_records, failure_records = load_run_records(args.run_root)
    successes, failures = list(success_records.values()), list(failure_records.values())
    mesh_successes = [r for r in successes if r.get("mode", "3d") == "3d"]
    count = len(successes) + len(failures)
    report = {
        "runs": count,
        "successRate": len(successes) / count if count else None,
        "failureRate": len(failures) / count if count else None,
        "successful3dRuns": len(mesh_successes),
        "successful2dRuns": len(successes) - len(mesh_successes),
        "meanLatencySeconds": float(np.mean([r["timingSeconds"] for r in successes + failures]))
        if count
        else None,
        "maxRecordedRssMB": max((r["memoryRssMB"] for r in successes), default=None),
        "meanSampledPenetrationRate": float(
            np.mean([r["fitting"]["sampledPenetrationRate"] for r in mesh_successes])
        )
        if mesh_successes
        else None,
        "gpuUsage": "See experiments/hardware.json; baseline inference runs on CPU",
        "measurementAccuracy": None,
        "sizeAccuracy": None,
        "poseAccuracy": None,
        "qualityReview": "Unscored until human review labels are recorded. See data/regression/review-template.json.",
        "limitation": "Mixed development runs and controlled samples; not generalization evidence.",
    }
    if args.ground_truth:
        truth = json.loads(args.ground_truth.read_text(encoding="utf-8"))
        report["splits"] = validate_splits(truth["records"])
        predictions, actual, ranks, sizes, poses = [], [], [], [], []
        skipped, failed = [], []
        for record in truth["records"]:
            run_id = record["runId"]
            if run_id in failure_records:
                failed.append(run_id)
                continue
            if run_id not in success_records:
                raise ValueError(f"Ground-truth run {run_id} has no terminal result or failure.")
            result = success_records[run_id]
            if result.get("mode", "3d") == "2d":
                skipped.append(run_id)
                continue
            for key, value in record.get("measurements", {}).items():
                predictions.append(result["measurements"][key])
                actual.append(value)
            if record.get("size"):
                ranks.append([c["sizeLabel"] for c in result["candidates"]])
                sizes.append(record["size"])
            if record.get("actualJoints"):
                poses.append(pose_metrics(record["predictedJoints"], record["actualJoints"]))
        report["measurementAccuracy"] = measurement_metrics(predictions, actual) if actual else None
        report["sizeAccuracy"] = size_metrics(ranks, sizes, truth["sizeOrder"]) if sizes else None
        report["poseAccuracy"] = poses or None
        report["groundTruthRunsExcludedNo3dMeasurements"] = skipped
        report["groundTruthRunsExcludedFailed"] = failed
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
