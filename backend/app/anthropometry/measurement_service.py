"""Deterministic single-view estimates. These are not measured body circumferences."""

import hashlib
import json
import math
from dataclasses import replace
from pathlib import Path
from time import perf_counter
from uuid import uuid4

import numpy as np
from PIL import Image, ImageDraw

from backend.app.anthropometry.diagnostics import diagnostic
from backend.app.anthropometry.pose_adapter import (
    MediaPipePose,
    PoseObservation,
    decode_person,
    refine_mask,
)
from backend.app.anthropometry.schemas import ExtractionResponse, PhotoMeasurements
from ml.errors import PipelineError

VISIBILITY_THRESHOLD = 0.65
KEY_LANDMARKS = {
    0: "nose", 11: "left shoulder", 12: "right shoulder",
    23: "left hip", 24: "right hip", 25: "left knee", 26: "right knee",
    27: "left ankle", 28: "right ankle", 29: "left heel", 30: "right heel",
}
KAPPA = {"chest": 2.45, "waist": 2.30, "hip": 2.40, "thigh": 2.50}
THIGH_FRACTION = 0.40  # Hip joints sit above the crotch; 25% often spans both legs.
CHEST_FRACTIONS = (0.25, 0.30, 0.35, 0.40, 0.45)
WAIST_FRACTIONS = (0.50, 0.48, 0.52)  # Local band only; do not substitute hips for waist.


def validate_pose(observation: PoseObservation) -> np.ndarray:
    if observation.image.ndim != 3 or observation.image.shape[2] != 3 or min(observation.image.shape[:2]) < 4:
        raise PipelineError("invalid_image", "Expected a valid RGB image for measurement.")
    landmarks = observation.landmarks
    if (landmarks.shape != (33, 4) or not np.isfinite(landmarks).all()
            or np.any((landmarks[:, 3] < 0) | (landmarks[:, 3] > 1))):
        raise PipelineError("invalid_pose", "Expected 33 finite MediaPipe landmarks.")
    h, w = observation.image.shape[:2]
    if observation.mask.shape != (h, w):
        raise PipelineError("invalid_mask", "Person mask dimensions do not match the image.")
    if not np.isfinite(observation.mask).all() or not np.isin(observation.mask, (0, 1)).all():
        raise PipelineError("invalid_mask", "Expected a binary person mask aligned with the processed image.")
    if not observation.mask.any():
        raise PipelineError("segmentation_missing", "No person outline was found. Use a contrasting background and retry.")
    weak = [name for index, name in KEY_LANDMARKS.items()
            if landmarks[index, 3] <= VISIBILITY_THRESHOLD]
    diagnostic("pose_validation", key_visibility={name: round(float(landmarks[i, 3]), 4)
               for i, name in KEY_LANDMARKS.items()}, low_visibility_count=len(weak))
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
    if (points[23, 0] - points[24, 0]) * (points[25, 0] - points[26, 0]) <= 0:
        raise PipelineError("unsupported_pose", "Stand with uncrossed legs, facing the camera.")
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
    endpoints = coordinates[[left, right]]
    if (not inside[left] or not inside[right] or left == 0 or right == len(offsets) - 1
            or np.any(endpoints <= 0)
            or np.any(endpoints >= np.array([mask.shape[1] - 1, mask.shape[0] - 1]))):
        raise PipelineError("partial_body", "Body outline reaches the image boundary.")
    width = float(offsets[right] - offsets[left] + 1)
    if width < 4:
        raise PipelineError("ambiguous_silhouette", "Body outline is too small to measure reliably.")
    return width, (center + offsets[left] * direction, center + offsets[right] * direction)


def band_width(mask, center, direction, axis):
    # Median over five adjacent sections limits isolated segmentation speckles.
    samples = [silhouette_width(mask, center + shift * axis, direction) for shift in (-2, -1, 0, 1, 2)]
    return sorted(samples, key=lambda item: item[0])[2]


