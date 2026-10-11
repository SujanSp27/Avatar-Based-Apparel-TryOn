import io

import numpy as np
import pytest
import trimesh
from PIL import Image

from ml.errors import PipelineError
from ml.fitting.service import project_outside
from ml.human.template import validate_mesh
from ml.measurement.service import measure_body, perimeter, section_loops
from ml.preprocessing.images import decode_image, preprocess_garment


def test_cross_section_matches_known_ellipse():
    mesh = trimesh.creation.icosphere(subdivisions=4)
    mesh.apply_scale([0.20, 0.80, 0.14])
    loop = section_loops(mesh, 0)[0]
    a, b = 0.20, 0.14
    expected = np.pi * (3 * (a + b) - np.sqrt((3 * a + b) * (a + 3 * b)))
    assert abs(perimeter(loop) - expected) < 0.003


def test_collision_projection_uses_real_body_surface():
    mesh = trimesh.creation.icosphere(subdivisions=3, radius=0.5)
    points = np.array([[0.48, 0, 0], [0, 0.2, 0.1], [0.8, 0, 0]])
    projected, count = project_outside(mesh, points, 0.01)
    assert count >= 2
    assert (trimesh.proximity.signed_distance(mesh, projected) < -0.009).all()
    assert np.array_equal(projected[2], points[2])


def test_invalid_mesh_stops_measurements():
    with pytest.raises(PipelineError, match="invalid body mesh"):
        validate_mesh(trimesh.creation.box())


@pytest.mark.integration
def test_image_mesh_measurement_milestones(body):
    assert validate_mesh(body.mesh)["watertight"]
    assert len(body.mesh.split()) == 1
    result = measure_body(body.mesh, body.landmarks)
    assert result["height"] == 172.0
    assert 65 < result["chest"] < 115  # Regression: connected arms yielded >150 cm.
    assert 30 < result["shoulderWidth"] < 55
    assert result["confidence"] is None
    restored = trimesh.load(
        io.BytesIO(body.mesh.export(file_type="glb")), file_type="glb", force="scene"
    )
    assert len(restored.geometry) == 1


def test_bad_inputs_rejected():
    with pytest.raises(PipelineError, match="decoded"):
        decode_image(b"not an image")
    data = io.BytesIO()
    Image.new("RGB", (64, 64)).save(data, format="PNG")
    with pytest.raises(PipelineError, match="256"):
        decode_image(data.getvalue())
    data = io.BytesIO()
    Image.new("RGB", (512, 512), "white").save(data, format="PNG")
    with pytest.raises(PipelineError, match="garment"):
        preprocess_garment(data.getvalue())
