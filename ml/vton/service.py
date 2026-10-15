"""Prepare actual photos for learned VTON and preserve unrelated source pixels."""

import importlib.util
import json
import logging
from pathlib import Path
from threading import Lock

import numpy as np
from PIL import Image

from ml.errors import PipelineError
from ml.preprocessing.images import ImageFeatures, crop_foreground, decode_image, preprocess_garment
from ml.progress import report_progress

logger = logging.getLogger(__name__)
SUPPORTED = ("t-shirt", "shirt")
VERSION = "catvton-vitonhd-16k-512"
NATIVE_SIZE = (384, 512)


def person_window(labels: np.ndarray) -> tuple[int, int, int, int]:
    """Condition the upper-body model on a portrait crop, not a stretched full body.

    This rectangular window is only model input framing. The final replacement
    mask is semantic and never the rectangle itself.
    """
    shirt_y, shirt_x = np.where(labels == 3)
    if shirt_y.size < labels.size * 0.01:
        raise PipelineError(
            "vton_clothing_not_found",
            "The clothing parser could not find a clear upper-body garment. Use a front-facing photo with the shirt and both shoulders visible.",
        )
    head_y, _ = np.where(np.isin(labels, [1, 2, 9, 11]))
    if head_y.size < labels.size * 0.001:
        raise PipelineError(
            "vton_head_not_found",
            "The face and head must be clearly visible so their original pixels can be preserved.",
        )
    h, w = labels.shape
    shirt_width = float(shirt_x.max() - shirt_x.min() + 1)
    top = max(0, int(head_y.min() - shirt_width * 0.08))
    bottom = min(h, int(shirt_y.max() + shirt_width * 0.20 + 1))
    height = max(bottom - top, shirt_width * 1.28 / 0.75)
    # Keep the image intact near its boundaries; letterboxing below preserves aspect.
    width = height * 0.75
    centre_x = (shirt_x.min() + shirt_x.max()) / 2
    return max(0, int(centre_x - width / 2)), top, min(w, int(centre_x + width / 2 + 1)), bottom


def fit_canvas(
    image: Image.Image, fill, *, nearest=False, canvas_size=NATIVE_SIZE
) -> tuple[Image.Image, tuple[int, int, int, int]]:
    """Aspect-preserving model input, with reversible padding coordinates."""
    width, height = canvas_size
    scale = min(width / image.width, height / image.height)
    size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    resized = image.resize(size, Image.Resampling.NEAREST if nearest else Image.Resampling.LANCZOS)
    left, top = (width - size[0]) // 2, (height - size[1]) // 2
    canvas = Image.new(image.mode, canvas_size, fill)
    canvas.paste(resized, (left, top))
    return canvas, (left, top, left + size[0], top + size[1])


