from dataclasses import dataclass

import numpy as np
import trimesh
from PIL import Image
from scipy.ndimage import distance_transform_edt
from trimesh.visual.material import PBRMaterial
from trimesh.visual.texture import TextureVisuals

from ml.errors import PipelineError
from ml.human.base import BodyResult
from ml.preprocessing.images import ImageFeatures


@dataclass
class GarmentResult:
    mesh: trimesh.Trimesh
    parameters: dict
    pinned: np.ndarray


def ring_surface(centers, radii, segments=48) -> trimesh.Trimesh:
    """Capped solid loft; end caps are opened after joining template volumes."""
    centers = np.asarray(centers)
    direction = centers[-1] - centers[0]
    direction /= np.linalg.norm(direction)
    z = np.array([0.0, 0.0, 1.0])
    x = np.cross(direction, z)
    x /= np.linalg.norm(x)
    theta = np.arange(segments) * 2 * np.pi / segments
    vertices = []
    for center, (rx, rz) in zip(centers, radii):
        vertices.extend(center + rx * np.cos(theta)[:, None] * x + rz * np.sin(theta)[:, None] * z)
    faces = []
    for ring in range(len(centers) - 1):
        for col in range(segments):
            a, b = ring * segments + col, ring * segments + (col + 1) % segments
            c, d = a + segments, b + segments
            faces.extend([[a, c, b], [b, c, d]])
    for ring, center in ((0, centers[0]), (len(centers) - 1, centers[-1])):
        center_index = len(vertices)
        vertices.append(center)
        for col in range(segments):
            faces.append(
                [center_index, ring * segments + col, ring * segments + (col + 1) % segments]
            )
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    mesh.fix_normals()
    if mesh.volume < 0:
        mesh.invert()
    mesh.metadata["openings"] = [
        {"center": c.tolist(), "normal": direction.tolist(), "radius": max(r) + 0.001}
        for c, r in ((centers[0], radii[0]), (centers[-1], radii[-1]))
    ]
    return mesh


def texture_from_crop(features: ImageFeatures) -> Image.Image:
    crop = features.crop
    foreground = crop[:, :, 3] > 127
    # Extend nearest fabric into the atlas background to prevent white halos at UV boundaries.
    indices = distance_transform_edt(~foreground, return_distances=False, return_indices=True)
    filled = crop[:, :, :3][tuple(indices)]
    return Image.fromarray(filled).resize((512, 512), Image.Resampling.LANCZOS)


