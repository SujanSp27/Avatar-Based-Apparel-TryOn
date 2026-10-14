"""Local pinned CatVTON inference with supplied semantic replacement masks.

The denoising algorithm comes from the vendored official implementation. The
adapter loads only safetensors locally, runs classifier-free guidance sequentially
to limit peak VRAM, and always applies the official safety checker on CPU.
"""

import hashlib
import json
from pathlib import Path
from threading import Lock

import numpy as np
from PIL import Image

from ml.errors import PipelineError
from ml.progress import report_progress

SOURCE_COMMIT = "999bdbe81e6008a3f5749af7c1e0b0fa3d21b48e"
BASE_REVISION = "8a4288a76071f7280aedbdb3253bdb9e9d5d84bb"
ATTN_REVISION = "2969fcf85fe62f2036605716f0b56f0b81d01d79"
VAE_REVISION = "31f26fdeee1355a5c34592e401dd41e45d25a493"
MIX_CHECKPOINT = "attention/mix-48k-1024/attention/model.safetensors"
MIX_SHA256 = "a1fc093f1b6744623079e6f4e7313411f524e388c4b7467df1e0e7f577cba23a"
CHECKPOINTS = {
    "base/unet/diffusion_pytorch_model.fp16.safetensors": "24b788b4a777748377cc20364eea4ae113c8c42f4468c16bc8c02fdae5492af9",
    "attention/vitonhd-16k-512/attention/model.safetensors": "915df7bf19a33bee36a28d5f9ceaef1e2267c47526f98ca9e4c49e90ae5f0fd0",
    "vae/diffusion_pytorch_model.safetensors": "a1d993488569e928462932c8c38a0760b874d166399b14414135bd9c42df5815",
    "base/safety_checker/model.fp16.safetensors": "08902f19b1cfebd7c989f152fc0507bef6898c706a91d666509383122324b511",
}
REQUIRED_FILES = (
    *CHECKPOINTS,
    "base/unet/config.json",
    "base/scheduler/scheduler_config.json",
    "vae/config.json",
    "base/safety_checker/config.json",
    "base/feature_extractor/preprocessor_config.json",
    "download-manifest.json",
)


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_shared_attention_weights(module, state: dict) -> None:
    """Restore aliases omitted by Accelerate's safetensors deduplication.

    Upstream's attention ModuleList registers each Attention and its children.
    Safetensors stores each shared parameter once. Require checkpoint coverage
    of every unique parameter before expanding only verified object aliases.
    """
    import torch

    expected = module.state_dict()
    if set(state) - set(expected):
        raise ValueError("Unexpected CatVTON attention checkpoint keys")
    aliases = {}
    for name, parameter in module.named_parameters(remove_duplicate=False):
        aliases.setdefault(id(parameter), []).append(name)
    expanded = dict(state)
    for names in aliases.values():
        supplied = [state[name] for name in names if name in state]
        if not supplied:
            raise ValueError(f"Checkpoint does not cover attention parameter {names[0]}")
        if any(not torch.equal(supplied[0], other) for other in supplied[1:]):
            raise ValueError("Conflicting values for shared attention parameter")
        for name in names:
            expanded[name] = supplied[0]
    module.load_state_dict(expanded, strict=True)


