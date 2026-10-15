import io
import json
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock

import cv2
import mediapipe as mp
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from ml.errors import PipelineError


@dataclass
class ImageFeatures:
    image: np.ndarray
    mask: np.ndarray
    crop: np.ndarray
    bbox: tuple[int, int, int, int]
    landmarks: np.ndarray | None = None
    world_landmarks: np.ndarray | None = None
    warnings: list[str] = field(default_factory=list)


def decode_image(data: bytes, *, min_dimension: int = 256) -> np.ndarray:
    try:
        with Image.open(io.BytesIO(data)) as source:
            if source.format not in {"JPEG", "PNG", "WEBP"}:
                raise PipelineError("image_format", "Use a JPEG, PNG or WebP image.")
            if source.width * source.height > 20_000_000:
                raise PipelineError("image_dimensions", "Image exceeds 20 megapixels.")
            if min(source.size) < min_dimension:
                raise PipelineError(
                    "low_resolution",
                    f"Both image dimensions must be at least {min_dimension} pixels.",
                )
            image = ImageOps.exif_transpose(source).convert("RGBA")
            image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
            return np.array(image)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise PipelineError("invalid_image", "The image could not be decoded.") from exc


def crop_foreground(image: np.ndarray, mask: np.ndarray) -> tuple[np.ndarray, tuple]:
    ys, xs = np.where(mask > 0)
    if len(xs) < 0.025 * mask.size or len(xs) > 0.94 * mask.size:
        raise PipelineError(
            "unclear_foreground",
            "Foreground is not clearly separated; use a plain contrasting background.",
        )
    x0, y0, x1, y1 = int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1
    rgba = np.dstack([image[:, :, :3], mask])
    return rgba[y0:y1, x0:x1], (x0, y0, x1, y1)