class PretrainedTryOn:
    def __init__(
        self, root: Path, device: str = "cuda", *, guidance_scale: float = 2.5,
        seed: int = 42, checkpoint: str = "vitonhd", height: int = 512,
        conditioning: str = "official",
    ):
        if height not in {512, 1024}:
            raise ValueError("CatVTON height must be 512 or 1024")
        self.root = Path(root)
        self.device = device
        self.guidance_scale = guidance_scale
        self.seed = seed
        self.checkpoint = checkpoint
        self.conditioning = conditioning
        self.native_size = (height * 3 // 4, height)
        self.version = VERSION if checkpoint == "vitonhd" else "catvton-mix-48k-1024"
        self._model = None
        self._parser = None
        self._lock = Lock()

    def availability(self) -> dict:
        missing = [
            name
            for name in ("torch", "transformers", "safetensors", "diffusers", "accelerate")
            if importlib.util.find_spec(name) is None
        ]
        from ml.vton.catvton import MIX_CHECKPOINT, REQUIRED_FILES

        paths = [self.root / "catvton" / name for name in REQUIRED_FILES]
        if self.checkpoint == "mix":
            paths.append(self.root / "catvton" / MIX_CHECKPOINT)
        paths += [self.root / "parser" / name for name in (
            "config.json", "model.safetensors", "download-manifest.json"
        )]
        reason, code = None, None
        if missing:
            code = "vton_dependency_unavailable"
            reason = (
                "Pretrained try-on dependencies are missing: "
                + ", ".join(missing)
                + ". Install the pinned requirements-vton.txt profile."
            )
        elif any(not p.is_file() or p.stat().st_size == 0 for p in paths):
            code = "vton_model_unavailable"
            reason = "The pretrained CatVTON or human-parser checkpoint is missing. Run the project's model setup; an image overlay will not be substituted."
        elif self.device not in {"cpu", "cuda"}:
            code = "vton_device_unavailable"
            reason = "VTON_DEVICE must be cpu or cuda."
        elif self.device == "cuda":
            import torch

            if not torch.cuda.is_available():
                code = "vton_device_unavailable"
                reason = "CUDA inference was requested, but this PyTorch installation cannot use CUDA. Configure the supported CPU backend or install the matching CUDA profile."
        return {
            "backend": self.version,
            "available": reason is None,
            "reason": reason,
            "code": code,
            "supportedCategories": list(SUPPORTED),
            "device": self.device,
            "nativeResolution": list(self.native_size),
            "qualityValidated": False,
            "conditioning": self.conditioning,
        }

    def _load(self):
        state = self.availability()
        if not state["available"]:
            raise PipelineError(state["code"], state["reason"], 503)
        if self._model is None:
            from ml.vton.catvton import CatVTONModel
            from ml.vton.parsing import FashnHumanParser

            self._model = CatVTONModel(
                self.root / "catvton", device=self.device,
                guidance_scale=self.guidance_scale, seed=self.seed, checkpoint=self.checkpoint,
                height=self.native_size[1],
                conditioning=self.conditioning,
            )
            self._parser = FashnHumanParser(self.root / "parser")

    def render(
        self, person: ImageFeatures, garment_data: bytes, category: str, folder: Path
    ) -> dict:
        if category not in SUPPORTED:
            raise PipelineError(
                "vton_category",
                "The installed pretrained 2D model supports T-shirts and shirts only. Dress and trouser try-on remain available only in the separate approximate 3D mode.",
            )
        with self._lock:
            try:
                report_progress("loading_model")
                self._load()
                return self._render(person, garment_data, category, folder)
            except PipelineError:
                raise
            except (ImportError, ModuleNotFoundError) as exc:
                logger.exception("Pretrained VTON dependency failure")
                raise PipelineError(
                    "vton_dependency_unavailable",
                    "The pretrained try-on dependencies could not load. Inspect the local server log and model setup report; no preview was substituted.",
                    503,
                ) from exc
            except (MemoryError, RuntimeError) as exc:
                logger.exception("Pretrained VTON inference failed")
                message = "The pretrained try-on model could not complete inference."
                if "memory" in str(exc).lower() or isinstance(exc, MemoryError):
                    message = "There is insufficient memory for the pretrained try-on model."
                raise PipelineError(
                    "vton_inference_failed",
                    message
                    + " Your input and diagnostics were retained; no overlay result was returned.",
                    500,
                ) from exc

    def _render(self, person, garment_data, category, folder):
        from ml.vton.masking import build_replacement_mask, short_sleeve_support
        from ml.vton.parsing import compose_preserving_identity
        from ml.vton.quality import assess_garment_fidelity

        original = np.ascontiguousarray(person.image[:, :, :3])
        report_progress("parsing_person")
        parsed = self._parser.predict(original)
        Image.fromarray(parsed.labels).save(folder / "personParsing.png")
        window = person_window(parsed.labels)
        x0, y0, x1, y1 = window
        person_native, content_box = fit_canvas(
            Image.fromarray(original[y0:y1, x0:x1]), (255, 255, 255), canvas_size=self.native_size
        )
        labels_native, _ = fit_canvas(
            Image.fromarray(parsed.labels[y0:y1, x0:x1]), 0, nearest=True,
            canvas_size=self.native_size,
        )
        sleeve_support = short_sleeve_support(parsed.labels, person.landmarks)
        support_native, _ = fit_canvas(
            Image.fromarray(sleeve_support[y0:y1, x0:x1].astype(np.uint8) * 255),
            0, nearest=True, canvas_size=self.native_size,
        )
        replacement_native = Image.fromarray(build_replacement_mask(
            np.asarray(labels_native), sleeve_support=np.asarray(support_native) > 127,
        ))
        Image.fromarray(sleeve_support.astype(np.uint8) * 255).save(
            folder / "vton-sleeve-support.png"
        )

        rgba = decode_image(garment_data, min_dimension=128)
        report_progress("preparing_garment")
        garment_rgb = np.ascontiguousarray(rgba[:, :, :3])
        garment_parse = self._parser.predict(garment_rgb)
        Image.fromarray(garment_parse.labels).save(folder / "garmentParsing.png")
        worn = np.mean(np.isin(garment_parse.labels, [1, 2, 12, 13])) > 0.02
        if np.any(rgba[:, :, 3] < 200):
            mask = (rgba[:, :, 3] > 127).astype(np.uint8) * 255
            garment_source = "provided-alpha"
        elif worn:
            mask = (garment_parse.labels == 3).astype(np.uint8) * 255
            garment_source = "semantic-top-parsing"
        else:
            mask = preprocess_garment(garment_data, min_dimension=128).mask
            garment_source = "flat-lay-background-segmentation"
        if np.count_nonzero(mask) < mask.size * 0.03:
            raise PipelineError(
                "vton_garment_not_found",
                "No clear T-shirt or shirt could be isolated. Use a product photo or a sharp photo with the garment fully visible.",
            )
        crop, bounds = crop_foreground(garment_rgb, mask)
        gx0, gy0, gx1, gy1 = bounds
        garment_crop = Image.fromarray(crop[:, :, :3])
        edge_crop = Image.fromarray(mask[gy0:gy1, gx0:gx1])
        garment_native, _ = fit_canvas(garment_crop, (255, 255, 255), canvas_size=self.native_size)
        edge_native, _ = fit_canvas(edge_crop, 0, nearest=True, canvas_size=self.native_size)
        Image.fromarray(mask).save(folder / "garmentMask.png")
        Image.fromarray(crop).save(folder / "garmentCrop.png")
        person_native.save(folder / "vton-person-input.png")
        edge_native.save(folder / "vton-garment-mask.png")
        replacement_native.save(folder / "vton-replacement-mask.png")

        # The diffusion model receives a segmented product image and a white-edit
        # semantic inpainting mask. It synthesizes clothing, not pasted RGB.
        garment_condition = Image.new("RGB", self.native_size, (255, 255, 255))
        garment_condition.paste(garment_native, mask=edge_native)
        garment_condition.save(folder / "vton-garment-input.png")
        generated = self._model.predict(person_native, garment_condition, replacement_native)
        report_progress("refining_boundaries")
        generated.save(folder / "vton-model-output.png")
        restored = generated.crop(content_box).resize((x1 - x0, y1 - y0), Image.Resampling.LANCZOS)
        generated_full = original.copy()
        generated_full[y0:y1, x0:x1] = np.asarray(restored)
        if not np.isfinite(generated_full).all():
            raise PipelineError(
                "vton_invalid_output",
                "The pretrained model returned invalid pixels; no result was published.",
                500,
            )
        generated_parse = self._parser.predict(generated_full)
        Image.fromarray(generated_parse.labels).save(folder / "generatedParsing.png")
        inference_support = np.zeros(parsed.labels.shape, dtype=bool)
        inference_support[y0:y1, x0:x1] = np.asarray(
            replacement_native.crop(content_box).resize(
                (x1 - x0, y1 - y0), Image.Resampling.NEAREST,
            )
        ) > 127
        Image.fromarray(inference_support.astype(np.uint8) * 255).save(
            folder / "vton-inference-support.png"
        )
        composite = compose_preserving_identity(
            original, generated_full, parsed, generated_parse, category,
            sleeve_support=sleeve_support,
            inference_support=inference_support,
        )
        composite.save_diagnostics(folder)
        Image.fromarray(original).save(folder / "original-person.png")
        fidelity = assess_garment_fidelity(
            np.asarray(garment_condition), np.asarray(edge_native) > 127,
            composite.image, generated_parse.labels == 3,
        )
        (folder / "garment-fidelity.json").write_text(
            json.dumps(fidelity.as_dict(), indent=2, allow_nan=False), encoding="utf-8"
        )
        diagnostics = {
            "method": "pretrained-garment-conditioned-diffusion-inpainting",
            "modelVersion": self.version,
            "model": self._model.provenance,
            "nativeResolution": list(self.native_size),
            "personWindow": list(window),
            "replacementMaskVersion": "semantic-pose-short-sleeve-v3-rounded-cap",
            "compositeVersion": "inference-bounded-seams-v2",
            "maskLimitations": "Pose permits proximal upper-arm synthesis; long-sleeve changes are not validated.",
            "garmentSegmentation": garment_source,
            "parsing": parsed.diagnostics,
            "compositing": composite.diagnostics,
            "device": self.device,
            "qualityValidated": False,
            "garmentFidelity": fidelity.as_dict(),
        }
        (folder / "vton-diagnostics.json").write_text(
            json.dumps(diagnostics, indent=2), encoding="utf-8"
        )
        if fidelity.rejected:
            raise PipelineError(
                "vton_garment_fidelity_failed",
                "The model lost the uploaded garment's prominent stripes. This generated image "
                "was rejected. Try a clear product photograph; no pasted overlay was substituted.",
                422,
            )
        report_progress("saving_result")
        Image.fromarray(composite.image).save(folder / "tryon-2d.png")
        return diagnostics
