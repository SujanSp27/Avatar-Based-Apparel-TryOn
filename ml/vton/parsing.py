"""Local pretrained semantic parsing and bounded neural-output compositing.

The parser predicts FASHN's 18 classes. It has no distinct neck or left/right
limb labels. Collar transitions below use adjacency to predicted torso/top,
not skin-colour heuristics or a rectangular body replacement.
"""

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock

import cv2
import numpy as np
from PIL import Image

from ml.errors import PipelineError

ROOT = Path(__file__).resolve().parents[2]
MODEL_REVISION = "1f80c34dbab321c5730dda5c3fea279fd3e97498"
SOURCE_COMMIT = "f2771f2fb8655349e87e2869bbde7ace0bd06f2c"
CHECKPOINT_SHA256 = "e43c8c8a9b04f28798f0a4630cf18caa2cdb27a0d454fae43a5716e6f7078244"
CONFIG_SHA256 = "87bd5b66419dbfa7c02cfbeb94e292454863b1606c5df29526b19a6c1de70d9f"
LABEL_NAMES = (
    "background",
    "face",
    "hair",
    "top",
    "dress",
    "skirt",
    "pants",
    "belt",
    "bag",
    "hat",
    "scarf",
    "glasses",
    "arms",
    "hands",
    "legs",
    "feet",
    "torso",
    "jewelry",
)
CATEGORY_LABELS = {"t-shirt": (3,), "shirt": (3,), "dress": (3, 4, 5), "trouser": (6,)}
_PALETTE = np.array(
    [
        (0, 0, 0),
        (255, 190, 150),
        (90, 55, 30),
        (30, 180, 210),
        (200, 60, 170),
        (170, 60, 240),
        (80, 90, 220),
        (170, 150, 60),
        (100, 140, 90),
        (220, 170, 20),
        (150, 60, 30),
        (30, 220, 180),
        (240, 150, 100),
        (230, 120, 90),
        (200, 130, 80),
        (130, 70, 40),
        (240, 190, 130),
        (230, 220, 100),
    ],
    dtype=np.uint8,
)


def _rgb(image: np.ndarray) -> np.ndarray:
    if not isinstance(image, np.ndarray) or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("Expected an HxWx3 RGB NumPy image")
    if image.dtype != np.uint8 or min(image.shape[:2]) < 2:
        raise ValueError("Expected a nonempty uint8 RGB image")
    return np.ascontiguousarray(image)


def _labels(value: "HumanParse | np.ndarray") -> np.ndarray:
    array = value.labels if isinstance(value, HumanParse) else value
    if not isinstance(array, np.ndarray) or array.ndim != 2:
        raise ValueError("Expected an HxW semantic label map")
    if not np.issubdtype(array.dtype, np.integer) or np.any(array < 0) or np.any(array > 17):
        raise ValueError("Semantic labels must be integer IDs 0 through 17")
    return array.astype(np.uint8, copy=False)


@dataclass
class HumanParse:
    labels: np.ndarray
    diagnostics: dict = field(default_factory=dict)

    def save_diagnostics(self, folder: Path, prefix: str = "person") -> None:
        folder.mkdir(parents=True, exist_ok=True)
        labels = _labels(self)
        Image.fromarray(labels).save(folder / f"{prefix}-parse-labels.png")
        Image.fromarray(_PALETTE[labels]).save(folder / f"{prefix}-parse-preview.png")
        (folder / f"{prefix}-parse.json").write_text(
            json.dumps(self.diagnostics, indent=2, allow_nan=False), encoding="utf-8"
        )