def intersects_arm(segment, points, visibility) -> bool:
    """Reject a torso section that includes a confidently detected arm centerline."""
    start, end = segment
    line = end - start
    for a, b in ((11, 13), (13, 15), (12, 14), (14, 16)):
        if min(visibility[[a, b]]) <= VISIBILITY_THRESHOLD:
            continue
        limb = points[b] - points[a]
        matrix = np.column_stack((line, -limb))
        if abs(np.linalg.det(matrix)) < 1e-6:
            # A forearm lying along the section is an overlap, not a safe skip.
            length = np.linalg.norm(line)
            if length and abs(float(np.linalg.det(np.column_stack((line, points[a] - start))))) / length < 1:
                projections = sorted(float(np.dot(points[i] - start, line) / (length * length)) for i in (a, b))
                if projections[0] <= 1 and projections[1] >= 0:
                    return True
            continue
        along_section, along_arm = np.linalg.solve(matrix, points[a] - start)
        if 0 <= along_section <= 1 and 0 <= along_arm <= 1:
            return True
    return False


def torso_sections(observation: PoseObservation, points: np.ndarray):
    """Use observed central spans only; never cut an arm off at an invented body edge."""
    shoulder, hip = points[[11, 12]].mean(0), points[[23, 24]].mean(0)
    axis = (hip - shoulder) / np.linalg.norm(hip - shoulder)
    direction = np.array([axis[1], -axis[0]])
    shoulder_width = float(np.linalg.norm(points[11] - points[12]))
    arm_ids = [11, 12, 13, 14, 15, 16]
    arms_known = bool(np.all(observation.landmarks[arm_ids, 3] > VISIBILITY_THRESHOLD)
                      and np.all((observation.landmarks[arm_ids, :2] > 0)
                                 & (observation.landmarks[arm_ids, :2] < 1)))
    widths, fractions, quality, sections = {}, {}, {}, []
    for name, candidates in (("chest", CHEST_FRACTIONS), ("waist", WAIST_FRACTIONS)):
        samples, usable = [], []
        for fraction in candidates:
            center = shoulder * (1 - fraction) + hip * fraction
            try:
                width, segment = band_width(observation.mask, center, direction, axis)
            except PipelineError as exc:
                if exc.code == "partial_body":
                    raise
                samples.append({"fraction": fraction, "rejected": "torso_segmentation_failed"})
                continue
            left, right = (float(np.linalg.norm(end - center)) for end in segment)
            crossing = intersects_arm(segment, points, observation.landmarks[:, 3])
            sample = {"fraction": fraction, "width_pixels": width,
                      "left_pixels": round(left, 2), "right_pixels": round(right, 2),
                      "arm_overlap": crossing}
            samples.append(sample)
            if not crossing and arms_known:
                usable.append((fraction, width, segment, left, right))
        metric = name + "_circumference"
        if not usable:
            reason = ("arm_landmarks_uncertain" if not arms_known else
                      "arms_overlap_torso" if any(s.get("arm_overlap") for s in samples) else
                      "torso_segmentation_failed")
            quality[metric] = {"status": "unavailable", "reason": reason, "requires_manual_review": True}
            widths[name], fractions[name] = None, None
        else:
            # Prefer a non-wide, symmetric natural silhouette at the intended level.
            # The old width ratio remains a review heuristic, never an anatomical verdict.
            def suspicious(item):
                return item[1] > 1.65 * shoulder_width or abs(item[3] - item[4]) / item[1] > .35
            selected = next((item for item in usable if not suspicious(item)), usable[0])
            fraction, width, segment, left, right = selected
            wide = width > 1.65 * shoulder_width
            asymmetric = abs(left - right) / width > .35
            widths[name], fractions[name] = width, fraction
            sections.append((name, segment))
            quality[metric] = {
                "status": "review_required" if wide or asymmetric else "estimated",
                "reason": "wide_clothing_outline" if wide else "asymmetric_outline" if asymmetric else "observed_arm_free_span",
                "requires_manual_review": wide or asymmetric,
                "sample_fraction": fraction,
            }
        diagnostic("torso_sections", region=name, mask_size=list(observation.mask.shape[::-1]),
                   arm_landmarks_usable=arms_known, samples=samples, decision=quality[metric])
    if all(v["reason"] == "torso_segmentation_failed" for v in quality.values()):
        raise PipelineError("torso_segmentation_failed", "Pose detected, but the central torso outline is missing. Use a clear contrasting background or enter tape measurements.")
    return widths, fractions, quality, sections


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
    hip_center = p[[23, 24]].mean(axis=0)
    widths, fractions, metric_quality, sections = torso_sections(observation, p)
    thigh_widths = []
    thigh_centers = [p[hip] * (1 - THIGH_FRACTION) + p[knee] * THIGH_FRACTION
                     for hip, knee in ((23, 25), (24, 26))]
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
        "chest_circumference": widths["chest"] * scale * KAPPA["chest"] if widths["chest"] is not None else None,
        "waist_circumference": widths["waist"] * scale * KAPPA["waist"] if widths["waist"] is not None else None,
        "hip_circumference": float(np.linalg.norm(p[23] - p[24]) * scale * KAPPA["hip"]),
        "thigh_circumference": float(np.mean(thigh_widths) * scale * KAPPA["thigh"]),
        "inseam_length": float(np.mean([np.linalg.norm(p[i] - hip_center) for i in (27, 28)]) * scale),
    }
    if values["shoulder_width"] > 100 or values["inseam_length"] > 200 or max(v for v in values.values() if v is not None) > 400:
        raise PipelineError("implausible_geometry", "Pose geometry is inconsistent with the reported height.")
    review = [name for name, info in metric_quality.items() if info["requires_manual_review"]]
    reasons = {
        "arms_overlap_torso": "Arms overlap the visible torso outline; no body boundary was invented. Move arms slightly away or enter this tape measurement.",
        "arm_landmarks_uncertain": "Elbows or wrists are unclear or outside the frame; arm separation cannot be verified. Keep both arms visible or enter this tape measurement.",
        "wide_clothing_outline": "The visible outline is wide relative to the shoulders. Loose/layered clothing or body shape may explain it; confirm with a tape measure.",
        "asymmetric_outline": "The two torso sides disagree. Clothing, an accessory or occlusion may affect the outline; confirm with a tape measure.",
        "torso_segmentation_failed": "No reliable torso edge was found here. Try a contrasting background or enter this tape measurement.",
    }
    for name, info in metric_quality.items():
        if info["requires_manual_review"]:
            info["message"] = reasons[info["reason"]]
    return {
        "scale_factor": scale,
        "measurements": {name: round(value, 2) if value is not None else None for name, value in values.items()},
        "quality": {"estimates_only": True,
                    "status": "review_required" if review else "estimated",
                    "requires_manual_review": review, "metrics": metric_quality,
                    "minimum_key_landmark_visibility": float(observation.landmarks[list(KEY_LANDMARKS), 3].min()),
                    "visibility_threshold_exclusive": VISIBILITY_THRESHOLD,
                    "statistical_uncertainty": "Not calibrated; landmark visibility is not measurement accuracy."},
        "geometry": {"height_cm": height_cm, "height_pixels": height_px,
                     "head_y": head_y, "ankle_y": ankle_y,
                     "head_reference": "minimum y of visible MediaPipe face landmarks 0-10",
                     "head_landmark_indices": head_indices,
                     "image_size": list(observation.image.shape[1::-1]),
                     "projection_multipliers": KAPPA,
                     "chest_torso_fraction": fractions["chest"], "waist_torso_fraction": fractions["waist"],
                     "thigh_leg_fraction": THIGH_FRACTION,
                     "inseam_reference": "mean Euclidean distance from hip midpoint to ankles 27/28"},
        "warnings": [
            "Single-view estimates depend on self-reported height, perspective, clothing and segmentation.",
            "MediaPipe has no crown or crotch landmark. Face-to-ankle scale and hip-midpoint inseam are biased anatomical proxies.",
            "Circumference multipliers are specified heuristics, not calibrated tape measurements. Hip joint spacing is not outer hip width.",
            (f"Chest uses an observed arm-free section at {fractions['chest']:.0%} of shoulder-to-hip distance; it may miss the fullest chest/bust."
             if fractions["chest"] is not None else "Chest circumference is unavailable; its body outline could not be separated from the arms."),
            "Confirm important dimensions with a tape measure before choosing a size.",
        ] + [name.replace("_", " ") + ": " + metric_quality[name]["message"] for name in review],
    }, sections


