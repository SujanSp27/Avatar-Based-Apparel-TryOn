"""Pose-conditioned deterministic mannequin. Not a learned SMPL shape regressor."""

import numpy as np
import trimesh
from skimage.measure import marching_cubes

from ml.errors import PipelineError
from ml.human.base import BodyResult
from ml.preprocessing.images import ImageFeatures


def validate_mesh(mesh: trimesh.Trimesh) -> dict:
    valid = (
        len(mesh.vertices) > 100
        and np.isfinite(mesh.vertices).all()
        and mesh.is_watertight
        and mesh.is_winding_consistent
        and mesh.volume > 0
        and 1.19 < mesh.extents[1] < 2.21
    )
    if not valid:
        raise PipelineError(
            "invalid_body_mesh",
            "Reconstruction produced an invalid body mesh; downstream processing stopped.",
        )
    return {
        "watertight": bool(mesh.is_watertight),
        "windingConsistent": bool(mesh.is_winding_consistent),
        "vertices": len(mesh.vertices),
        "faces": len(mesh.faces),
        "volumeM3": float(mesh.volume),
    }


class MediaPipeTemplateReconstructor:
    version = "mediapipe-template-1.1"

    def reconstruct(self, features: ImageFeatures, height_cm: float) -> BodyResult:
        h = height_cm / 100
        points = features.landmarks
        ih, iw = features.mask.shape
        x0, y0, x1, y1 = features.bbox
        scale = h / (y1 - y0)
        shoulder_width = np.clip(
            abs(points[11, 0] - points[12, 0]) * iw * scale, h * 0.19, h * 0.29
        )
        hip_y = points[[23, 24], 1].mean() * ih
        shoulder_y = points[[11, 12], 1].mean() * ih
        center = points[[11, 12, 23, 24], 0].mean() * iw

        def silhouette_width(frac):
            row = int(shoulder_y + frac * (hip_y - shoulder_y))
            row = int(np.clip(row, 0, ih - 1))
            hits = np.flatnonzero(features.mask[row] > 0)
            groups = np.split(hits, np.where(np.diff(hits) > 1)[0] + 1)
            group = min((g for g in groups if len(g)), key=lambda g: abs(g.mean() - center))
            return float(np.clip((group[-1] - group[0]) * scale, h * 0.14, h * 0.32))

        chest_w, waist_w, hip_w = [silhouette_width(t) for t in (0.26, 0.65, 1.0)]
        # Clothing arms can merge with the torso mask; cap this unobservable quantity explicitly.
        chest_w = min(chest_w, shoulder_width * 1.06)
        waist_w = min(waist_w, shoulder_width * 1.03)
        hip_w = min(hip_w, shoulder_width * 1.18)
        # Canonical A pose makes anatomical sections and template fitting reproducible.
        # World landmarks are retained as observed pose, rather than mislabelled SMPL rotations.
        step = h / 145
        low = np.array([-h * 0.39, -step * 2, -h * 0.17])
        high = np.array([h * 0.39, h * 1.02, h * 0.20])
        axes = [np.arange(a, b + step, step) for a, b in zip(low, high)]
        grid = np.stack(np.meshgrid(*axes, indexing="ij"), axis=-1).astype(np.float32)
        field = np.full(grid.shape[:-1], 10, dtype=np.float32)

        def blend(distance, smooth=0.008):
            nonlocal field
            k = smooth * h
            t = np.maximum(k - np.abs(field - distance), 0) / k
            field = np.minimum(field, distance) - t * t * k * 0.25

        def ellipsoid(c, r):
            r = np.array(r)
            distance = (np.linalg.norm((grid - np.array(c)) / r, axis=-1) - 1) * min(r)
            blend(distance)

        def limb(a, b, r0, r1, depth=1.0):
            a, b = np.array(a), np.array(b)
            d = b - a
            t = np.clip(np.sum((grid - a) * d, axis=-1) / np.dot(d, d), 0, 1)
            delta = grid - (a + t[..., None] * d)
            delta[..., 2] /= depth
            blend(np.linalg.norm(delta, axis=-1) - (r0 + t * (r1 - r0)))

        # Torso is an interpolated elliptical solid; measured widths come from foreground rows.
        levels = h * np.array([0.465, 0.54, 0.62, 0.72, 0.80, 0.825])
        widths = np.array(
            [
                hip_w * 0.36,
                hip_w * 0.50,
                waist_w * 0.50,
                chest_w * 0.50,
                shoulder_width * 0.49,
                shoulder_width * 0.38,
            ]
        )
        depths = widths * np.array([0.85, 0.76, 0.72, 0.72, 0.60, 0.65])
        ry = grid[..., 1]
        rx = np.interp(ry, levels, widths)
        rz = np.interp(ry, levels, depths)
        radial = (np.sqrt((grid[..., 0] / rx) ** 2 + (grid[..., 2] / rz) ** 2) - 1) * np.minimum(
            rx, rz
        )
        slab = np.maximum(levels[0] - ry, ry - levels[-1])
        blend(np.maximum(radial, slab))
        ellipsoid([0, h * 0.84, 0], [h * 0.043, h * 0.063, h * 0.045])
        ellipsoid([0, h * 0.923, 0.008], [h * 0.061, h * 0.077, h * 0.064])
        landmarks = {
            "chestY": float(h * 0.69),
            "waistY": float(h * 0.62),
            "hipY": float(h * 0.54),
            "thighY": float(h * 0.40),
            "crotchY": float(h * 0.465),
        }
        for side, sign in (("left", -1), ("right", 1)):
            shoulder = [sign * shoulder_width * 0.48, h * 0.79, 0]
            elbow = [sign * (shoulder_width * 0.5 + h * 0.10), h * 0.64, 0]
            wrist = [sign * (shoulder_width * 0.5 + h * 0.14), h * 0.49, 0.015]
            hip = [sign * hip_w * 0.25, h * 0.49, 0]
            knee = [sign * hip_w * 0.27, h * 0.275, 0]
            ankle = [sign * hip_w * 0.30, h * 0.06, 0]
            limb(shoulder, elbow, h * 0.038, h * 0.029)
            limb(elbow, wrist, h * 0.029, h * 0.019)
            ellipsoid([wrist[0], h * 0.46, 0.018], [h * 0.022, h * 0.047, h * 0.018])
            limb(hip, knee, hip_w * 0.235, h * 0.037, 0.94)
            limb(knee, ankle, h * 0.036, h * 0.023)
            ellipsoid([ankle[0], h * 0.030, h * 0.034], [h * 0.030, h * 0.030, h * 0.069])
            landmarks[side] = {
                "shoulder": shoulder,
                "elbow": elbow,
                "wrist": wrist,
                "hip": hip,
                "knee": knee,
                "ankle": ankle,
            }
        vertices, faces, _, _ = marching_cubes(field, 0, spacing=(step, step, step))
        mesh = trimesh.Trimesh(vertices=vertices + low, faces=faces, process=True)
        mesh.fix_normals()
        # Calibrate to the supplied height exactly, including discretization at head and soles.
        offset = mesh.bounds[0, 1]
        factor = h / mesh.extents[1]
        mesh.vertices[:, 1] -= offset
        mesh.apply_scale(factor)
        for name in ["chestY", "waistY", "hipY", "thighY", "crotchY"]:
            landmarks[name] = (landmarks[name] - offset) * factor
        for side in ("left", "right"):
            for joint, value in landmarks[side].items():
                v = np.array(value)
                v[1] -= offset
                landmarks[side][joint] = (v * factor).tolist()
        mesh.visual.vertex_colors = [187, 167, 145, 255]
        quality = validate_mesh(mesh)
        return BodyResult(
            mesh,
            {
                "representation": "elliptical-surface-and-capsule-template",
                "smplCompatible": False,
                "shapeParameters": {
                    "shoulderWidthM": float(shoulder_width),
                    "chestWidthM": chest_w,
                    "waistWidthM": waist_w,
                    "hipWidthM": hip_w,
                    "depthPriorRatio": 0.72,
                },
                "poseParameters": {
                    "outputPose": "canonical A",
                    "observedWorldLandmarks": features.world_landmarks.tolist(),
                },
                "cameraParameters": {
                    "type": "weak-perspective",
                    "metresPerPixel": scale,
                    "imageWidth": iw,
                    "imageHeight": ih,
                },
                "heightCm": height_cm,
                "quality": quality,
                "landmarks": landmarks,
            },
            landmarks,
            {
                "backend": self.version,
                "pretrainedComponent": "MediaPipe Pose Landmarker Full float16 v1",
                "shapeRecovery": "deterministic approximate template",
                "validatedAnthropometry": False,
            },
        )