class FashnHumanParser:
    """Lazy CPU parser; no inference call downloads assets or executes remote code."""

    version = f"fashn-human-parser@{MODEL_REVISION}"

    def __init__(self, checkpoint_dir: Path | str = ROOT / "assets/vton/parser"):
        self.checkpoint_dir = Path(checkpoint_dir).resolve()
        self._parser = None
        self._lock = Lock()

    def available(self) -> bool:
        return all(
            (self.checkpoint_dir / name).is_file()
            for name in ("config.json", "model.safetensors", "download-manifest.json")
        )

    def _load(self):
        if self._parser is not None:
            return self._parser
        if not self.available():
            raise PipelineError(
                "parser_unavailable",
                "Local semantic parser assets are missing. Run scripts/download_parser.py.",
                503,
            )
        weights = self.checkpoint_dir / "model.safetensors"
        digest = hashlib.sha256()
        with weights.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != CHECKPOINT_SHA256:
            raise PipelineError(
                "parser_checkpoint_invalid", "Semantic parser checkpoint checksum mismatch.", 503
            )
        if (
            hashlib.sha256((self.checkpoint_dir / "config.json").read_bytes()).hexdigest()
            != CONFIG_SHA256
        ):
            raise PipelineError(
                "parser_checkpoint_invalid", "Semantic parser configuration checksum mismatch.", 503
            )
        # Imports are intentionally deferred so missing research dependencies do
        # not prevent unrelated APIs or pure semantic-mask tests from starting.
        try:
            from ml.vton.runtime import configure_local_cache

            configure_local_cache()
            import torch
            from transformers import SegformerForSemanticSegmentation

            from ml.vton.vendor.fashn_human_parser.parser import FashnHumanParser as UpstreamParser
        except ImportError as exc:
            raise PipelineError(
                "parser_unavailable", "Semantic parser dependencies are not installed.", 503
            ) from exc
        torch.set_num_threads(2)
        parser = UpstreamParser.__new__(UpstreamParser)
        parser.device = "cpu"
        try:
            parser.model = (
                SegformerForSemanticSegmentation.from_pretrained(
                    str(self.checkpoint_dir),
                    local_files_only=True,
                    use_safetensors=True,
                    trust_remote_code=False,
                )
                .to("cpu")
                .eval()
            )
        except (OSError, ValueError, RuntimeError) as exc:
            raise PipelineError(
                "parser_checkpoint_invalid",
                "The local semantic parser could not load its verified checkpoint.",
                503,
            ) from exc
        if parser.model.config.num_labels != 18:
            raise PipelineError(
                "parser_checkpoint_invalid", "Expected the official 18-class FASHN parser.", 503
            )
        self._parser = parser
        return parser

    def predict(self, rgb: np.ndarray) -> HumanParse:
        rgb = _rgb(rgb)
        start = time.perf_counter()
        with self._lock:
            labels = _labels(self._load().predict(rgb))
        if labels.shape != rgb.shape[:2]:
            raise PipelineError(
                "parser_output_invalid",
                "Semantic parser output dimensions do not match the input image.",
                500,
            )
        values, counts = np.unique(labels, return_counts=True)
        return HumanParse(
            labels,
            {
                "modelVersion": self.version,
                "sourceCommit": SOURCE_COMMIT,
                "checkpointSha256": CHECKPOINT_SHA256,
                "device": "cpu",
                "inputSize": {"width": rgb.shape[1], "height": rgb.shape[0]},
                "modelInputSize": {"width": 384, "height": 576},
                "preprocessing": "Official cv2.INTER_AREA resize and ImageNet normalization",
                "labels": {str(index): name for index, name in enumerate(LABEL_NAMES)},
                "labelPixels": {LABEL_NAMES[int(v)]: int(n) for v, n in zip(values, counts)},
                "timingSeconds": round(time.perf_counter() - start, 3),
                "limitations": "Semantic estimates; neck and left/right limbs are not separate model classes.",
            },
        )


def clothing_mask(parse: HumanParse | np.ndarray, category: str = "t-shirt") -> np.ndarray:
    if category not in CATEGORY_LABELS:
        raise PipelineError("garment_category", "Unsupported semantic garment category.")
    return np.isin(_labels(parse), CATEGORY_LABELS[category])