class MeasurementService:
    def __init__(self, detector: MediaPipePose, output_root: Path):
        self.detector = detector
        self.output_root = output_root

    def extract(self, data: bytes, height_cm: float) -> ExtractionResponse:
        started = perf_counter()
        try:
            response = self._extract(data, height_cm)
        except PipelineError as exc:
            diagnostic("measurement_failed", code=exc.code, duration_seconds=round(perf_counter() - started, 3))
            raise
        diagnostic("measurement_completed", quality=response.quality["status"],
                   duration_seconds=round(perf_counter() - started, 3))
        return response

    def _extract(self, data: bytes, height_cm: float) -> ExtractionResponse:
        image = decode_person(data)
        observation = self.detector.detect(image)
        if observation.image.shape != image.shape:
            raise PipelineError("invalid_pose_frame", "The pose and photo use different image dimensions. Retry extraction.")
        result, sections = estimate(observation, height_cm)
        # Only retry image-guided segmentation when its coarse map bridged arms.
        # Full-resolution colour evidence can restore a real narrow gap; geometry
        # never paints a substitute contour through touching clothing or skin.
        if (observation.probabilities is not None and max(image.shape[:2]) > 800
                and any(q["reason"] == "arms_overlap_torso" for q in result["quality"]["metrics"].values())):
            try:
                refined = replace(observation, mask=refine_mask(image, observation.probabilities, max_edge=1600))
                next_result, next_sections = estimate(refined, height_cm)
                if len(next_result["quality"]["requires_manual_review"]) < len(result["quality"]["requires_manual_review"]):
                    observation, result, sections = refined, next_result, next_sections
                    diagnostic("torso_refinement", accepted=True, max_edge=1600)
            except PipelineError as exc:
                diagnostic("torso_refinement", accepted=False, code=exc.code)
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
            **result, measurement_id=filename, annotated_image_url=f"/static/annotated/{filename}.png",
            landmarks_normalized=observation.landmarks.tolist(),
            provenance={"model": "MediaPipe Pose Landmarker Full", "landmarks": 33,
                        "model_sha256": self.detector.model_sha256, "device": "cpu",
                        "local_gpu_used": False, "input_sha256": hashlib.sha256(data).hexdigest(),
                        "method": "landmark-silhouette-projection-v3",
                        "segmentation": "MediaPipe probabilities with deterministic CPU GrabCut refinement"},
        )
        # Validate all geometry before creating successful artifacts.
        PhotoMeasurements.model_validate(result["measurements"])
        try:
            self.output_root.mkdir(parents=True, exist_ok=True)
            canvas.save(self.output_root / f"{filename}.png")
            Image.fromarray(observation.mask.astype(np.uint8) * 255).save(self.output_root / f"{filename}_mask.png")
            (self.output_root / f"{filename}.json").write_text(json.dumps({
                **response.model_dump(), "landmarks_normalized": observation.landmarks.tolist(),
                "landmarks_world_meters": observation.world_landmarks.tolist(),
            }, indent=2, allow_nan=False), encoding="utf-8")
        except OSError as exc:
            self.remove_artifacts(filename)
            raise PipelineError("measurement_storage_unavailable", "Measurement output could not be saved. Check available storage.", 503) from exc
        return response

    def artifact_path(self, measurement_id: str, suffix: str = ".png") -> Path:
        import re
        if not re.fullmatch(r"pose_[0-9a-f]{32}", measurement_id) or suffix not in (".png", "_mask.png", ".json"):
            raise PipelineError("measurement_missing", "This measurement artifact was not found.", 404)
        root = self.output_root.resolve()
        path = root / f"{measurement_id}{suffix}"
        if path.resolve().parent != root:
            raise PipelineError("measurement_missing", "This measurement artifact was not found.", 404)
        return path

    def remove_artifacts(self, measurement_id: str):
        try:
            for suffix in (".png", "_mask.png", ".json"):
                self.artifact_path(measurement_id, suffix).unlink(missing_ok=True)
        except OSError as exc:
            raise PipelineError("measurement_storage_unavailable", "Measurement artifacts could not be removed; retry when storage is writable.", 503) from exc
