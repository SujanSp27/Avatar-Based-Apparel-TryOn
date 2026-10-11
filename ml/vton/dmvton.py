"""Verified official DM-VTON checkpoints with portable PyTorch inference.

Network source and equations are from the pinned official repository in vendor/.
Only cost-volume execution is ported from CuPy to equivalent native torch ops.
This is a low-resolution, upper-body research model, not a diffusion model.
"""

import hashlib
from pathlib import Path

import numpy as np
from PIL import Image

from ml.errors import PipelineError

COMMIT = "5dcd04ee3f5b1fb392df1184c887c1a7e910c72e"
WEIGHTS = {
    "gen.pth": {"id": "1i-Ple5L9__LV_Fbx1cZyxiOC-CRFxi0C", "size": 26406925, "sha256": "3147a3731e5fc18c473f563a4d896a5ddf620f0a7f293b8fbda3069a76e8e6f7"},
    "warp.pth": {"id": "16H16AhGJrqndDrAaHWZvTFzGSsaDecpS", "size": 86485495, "sha256": "0e2fb5220f0e6829a17de8894c56b09463e08f279aa4ac410bf808bc6287b74e"},
}


def checkpoint_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class DMVTONModel:
    def __init__(self, weights_dir: Path, device: str = "cpu"):
        import torch

        from ml.vton.vendor.dmvton.models.generators.mobile_unet import MobileNetV2_unet
        from ml.vton.vendor.dmvton.models.warp_modules.mobile_afwm import MobileAFWM

        self.device = torch.device(device)
        if self.device.type == "cuda" and not torch.cuda.is_available():
            raise PipelineError("vton_device_unavailable", "CUDA is unavailable in the installed PyTorch runtime.", 503)
        torch.set_num_threads(2)
        self.warp = MobileAFWM(3, align_corners=True)
        self.gen = MobileNetV2_unet(7, 4)
        for name, model in (("warp.pth", self.warp), ("gen.pth", self.gen)):
            path = Path(weights_dir) / name
            expected = WEIGHTS[name]
            if not path.is_file():
                raise PipelineError("vton_model_unavailable", f"Missing pretrained DM-VTON checkpoint {name}.", 503)
            if path.stat().st_size != expected["size"] or checkpoint_hash(path) != expected["sha256"]:
                raise PipelineError("vton_checkpoint_invalid", f"DM-VTON checkpoint {name} failed integrity verification.", 503)
            # Original checkpoints contain optimizer and NumPy scalar metrics.
            # Permit those specific scalar types; never execute arbitrary pickle.
            with torch.serialization.safe_globals([np.core.multiarray.scalar, np.dtype, type(np.dtype("float64"))]):
                saved = torch.load(path, map_location="cpu", weights_only=True)
            state = saved["model"]
            if name == "warp.pth" and "aflow_net.weight" in state:
                # Upstream creates these four fixed second-derivative stencils
                # inside its training-only loss path. They are not inference
                # parameters. Verify the exact constants before omitting them.
                expected_stencils = torch.tensor([
                    [[0, 0, 0], [1, -2, 1], [0, 0, 0]],
                    [[0, 1, 0], [0, -2, 0], [0, 1, 0]],
                    [[1, 0, 0], [0, -2, 0], [0, 0, 1]],
                    [[0, 0, 1], [0, -2, 0], [1, 0, 0]],
                ], dtype=torch.float32).unsqueeze(1)
                if not torch.equal(state["aflow_net.weight"], expected_stencils):
                    raise PipelineError("vton_checkpoint_invalid", "Unexpected training stencil in DM-VTON checkpoint.", 503)
                del state["aflow_net.weight"]
            model.load_state_dict(state, strict=True)
            del saved
            model.to(self.device).eval().requires_grad_(False)
        self.provenance = {
            "backend": "DM-VTON",
            "source": "https://github.com/KiseKloset/DM-VTON",
            "sourceCommit": COMMIT,
            "checkpointSha256": {name: value["sha256"] for name, value in WEIGHTS.items()},
            "loadVerified": True,
            "nativeResolution": [192, 256],
            "device": str(self.device),
            "operator": "native PyTorch equivalent of stride-one 7x7 CuPy cost volume",
            "license": "CC-BY-NC-SA-4.0; academic/non-commercial research",
        }

    def predict(self, person: Image.Image, garment: Image.Image, garment_mask: Image.Image) -> tuple[Image.Image, Image.Image]:
        import torch
        import torch.nn.functional as F

        if any(image.size != (192, 256) for image in (person, garment, garment_mask)):
            raise ValueError("DM-VTON requires explicitly prepared 192x256 inputs")

        def tensor(image):
            array = np.array(image.convert("RGB"), dtype=np.float32) / 127.5 - 1.0
            return torch.from_numpy(array.transpose(2, 0, 1)).unsqueeze(0).to(self.device)

        def pil(value):
            array = ((value.squeeze(0).permute(1, 2, 0).cpu().numpy() + 1) * 127.5)
            return Image.fromarray(np.rint(array).clip(0, 255).astype(np.uint8))

        with torch.inference_mode():
            person_tensor = tensor(person)
            edge = torch.from_numpy((np.array(garment_mask.convert("L")) > 127).astype(np.float32))[None, None].to(self.device)
            cloth = tensor(garment) * edge
            warped, flow = self.warp(person_tensor, cloth, phase="test")
            warped_edge = F.grid_sample(edge, flow.permute(0, 2, 3, 1), mode="bilinear", padding_mode="zeros", align_corners=True)
            outputs = self.gen(torch.cat([person_tensor, warped, warped_edge], dim=1))
            rendered, blend = torch.split(outputs, [3, 1], dim=1)
            blend = torch.sigmoid(blend) * warped_edge
            generated = warped * blend + torch.tanh(rendered) * (1 - blend)
            if not torch.isfinite(generated).all() or not torch.isfinite(flow).all():
                raise PipelineError("vton_invalid_output", "The pretrained model produced invalid values; no result was published.", 500)
            return pil(generated), pil(warped)