def preservation_mask(parse: HumanParse | np.ndarray, category: str = "t-shirt") -> np.ndarray:
    """Preserve identity, exposed limbs, background and unrelated clothing classes."""
    labels = _labels(parse)
    # Bare torso is eligible only for a narrowly bounded generated collar change.
    return ~(clothing_mask(labels, category) | (labels == 16))


@dataclass
class CompositeResult:
    image: np.ndarray
    edit_mask: np.ndarray
    preserve_mask: np.ndarray
    alpha: np.ndarray
    old_clothing_mask: np.ndarray
    diagnostics: dict

    def save_diagnostics(self, folder: Path) -> None:
        folder.mkdir(parents=True, exist_ok=True)
        for name, mask in (
            ("semantic-edit-mask", self.edit_mask),
            ("semantic-preserve-mask", self.preserve_mask),
            ("old-clothing-mask", self.old_clothing_mask),
        ):
            Image.fromarray(mask.astype(np.uint8) * 255).save(folder / f"{name}.png")
        Image.fromarray(np.rint(self.alpha * 255).astype(np.uint8)).save(
            folder / "semantic-alpha.png"
        )
        (folder / "semantic-composite.json").write_text(
            json.dumps(self.diagnostics, indent=2, allow_nan=False), encoding="utf-8"
        )


