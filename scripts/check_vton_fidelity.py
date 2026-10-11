"""Inspect retained VTON outputs without loading any inference model.

Usage: python scripts/check_vton_fidelity.py RUN_FOLDER [RUN_FOLDER ...]
Each run must contain the recorded garment input/mask, final composite and its
generated semantic parsing. The diagnostic never rewrites those image assets.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ml.vton.quality import assess_garment_fidelity


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folders", nargs="+", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    reports = []
    for folder in args.folders:
        names = [
            "vton-garment-input.png",
            "vton-garment-mask.png",
            "tryon-2d.png",
            "generatedParsing.png",
        ]
        images = []
        for name in names:
            with Image.open(folder / name) as image:
                images.append(np.array(image))
        garment, garment_mask, result, result_labels = images
        assessment = assess_garment_fidelity(garment, garment_mask, result, result_labels == 3)
        reports.append({"folder": str(folder), **assessment.as_dict()})
    report = {
        "limitations": "A narrow catastrophic stripe-loss heuristic, not a general quality or fitting validator.",
        "runs": reports,
    }
    encoded = json.dumps(report, indent=2, allow_nan=False)
    print(encoded)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(encoded + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
