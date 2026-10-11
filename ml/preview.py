"""Dependency-light orthographic mesh previews for reproducible visual inspection."""

from pathlib import Path

import numpy as np
import trimesh
from PIL import Image, ImageDraw


def render_preview(meshes: list[trimesh.Trimesh], output: Path, view="front") -> None:
    image = Image.new("RGB", (640, 800), (238, 239, 231))
    draw = ImageDraw.Draw(image)
    angle = {"front": 0, "side": np.pi / 2, "back": np.pi}[view]
    rotation = trimesh.transformations.rotation_matrix(angle, [0, 1, 0])[:3, :3]
    height = max(m.bounds[1, 1] for m in meshes)
    scale = 690 / height
    polygons = []
    for i, mesh in enumerate(meshes):
        v = mesh.vertices @ rotation.T
        normal = mesh.face_normals @ rotation.T
        light = np.array([-0.4, 0.6, 0.7])
        colors = np.array([187, 167, 145]) if i == 0 else np.array([67, 106, 104])
        if (
            i > 0
            and hasattr(mesh.visual, "material")
            and getattr(mesh.visual.material, "baseColorTexture", None) is not None
        ):
            colors = (
                np.asarray(mesh.visual.material.baseColorTexture.convert("RGB"))
                .reshape(-1, 3)
                .mean(axis=0)
            )
        for face, n in zip(mesh.faces, normal):
            points = v[face]
            if n[2] < 0:
                continue
            shading = np.clip(0.65 + 0.35 * np.dot(n, light), 0.35, 1)
            color = tuple((colors * shading).astype(int))
            polygon = [(float(p[0] * scale + 320), float(745 - p[1] * scale)) for p in points]
            polygons.append((points[:, 2].mean(), polygon, color))
    draw.ellipse((200, 724, 440, 765), fill=(213, 216, 204))
    for _, polygon, color in sorted(polygons, key=lambda x: x[0]):
        draw.polygon(polygon, fill=color)
    draw.text((24, 24), f"FORM / FIT  -  {view.upper()}", fill=(52, 68, 54))
    draw.text(
        (24, 774), "Approximate template geometry - not validated anthropometry", fill=(80, 89, 76)
    )
    image.save(output)
