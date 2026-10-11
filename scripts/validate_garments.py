"""Milestones 4/5: template topology, collision diagnostics, exports and previews."""

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import trimesh

from ml.fitting.service import fit_garment
from ml.garment.templates import reconstruct_garment
from ml.human.template import MediaPipeTemplateReconstructor
from ml.measurement.service import measure_body
from ml.preprocessing.images import PersonPreprocessor, preprocess_garment
from ml.preview import render_preview
from ml.sizing.engine import recommend


def main():
    folder = ROOT / "experiments/runs/garments"
    folder.mkdir(parents=True, exist_ok=True)
    features = PersonPreprocessor(ROOT / "assets/bodyModels/pose_landmarker_full.task").process(
        (ROOT / "data/raw/studio-person.jpg").read_bytes()
    )
    body = MediaPipeTemplateReconstructor().reconstruct(features, 172)
    measurements = measure_body(body.mesh, body.landmarks)
    garment = preprocess_garment((ROOT / "data/raw/garment-demo.png").read_bytes())
    rows = json.loads((ROOT / "data/brandCharts/demo-v1.json").read_text())["brands"][0]["sizes"]
    report = []
    for category in ["t-shirt", "shirt", "dress", "trouser"]:
        tick = time.perf_counter()
        size = recommend(measurements, rows, category, "regular")["recommendedSize"]
        row = next(r for r in rows if r["sizeLabel"] == size)
        template = reconstruct_garment(garment, category, body, measurements, row, "regular")
        fitted, diagnostics = fit_garment(body.mesh, template)
        scene = trimesh.Scene()
        scene.add_geometry(body.mesh, geom_name="body")
        scene.add_geometry(fitted, geom_name="garment")
        scene.export(folder / f"{category}.glb")
        loaded = trimesh.load(folder / f"{category}.glb", force="scene")
        assert len(loaded.geometry) == 2
        assert any(hasattr(g.visual, "uv") for g in loaded.geometry.values())
        render_preview([body.mesh, fitted], folder / f"{category}.png")
        entry = {
            "category": category,
            "size": size,
            "faces": len(fitted.faces),
            "seconds": round(time.perf_counter() - tick, 2),
            **diagnostics,
        }
        report.append(entry)
        print(json.dumps(entry), flush=True)
    (ROOT / "experiments/garment-report.json").write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
