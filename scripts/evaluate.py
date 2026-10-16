"""Evaluate recorded ground truth or summarize actual run artifacts; never invent labels."""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ml.evaluation.metrics import size_metrics, validate_splits


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
    successes = [r for r in successes if r.get("mode") == "2d"]
    count = len(successes) + len(failures)
    times = [r["timingSeconds"] for r in successes + failures]
    report = {
        "runs": count,
        "successRate": len(successes) / count if count else None,
        "failureRate": len(failures) / count if count else None,
        "successful2dRuns": len(successes),
        "meanLatencySeconds": float(np.mean(times)) if times else None,
        "p95LatencySeconds": float(np.percentile(times, 95)) if times else None,
        "under10SecondsRate": float(np.mean([r["timingSeconds"] < 10 for r in successes])) if successes else None,
        "sizeAccuracy": None,
        "qualityReview": "Requires visual review; API completion is not quality acceptance.",
        "limitation": "Development runs are not generalization evidence. Cached responses must be reported separately.",
    }
    if args.ground_truth:
        truth = json.loads(args.ground_truth.read_text(encoding="utf-8"))
        report["splits"] = validate_splits(truth["records"])
        pairs = [r for r in truth["records"] if r.get("rankedSizes") and r.get("size")]
        if pairs:
            report["sizeAccuracy"] = size_metrics([r["rankedSizes"] for r in pairs], [r["size"] for r in pairs], truth["sizeOrder"])
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
