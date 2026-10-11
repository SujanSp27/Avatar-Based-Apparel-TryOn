"""Locate numerical failures using the actual prepared regression inputs."""

import argparse
import json
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import torch
from PIL import Image

from ml.vton.catvton import CatVTONModel


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--disable-cudnn", action="store_true")
    args = parser.parse_args()
    torch.backends.cudnn.enabled = not args.disable_cudnn
    model = CatVTONModel(ROOT / "assets/vton/catvton", "cuda")
    folder = ROOT / "experiments/runs/catvton-initial/reported-striped-shirt"
    report = {"cudnnEnabled": torch.backends.cudnn.enabled, "failures": []}

    def hook(name):
        def check(module, inputs, output):
            if isinstance(output, torch.Tensor) and not torch.isfinite(output).all():
                row = {
                    "layer": name,
                    "type": type(module).__name__,
                    "outputShape": list(output.shape),
                }
                row["inputs"] = [
                    {
                        "shape": list(x.shape),
                        "finite": bool(torch.isfinite(x).all()),
                        "maxAbs": float(x.abs().max()),
                    }
                    for x in inputs
                    if isinstance(x, torch.Tensor)
                ]
                report["failures"].append(row)
                raise RuntimeError(f"First nonfinite layer: {row}")

        return check

    handles = [
        module.register_forward_hook(hook(name))
        for name, module in model.pipeline.unet.model.named_modules()
        if not list(module.children())
    ]
    try:
        result = model.predict(
            Image.open(folder / "vton-person-input.png"),
            Image.open(folder / "vton-garment-input.png"),
            Image.open(folder / "vton-replacement-mask.png"),
        )
        result.save(folder / "numerical-diagnostic-output.png")
        report["status"] = "generated"
    except Exception:
        report["status"] = "failed"
        report["traceback"] = traceback.format_exc()
    finally:
        for handle in handles:
            handle.remove()
    path = (
        ROOT
        / "experiments"
        / ("vton-numerics-no-cudnn.json" if args.disable_cudnn else "vton-numerics.json")
    )
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
