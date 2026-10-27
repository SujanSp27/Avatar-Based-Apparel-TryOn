"""Private, reproducible comparison ledger; never publishes or approves products."""
from __future__ import annotations

import argparse
import html
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path

from scripts.evaluate_wardrobe import ROOT, catalog_rows, digest, save


def collect(folder: Path, variant: str):
    cases = []
    for path in sorted(folder.glob("cases/*/*/trial.json")):
        trial = json.loads(path.read_text())
        review_path = path.with_name("visual-review.json")
        review = json.loads(review_path.read_text()) if review_path.exists() else {}
        output = path.with_name("after.png")
        current_output = (output.is_file() and digest(output.read_bytes()) == trial.get("outputSha256"))
        current_review = (current_output and review.get("outputSha256") == trial.get("outputSha256")
                          and review.get("fullResolutionInspected") is True)
        seconds = trial.get("observedEndToEndSeconds")
        timing_pass = type(seconds) in (int, float) and math.isfinite(seconds) and 0 < seconds < 30
        diagnostics = trial.get("diagnostics", {})
        cases.append({
            "id": trial["productId"], "person": trial["personId"], "variant": variant,
            "status": trial["status"], "jobId": trial["jobId"], "outputHashVerified": bool(current_output),
            "visualDecision": review.get("decision") if current_review else "pending_or_stale",
            "visualNotes": review.get("notes") if current_review else None,
            "seconds": seconds, "under30Seconds": timing_pass,
            "serverSeconds": trial.get("timingSeconds"), "stages": diagnostics.get("stageSeconds"),
            "transport": diagnostics.get("transport"), "error": trial.get("error"),
            "model": {key: diagnostics.get(key) for key in
                      ("sourceCommit", "modelRevision", "gpu", "dtype", "steps", "modelResolution")},
            "inputHashes": trial["inputs"], "folder": str(path.parent.resolve()),
        })
    return cases


def write_report(baseline: Path, experiment: Path, destination: Path):
    cases = collect(baseline, "catalog_original") + collect(experiment, "background_only_experiment")
    rows = {row["id"]: row for row in catalog_rows()}
    generated = [case for case in cases if case["status"] == "generated"]
    durations = [case["seconds"] for case in generated if type(case["seconds"]) in (float, int)
                 and math.isfinite(case["seconds"])]
    manifest = json.loads((ROOT / "data/catalog/wardrobe-approved-v1.json").read_text())
    summary = {
        "generatedAt": datetime.now(timezone.utc).isoformat(), "catalogCount": len(rows),
        "distinctGarmentsSubmitted": len({case["id"] for case in cases}), "trialCount": len(cases),
        "generatedCount": len(generated), "inferenceFailures": sum(c["status"] == "failed" for c in cases),
        "reviewedOutputs": sum(c["visualDecision"] != "pending_or_stale" for c in generated),
        "visuallyPassingCases": sum(c["visualDecision"] == "visual_pass" for c in generated),
        "under30SecondCases": sum(c["under30Seconds"] for c in generated),
        "minimumSeconds": min(durations) if durations else None,
        "maximumSeconds": max(durations) if durations else None,
        "publishedCount": len(manifest["garments"]) if manifest["enforced"] else 0,
        "limitation": "A visually passing single case is not garment approval. Publication requires both people, all provenance/mask checks and strict end-to-end latency. Experimental inputs are not catalog approvals.",
    }
    save(destination / "summary.json", {"summary": summary, "cases": cases})
    lines = ["# Wardrobe trial ledger", "", summary["limitation"], "",
             f"{len(cases)} trials; {len(generated)} generated outputs; {summary['reviewedOutputs']} reviewed outputs; "
             f"{summary['publishedCount']} published approvals.", "",
             "| Garment | Person / input | Status | Visual review | Total seconds | Preprocess / generation / postprocess | Evidence |",
             "| --- | --- | --- | --- | --- | --- | --- |"]
    cards = []

    def relative(path):
        return Path(os.path.relpath(path, destination)).as_posix()

    for case in cases:
        folder = Path(case["folder"])
        name = rows.get(case["id"], {}).get("name", case["id"])
        title = f"{name} / {case['person']} / {case['variant']}"
        timing = " / ".join(str((case["stages"] or {}).get(key, "—")) for key in
                            ("preprocessing", "generation", "postprocessingAndSaving"))
        note = case["visualNotes"] or (case["error"] or {}).get("message", "Review pending")
        lines.append(f"| {case['id']} — {name} | {case['person']} / {case['variant']} | {case['status']} | "
                     f"{case['visualDecision']} | {case['seconds'] or '—'} | {timing} | "
                     f"[Trial]({relative(folder / 'trial.json')}) · [Comparison]({relative(folder / 'comparison.jpg')}) |")
        pictures = []
        for file, label in (("before.png", "Original person"), ("garment.bin", "Actual input garment"), ("after.png", "Generated output")):
            if (folder / file).is_file():
                pictures.append(f'<figure><img loading="lazy" src="{html.escape(relative(folder / file), quote=True)}" '
                                f'alt="{label}"><figcaption>{label}</figcaption></figure>')
        cards.append(f'<article><h2>{html.escape(title)}</h2><p>{html.escape(case["visualDecision"])} · '
                     f'{case["seconds"] or "unmeasured"} seconds end to end</p><div class="pictures">'
                     + "".join(pictures) + f'</div><p>{html.escape(str(note))}</p></article>')
    (destination / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (destination / "comparisons.html").write_text(
        '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; img-src \'self\'; style-src \'unsafe-inline\'">'
        '<title>Private wardrobe trial review</title><style>body{font:16px system-ui;background:#faf9f5;color:#233a30;'
        'max-width:1200px;margin:32px auto;padding:16px}article{border:1px solid #d8ddd4;padding:18px;margin:24px 0}'
        '.pictures{display:flex;gap:12px}figure{margin:0;flex:1;min-width:0}img{width:100%;height:500px;object-fit:contain}'
        '@media(max-width:650px){.pictures{flex-wrap:wrap}figure{flex-basis:100%}}</style>'
        '<h1>Private wardrobe trial review</h1><p>Actual saved inputs and outputs. Visual review is separate from successful generation.</p>'
        + "".join(cards) + '</html>', encoding="utf-8")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=ROOT / "experiments/wardrobe-curation")
    parser.add_argument("--experiment", type=Path, default=ROOT / "experiments/wardrobe-neutral")
    parser.add_argument("--output", type=Path, default=ROOT / "experiments/wardrobe-review")
    args = parser.parse_args()
    if not all(path.resolve().is_relative_to((ROOT / "experiments").resolve()) for path in
               (args.baseline, args.experiment, args.output)):
        parser.error("All trial reports must remain in the private experiments directory")
    print(json.dumps(write_report(args.baseline, args.experiment, args.output), indent=2))
