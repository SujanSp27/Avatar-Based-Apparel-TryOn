"""Measure a fresh generation on the existing private Colab worker, never locally."""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.config import settings
from backend.app.online_vton import OnlineTryOn
from ml.errors import PipelineError
from ml.vton.categories import MODEL_CATEGORIES


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--person", type=Path, default=ROOT / "data/raw/studio-person.jpg")
    parser.add_argument("--garment", type=Path, default=ROOT / "data/raw/garment-demo.png")
    parser.add_argument("--category", choices=list(MODEL_CATEGORIES), default="t-shirt")
    parser.add_argument("--photo-type", choices=["model", "flat-lay"], default="flat-lay")
    parser.add_argument("--steps", type=int, choices=[10, 15, 20, 30, 50], default=20)
    parser.add_argument("--input-encoding", choices=["lossless", "jpeg95"], default="lossless")
    parser.add_argument("--target-seconds", type=float, default=30.)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not 0 < args.target_seconds <= 600:
        parser.error("--target-seconds must be between 0 and 600")
    args.output.mkdir(parents=True, exist_ok=False)
    settings.online_vton_steps = args.steps
    settings.online_vton_input_encoding = args.input_encoding
    settings.online_vton_timeout = 600
    start = time.perf_counter()
    try:
        diagnostics = OnlineTryOn().render(args.person.read_bytes(), args.garment.read_bytes(), args.category, args.photo_type, args.output)
        report = {"status": "generated", "diagnostics": diagnostics, "freshGeneration": True,
                  "visualAcceptance": "pending inspection"}
    except PipelineError as exc:
        report = {"status": "failed", "code": exc.code, "message": str(exc)}
        failure_path = args.output / "remote-failure.json"
        if failure_path.is_file():
            report["failureDiagnostics"] = json.loads(failure_path.read_text())
    report["endToEndSeconds"] = round(time.perf_counter() - start, 3)
    report["targetSeconds"] = args.target_seconds
    report["timingTargetMet"] = report["status"] == "generated" and report["endToEndSeconds"] <= args.target_seconds
    report["inputs"] = {"personSha256": hashlib.sha256(args.person.read_bytes()).hexdigest(),
                        "garmentSha256": hashlib.sha256(args.garment.read_bytes()).hexdigest(),
                        "category": args.category, "photoType": args.photo_type, "steps": args.steps,
                        "inputEncoding": args.input_encoding}
    (args.output / "benchmark.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    if report["status"] != "generated":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
