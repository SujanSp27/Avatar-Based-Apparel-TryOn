"""Milestone 1: actual image inference, mesh validity, exports and previews."""

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ml.errors import PipelineError
from ml.human.template import MediaPipeTemplateReconstructor
from ml.preprocessing.images import PersonPreprocessor
from ml.preview import render_preview


def main():
    processor = PersonPreprocessor(ROOT / "assets/bodyModels/pose_landmarker_full.task")
    model = MediaPipeTemplateReconstructor()
    report = []
    files = sorted((ROOT / "data/raw").glob("*.jpg")) + [ROOT / "data/raw/skates.png"]
    for source in files:
        if source.name.startswith("garment"):
            continue
        folder = ROOT / "experiments/runs/reconstruction" / source.stem
        folder.mkdir(parents=True, exist_ok=True)
        # A formerly accepted image may now be rejected after a validation improvement.
        # Remove only this script's known outputs so stale meshes cannot imply success.
        for name in (
            "body.obj",
            "body.ply",
            "body.glb",
            "bodyParameters.json",
            "front.png",
            "side.png",
            "back.png",
            "failure.json",
        ):
            (folder / name).unlink(missing_ok=True)
        start = time.perf_counter()
        try:
            features = processor.process(source.read_bytes(), folder)
            body = model.reconstruct(features, 172)
            for ext in ("obj", "ply", "glb"):
                body.mesh.export(folder / f"body.{ext}")
            (folder / "bodyParameters.json").write_text(json.dumps(body.parameters, indent=2))
            for view in ("front", "side", "back"):
                render_preview([body.mesh], folder / f"{view}.png", view)
            entry = {
                "input": source.name,
                "status": "valid_template_mesh",
                "quality": body.parameters["quality"],
                "provenance": body.provenance,
            }
        except PipelineError as exc:
            entry = {
                "input": source.name,
                "status": "rejected",
                "code": exc.code,
                "reason": str(exc),
            }
            (folder / "failure.json").write_text(json.dumps(entry, indent=2))
        entry["seconds"] = round(time.perf_counter() - start, 3)
        report.append(entry)
        print(json.dumps(entry), flush=True)
    (ROOT / "experiments/reconstruction-report.json").write_text(json.dumps(report, indent=2))
    if not any(r["status"] == "valid_template_mesh" for r in report):
        raise SystemExit("No valid reconstruction; do not proceed to measurements")


if __name__ == "__main__":
    main()
