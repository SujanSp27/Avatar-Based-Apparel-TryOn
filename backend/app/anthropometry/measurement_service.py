"""Deterministic single-view estimates. These are not measured body circumferences."""

import hashlib
import json
import math
from pathlib import Path
from uuid import uuid4

import numpy as np
from PIL import Image, ImageDraw

from backend.app.anthropometry.pose_adapter import MediaPipePose, PoseObservation, decode_person
from backend.app.anthropometry.schemas import ExtractionResponse, Measurements
from ml.errors import PipelineError

VISIBILITY_THRESHOLD = 0.65
KEY_LANDMARKS = {
    0: "nose", 11: "left shoulder", 12: "right shoulder",
    23: "left hip", 24: "right hip", 25: "left knee", 26: "right knee",
    27: "left ankle", 28: "right ankle", 29: "left heel", 30: "right heel",
}
KAPPA = {"chest": 2.45, "waist": 2.30, "hip": 2.40, "thigh": 2.50}


def validate_pose(observation: PoseObservation) -> np.ndarray:
    landmarks = observation.landmarks
    if landmarks.shape != (33, 4) or not np.isfinite(landmarks).all():
        raise PipelineError("invalid_pose", "Expected 33 finite MediaPipe landmarks.")
    h, w = observation.image.shape[:2]
    if observation.mask.shape != (h, w):
        raise PipelineError("invalid_mask", "Person mask dimensions do not match the image.")
    weak = [name for index, name in KEY_LANDMARKS.items()
            if landmarks[index, 3] <= VISIBILITY_THRESHOLD]
    if weak:
        raise PipelineError("low_visibility", "Visibility must exceed 0.65 for: " + ", ".join(weak) + ".")
    if any(np.any(landmarks[index, :2] <= 0.005) or np.any(landmarks[index, :2] >= 0.995)
           for index in KEY_LANDMARKS):
        raise PipelineError("partial_body", "Show your complete head, torso, knees, ankles and heels inside the frame.")
    points = landmarks[:, :2] * [w, h]
    head, shoulder, hip, knee, ankle = (
        points[0, 1], points[[11, 12], 1].mean(), points[[23, 24], 1].mean(),
        points[[25, 26], 1].mean(), points[[27, 28], 1].mean(),
    )
    if not head < shoulder < hip < knee < ankle:
        raise PipelineError("unsupported_pose", "Stand upright, facing the camera with both legs visible.")
    shoulder_width = float(np.linalg.norm(points[11] - points[12]))
    if shoulder_width < 10 or abs(points[11, 1] - points[12, 1]) > 0.3 * shoulder_width:
        raise PipelineError("unsupported_pose", "Keep your shoulders level and face the camera.")
    world = observation.world_landmarks
    if world.shape == (33, 3) and np.isfinite(world).all():
        span = world[11] - world[12]
        if abs(span[2]) > max(abs(span[0]) * 0.65, 0.08):
            raise PipelineError("unsupported_pose", "Turn your torso towards the camera; side views cannot be measured.")
    for leg in ((23, 25, 27), (24, 26, 28)):
        length = sum(np.linalg.norm(points[a] - points[b]) for a, b in zip(leg, leg[1:]))
        if length <= 0 or (points[leg[-1], 1] - points[leg[0], 1]) / length < 0.9:
            raise PipelineError("unsupported_pose", "Stand with straight, uncrossed legs.")
    return points


def silhouette_width(mask: np.ndarray, center: np.ndarray, direction: np.ndarray):
    """Connected foreground span through the anatomical anchor; never a whole-row bbox."""
    direction = direction / np.linalg.norm(direction)
    radius = int(math.hypot(*mask.shape))
    offsets = np.arange(-radius, radius + 1)
    coordinates = np.rint(center + offsets[:, None] * direction).astype(int)
    x, y = coordinates.T
    inside = (x >= 0) & (x < mask.shape[1]) & (y >= 0) & (y < mask.shape[0])
    foreground = np.zeros(len(offsets), dtype=bool)
    foreground[inside] = mask[y[inside], x[inside]] > 0
    if not foreground[radius]:
        raise PipelineError("ambiguous_silhouette", "Body landmarks are outside the person mask; use a clear contrasting background.")
    left = right = radius
    while left > 0 and foreground[left - 1]:
        left -= 1
    while right + 1 < len(offsets) and foreground[right + 1]:
        right += 1
    if not inside[left] or not inside[right] or left == 0 or right == len(offsets) - 1:
        raise PipelineError("partial_body", "Body outline reaches the image boundary.")
    width = float(offsets[right] - offsets[left] + 1)
    if width < 4:
        raise PipelineError("ambiguous_silhouette", "Body outline is too small to measure reliably.")
    return width, (center + offsets[left] * direction, center + offsets[right] * direction)


