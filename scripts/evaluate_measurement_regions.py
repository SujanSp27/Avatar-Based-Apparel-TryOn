"""Local CPU regression evidence; heights are test inputs, never ground truth."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.anthropometry.measurement_service import MeasurementService
from backend.app.anthropometry.pose_adapter import MediaPipePose
from backend.app.config import settings
from ml.errors import PipelineError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True)
    parser.add_argument("--extra-person", type=Path, action="append", default=[],
                        help="Also evaluate an explicitly selected private image inside this workspace; never uploads it.")
    args = parser.parse_args()
    if not args.label.replace("-", "").isalnum():
        parser.error("Use a simple alphanumeric report label")
    root = ROOT / "experiments/measurement-regions" / args.label
    if (root / "report.json").exists():
        parser.error("This report already exists. Use a new label to preserve previous evidence.")
    extra_people = [(ROOT / path).resolve() for path in args.extra_person]
    if any(not path.is_relative_to(ROOT) or not path.is_file() for path in extra_people):
        parser.error("Extra person images must be existing files inside this workspace")
    root.mkdir(parents=True, exist_ok=True)
    detector = MediaPipePose(settings.measurement_model_path)
    service = MeasurementService(detector, root / "private")
    manifest = json.loads((ROOT / "data/regression/measurement-regions-v4.json").read_text(encoding="utf-8"))
    rows = []
    try:
        fixtures = manifest["fixtures"] + [{"path": str(path.relative_to(ROOT))} for path in extra_people]
        for fixture in fixtures:
            path = ROOT / fixture["path"]
            filename = str(path.relative_to(ROOT))
            if not path.is_file():
                rows.append({"fixture": filename, "status": "fixture_unavailable"})
                continue
            data = path.read_bytes()
            start = perf_counter()
            row = {"fixture": filename, "input_sha256": hashlib.sha256(data).hexdigest(), "test_height_cm": 172}
            try:
                scan = service.extract(data, 172)
                row.update(status="estimated", measurements=scan.measurements.model_dump(), quality=scan.quality,
                           geometry=scan.geometry, annotation=scan.measurement_id + ".png", provenance=scan.provenance)
            except PipelineError as exc:
                row.update(status="unavailable", error_code=exc.code, reason=str(exc))
            row["duration_seconds"] = round(perf_counter() - start, 3)
            rows.append(row)
            print(filename, row["status"], row.get("error_code", ""), row["duration_seconds"], flush=True)
    finally:
        detector.close()
    (root / "report.json").write_text(json.dumps({"height_is_ground_truth": False,
        "accuracy_evaluated_against_tape": False, "device": "cpu", "cases": rows}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