def compose_preserving_identity(
    original: np.ndarray,
    generated: np.ndarray,
    original_parse: HumanParse | np.ndarray,
    generated_parse: HumanParse | np.ndarray,
    category: str = "t-shirt",
    *,
    sleeve_support: np.ndarray | None = None,
    inference_support: np.ndarray | None = None,
) -> CompositeResult:
    """Restore source identity while admitting the model's local garment boundary.

    Original clothing is replaced at full opacity. For upper-body garments, a
    narrow background/torso context repairs parser uncertainty at the shoulder
    and collar. Further extensions require generated clothing semantics and stay
    near the original garment. Only the outer edge is feathered: source face,
    hair, hands and unrelated clothing are never blended or regenerated here.
    """
    original, generated = _rgb(original), _rgb(generated)
    source_labels, target_labels = _labels(original_parse), _labels(generated_parse)
    if (
        original.shape != generated.shape
        or source_labels.shape != original.shape[:2]
        or target_labels.shape != source_labels.shape
    ):
        raise ValueError("Images and both semantic maps must share identical HxW dimensions")
    old = clothing_mask(source_labels, category)
    if np.count_nonzero(old) < max(16, old.size * 0.001):
        raise PipelineError(
            "clothing_not_visible",
            "The pretrained parser could not identify enough existing clothing to replace.",
        )
    generated_clothing = clothing_mask(target_labels, category)
    distance = cv2.distanceTransform((~old).astype(np.uint8), cv2.DIST_L2, 5)
    upper_body = category in {"t-shirt", "shirt"}
    context_radius = max(1, round(min(old.shape) * 0.004)) if upper_body else 0
    feather_width = max(2, round(min(old.shape) * 0.002))
    radius = max(context_radius + feather_width, round(min(old.shape) * 0.018))
    permitted_sleeves = np.zeros(old.shape, dtype=bool)
    if sleeve_support is not None:
        from ml.vton.masking import binary_support

        permitted_sleeves = binary_support(sleeve_support, old.shape)
    permitted_inference = np.zeros(old.shape, dtype=bool)
    if inference_support is not None:
        from ml.vton.masking import binary_support

        permitted_inference = binary_support(inference_support, old.shape)
        # A model may narrow an exposed shoulder and put background where skin
        # should be. Keeping that skin produces detached shoulder fragments;
        # erasing it changes body proportions. Reject substantial loss instead.
        arm_interior = cv2.distanceTransform(
            (source_labels == 12).astype(np.uint8), cv2.DIST_L2, 5,
        ) > max(2, round(min(old.shape) * 0.004))
        editable_arms = permitted_inference & (source_labels == 12)
        missing_arms = editable_arms & arm_interior & (target_labels == 0)
        missing_count = int(np.count_nonzero(missing_arms))
        if missing_count > max(64, np.count_nonzero(editable_arms) * 0.03):
            raise PipelineError(
                "vton_body_shape_changed",
                "The model narrowed an exposed shoulder or arm. This result was rejected "
                "to preserve your body shape. Try a front-facing photo wearing a short-sleeved top.",
                422,
            )
    # A parser's hard boundary can lie several pixels inside the actual fabric.
    # Keeping that boundary exact would restore a white/beige outline from the
    # source photo. The model supplies this small context, not a garment overlay.
    context = (
        upper_body
        & np.isin(source_labels, (0, 16))
        & np.isin(target_labels, (0, 3, 12, 16))
        & (distance <= context_radius + feather_width)
    )
    extension = (
        upper_body
        & np.isin(source_labels, (0, 12, 16))
        & generated_clothing
        & ((distance <= radius) | permitted_sleeves | permitted_inference)
    )
    # The inference mask includes seam context beyond the pose corridor. Using
    # only the smaller corridor here pastes old vest/skin wedges over generated
    # shoulder caps. Admit generated clothing within the exact inpainted region,
    # with a narrow parser-edge allowance; never admit unrelated skin or clothes.
    generated_edge = cv2.dilate(
        generated_clothing.astype(np.uint8),
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * feather_width + 1,) * 2),
    ).astype(bool)
    seam = (
        upper_body & permitted_inference & generated_edge
        & np.isin(source_labels, (0, 12, 16))
        & np.isin(target_labels, (0, 3, 12, 16))
    )
    protected = ~(old | (upper_body & np.isin(source_labels, (0, 12, 16))))
    support = old | context | extension | seam
    interior_distance = cv2.distanceTransform(support.astype(np.uint8), cv2.DIST_L2, 5)
    alpha = np.zeros(old.shape, dtype=np.float32)
    alpha[support] = np.minimum(interior_distance[support] / feather_width, 1.0)
    # Never mix old clothing back into the generated garment, including where
    # the generated parser disagrees about a sleeve or neckline.
    alpha[old] = 1.0
    alpha[protected] = 0.0
    edit = alpha > 0
    preserve = ~edit
    image = original.copy()
    blend = generated.astype(np.float32) * alpha[:, :, None] + original * (1 - alpha[:, :, None])
    image[edit] = np.rint(blend[edit]).clip(0, 255).astype(np.uint8)
    return CompositeResult(
        image,
        edit,
        preserve,
        alpha,
        old,
        {
            "method": "pretrained-semantic-bounded-neural-composite",
            "category": category,
            "oldClothingPixels": int(np.count_nonzero(old)),
            "oldClothingMinimumAlpha": float(alpha[old].min()),
            "editedPixels": int(np.count_nonzero(edit)),
            "preservedPixels": int(np.count_nonzero(preserve)),
            "changedPixelsOutsideEditMask": int(
                np.count_nonzero(np.any(image != original, axis=2) & preserve)
            ),
            "identityPreservedExactly": bool(np.array_equal(image[protected], original[protected])),
            "collarTransition": "Narrow generated context on adjacent background/bare torso; further changes require generated clothing semantics.",
            "collarTransitionRadiusPixels": radius,
            "sourceContextRadiusPixels": context_radius,
            "outerFeatherWidthPixels": feather_width,
            "semanticContextPixels": int(np.count_nonzero(context)),
            "generatedClothingExtensionPixels": int(np.count_nonzero(extension)),
            "poseSleeveSupportPixels": int(np.count_nonzero(permitted_sleeves)),
            "inferenceSupportPixels": int(np.count_nonzero(permitted_inference)),
            "inferenceSeamPixels": int(np.count_nonzero(seam)),
            "silhouettePolicy": "Bounded generated clothing may cover nearby background, bare torso or upper arms. Face, hair, hands and unrelated clothing stay exact; distant background and limbs stay exact.",
            "limitations": "Preservation is conditional on semantic parsing; it does not guarantee perceptual realism or accurate fit.",
        },
    )
