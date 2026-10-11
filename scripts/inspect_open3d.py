"""Independent Open3D topology inspection; no GUI or licensed model required."""

import importlib.metadata
import json
from pathlib import Path

import open3d as o3d
import smplx  # noqa: F401

root = Path(__file__).resolve().parents[1]
path = root / "experiments/runs/reconstruction/studio-person/body.ply"
mesh = o3d.io.read_triangle_mesh(str(path))
report = {
    "mesh": str(path.relative_to(root)),
    "open3dVersion": o3d.__version__,
    "smplxPackageVersion": importlib.metadata.version("smplx"),
    "smplxInferenceAvailable": False,
    "vertices": len(mesh.vertices),
    "triangles": len(mesh.triangles),
    "edgeManifold": mesh.is_edge_manifold(allow_boundary_edges=False),
    "vertexManifold": mesh.is_vertex_manifold(),
    "orientable": mesh.is_orientable(),
    "selfIntersecting": mesh.is_self_intersecting(),
    "watertight": mesh.is_watertight(),
}
(root / "experiments/open3d-report.json").write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
assert report["watertight"] and report["edgeManifold"] and not report["selfIntersecting"]
