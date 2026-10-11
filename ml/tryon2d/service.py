"""Legacy debug-only garment overlay; never used by the application API.

Retained solely to reproduce the rejected baseline. This is not virtual try-on.
It never generates unseen anatomy or interprets pixel lengths as centimetres.
"""

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from ml.errors import PipelineError
from ml.preprocessing.images import ImageFeatures

VERSION = "opencv-overlay-1.0"


def _visible(points: np.ndarray, indices: list[int], threshold: float = 0.55) -> bool:
    selected = points[indices]
    return bool(
        np.all(np.isfinite(selected))
        and np.all(selected[:, 3] >= threshold)
        and np.all(selected[:, :2] >= 0.01)
        and np.all(selected[:, :2] <= 0.99)
    )


def _skin(rgb: np.ndarray) -> np.ndarray:
    """Conservative skin-colour candidate mask; never a semantic skin claim."""
    ycrcb = cv2.cvtColor(rgb, cv2.COLOR_RGB2YCrCb)
    red, green, blue = (rgb[:, :, i].astype(np.int16) for i in range(3))
    return (
        (ycrcb[:, :, 1] >= 133)
        & (ycrcb[:, :, 1] <= 176)
        & (ycrcb[:, :, 2] >= 77)
        & (ycrcb[:, :, 2] <= 128)
        & (red > green)
        & (red > blue)
        & (red - blue > 15)
        & (green > 40)
    ).astype(np.uint8)


def _garment_pixels(garment: ImageFeatures, category: str) -> tuple[np.ndarray, np.ndarray]:
    rgb = np.ascontiguousarray(garment.crop[:, :, :3])
    alpha = garment.crop[:, :, 3].copy()
    if category != "trouser":
        # Remove exposed skin from a worn garment image only near its perimeter.
        # Central printed graphics are preserved even if they are skin-coloured.
        skin = _skin(rgb)
        count, labels, stats, _ = cv2.connectedComponentsWithStats(skin)
        height, width = alpha.shape
        foreground_area = max(1, np.count_nonzero(alpha))
        for index in range(1, count):
            x, y, component_w, component_h, area = stats[index]
            # A large connected beige/brown region is more likely the uploaded
            # fabric than a small exposed neck or arm. Do not erase that fabric
            # based on its colour alone.
            if area < 4 or area > foreground_area * 0.18:
                continue
            touches_top = y < height * 0.05
            outer_arm = (x < width * 0.2 or x + component_w > width * 0.8) and (
                y + component_h > height * 0.35
            )
            if touches_top or outer_arm:
                alpha[labels == index] = 0
    return rgb, alpha


def _upper_transform(
    person: ImageFeatures, crop_shape: tuple, fit: str
) -> tuple[np.ndarray, float, bool]:
    points = person.landmarks
    h, w = person.mask.shape
    if points is None or points.shape != (33, 4) or not _visible(points, [11, 12]):
        raise PipelineError(
            "upper_body_not_visible",
            "For a 2D top preview, show both shoulders and your chest clearly. "
            "A face-only photo cannot be used; a waist-up photo is enough.",
        )
    shoulders = points[[11, 12], :2] * [w, h]
    shoulders = shoulders[np.argsort(shoulders[:, 0])]
    centre = shoulders.mean(axis=0)
    span = float(np.linalg.norm(shoulders[1] - shoulders[0]))
    if span < 0.14 * w or abs(shoulders[1, 1] - shoulders[0, 1]) > span * 0.45:
        raise PipelineError(
            "upper_body_pose",
            "Face the camera with both shoulders visible for the 2D preview.",
        )
    if h - centre[1] < span * 0.35:
        raise PipelineError(
            "upper_body_not_visible",
            "Include more of your chest below the shoulders; face-only photos cannot show a top.",
        )
    has_hips = _visible(points, [23, 24])
    if has_hips:
        hip_centre = points[[23, 24], :2].mean(axis=0) * [w, h]
        length = float(hip_centre[1] - centre[1])
        if length < span * 0.55:
            has_hips = False
    if not has_hips:
        # Virtual placement extends beyond the frame and is clipped. It does not
        # hallucinate a visible lower body or estimate a physical body length.
        hip_centre = centre + [0, span * 1.2]
        length = span * 1.2
    ease = {"tight": 0.96, "regular": 1.03, "loose": 1.11}[fit]
    top = centre + (shoulders - centre) * ease
    top[:, 1] -= span * 0.09
    bottom_width = span * ease * 0.90
    bottom = np.array(
        [
            hip_centre + [-bottom_width / 2, length * 0.06],
            hip_centre + [bottom_width / 2, length * 0.06],
        ]
    )
    source_h, source_w = crop_shape[:2]
    # Shoulder anchors lie inside sleeves; mapping the whole silhouette then
    # retains the uploaded sleeve and neckline geometry rather than a rectangle.
    source = np.float32(
        [
            [source_w * 0.19, source_h * 0.12],
            [source_w * 0.81, source_h * 0.12],
            [source_w * 0.25, source_h * 0.97],
            [source_w * 0.75, source_h * 0.97],
        ]
    )
    target = np.float32([top[0], top[1], bottom[0], bottom[1]])
    head_boundary = float(centre[1] - span * 0.25)
    return cv2.getPerspectiveTransform(source, target), head_boundary, not has_hips


