"""Deterministic constrained relaxation and actual body-surface collision projection."""

import numpy as np
import trimesh

from ml.errors import PipelineError
from ml.garment.templates import GarmentResult


def collision_distances(body: trimesh.Trimesh, points: np.ndarray) -> np.ndarray:
    # Bounded batches avoid large ray/proximity temporary arrays on 8 GB machines.
    return np.concatenate(
        [
            trimesh.proximity.signed_distance(body, batch)
            for batch in np.array_split(points, max(1, (len(points) + 255) // 256))
        ]
    )


def project_outside(
    body: trimesh.Trimesh, vertices: np.ndarray, gap: float
) -> tuple[np.ndarray, int]:
    points = vertices.copy()
    moved = 0
    # Positive signed distance denotes interior. Normals of the validated closed body point out.
    for _ in range(3):
        signed = collision_distances(body, points)
        ids = np.flatnonzero(signed > -gap)
        if not len(ids):
            break
        closest, _, face_ids = trimesh.proximity.closest_point(body, points[ids])
        points[ids] = closest + body.face_normals[face_ids] * (gap + 0.001)
        moved += len(ids)
    return points, moved


def fit_garment(body: trimesh.Trimesh, garment: GarmentResult) -> tuple[trimesh.Trimesh, dict]:
    mesh = garment.mesh.copy()
    gap = 0.004
    initial = collision_distances(body, mesh.vertices)
    vertices, projected = project_outside(body, mesh.vertices, gap)
    # Mild constrained Laplacian relaxation: seams/openings stay fixed; torso settles down.
    adjacency = trimesh.smoothing.laplacian_calculation(mesh)
    rest = vertices.copy()
    for _ in range(5):
        relaxed = adjacency.dot(vertices)
        vertices = 0.90 * vertices + 0.10 * relaxed
        vertices[:, 1] -= 0.0004
        vertices[garment.pinned] = rest[garment.pinned]
    vertices, moved = project_outside(body, vertices, gap)
    projected += moved
    mesh.vertices = vertices
    # Check triangle centres too: vertex-only collision tests miss faces crossing the body.
    for _ in range(3):
        centers = mesh.triangles_center
        signed = collision_distances(body, centers)
        faces = np.flatnonzero(signed > -0.001)
        if not len(faces):
            break
        nearest, _, ids = trimesh.proximity.closest_point(body, centers[faces])
        shift = nearest + body.face_normals[ids] * (gap + 0.003) - centers[faces]
        accum = np.zeros_like(vertices)
        count = np.zeros(len(vertices))
        for corner in range(3):
            np.add.at(accum, mesh.faces[faces, corner], shift)
            np.add.at(count, mesh.faces[faces, corner], 1)
        used = count > 0
        vertices[used] += accum[used] / count[used, None]
        vertices, moved = project_outside(body, vertices, gap)
        projected += moved
        mesh.vertices = vertices
    final_vertices = collision_distances(body, mesh.vertices)
    final_centers = collision_distances(body, mesh.triangles_center)
    penetration = int((final_vertices > 0.001).sum() + (final_centers > 0.001).sum())
    rate = penetration / (len(mesh.vertices) + len(mesh.faces))
    if rate > 0.005 or not np.isfinite(mesh.vertices).all():
        raise PipelineError(
            "fitting_failed",
            "Garment still intersects the body after projection; try a different garment or fit.",
        )
    return mesh, {
        "method": "anatomical loft alignment + constrained relaxation + surface projection",
        "initialPenetratingVertices": int((initial > 0).sum()),
        "projectionOperations": projected,
        "remainingPenetrationSamples": penetration,
        "sampledPenetrationRate": rate,
        "clearanceM": gap,
        "relaxationIterations": 5,
        "selfCollisionChecked": False,
        "collisionSampling": "vertices and face centres; not continuous collision detection",
    }
