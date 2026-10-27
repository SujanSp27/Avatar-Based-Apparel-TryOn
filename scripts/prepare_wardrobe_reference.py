"""Controlled background-only experiment using a retrieved actual parser mask.

No generated contour, recolouring, warping or cropping. Must be visually reviewed
before testing; this tool does not change a product, default preprocessing or model.
"""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from backend.app.config import ROOT
from scripts.evaluate_wardrobe import digest, save


def prepare(case: Path, output: Path):
    trial = json.loads((case / "trial.json").read_text())
    if trial["inputs"]["photoType"] != "flat-lay":
        raise ValueError("Experiment is limited to isolated garment photos")
    image = np.asarray(Image.open(case / "garment-input.png").convert("RGB"))
    labels = np.asarray(Image.open(case / "garment-labels.png"))
    category = trial["diagnostics"]["category"]
    allowed = {"tops": [3], "bottoms": [5, 6], "one-pieces": [4]}[category]
    mask = np.isin(labels, allowed)
    if mask.shape != image.shape[:2] or not .05 < mask.mean() < .90:
        raise ValueError("Garment mask has insufficient or excessive coverage")
    if mask[0].any() or mask[-1].any() or mask[:, 0].any() or mask[:, -1].any():
        raise ValueError("Garment mask reaches the border; cannot infer hidden contours")
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8))
    if count < 2 or stats[1:, cv2.CC_STAT_AREA].max() / mask.sum() < .98:
        raise ValueError("Garment mask contains separate major components")
    prepared = image.copy()
    prepared[~mask] = 127
    output.mkdir(parents=True, exist_ok=True)
    path = output / (trial["productId"] + ".png")
    Image.fromarray(prepared).save(path)
    # Boundary diagnostic is separate from conditioning; never feed coloured outlines.
    contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    overlay = image.copy()
    cv2.drawContours(overlay, contours, -1, (255, 0, 0), 2)
    Image.fromarray(overlay).save(output / (trial["productId"] + "-boundary.png"))
    save(output / (trial["productId"] + ".json"), {
        "status": "experimental_not_approved", "sourceSha256": trial["inputs"]["garmentSha256"],
        "normalizedSourceRgbSha256": digest(image.tobytes()), "preparedSha256": digest(path.read_bytes()),
        "maskSha256": digest((case / "garment-labels.png").read_bytes()),
        "fabricPixelsUnchanged": bool(np.array_equal(image[mask], prepared[mask])),
        "foregroundFraction": float(mask.mean()), "reviewRequired": "Inspect full outline before inference",
    })


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if not all(p.resolve().is_relative_to((ROOT / "experiments").resolve()) for p in (args.case, args.output)):
        parser.error("All artifacts must stay in private experiments")
    prepare(args.case, args.output)