def _lower_transform(
    person: ImageFeatures, crop_shape: tuple, fit: str
) -> tuple[np.ndarray, float]:
    points = person.landmarks
    h, w = person.mask.shape
    if points is None or not _visible(points, [23, 24, 25, 26]):
        raise PipelineError(
            "lower_body_not_visible",
            "A 2D trouser preview needs both hips and knees visible. "
            "Use a lower-body or full-body photo, or select a T-shirt or shirt for this portrait.",
        )
    hips = points[[23, 24], :2] * [w, h]
    hips = hips[np.argsort(hips[:, 0])]
    knees = points[[25, 26], :2] * [w, h]
    hip_centre = hips.mean(axis=0)
    knee_y = float(knees[:, 1].mean())
    span = float(hips[1, 0] - hips[0, 0])
    if span < 0.08 * w or knee_y < hip_centre[1] + span * 0.6:
        raise PipelineError(
            "lower_body_pose", "Stand facing forward with legs uncrossed for trousers."
        )
    ease = {"tight": 1.18, "regular": 1.28, "loose": 1.40}[fit]
    half_width = span * ease / 2
    bottom_y = float(
        points[[27, 28], 1].mean() * h
        if _visible(points, [27, 28])
        else knee_y + (knee_y - hip_centre[1])
    )
    sh, sw = crop_shape[:2]
    source = np.float32([[0, 0], [sw - 1, 0], [0, sh - 1], [sw - 1, sh - 1]])
    target = np.float32(
        [
            [hip_centre[0] - half_width, hip_centre[1] - span * 0.12],
            [hip_centre[0] + half_width, hip_centre[1] - span * 0.12],
            [hip_centre[0] - half_width, bottom_y],
            [hip_centre[0] + half_width, bottom_y],
        ]
    )
    return cv2.getPerspectiveTransform(source, target), float(hip_centre[1] - span * 0.13)


def _foreground_occlusion(person: ImageFeatures, protected_above: float) -> np.ndarray:
    """Preserve head and landmark-supported hands/forearms in front of a top.

    Skin-like colour is evidence only inside an anatomical region. A beige shirt
    can match every colour threshold and must not disappear from the overlay.
    """
    h, w = person.mask.shape
    protected = np.zeros((h, w), dtype=np.uint8)
    protected[: max(0, int(protected_above) + 1)] = 1
    skin_regions = np.zeros((h, w), dtype=np.uint8)
    points = person.landmarks
    shoulders = points[[11, 12], :2] * [w, h]
    shoulder_width = float(np.linalg.norm(shoulders[0] - shoulders[1]))
    centre = shoulders.mean(axis=0)
    cv2.rectangle(
        skin_regions,
        (int(centre[0] - shoulder_width * 0.16), int(protected_above)),
        (int(centre[0] + shoulder_width * 0.16), int(centre[1] - shoulder_width * 0.04)),
        1,
        -1,
    )
    left, right = sorted(shoulders[:, 0])
    for elbow_index, wrist_index, fingers in ((13, 15, [17, 19, 21]), (14, 16, [18, 20, 22])):
        elbow, wrist = points[[elbow_index, wrist_index]]
        if wrist[3] > 0.45 and np.all(wrist[:2] > 0) and np.all(wrist[:2] < 1.05):
            for index in [wrist_index, *fingers]:
                point = points[index]
                if point[3] < 0.3 or np.any(point[:2] < 0) or np.any(point[:2] > 1.05):
                    continue
                pixel = tuple(np.rint(point[:2] * [w, h]).astype(int))
                cv2.circle(skin_regions, pixel, max(3, int(shoulder_width * 0.11)), 1, -1)
            if elbow[3] > 0.55:
                start, end = np.rint(np.array([elbow[:2], wrist[:2]]) * [w, h]).astype(int)
                cv2.line(
                    skin_regions,
                    tuple(start),
                    tuple(end),
                    1,
                    max(3, int(shoulder_width * 0.18)),
                )
        if (
            elbow[3] > 0.55
            and wrist[3] > 0.45
            and 0 < wrist[1] < 1.05
            and left < wrist[0] * w < right
            and abs(wrist[0] - elbow[0]) * w > shoulder_width * 0.2
        ):
            start, end = np.rint(np.array([elbow[:2], wrist[:2]]) * [w, h]).astype(int)
            cv2.line(protected, tuple(start), tuple(end), 1, max(3, int(shoulder_width * 0.18)))
    protected |= skin_regions & _skin(person.image[:, :, :3])
    return protected