def reconstruct_garment(
    features: ImageFeatures,
    category: str,
    body: BodyResult,
    measurements: dict,
    selected_size: dict,
    fit: str,
    dimensions: dict | None = None,
) -> GarmentResult:
    h = body.mesh.extents[1]
    shape = body.parameters["shapeParameters"]
    dims = dimensions or {}
    clearance = {"tight": 0.006, "regular": 0.013, "loose": 0.028}[fit]
    chest_target = (selected_size["chestMin"] + selected_size["chestMax"]) / 2
    hip_target = (selected_size["hipMin"] + selected_size["hipMax"]) / 2
    chest_scale = np.clip((chest_target + clearance * 500) / measurements["chest"], 0.94, 1.28)
    hip_scale = np.clip((hip_target + clearance * 500) / measurements["hip"], 0.94, 1.28)
    silhouette_ratio = features.crop.shape[0] / features.crop.shape[1]
    pieces = []
    if category == "trouser":
        y = np.linspace(h * 0.477, h * 0.62, 12)
        width_scale = dims.get("widthCm", shape["hipWidthM"] * 100) / (shape["hipWidthM"] * 100)
        width = (shape["hipWidthM"] * 0.5 * hip_scale + clearance) * width_scale
        length = float(dims.get("lengthCm", h * 0.575 * 100)) / 100
        hem_y = h * 0.62 - length
        if not h * 0.015 <= hem_y < h * 0.35:
            raise PipelineError(
                "garment_dimensions",
                "Trouser length is outside the supported ankle-to-below-knee range for this height.",
            )
        pieces.append(
            ring_surface(
                [[0, v, 0] for v in y],
                [[width * (0.90 + 0.10 * np.sin(i / 11 * np.pi)), width * 0.76] for i in range(12)],
            )
        )
        for side in ("left", "right"):
            joints = body.landmarks[side]
            start, end = np.array(joints["ankle"]), np.array(joints["hip"])
            start[1] = hem_y
            end[1] = h * 0.515
            centers = [start * (1 - t) + end * t for t in np.linspace(0, 1, 22)]
            radii = [
                (h * 0.03 + clearance) * (1 - t) + (shape["hipWidthM"] * 0.247 + clearance) * t
                for t in np.linspace(0, 1, 22)
            ]
            pieces.append(
                ring_surface(
                    centers,
                    [
                        [r * hip_scale * width_scale, r * 0.95 * hip_scale * width_scale]
                        for r in radii
                    ],
                )
            )
    else:
        shoulder_y = h * 0.819
        default_length = h * (
            0.60 if category == "dress" else np.clip(0.30 + 0.075 * silhouette_ratio, 0.33, 0.43)
        )
        length = float(dims.get("lengthCm", default_length * 100)) / 100
        hem_y = shoulder_y - length
        if not h * 0.03 < hem_y < h * 0.73:
            raise PipelineError(
                "garment_dimensions",
                "Garment length cannot be represented above the floor and below the chest for this height.",
            )
        ys = np.linspace(hem_y, shoulder_y, 24)
        centers, radii = [], []
        for y in ys:
            width = float(
                np.interp(
                    y / h,
                    [0.45, 0.54, 0.62, 0.72, 0.819],
                    [
                        shape["hipWidthM"] * 0.51,
                        shape["hipWidthM"] * 0.51,
                        shape["waistWidthM"] * 0.52,
                        shape["chestWidthM"] * 0.53,
                        measurements["shoulderWidth"] / 200,
                    ],
                )
            )
            if category == "dress" and y < h * 0.54:
                width += (h * 0.54 - y) * 0.32
            width = width * chest_scale + clearance
            if "widthCm" in dims:
                width *= dims["widthCm"] / max(shape["chestWidthM"] * 100, 1)
            centers.append([0, y, 0])
            radii.append([width, width * 0.72])
        # Sloping shoulders end at an actual open neckline.
        centers.extend([[0, h * 0.831, 0], [0, h * 0.842, 0]])
        radii.extend([[h * 0.088, h * 0.065], [h * 0.052 + clearance, h * 0.049 + clearance]])
        pieces.append(ring_surface(centers, radii))
        if category in ("t-shirt", "shirt", "dress"):
            for side in ("left", "right"):
                joints = body.landmarks[side]
                shoulder, elbow, wrist = [
                    np.array(joints[k]) for k in ("shoulder", "elbow", "wrist")
                ]
                if category != "shirt":
                    sleeve_fraction = 0.45 if category == "dress" else 0.70
                    end = (1 - sleeve_fraction) * shoulder + sleeve_fraction * elbow
                    centers = [end * (1 - t) + shoulder * t for t in np.linspace(0, 1, 10)]
                    radius = [h * 0.034 + clearance + t * h * 0.010 for t in np.linspace(0, 1, 10)]
                else:
                    centers = [wrist * (1 - t) + elbow * t for t in np.linspace(0.08, 1, 10)] + [
                        elbow * (1 - t) + shoulder * t for t in np.linspace(0.1, 1, 10)
                    ]
                    radius = list(
                        np.linspace(h * 0.024 + clearance, h * 0.046 + clearance, len(centers))
                    )
                pieces.append(ring_surface(centers, [[r, r] for r in radius]))
    # Join overlapping sleeve/pelvis volumes first. Leaving their internal faces in the
    # garment would cause surface projection to create spikes at shoulder/crotch seams.
    try:
        mesh = (
            trimesh.boolean.union(pieces, engine="manifold")
            if len(pieces) > 1
            else pieces[0].copy()
        )
    except (ValueError, RuntimeError) as exc:
        raise PipelineError(
            "template_union_failed", "Garment template could not be joined into a valid surface."
        ) from exc
    centers_of_faces = mesh.triangles_center
    keep = np.ones(len(mesh.faces), dtype=bool)
    for index, piece in enumerate(pieces):
        openings = piece.metadata["openings"]
        if index == 0 and category == "trouser":
            openings = openings[1:]  # waist only; crotch is a sewn surface
        elif index > 0:
            openings = openings[:1]  # cuffs only; roots join torso/pelvis
        for opening in openings:
            delta = centers_of_faces - opening["center"]
            cap = (np.abs(delta @ opening["normal"]) < 1e-6) & (
                np.linalg.norm(delta, axis=1) < opening["radius"]
            )
            keep &= ~cap
    mesh.update_faces(keep)
    mesh.remove_unreferenced_vertices()
    top_y = mesh.bounds[1, 1]
    uv = np.empty((len(mesh.vertices), 2))
    width = max(mesh.extents[0], 0.01)
    uv[:, 0] = np.clip(0.5 + mesh.vertices[:, 0] / width, 0.04, 0.96)
    uv[:, 1] = np.clip(
        (mesh.vertices[:, 1] - mesh.bounds[0, 1]) / max(mesh.extents[1], 0.01), 0.02, 0.98
    )
    material = PBRMaterial(
        name=f"{category}-photo-texture",
        baseColorTexture=texture_from_crop(features),
        metallicFactor=0.0,
        roughnessFactor=0.95,
        doubleSided=True,
    )
    mesh.visual = TextureVisuals(uv=uv, material=material)
    edges, counts = np.unique(np.sort(mesh.edges, axis=1), axis=0, return_counts=True)
    boundary = np.unique(edges[counts == 1])
    pinned = np.zeros(len(mesh.vertices), dtype=bool)
    pinned[boundary] = True
    pinned |= mesh.vertices[:, 1] > top_y - 0.015
    return GarmentResult(
        mesh,
        {
            "template": category,
            "version": "joined-loft-v2",
            "silhouetteAspectRatio": round(silhouette_ratio, 4),
            "lengthM": length,
            "selectedSize": selected_size["sizeLabel"],
            "fit": fit,
            "clearanceM": clearance,
            "textureMethod": "front image projected UV; unseen back repeats front fabric",
            "inputDimensionsCm": dims,
            "isPhysicalClothSimulation": False,
        },
        pinned,
    )
