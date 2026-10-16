"""Run real, pinned model checkpoints on retained inputs; record failures honestly."""

import argparse
import hashlib
import json
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ml.preprocessing.images import PersonPreprocessor
from ml.vton.service import PretrainedTryOn


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    parser.add_argument("--guidance", type=float, default=2.5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--checkpoint", choices=["vitonhd", "mix"], default="vitonhd")
    parser.add_argument("--height", type=int, choices=[512, 1024], default=512)
    parser.add_argument("--person", type=Path)
    parser.add_argument("--garment", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "experiments/runs/pretrained-vton")
    parser.add_argument(
        "--report", type=Path, default=ROOT / "experiments/pretrained-vton-report.json"
    )
    args = parser.parse_args()
    if bool(args.person) != bool(args.garment):
        parser.error("--person and --garment must be provided together")
    if args.person and args.all:
        parser.error("Use either a custom pair or --all, not both")
    original_run = ROOT / "data/processed/9658bcca-8a2b-4a88-a134-cea3ff8739dd"
    portrait_run = ROOT / "data/processed/4fd1db83-60cb-460f-9887-985eb1ffb82f"
    person = original_run / "personInput.bin"
    garment = original_run / "garmentInput.bin"
    cases = [("reported-striped-shirt", person, garment, "t-shirt")]
    if args.person:
        cases = [("custom-pair", args.person, args.garment, "t-shirt")]
    if args.all:
        cases.extend(
            [
                ("different-garment", person, portrait_run / "garmentInput.bin", "t-shirt"),
                ("different-person", portrait_run / "personInput.bin", garment, "t-shirt"),
                ("shirt-category", person, garment, "shirt"),
                ("unsupported-dress", person, garment, "dress"),
                ("unsupported-trouser", person, garment, "trouser"),
            ]
        )
    args.output.mkdir(parents=True, exist_ok=True)
    service = PretrainedTryOn(
        ROOT / "assets/vton", args.device, guidance_scale=args.guidance, seed=args.seed,
        checkpoint=args.checkpoint, height=args.height,
    )
    preprocessor = PersonPreprocessor(ROOT / "assets/pose/pose_landmarker_full.task")
    records = []
    for name, person_path, garment_path, category in cases:
        destination = args.output / name
        destination.mkdir(parents=True, exist_ok=True)
        start = time.perf_counter()
        row = {"case": name, "category": category}
        try:
            person_data, garment_data = person_path.read_bytes(), garment_path.read_bytes()
            row["inputSha256"] = {
                "person": hashlib.sha256(person_data).hexdigest(),
                "garment": hashlib.sha256(garment_data).hexdigest(),
            }
            features = preprocessor.detect(person_data, destination)
            result = service.render(features, garment_data, category, destination)
            row.update(
                status="generated",
                diagnostics=result,
                output=str(destination / "tryon-2d.png"),
                visualAcceptance="pending human inspection",
            )
            (destination / "failure.json").unlink(missing_ok=True)
            (destination / "traceback.txt").unlink(missing_ok=True)
        except Exception as exc:
            (destination / "traceback.txt").write_text(traceback.format_exc(), encoding="utf-8")
            row.update(
                status="failed", code=getattr(exc, "code", type(exc).__name__), error=str(exc)
            )
            (destination / "failure.json").write_text(json.dumps(row, indent=2), encoding="utf-8")
        row["seconds"] = round(time.perf_counter() - start, 3)
        row["rssMB"] = round(psutil.Process().memory_info().rss / 1024**2, 1)
        records.append(row)
        report = {
            "recordedAt": datetime.now(timezone.utc).isoformat(),
            "cases": records,
            "scope": "Actual inference and software diagnostics; visual acceptance is recorded separately after image inspection.",
        }
        args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps({k: v for k, v in row.items() if k != "diagnostics"}), flush=True)
    if any(r["status"] != "generated" for r in records if not r["case"].startswith("unsupported-")):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