def render_tryon_2d(
    person: ImageFeatures, garment: ImageFeatures, category: str, fit: str, folder: Path
) -> dict:
    """Write a real garment-pixel composite and reproducible placement metadata."""
    if category not in {"t-shirt", "shirt", "dress", "trouser"}:
        raise PipelineError("garment_category", "Unsupported garment category.")
    if fit not in {"tight", "regular", "loose"}:
        raise PipelineError("fit_preference", "Choose tight, regular or loose fit.")
    rgb, source_alpha = _garment_pixels(garment, category)
    warnings = list(garment.warnings)
    warnings.append(
        "This is a 2D garment overlay, not a photorealistic simulation. "
        "Fabric drape, sleeve pose and crossed-arm depth may be inaccurate."
    )
    if category == "trouser":
        transform, boundary = _lower_transform(person, rgb.shape, fit)
        cropped = not _visible(person.landmarks, [27, 28])
        visible_region = "lower_body"
        protected = np.zeros(person.mask.shape, dtype=np.uint8)
        protected[: max(0, int(boundary) + 1)] = 1
    else:
        transform, boundary, cropped = _upper_transform(person, rgb.shape, fit)
        protected = _foreground_occlusion(person, boundary)
        visible_region = "upper_body" if cropped else "torso"
        if category == "dress":
            warnings.append(
                "The dress is shown only over the visible torso; skirt length and lower-body fit "
                "are not reconstructed in this 2D preview."
            )
    if cropped:
        warnings.append(
            "Only the visible part of your body is shown; the garment is clipped to the photo."
        )
    h, w = person.mask.shape
    warped_rgb = cv2.warpPerspective(rgb, transform, (w, h), flags=cv2.INTER_LINEAR)
    warped_alpha = cv2.warpPerspective(source_alpha, transform, (w, h), flags=cv2.INTER_LINEAR)
    alpha = cv2.GaussianBlur(warped_alpha, (3, 3), 0.5).astype(np.float32) / 255
    alpha *= person.mask.astype(np.float32) / 255
    alpha[protected > 0] = 0
    if np.count_nonzero(alpha > 0.5) < 0.015 * h * w:
        raise PipelineError(
            "overlay_not_visible",
            "There is too little visible clothing area for a 2D preview. "
            "Use a clear chest-up or waist-up photo with both shoulders visible.",
        )
    original = np.ascontiguousarray(person.image[:, :, :3])
    composite = np.rint(warped_rgb * alpha[:, :, None] + original * (1 - alpha[:, :, None]))
    composite = np.clip(composite, 0, 255).astype(np.uint8)
    folder.mkdir(parents=True, exist_ok=True)
    Image.fromarray(composite).save(folder / "tryon-2d.png")
    Image.fromarray(original).save(folder / "original-person.png")
    diagnostics = {
        "method": "pose-guided-garment-overlay",
        "modelVersion": VERSION,
        "visibleRegion": visible_region,
        "outputFile": "tryon-2d.png",
        "originalFile": "original-person.png",
        "warnings": warnings,
        "diagnostics": {
            "imagePixels": {"width": w, "height": h},
            "projectiveTransform": transform.tolist(),
            "protectedAbovePixelY": boundary,
            "overlaidPixels": int(np.count_nonzero(alpha > 0.5)),
            "croppedBody": cropped,
            "backgroundPreserved": True,
            "physicalSizingAvailable": False,
        },
    }
    (folder / "overlay-diagnostics.json").write_text(
        json.dumps(diagnostics, indent=2), encoding="utf-8"
    )
    return diagnostics
