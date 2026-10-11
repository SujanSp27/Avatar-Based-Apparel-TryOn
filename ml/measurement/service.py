"""Measurements from actual mesh sections, in centimetres, with explicit priors."""

import numpy as np
import trimesh

from ml.errors import PipelineError
from ml.human.template import validate_mesh


def section_loops(mesh: trimesh.Trimesh, y: float) -> list[np.ndarray]:
    section = mesh.section(plane_origin=[0, y, 0], plane_normal=[0, 1, 0])
    if section is None:
        raise PipelineError("missing_section", f"Mesh has no cross section at {y:.3f} m.")
    loops = [p for p in section.discrete if len(p) > 3 and np.linalg.norm(p[0] - p[-1]) < 0.002]
    if not loops:
        raise PipelineError("open_section", "An anatomical mesh section is not closed.")
    return loops


def perimeter(loop: np.ndarray) -> float:
    return float(np.linalg.norm(np.diff(loop, axis=0), axis=1).sum())


def measure_body(mesh: trimesh.Trimesh, landmarks: dict) -> dict:
    validate_mesh(mesh)
    values = {"height": float(mesh.extents[1] * 100)}
    for name in ("chest", "waist", "hip"):
        loops = section_loops(mesh, landmarks[f"{name}Y"])
        # Arms form separate loops. The torso crosses the sagittal plane and contains the origin.
        central = [loop for loop in loops if loop[:, 0].min() < 0 < loop[:, 0].max()]
        if not central:
            raise PipelineError("anatomical_section", f"No central torso loop at {name}.")
        loop = max(central, key=perimeter)
        if (
            name == "chest"
            and np.ptp(loop[:, 0])
            > abs(landmarks["left"]["shoulder"][0] - landmarks["right"]["shoulder"][0]) * 1.3
        ):
            raise PipelineError(
                "merged_chest_section", "Chest section includes arm geometry; measurement stopped."
            )
        values[name] = perimeter(loop) * 100
    thigh = section_loops(mesh, landmarks["thighY"])
    separate = [loop for loop in thigh if loop[:, 0].max() < 0 or loop[:, 0].min() > 0]
    if len(separate) < 2:
        raise PipelineError(
            "anatomical_section", "Thigh sections are merged; cannot estimate circumference."
        )
    values["thigh"] = float(np.mean([perimeter(p) for p in separate]) * 100)
    left, right = landmarks["left"], landmarks["right"]
    shoulder_y = (left["shoulder"][1] + right["shoulder"][1]) / 2 + mesh.extents[1] * 0.015
    shoulder_points = np.concatenate(section_loops(mesh, shoulder_y))
    values["shoulderWidth"] = float(np.ptp(shoulder_points[:, 0]) * 100)
    values["armLength"] = float(
        np.mean(
            [
                sum(
                    np.linalg.norm(np.array(s[a]) - s[b])
                    for a, b in (("shoulder", "elbow"), ("elbow", "wrist"))
                )
                for s in (left, right)
            ]
        )
        * 100
    )
    values["inseam"] = float((landmarks["crotchY"] - mesh.bounds[0, 1]) * 100)
    rounded = {k: round(v, 1) for k, v in values.items()}
    rounded.update(
        {
            "units": "cm",
            "method": "mesh_sections_and_anatomical_landmarks",
            "confidence": None,
            "uncertaintyCm": {
                key: round(value * (0.02 if key == "height" else 0.15), 1)
                for key, value in values.items()
            },
            "uncertaintyMethod": "uncalibrated heuristic ±15%; height ±2%; does not cover all image/depth errors",
        }
    )
    return rounded
