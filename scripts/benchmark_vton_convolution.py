"""Check the observed GTX 16xx numerical failure with an actual UNet layer."""

import json
import time
from pathlib import Path

import torch
from safetensors import safe_open
from torch.nn import functional as F

ROOT = Path(__file__).resolve().parents[1]
WEIGHTS = ROOT / "assets/vton/catvton/base/unet/diffusion_pytorch_model.fp16.safetensors"


def main():
    torch.set_num_threads(2)
    torch.manual_seed(42)
    with safe_open(WEIGHTS, framework="pt", device="cpu") as file:
        weight = file.get_tensor("down_blocks.0.resnets.0.conv1.weight").cuda()
        bias = file.get_tensor("down_blocks.0.resnets.0.conv1.bias").cuda()
    sample = torch.randn((1, 320, 128, 48), device="cuda", dtype=torch.float16)
    records = []
    outputs = {}
    with torch.inference_mode():
        for label, dtype, enabled, deterministic in (
            ("cudnn-half", torch.float16, True, False),
            ("cudnn-half-deterministic", torch.float16, True, True),
            ("cudnn-float", torch.float32, True, False),
            ("native-half", torch.float16, False, False),
        ):
            with torch.backends.cudnn.flags(enabled=enabled, deterministic=deterministic):
                x, w, b = sample.to(dtype), weight.to(dtype), bias.to(dtype)
                torch.cuda.synchronize()
                start = time.perf_counter()
                for _ in range(5):
                    output = F.conv2d(x, w, b, padding=1)
                torch.cuda.synchronize()
                records.append(
                    {
                        "mode": label,
                        "secondsPerLayer": (time.perf_counter() - start) / 5,
                        "finite": bool(torch.isfinite(output).all()),
                    }
                )
                outputs[label] = output.float().cpu()
    reference = outputs["cudnn-float"]
    for row in records:
        if row["finite"]:
            row["relativeRMSE"] = float(
                (outputs[row["mode"]] - reference).square().mean().sqrt()
                / reference.square().mean().sqrt()
            )
    report = {
        "torch": torch.__version__,
        "gpu": torch.cuda.get_device_name(),
        "layer": "down_blocks.0.resnets.0.conv1",
        "results": records,
    }
    (ROOT / "experiments/vton-convolution-report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