def band_width(mask, center, direction, axis):
    # Median over five adjacent sections limits isolated segmentation speckles.
    samples = [silhouette_width(mask, center + shift * axis, direction) for shift in (-2, -1, 0, 1, 2)]
    return sorted(samples, key=lambda item: item[0])[2]


def estimate(observation: PoseObservation, height_cm: float) -> tuple[dict, list]:
    if not math.isfinite(height_cm) or not 80 <= height_cm <= 250:
        raise PipelineError("invalid_height", "Self-reported height must be between 80 and 250 cm.")
    p = validate_pose(observation)
    head_indices = [i for i in range(11) if observation.landmarks[i, 3] > VISIBILITY_THRESHOLD
                    and 0 < observation.landmarks[i, 1] < 1]
    head_y = float(p[head_indices, 1].min())
    ankle_y = float(p[[27, 28], 1].max())
    height_px = ankle_y - head_y
    if height_px < 100:
        raise PipelineError("person_too_small", "Move closer while keeping your entire body in frame.")
    scale = height_cm / height_px
    shoulder_center, hip_center = p[[11, 12]].mean(axis=0), p[[23, 24]].mean(axis=0)
    torso_axis = hip_center - shoulder_center
    torso_axis /= np.linalg.norm(torso_axis)
    torso_direction = np.array([torso_axis[1], -torso_axis[0]])
    sections = []
    widths = {}
    for name, fraction in (("chest", 0.25), ("waist", 0.50)):
        center = shoulder_center * (1 - fraction) + hip_center * fraction
        width, segment = band_width(observation.mask, center, torso_direction, torso_axis)
        if width > 1.65 * np.linalg.norm(p[11] - p[12]):
            raise PipelineError("ambiguous_silhouette", "Torso outline includes arms or loose clothing. Keep arms apart and wear close-fitting clothing.")
        widths[name] = width
        sections.append((name, segment))
    thigh_widths = []
    thigh_centers = [p[hip] * 0.75 + p[knee] * 0.25 for hip, knee in ((23, 25), (24, 26))]
    for index, (hip, knee) in enumerate(((23, 25), (24, 26))):
        axis = p[knee] - p[hip]
        axis /= np.linalg.norm(axis)
        direction = np.array([axis[1], -axis[0]])
        width, segment = band_width(observation.mask, thigh_centers[index], direction, axis)
        other = thigh_centers[1 - index]
        # A section containing the other thigh is not an individual thigh width.
        low, high = sorted(float(np.dot(end - thigh_centers[index], direction)) for end in segment)
        if low <= float(np.dot(other - thigh_centers[index], direction)) <= high:
            raise PipelineError("ambiguous_thigh", "Separate your legs slightly so each upper-thigh outline is visible.")
        thigh_widths.append(width)
        sections.append((f"thigh_{index + 1}", segment))
    values = {
        "shoulder_width": float(np.linalg.norm(p[11] - p[12]) * scale),
        "chest_circumference": widths["chest"] * scale * KAPPA["chest"],
        "waist_circumference": widths["waist"] * scale * KAPPA["waist"],
        "hip_circumference": float(np.linalg.norm(p[23] - p[24]) * scale * KAPPA["hip"]),
        "thigh_circumference": float(np.mean(thigh_widths) * scale * KAPPA["thigh"]),
        "inseam_length": float(np.mean([np.linalg.norm(p[i] - hip_center) for i in (27, 28)]) * scale),
    }
    if values["shoulder_width"] > 100 or values["inseam_length"] > 200 or max(values.values()) > 400:
        raise PipelineError("implausible_geometry", "Pose geometry is inconsistent with the reported height.")
    return {
        "scale_factor": scale,
        "measurements": {name: round(value, 2) for name, value in values.items()},
        "quality": {"estimates_only": True,
                    "minimum_key_landmark_visibility": float(observation.landmarks[list(KEY_LANDMARKS), 3].min()),
                    "visibility_threshold_exclusive": VISIBILITY_THRESHOLD,
                    "statistical_uncertainty": "Not calibrated; landmark visibility is not measurement accuracy."},
        "geometry": {"height_cm": height_cm, "height_pixels": height_px,
                     "head_y": head_y, "ankle_y": ankle_y,
                     "head_reference": "minimum y of visible MediaPipe face landmarks 0-10",
                     "head_landmark_indices": head_indices,
                     "image_size": list(observation.image.shape[1::-1]),
                     "projection_multipliers": KAPPA,
                     "chest_torso_fraction": 0.25, "waist_torso_fraction": 0.50,
                     "thigh_leg_fraction": 0.25,
                     "inseam_reference": "mean Euclidean distance from hip midpoint to ankles 27/28"},
        "warnings": [
            "Single-view estimates depend on self-reported height, perspective, clothing and segmentation.",
            "MediaPipe has no crown or crotch landmark. Face-to-ankle scale and hip-midpoint inseam are biased anatomical proxies.",
            "Circumference multipliers are specified heuristics, not calibrated tape measurements. Hip joint spacing is not outer hip width.",
            "Confirm important dimensions with a tape measure before choosing a size.",
        ],
    }, sections


