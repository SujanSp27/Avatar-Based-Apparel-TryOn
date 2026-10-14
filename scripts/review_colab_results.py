"""Audit recovered images and preview revised masks, without running any model.

Visual judgments are supplied separately after image inspection. Pixel equality
and mask coverage are mechanical evidence, not automatic perceptual acceptance.
The collected cloud artifacts are never changed by this script.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import sys
from pathlib import Path
from urllib.parse import quote

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ml.vton.masking import PROTECTED_LABELS, build_replacement_mask, short_sleeve_support
from ml.vton.service import fit_canvas


def read_image(path: Path, mode: str | None = None) -> np.ndarray:
    with Image.open(path) as value:
        return np.array(value.convert(mode) if mode else value)


def preservation_metrics(original, result, labels, edit, alpha) -> dict:
    if (
        original.shape != result.shape or original.ndim != 3
        or labels.shape != original.shape[:2] or edit.shape != labels.shape
        or alpha.shape != labels.shape
    ):
        raise ValueError("Saved images and masks have inconsistent dimensions")
    changed = np.any(original != result, axis=2)
    regions = {"face": (1,), "hair": (2,), "hands": (13,), "lowerClothing": (5, 6), "feet": (15,)}
    return {
        "changedPixelsOutsideEditMask": int(np.count_nonzero(changed & ~edit)),
        "protectedRegions": {
            name: {"pixels": int(np.count_nonzero(np.isin(labels, ids))),
                   "changedPixels": int(np.count_nonzero(changed & np.isin(labels, ids)))}
            for name, ids in regions.items()
        },
        "oldClothingPixelsNotFullyReplaced": int(np.count_nonzero((labels == 3) & (alpha != 255))),
        "limitation": "Pixel preservation is conditional on saved parser labels; it cannot certify fit or texture fidelity.",
    }


def artifact_path(collection: Path, relative: str) -> Path:
    path = (collection / relative).resolve()
    if not path.is_relative_to(collection.resolve()) or not path.is_file():
        raise ValueError(f"Missing or out-of-scope collected artifact: {relative}")
    return path


def review(collection: Path, observations: Path, output: Path) -> dict:
    collection, output = collection.resolve(), output.resolve()
    if output.is_relative_to(collection):
        raise ValueError("Keep the review separate from immutable collected evidence")
    if output.exists() and any(output.iterdir()):
        raise ValueError("Use an empty review directory to preserve earlier evidence")
    collected = json.loads((collection / "collection-report.json").read_text(encoding="utf-8"))
    judgments = json.loads(observations.read_text(encoding="utf-8"))
    if judgments["archiveSha256"] != collected["archiveSha256"]:
        raise ValueError("Visual observations belong to a different result archive")
    if set(judgments["cases"]) != {case["case"] for case in collected["cases"]}:
        raise ValueError("Every recovered case must have an explicit visual assessment")
    output.mkdir(parents=True, exist_ok=True)
    records, sections = [], []
    for case in collected["cases"]:
        report_path = artifact_path(collection, case["report"])
        run = json.loads(report_path.read_text(encoding="utf-8"))
        folder = report_path.parent
        for name, metadata in run["artifacts"].items():
            path = folder / name
            if path.suffix == ".bin":  # explicitly excluded from cloud export
                continue
            path = artifact_path(collection, path.relative_to(collection).as_posix())
            if hashlib.sha256(path.read_bytes()).hexdigest() != metadata["sha256"]:
                raise ValueError(f"Collected artifact changed since inference: {path.name}")
        name = case["case"]
        target = output / name
        target.mkdir()
        labels = read_image(folder / "personParsing.png")
        points = np.asarray(json.loads((folder / "poseKeypoints.json").read_text())["normalized"])
        support = short_sleeve_support(labels, points)
        diagnostics = json.loads((folder / "vton-diagnostics.json").read_text(encoding="utf-8"))
        x0, y0, x1, y1 = diagnostics["personWindow"]
        size = tuple(run["nativeResolution"])
        native_labels, _ = fit_canvas(Image.fromarray(labels[y0:y1, x0:x1]), 0, nearest=True, canvas_size=size)
        native_support, _ = fit_canvas(
            Image.fromarray(support[y0:y1, x0:x1].astype(np.uint8) * 255),
            0, nearest=True, canvas_size=size,
        )
        revised = build_replacement_mask(np.asarray(native_labels), sleeve_support=np.asarray(native_support) > 127)
        previous = read_image(folder / "vton-replacement-mask.png")
        same_mask = np.array_equal(previous, revised)
        Image.fromarray(revised).save(target / "revised-mask-preview.png")
        Image.fromarray(support.astype(np.uint8) * 255).save(target / "source-sleeve-support.png")
        native_array = np.asarray(native_labels)
        record = {
            "case": name, "executionStatus": case["status"], "seconds": run["seconds"],
            "visualReview": judgments["cases"][name], "qualityValidated": False,
            "maskRevision": {
                "newInferencePerformed": False,
                "matchesExecutedMask": bool(same_mask),
                "newlyEditableUpperArmPixels": int(np.count_nonzero((previous == 0) & (revised > 0) & (native_array == 12))),
                "protectedPixelsOpened": int(np.count_nonzero((revised > 0) & np.isin(native_array, PROTECTED_LABELS))),
                "oldClothingPixelsOmitted": int(np.count_nonzero((revised == 0) & (native_array == 3))),
                "limitation": (
                    "Preview matches the mask used for the saved inference; inspect its actual generated sleeves."
                    if same_mask else "Mask geometry only; the saved inference used a different mask."
                ),
            },
            "inputSha256": run["inputSha256"],
            "inferenceArtifactSha256": run["artifacts"],
        }
        final = folder / "tryon-2d.png"
        if final.is_file():
            record["preservation"] = preservation_metrics(
                read_image(folder / "original-person.png", "RGB"), read_image(final, "RGB"), labels,
                read_image(folder / "semantic-edit-mask.png") > 127,
                read_image(folder / "semantic-alpha.png"),
            )
        records.append(record)
        figures = []
        for image_path, caption in (
            (folder / "original-person.png", "Original person"),
            (folder / "vton-garment-input.png", "Actual model garment input"),
            (folder / "vton-model-output.png", "Raw model output (diagnostic)"),
            (final, "Recovered final candidate"),
            (folder / "vton-replacement-mask.png", "Mask used by completed job"),
            (target / "revised-mask-preview.png", "Current mask (matches executed mask)" if same_mask else "Revised mask only; no new inference"),
        ):
            if image_path.is_file():
                url = quote(Path(os.path.relpath(image_path, output)).as_posix(), safe="/.")
                figures.append(f'<figure><a href="{url}"><img src="{url}" alt="{html.escape(caption)}"></a><figcaption>{html.escape(caption)}</figcaption></figure>')
        notes = html.escape(" ".join(judgments["cases"][name]["observations"]))
        verdict = html.escape(judgments["cases"][name]["verdict"])
        sections.append(f'<section><h2>{html.escape(name)}: {verdict}</h2><p>{notes}</p><div class="images">{"".join(figures)}</div></section>')
    report = {
        "archiveSha256": collected["archiveSha256"], "cloudRunCompleted": True,
        "recoveryMethod": "Existing browser download; original archive and collected reports preserved",
        "model": f"{run['model']} {run['checkpoint']}",
        "gpu": run["runtime"]["gpu"]["name"], "nativeResolution": run["nativeResolution"],
        "newInferencePerformed": False, "trainingPerformed": False,
        "qualityValidated": False, "cases": records,
    }
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    page = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Recovered Colab try-on review</title><style>body{font:16px system-ui;margin:24px;background:#eee;color:#222}section{padding:20px;background:white;margin:24px 0}.images{display:flex;flex-wrap:wrap;gap:12px}figure{margin:0;width:280px}img{max-width:100%;height:380px;object-fit:contain;background:#ddd}figcaption{padding:8px}h1,h2{line-height:1.3}</style>
<h1>Recovered Colab try-on review</h1><p>Existing T4 job, four cases. Click an image for its full resolution. Raw outputs and failed candidates are diagnostics. Mask previews did not execute inference. This review does not establish production-quality fitting.</p>'''
    (output / "index.html").write_text(page + "".join(sections) + "</html>", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collection", type=Path, required=True)
    parser.add_argument("--observations", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    result = review(arguments.collection, arguments.observations, arguments.output)
    print(json.dumps({"cases": [{"case": c["case"], "review": c["visualReview"]["verdict"], "maskRevision": c["maskRevision"], "preservation": c.get("preservation")} for c in result["cases"]]}, indent=2))