def save_features(features: ImageFeatures, folder: Path, prefix: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    Image.fromarray(features.mask).save(folder / f"{prefix}Mask.png")
    Image.fromarray(features.crop).save(folder / f"{prefix}Crop.png")
    normalized = ImageOps.pad(
        Image.fromarray(features.crop),
        (512, 768) if prefix == "person" else (512, 512),
        color=(255, 255, 255, 0),
    )
    normalized.save(folder / f"{prefix}Normalized.png")
    if features.landmarks is not None:
        (folder / "poseKeypoints.json").write_text(
            json.dumps(
                {
                    "normalized": features.landmarks.tolist(),
                    "world": features.world_landmarks.tolist(),
                    "layout": "MediaPipe 33: normalized x,y,z,visibility; world x,y,z in metres",
                    "bbox": features.bbox,
                    "warnings": features.warnings,
                },
                indent=2,
            )
        )


class PersonPreprocessor:
    """Cached pretrained Tasks model, serialized for deterministic IMAGE inference."""

    def __init__(self, model_path: Path):
        self.model_path = model_path
        self._model = None
        self._lock = Lock()

    def process(self, data: bytes, folder: Path | None = None) -> ImageFeatures:
        features = self.detect(data, folder)
        return features

    def detect(self, data: bytes, folder: Path | None = None) -> ImageFeatures:
        """Detect one person without assuming that the entire body is in frame.

        Each consumer validates the landmarks its output actually needs.
        """
        rgba = decode_image(data)
        rgb = np.ascontiguousarray(rgba[:, :, :3])
        if not self.model_path.is_file():
            raise PipelineError(
                "model_unavailable",
                "MediaPipe checkpoint is missing; run scripts/download_assets.py.",
                503,
            )
        with self._lock:
            if self._model is None:
                options = mp.tasks.vision.PoseLandmarkerOptions(
                    base_options=mp.tasks.BaseOptions(model_asset_path=str(self.model_path)),
                    running_mode=mp.tasks.vision.RunningMode.IMAGE,
                    num_poses=3,
                    output_segmentation_masks=True,
                    min_pose_detection_confidence=0.5,
                    min_pose_presence_confidence=0.5,
                )
                self._model = mp.tasks.vision.PoseLandmarker.create_from_options(options)
            result = self._model.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
        if len(result.pose_landmarks) != 1:
            raise PipelineError(
                "person_count",
                f"Expected one visible person; detected {len(result.pose_landmarks)}.",
            )
        points = np.array([[p.x, p.y, p.z, p.visibility] for p in result.pose_landmarks[0]])
        world = np.array([[p.x, p.y, p.z] for p in result.pose_world_landmarks[0]])
        mask = (result.segmentation_masks[0].numpy_view() > 0.5).astype(np.uint8) * 255
        crop, bbox = crop_foreground(rgb, mask)
        features = ImageFeatures(rgb, mask, crop, bbox, points, world)
        if folder:
            save_features(features, folder, "person")
        return features



def preprocess_garment(
    data: bytes,
    folder: Path | None = None,
    *,
    min_dimension: int = 256,
    allow_worn: bool = False,
) -> ImageFeatures:
    rgba = decode_image(data, min_dimension=min_dimension)
    rgb = rgba[:, :, :3]
    if np.any(rgba[:, :, 3] < 200):
        mask = (rgba[:, :, 3] > 127).astype(np.uint8) * 255
    else:
        lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(float)
        border = np.concatenate(
            [
                lab[:8].reshape(-1, 3),
                lab[-8:].reshape(-1, 3),
                lab[:, :8].reshape(-1, 3),
                lab[:, -8:].reshape(-1, 3),
            ]
        )
        bg = np.median(border, axis=0)
        variation = np.median(np.linalg.norm(border - bg, axis=1))
        if variation > 18 and not allow_worn:
            raise PipelineError(
                "garment_background",
                "Use a plain, contrasting garment background or transparent PNG.",
            )
        if allow_worn:
            # A studio garment photo may have a gentle background gradient and
            # a model entering the top/bottom border. Its side margins still
            # provide a deterministic local background estimate.
            edge = max(2, min(8, rgb.shape[1] // 40))
            left = np.median(lab[:, :edge], axis=1)[:, None, :]
            right = np.median(lab[:, -edge:], axis=1)[:, None, :]
            fraction = np.linspace(0, 1, rgb.shape[1])[None, :, None]
            local_background = left * (1 - fraction) + right * fraction
            mask = (np.linalg.norm(lab - local_background, axis=2) > 26).astype(np.uint8) * 255
        else:
            # Calibrate to actual background noise. A fixed cutoff of 24
            # discarded light cream fabric (including stripes at sleeve edges)
            # even on a perfectly uniform background.
            background_noise = np.percentile(np.linalg.norm(border - bg, axis=1), 95)
            threshold = max(8.0, float(background_noise) + 3.0)
            mask = (np.linalg.norm(lab - bg, axis=2) > threshold).astype(np.uint8) * 255
    kernel = max(5, int(min(mask.shape) * 0.025) | 1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((kernel, kernel), np.uint8))
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
    if count < 2:
        raise PipelineError("garment_not_visible", "No clear garment was found.")
    largest = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
    others = np.delete(stats[1:, cv2.CC_STAT_AREA], largest - 1)
    if np.any(others > stats[largest, cv2.CC_STAT_AREA] * 0.2):
        raise PipelineError(
            "multiple_garments", "Use one garment without other foreground objects."
        )
    mask = (labels == largest).astype(np.uint8) * 255
    crop, bbox = crop_foreground(rgb, mask)
    if min(crop.shape[:2]) < 100:
        raise PipelineError("garment_not_visible", "The garment is too small in the photo.")
    result = ImageFeatures(rgb, mask, crop, bbox)
    if allow_worn and not np.any(rgba[:, :, 3] < 200):
        result.warnings.append(
            "Garment edges are estimated from the studio background; a product-only image "
            "gives a cleaner overlay than clothing worn by a person."
        )
    if min(rgb.shape[:2]) < 256:
        result.warnings.append(
            "This small garment photo is accepted for a 2D preview; its texture may look blurry."
        )
    if folder:
        save_features(result, folder, "garment")
    return result
