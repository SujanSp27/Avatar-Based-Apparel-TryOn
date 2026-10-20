"""Lazy, serialized MediaPipe Tasks IMAGE inference with an explicit CPU delegate."""

import hashlib
import io
from dataclasses import dataclass
from pathlib import Path
from threading import Lock

import numpy as np
from PIL import Image, ImageCms, ImageOps, UnidentifiedImageError

from ml.errors import PipelineError


@dataclass
class PoseObservation:
    image: np.ndarray
    landmarks: np.ndarray  # 33 normalized x, y, z, visibility
    world_landmarks: np.ndarray  # 33 xyz in model-estimated metres, not used for scale
    mask: np.ndarray


def decode_person(data: bytes) -> np.ndarray:
    try:
        with Image.open(io.BytesIO(data)) as source:
            if source.format not in {"JPEG", "PNG"}:
                raise PipelineError("image_format", "Measurement extraction accepts JPEG or PNG.")
            if source.width * source.height > 20_000_000:
                raise PipelineError("image_dimensions", "Image exceeds 20 megapixels.")
            if min(source.size) < 256:
                raise PipelineError("low_resolution", "Both image dimensions must be at least 256 pixels.")
            image = ImageOps.exif_transpose(source)
            alpha = image.convert("RGBA").getchannel("A")
            if profile := source.info.get("icc_profile"):
                image = ImageCms.profileToProfile(
                    image.convert("RGB"), ImageCms.ImageCmsProfile(io.BytesIO(profile)),
                    ImageCms.createProfile("sRGB"), outputMode="RGB",
                )
            else:
                image = image.convert("RGB")
            background = Image.new("RGB", image.size, "white")
            background.paste(image, mask=alpha)
            background.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
            return np.ascontiguousarray(background, dtype=np.uint8)
    except (UnidentifiedImageError, OSError, ValueError, ImageCms.PyCMSError,
            Image.DecompressionBombError) as exc:
        raise PipelineError("invalid_image", "Image or colour profile could not be decoded.") from exc


class MediaPipePose:
    def __init__(self, model_path: Path):
        self.model_path = model_path
        self._model = None
        self._lock = Lock()
        self.model_sha256 = None

    def detect(self, image: np.ndarray) -> PoseObservation:
        if not self.model_path.is_file():
            raise PipelineError(
                "measurement_model_missing",
                "The MediaPipe pose checkpoint is missing. Run scripts/download_measurement_model.py.",
                503,
            )
        # Do not load MediaPipe (or any local ML runtime) just to serve try-on/sizing.
        import mediapipe as mp

        with self._lock:
            if self._model is None:
                try:
                    options = mp.tasks.vision.PoseLandmarkerOptions(
                        base_options=mp.tasks.BaseOptions(
                            model_asset_path=str(self.model_path),
                            delegate=mp.tasks.BaseOptions.Delegate.CPU,
                        ),
                        running_mode=mp.tasks.vision.RunningMode.IMAGE,
                        num_poses=3, output_segmentation_masks=True,
                        min_pose_detection_confidence=0.5,
                        min_pose_presence_confidence=0.5,
                    )
                    self._model = mp.tasks.vision.PoseLandmarker.create_from_options(options)
                    self.model_sha256 = hashlib.sha256(self.model_path.read_bytes()).hexdigest()
                except (RuntimeError, ValueError) as exc:
                    raise PipelineError("measurement_model_unavailable", "MediaPipe could not load its checkpoint.", 503) from exc
            result = self._model.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=image))
            if len(result.pose_landmarks) != 1:
                raise PipelineError("person_count", f"Expected one person; detected {len(result.pose_landmarks)}.")
            if not result.segmentation_masks:
                raise PipelineError("segmentation_missing", "MediaPipe could not segment this person.")
            # Copy while serialized: MediaPipe owns the mask's underlying buffer.
            return PoseObservation(
                image=image,
                landmarks=np.array([[p.x, p.y, p.z, p.visibility] for p in result.pose_landmarks[0]]),
                world_landmarks=np.array([[p.x, p.y, p.z] for p in result.pose_world_landmarks[0]]),
                mask=(result.segmentation_masks[0].numpy_view() > 0.5).copy(),
            )

    def close(self):
        with self._lock:
            if self._model is not None:
                self._model.close()
                self._model = None