class MeasurementService:
    def __init__(self, detector: MediaPipePose, output_root: Path):
        self.detector = detector
        self.output_root = output_root

    def extract(self, data: bytes, height_cm: float) -> ExtractionResponse:
        image = decode_person(data)
        observation = self.detector.detect(image)
        result, sections = estimate(observation, height_cm)
        filename = f"pose_{uuid4().hex}"
        canvas = Image.fromarray(image)
        draw = ImageDraw.Draw(canvas)
        points = observation.landmarks[:, :2] * [image.shape[1], image.shape[0]]
        for a, b in ((11, 12), (11, 23), (12, 24), (23, 24), (11, 13), (13, 15),
                     (12, 14), (14, 16), (23, 25), (25, 27), (24, 26), (26, 28), (27, 29), (28, 30)):
            if min(observation.landmarks[[a, b], 3]) > VISIBILITY_THRESHOLD:
                draw.line([tuple(points[a]), tuple(points[b])], fill="#34bd68", width=2)
        for index, point in enumerate(points):
            if observation.landmarks[index, 3] > VISIBILITY_THRESHOLD:
                x, y = point
                draw.ellipse((x - 3, y - 3, x + 3, y + 3), fill="#ffd34d")
                draw.text((x + 4, y), str(index), fill="#193c28")
        for name, segment in sections:
            draw.line([tuple(end) for end in segment], fill="#00b0ff", width=3)
            draw.text(tuple(segment[0]), name, fill="#005085")
        response = ExtractionResponse(
            **result, annotated_image_url=f"/static/annotated/{filename}.png",
            provenance={"model": "MediaPipe Pose Landmarker Full", "landmarks": 33,
                        "model_sha256": self.detector.model_sha256, "device": "cpu",
                        "local_gpu_used": False, "input_sha256": hashlib.sha256(data).hexdigest(),
                        "method": "landmark-silhouette-projection-v1"},
        )
        # Validate all geometry before creating successful artifacts.
        Measurements.model_validate(result["measurements"])
        self.output_root.mkdir(parents=True, exist_ok=True)
        canvas.save(self.output_root / f"{filename}.png")
        Image.fromarray(observation.mask.astype(np.uint8) * 255).save(self.output_root / f"{filename}_mask.png")
        (self.output_root / f"{filename}.json").write_text(json.dumps({
            **response.model_dump(), "landmarks_normalized": observation.landmarks.tolist(),
            "landmarks_world_meters": observation.world_landmarks.tolist(),
        }, indent=2), encoding="utf-8")
        return response
