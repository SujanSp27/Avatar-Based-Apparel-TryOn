"""Lazy, serialized MediaPipe Tasks IMAGE inference with an explicit CPU delegate."""

import hashlib
import io
from dataclasses import dataclass
from pathlib import Path
from threading import Lock

import numpy as np
from PIL import Image, ImageCms, ImageOps, UnidentifiedImageError

from ml.errors import PipelineError

from .diagnostics import diagnostic

_refinement_lock = Lock()


@dataclass
class PoseObservation:
    image: np.ndarray
    landmarks: np.ndarray  # 33 normalized x, y, z, visibility
    world_landmarks: np.ndarray  # 33 xyz in model-estimated metres, not used for scale
    mask: np.ndarray
    probabilities: np.ndarray | None = None
    presence: np.ndarray | None = None  # Tasks probability; absent in older fixtures/adapters


def normalize_probabilities(probabilities: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    import cv2

    prior = np.asarray(probabilities)
    if prior.ndim == 3 and prior.shape[-1] == 1:
        prior = prior[..., 0]
    if prior.ndim != 2 or min(prior.shape) < 2 or not np.isfinite(prior).all():
        raise PipelineError("invalid_mask", "The person segmentation map is invalid. Retry with another clear photo.")
    # MediaPipe provides likelihoods in [0,1], not uint8 intensities or logits.
    if prior.min() < 0 or prior.max() > 1:
        raise PipelineError("invalid_mask", "The person segmentation probabilities are outside their expected range.")
    return cv2.resize(prior.astype(np.float32), (shape[1], shape[0]), interpolation=cv2.INTER_LINEAR)


def refine_mask(image: np.ndarray, probabilities: np.ndarray, *, max_edge: int = 800,
                reconsider_foreground: bool = False) -> np.ndarray:
    """Image-guided CPU refinement recovers gaps blurred by the pose mask."""
    import cv2

    # Pose probability maps alone bridge narrow arm/torso gaps. GrabCut uses
    # image colours within the pose prior; it is not an anatomical body parser.
    height, width = image.shape[:2]
    probabilities = normalize_probabilities(probabilities, (height, width))
    ratio = min(1.0, max_edge / max(height, width))
    dimensions = (round(width * ratio), round(height * ratio))
    small = cv2.resize(image, dimensions, interpolation=cv2.INTER_AREA)
    prior = cv2.resize(probabilities, dimensions, interpolation=cv2.INTER_LINEAR)
    labels = np.where(prior > 0.5, cv2.GC_PR_FGD, cv2.GC_PR_BGD).astype(np.uint8)
    labels[prior < 0.01] = cv2.GC_BGD
    core = cv2.erode((prior > 0.99).astype(np.uint8), np.ones((9, 9), np.uint8))
    # High pose confidence is not proof of an anatomical edge. In a guarded
    # retry, let image evidence reclassify even confident arm/torso bridges.
    # Keep the conservative default for the primary segmentation.
    if not reconsider_foreground:
        labels[core > 0] = cv2.GC_FGD
    if not core.any() or not np.any(labels == cv2.GC_BGD):
        raise PipelineError("segmentation_missing", "A clear person outline and background are required.")
    try:
        # Also serialize the optional native-resolution retry outside detect().
        with _refinement_lock:
            cv2.setRNGSeed(0)
            cv2.grabCut(small, labels, None, np.zeros((1, 65)), np.zeros((1, 65)), 3, cv2.GC_INIT_WITH_MASK)
    except cv2.error as exc:
        raise PipelineError("segmentation_failed", "The person outline could not be refined. Use a clear, contrasting background.") from exc
    mask = np.isin(labels, (cv2.GC_FGD, cv2.GC_PR_FGD)).astype(np.uint8)
    diagnostic("segmentation", image_size=[width, height], processing_size=list(dimensions),
               reconsider_foreground=reconsider_foreground,
               foreground_fraction=round(float(mask.mean()), 4),
               uncertain_prior_fraction=round(float(((prior > .1) & (prior < .9)).mean()), 4))
    return cv2.resize(mask, (width, height), interpolation=cv2.INTER_NEAREST).astype(bool)


def decode_person(data: bytes) -> np.ndarray:
    try:
        with Image.open(io.BytesIO(data)) as source:
            original_size = list(source.size)
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
            diagnostic("image_preprocessing", original_size=original_size,
                       oriented_size=list(image.size), processed_size=list(background.size),
                       scale_x=background.width / image.width, scale_y=background.height / image.height)
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
        try:
            import mediapipe as mp
        except (ImportError, OSError) as exc:
            raise PipelineError("measurement_runtime_unavailable", "The MediaPipe CPU runtime is unavailable. Check the backend dependencies.", 503) from exc

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
                except (RuntimeError, ValueError, OSError) as exc:
                    raise PipelineError("measurement_model_unavailable", "MediaPipe could not load its checkpoint.", 503) from exc
            try:
                result = self._model.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=image))
            except (RuntimeError, ValueError) as exc:
                raise PipelineError("pose_inference_failed", "The pose estimator could not process this image.", 422) from exc
            if len(result.pose_landmarks) != 1:
                diagnostic("pose_detection", person_count=len(result.pose_landmarks))
                raise PipelineError("person_count", f"Expected one person; detected {len(result.pose_landmarks)}.")
            if not result.segmentation_masks:
                raise PipelineError("segmentation_missing", "MediaPipe could not segment this person.")
            # Copy while serialized: MediaPipe owns the mask's underlying buffer.
            prior = normalize_probabilities(result.segmentation_masks[0].numpy_view().copy(), image.shape[:2])
            diagnostic("pose_detection", person_count=1, image_size=list(image.shape[1::-1]),
                       minimum_visibility=min(float(p.visibility) for p in result.pose_landmarks[0]))
            return PoseObservation(
                image=image,
                landmarks=np.array([[p.x, p.y, p.z, p.visibility] for p in result.pose_landmarks[0]]),
                world_landmarks=np.array([[p.x, p.y, p.z] for p in result.pose_world_landmarks[0]]),
                mask=refine_mask(image, prior), probabilities=prior,
                presence=np.array([p.presence for p in result.pose_landmarks[0]], dtype=float),
            )

    def close(self):
        with self._lock:
            if self._model is not None:
                self._model.close()
                self._model = None
