"""Landmark dependencies and observed foot evidence, independent of gender."""
import cv2
import numpy as np

from ml.errors import PipelineError

VISIBILITY_THRESHOLD = .65
PRESENCE_THRESHOLD = .5  # Same as the configured Tasks pose presence threshold.


def usable(observation) -> np.ndarray:
    landmarks = observation.landmarks
    valid = ((landmarks[:, 3] > VISIBILITY_THRESHOLD)
             & np.all((landmarks[:, :2] > .005) & (landmarks[:, :2] < .995), axis=1))
    if observation.presence is not None:
        valid &= observation.presence > PRESENCE_THRESHOLD
    return valid


def quality(observation, indices, method, reason=None, **details):
    return {
        "status": "unavailable" if reason else "estimated",
        "reason": reason or "observed_geometry",
        "requires_manual_review": reason is not None,
        "method": method, "unit": "cm", "landmark_indices": list(indices),
        "landmark_visibility_min": float(observation.landmarks[list(indices), 3].min()),
        "landmark_presence_min": (float(observation.presence[list(indices)].min())
                                  if observation.presence is not None else None),
        "confidence": None,  # No calibrated accuracy model exists for these heuristics.
        **details,
    }


def calibrate(observation, points, height_cm):
    valid = usable(observation)
    heads = [i for i in range(11) if valid[i]]
    if np.any((observation.landmarks[[27, 28], :2] <= .005)
              | (observation.landmarks[[27, 28], :2] >= .995)):
        raise PipelineError("partial_body", "Feet are outside the image. Include your full head and both feet with space below them.")
    if not heads or not valid[[27, 28]].all():
        raise PipelineError("scale_unavailable", "Image scale needs a visible face and both ankles. Include your full body or enter tape measurements.")
    _, body_labels = cv2.connectedComponents(observation.mask.astype(np.uint8))
    face_pixels = np.rint(points[heads]).astype(int)
    head_labels = np.unique(body_labels[face_pixels[:, 1], face_pixels[:, 0]])
    if np.isin(body_labels[:2], head_labels[head_labels != 0]).any():
        raise PipelineError("partial_body", "The person outline reaches the top of the image. Include space above your head for height calibration.")
    head_y, ankle_y = float(points[heads, 1].min()), float(points[[27, 28], 1].max())
    height_px = ankle_y - head_y
    if height_px < 100:
        raise PipelineError("person_too_small", "Move closer while keeping your entire body in frame.")
    h, w = observation.mask.shape
    feet = []
    for ankle, heel, toe in ((27, 29, 31), (28, 30, 32)):
        x, y = points[ankle]
        radius = max(4, round(height_px * .065))
        x0, x1 = max(0, round(x) - radius), min(w, round(x) + radius + 1)
        y0 = max(0, round(y) - max(3, round(height_px * .015)))
        patch = observation.mask[y0:, x0:x1].astype(np.uint8)
        _, labels = cv2.connectedComponents(patch)
        label = labels[round(y) - y0, round(x) - x0]
        if not label:
            raise PipelineError("scale_unavailable", "The ankle and foot outline disagree. Use a clearer full-body photo or enter tape measurements.")
        yy, xx = np.where(labels == label)
        bottom = int(yy.max() + y0)
        if bottom >= h - 2 or np.any(xx + x0 <= 0) or np.any(xx + x0 >= w - 1):
            raise PipelineError("partial_body", "A foot outline reaches the image edge. Leave space below and beside both feet.")
        # A foot landmark must actually lie near this ankle, in the observed mask.
        supported = []
        for index in (heel, toe):
            px, py = points[index]
            if not (y0 <= round(py) < h and x0 <= round(px) < x1):
                continue
            if (valid[index] and abs(px - x) < radius and y - height_px * .025 <= py <= bottom + 2
                    and labels[round(py) - y0, round(px) - x0] == label):
                supported.append(index)
        visible_depth = bottom - y
        if visible_depth < max(3, height_px * .008) or (not supported and visible_depth < height_px * .02):
            raise PipelineError("scale_unavailable", "The complete foot outline cannot be verified. Include both feet clearly or enter tape measurements.")
        feet.append({"ankle": ankle, "supporting_landmarks": supported,
                     "silhouette_bottom_y": bottom, "below_ankle_pixels": round(visible_depth, 2),
                     "method": "ankle_with_bounded_foot_silhouette"})
    return height_cm / height_px, head_y, ankle_y, heads, feet


def uncertain_arm_is_separate(observation, points, center, valid):
    """Only accept an uncertain wrist when an actual mask gap separates its arm.

    Cutting above the section removes the anatomical shoulder connection. A
    distinct foreground component at the visible elbow proves separation here;
    a joined arm or missing elbow provides no such evidence.
    """
    y0 = max(0, int(center[1]) - 3)
    _, labels = cv2.connectedComponents(observation.mask[y0:].astype(np.uint8))
    cx, cy = np.rint(center).astype(int)
    torso = labels[cy - y0, cx]
    if not torso:
        return False
    for shoulder, elbow, wrist in ((11, 13, 15), (12, 14, 16)):
        if valid[[shoulder, elbow, wrist]].all():
            continue
        if not valid[[shoulder, elbow]].all() or points[elbow, 1] < y0:
            return False
        x, y = np.rint(points[elbow]).astype(int)
        label = labels[y - y0, x]
        if not label or label == torso:
            return False
    return True
