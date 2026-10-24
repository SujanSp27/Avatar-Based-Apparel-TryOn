"""Measure retained online runs without inference or modifying their images.

The reference parser mask and target clothing labels must come from the actual
worker. This reports catastrophic color changes and exact preservation regions;
it does not substitute for full-resolution visual review.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ml.vton.garment_fidelity import assess_dark_reference


def review(folder: Path) -> dict:
    def read(name):
        return np.array(Image.open(folder / name))
    original, generated = read('person-input.png'), read('raw.png')
    final = read('result.png')
    source, target = read('source-labels.png'), read('target-labels.png')
    reference, reference_labels = read('garment-input.png'), read('garment-labels.png')
    protected = np.isin(source, (1, 2, 8, 9, 11, 13, 15, 17))
    target_fabric = (target == 3) & ~protected
    measurements = assess_dark_reference(reference, reference_labels == 3, generated, target_fabric)
    regions = {'face': source == 1, 'hair': source == 2, 'bag': source == 8,
               'hands': source == 13, 'jeans': source == 6, 'background': source == 0}
    changed = np.any(original != final, axis=2)
    return {'colorDiagnostic': measurements, 'preservation': {
        name: {'pixels': int(mask.sum()), 'changedPixels': int((mask & changed).sum())}
        for name, mask in regions.items()
    }, 'visualAcceptance': 'pending full-resolution inspection',
        'limitations': 'Parser errors affect these measurements. Non-rejection is not a garment-fidelity certificate.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path)
    args = parser.parse_args()
    report = review(args.folder)
    (args.folder / 'fidelity-metrics.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