class CatVTONModel:
    """Native 384x512 upper-body inference; no request downloads any files."""

    def __init__(
        self, weights_dir: Path, device: str = "cuda", *, guidance_scale: float = 2.5,
        seed: int = 42, checkpoint: str = "vitonhd", height: int = 512,
    ):
        if height not in {512, 1024}:
            raise ValueError("CatVTON height must be 512 or 1024")
        self.native_size = (height * 3 // 4, height)
        if checkpoint not in {"vitonhd", "mix"}:
            raise ValueError("CatVTON checkpoint must be vitonhd or mix")
        self.checkpoint = checkpoint
        if not np.isfinite(guidance_scale) or not 1 <= guidance_scale <= 10:
            raise ValueError("CatVTON guidance_scale must be between 1 and 10")
        self.guidance_scale = float(guidance_scale)
        self.seed = int(seed)
        self.weights_dir = Path(weights_dir).resolve()
        self._lock = Lock()
        for name in REQUIRED_FILES:
            if not (self.weights_dir / name).is_file():
                raise PipelineError(
                    "vton_model_unavailable",
                    f"Missing CatVTON asset {name}. Run scripts/download_vton.py.",
                    503,
                )
        for name, expected in CHECKPOINTS.items():
            if _hash(self.weights_dir / name) != expected:
                raise PipelineError(
                    "vton_checkpoint_invalid",
                    f"CatVTON asset {name} failed SHA-256 verification.",
                    503,
                )
        try:
            manifest = json.loads((self.weights_dir / "download-manifest.json").read_text())
            if manifest.get("sourceCommit") != SOURCE_COMMIT:
                raise ValueError("Wrong CatVTON source revision")
            records = manifest["files"]
            expected_files = set(REQUIRED_FILES) - {"download-manifest.json"}
            if (
                len(records) != len(expected_files)
                or {r["file"] for r in records} != expected_files
            ):
                raise ValueError("Incomplete or duplicated CatVTON asset manifest")
            for record in records:
                path = (self.weights_dir / record["file"]).resolve()
                if not path.is_relative_to(self.weights_dir):
                    raise ValueError("Manifest path outside model directory")
                if path.stat().st_size != record["bytes"]:
                    raise ValueError("Manifest asset size mismatch")
                if (
                    record["file"] in CHECKPOINTS
                    and record["sha256"] != CHECKPOINTS[record["file"]]
                ):
                    raise ValueError("Manifest checkpoint checksum mismatch")
                if record["file"] not in CHECKPOINTS and _hash(path) != record["sha256"]:
                    raise ValueError("Manifest asset checksum mismatch")
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise PipelineError(
                "vton_checkpoint_invalid", "CatVTON asset manifest validation failed.", 503
            ) from exc
        attention_path = "attention/vitonhd-16k-512/attention/model.safetensors"
        if checkpoint == "mix":
            attention_path = MIX_CHECKPOINT
            if not (self.weights_dir / attention_path).is_file():
                raise PipelineError(
                    "vton_model_unavailable",
                    "Missing mixed CatVTON checkpoint. Run scripts/download_vton_mix.py.", 503,
                )
            if _hash(self.weights_dir / attention_path) != MIX_SHA256:
                raise PipelineError(
                    "vton_checkpoint_invalid", "Mixed CatVTON checkpoint checksum mismatch.", 503
                )
        try:
            from ml.vton.runtime import configure_local_cache

            configure_local_cache()
            import torch
            from diffusers import AutoencoderKL, DDIMScheduler, UNet2DConditionModel
            from diffusers.pipelines.stable_diffusion.safety_checker import (
                StableDiffusionSafetyChecker,
            )
            from safetensors.torch import load_file
            from transformers import CLIPImageProcessor

            from ml.vton.vendor.catvton.model.attn_processor import SkipAttnProcessor
            from ml.vton.vendor.catvton.model.pipeline import CatVTONPipeline
            from ml.vton.vendor.catvton.model.utils import get_trainable_module, init_adapter
        except ImportError as exc:
            raise PipelineError(
                "vton_model_unavailable",
                "Install requirements-vton.txt to load the pretrained CatVTON model.",
                503,
            ) from exc
        self.device = torch.device(device)
        if self.device.type == "cuda" and not torch.cuda.is_available():
            raise PipelineError(
                "vton_device_unavailable",
                "CatVTON needs the CUDA PyTorch runtime on this machine; CUDA is currently unavailable.",
                503,
            )
        if self.device.type not in {"cpu", "cuda"}:
            raise PipelineError(
                "vton_device_unavailable", "CatVTON supports CPU or CUDA in this application.", 503
            )
        torch.set_num_threads(2)
        self.dtype = torch.float16 if self.device.type == "cuda" else torch.float32
        # This GTX 1650/cuDNN combination emits NaNs in FP16 Conv2d. Promote
        # only convolution arithmetic, retaining FP16 resident weights.
        # Both the real layer diagnostic and numerical tests verify FP32 math.
        self.promote_convolutions = (
            self.device.type == "cuda" and "GTX 16" in torch.cuda.get_device_name(self.device)
        )
        self.cudnn_enabled = torch.backends.cudnn.enabled

        class SequentialGuidanceUNet(torch.nn.Module):
            """Identical independent CFG passes, with batch size one on a 4GB GPU."""

            def __init__(self, model):
                super().__init__()
                self.model = model

            def forward(self, sample, timestep, **kwargs):
                predictions = []
                for part in sample.split(1):
                    output = self.model(part, timestep, **kwargs)[0]
                    if not torch.isfinite(output).all():
                        raise PipelineError(
                            "vton_invalid_output",
                            "CatVTON produced invalid numeric values; no image was published.",
                            500,
                        )
                    predictions.append(output)
                return (torch.cat(predictions),)

        class CheckedVAE(torch.nn.Module):
            """Prevent FP16 overflow from becoming a superficially successful PNG."""

            def __init__(self, model):
                super().__init__()
                self.model = model

            @property
            def config(self):
                return self.model.config

            @property
            def device(self):
                return self.model.device

            @property
            def dtype(self):
                return self.model.dtype

            def encode(self, pixels):
                encoded = self.model.encode(pixels)
                if (
                    not torch.isfinite(encoded.latent_dist.mean).all()
                    or not torch.isfinite(encoded.latent_dist.logvar).all()
                ):
                    raise PipelineError(
                        "vton_invalid_output",
                        "The VAE produced invalid values at this precision; no image was published.",
                        500,
                    )
                return encoded

            def decode(self, latents):
                decoded = self.model.decode(latents)
                if not torch.isfinite(decoded.sample).all():
                    raise PipelineError(
                        "vton_invalid_output",
                        "The VAE produced invalid pixels at this precision; no image was published.",
                        500,
                    )
                return decoded

        base = self.weights_dir / "base"
        safe_load = {"local_files_only": True, "use_safetensors": True, "low_cpu_mem_usage": True}
        try:
            pipeline = CatVTONPipeline.__new__(CatVTONPipeline)
            pipeline.device = self.device
            pipeline.weight_dtype = self.dtype
            # The public adapter below always executes the official checker and
            # raises an actionable error. Do not use upstream's static placeholder.
            pipeline.skip_safety_check = True
            pipeline.noise_scheduler = DDIMScheduler.from_pretrained(
                str(base), subfolder="scheduler", local_files_only=True
            )
            unet = UNet2DConditionModel.from_pretrained(
                str(base), subfolder="unet", variant="fp16", torch_dtype=self.dtype, **safe_load
            )
            init_adapter(unet, cross_attn_cls=SkipAttnProcessor)
            if height == 1024:
                from ml.vton.attention import QuerySlicedAttnProcessor2_0

                unet.set_attn_processor({
                    name: QuerySlicedAttnProcessor2_0(query_chunk_size=256)
                    if name.endswith("attn1.processor") else processor
                    for name, processor in unet.attn_processors.items()
                })
            attention = get_trainable_module(unet, "attention")
            state = load_file(
                str(self.weights_dir / attention_path),
                device="cpu",
            )
            load_shared_attention_weights(attention, state)
            del state, attention
            unet = unet.eval().requires_grad_(False).to(self.device)
            from ml.vton.precision import promote_conv2d_math_to_float32

            promoted_layers = promote_conv2d_math_to_float32(unet) if self.promote_convolutions else 0
            pipeline.unet = SequentialGuidanceUNet(unet)
            pipeline.vae = (
                AutoencoderKL.from_pretrained(
                    str(self.weights_dir / "vae"), torch_dtype=self.dtype, **safe_load
                )
                .eval()
                .requires_grad_(False)
                .to(self.device)
            )
            pipeline.vae.enable_slicing()
            if height == 1024:
                pipeline.vae.enable_tiling()
            if self.promote_convolutions:
                promoted_layers += promote_conv2d_math_to_float32(pipeline.vae)
            pipeline.vae = CheckedVAE(pipeline.vae)
            self.feature_extractor = CLIPImageProcessor.from_pretrained(
                str(base), subfolder="feature_extractor", local_files_only=True
            )
            self.safety_checker = (
                StableDiffusionSafetyChecker.from_pretrained(
                    str(base),
                    subfolder="safety_checker",
                    variant="fp16",
                    torch_dtype=torch.float32,
                    **safe_load,
                )
                .eval()
                .requires_grad_(False)
                .to("cpu")
            )
            self.pipeline = pipeline
        except (OSError, ValueError, RuntimeError) as exc:
            raise PipelineError(
                "vton_model_load_failed",
                "The verified CatVTON model could not load. Check available memory and the installed PyTorch/CUDA runtime.",
                503,
            ) from exc
        self.provenance = {
            "backend": "CatVTON",
            "source": "https://github.com/Zheng-Chong/CatVTON",
            "sourceCommit": SOURCE_COMMIT,
            "baseModel": "stable-diffusion-v1-5/stable-diffusion-inpainting",
            "baseRevision": BASE_REVISION,
            "attentionCheckpoint": f"zhengchong/CatVTON/{Path(attention_path).parts[1]}",
            "attentionRevision": ATTN_REVISION,
            "vaeModel": "stabilityai/sd-vae-ft-mse",
            "vaeRevision": VAE_REVISION,
            "checkpointSha256": {
                **CHECKPOINTS, **({MIX_CHECKPOINT: MIX_SHA256} if checkpoint == "mix" else {})
            },
            "loadVerified": True,
            "nativeResolution": list(self.native_size),
            "trainedResolution": [768, 1024] if checkpoint == "mix" else [384, 512],
            "device": str(self.device),
            "dtype": str(self.dtype),
            "cudnnEnabled": self.cudnn_enabled,
            "convolutionMath": "float32" if self.promote_convolutions else str(self.dtype),
            "promotedConvolutionLayers": promoted_layers,
            "inferenceSteps": 50,
            "guidanceScale": self.guidance_scale,
            "seed": self.seed,
            "attention": (
                "Full memory-efficient CUDA self attention when supported, otherwise exact "
                "256-query chunks; official cross attention skip"
                if height == 1024 else "Official SDPA self attention; official cross attention skip"
            ),
            "memoryPolicy": "Sequential classifier-free guidance; CPU safety checker; VAE slicing",
            "vaeTiling": height == 1024,
            "safetyChecker": "Official Stable Diffusion checker runs on every generated image, on CPU",
            "maskSource": "Caller-supplied semantic binary replacement mask; not upstream SCHP/DensePose automasking",
            "license": "CC-BY-NC-SA-4.0; research/non-commercial use",
        }

    def predict(
        self, person: Image.Image, garment: Image.Image, replacement_mask: Image.Image
    ) -> Image.Image:
        import torch

        native_size = getattr(self, "native_size", (384, 512))
        if any(image.size != native_size for image in (person, garment, replacement_mask)):
            raise ValueError(f"CatVTON requires explicitly prepared {native_size} inputs")
        mask = np.asarray(replacement_mask.convert("L"))
        if not np.any(mask > 127) or np.all(mask > 127):
            raise PipelineError(
                "vton_invalid_mask",
                "The clothing replacement mask must cover clothing while preserving the rest of the person.",
            )
        devices = [self.device.index or 0] if self.device.type == "cuda" else []
        try:
            with (
                self._lock,
                torch.inference_mode(),
                torch.random.fork_rng(devices=devices),
                torch.backends.cudnn.flags(enabled=getattr(self, "cudnn_enabled", True)),
            ):
                seed = getattr(self, "seed", 42)
                torch.manual_seed(seed)
                generator = torch.Generator(device=self.device).manual_seed(seed)
                completed = 0

                def denoising_step(*_):
                    nonlocal completed
                    completed += 1
                    report_progress("generating", completed, 50)

                report_progress("encoding_images")
                hook = self.pipeline.unet.register_forward_hook(denoising_step)
                try:
                    generated = self.pipeline(
                        image=person.convert("RGB"),
                        condition_image=garment.convert("RGB"),
                        mask=replacement_mask.convert("L"),
                        height=native_size[1],
                        width=native_size[0],
                        num_inference_steps=50,
                        guidance_scale=getattr(self, "guidance_scale", 2.5),
                        generator=generator,
                    )[0]
                finally:
                    hook.remove()
                report_progress("checking_output")
                features = self.feature_extractor(images=[generated], return_tensors="pt")
                pixels = np.asarray(generated, dtype=np.float32)[None] / 255.0
                _, unsafe = self.safety_checker(
                    images=pixels.copy(),
                    clip_input=features.pixel_values.to("cpu", dtype=torch.float32),
                )
                if any(unsafe):
                    raise PipelineError(
                        "vton_output_rejected",
                        "The generated image was rejected by the model's image safety checker. Try a clearly visible, fully clothed person and garment.",
                    )
                return generated
        except torch.cuda.OutOfMemoryError as exc:
            torch.cuda.empty_cache()
            raise PipelineError(
                "vton_memory_exhausted",
                "The GPU ran out of memory during CatVTON inference. Close other GPU applications and retry.",
                503,
            ) from exc
