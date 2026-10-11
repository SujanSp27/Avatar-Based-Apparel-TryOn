from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from ml.errors import PipelineError
from ml.vton.service import NATIVE_SIZE, PretrainedTryOn, fit_canvas, person_window


def test_person_crop_is_bounded_and_requires_detected_head_and_clothing():
    labels = np.zeros((600, 400), dtype=np.uint8)
    labels[50:130, 160:235] = 1
    labels[130:350, 100:300] = 3
    x0, y0, x1, y1 = person_window(labels)
    assert 0 <= x0 < 100 and 300 < x1 <= 400
    assert 0 <= y0 <= 50 and 350 < y1 <= 600
    labels[labels == 1] = 0
    with pytest.raises(PipelineError, match="face and head"):
        person_window(labels)


def test_model_framing_preserves_aspect_and_mask_coordinates():
    photo = Image.new("RGB", (300, 100), "red")
    mask = Image.new("L", photo.size, 255)
    canvas, bounds = fit_canvas(photo, "white")
    mask_canvas, mask_bounds = fit_canvas(mask, 0, nearest=True)
    assert canvas.size == NATIVE_SIZE and bounds == mask_bounds
    assert bounds[2] - bounds[0] == 3 * (bounds[3] - bounds[1])
    assert np.all(np.array(mask_canvas.crop(bounds)) == 255)
    assert np.all(np.array(canvas.crop(bounds)) == [255, 0, 0])


def test_full_resolution_framing_retains_identical_photo_and_mask_bounds():
    photo = Image.new("RGB", (300, 200), "red")
    mask = Image.new("L", photo.size, 255)
    canvas, bounds = fit_canvas(photo, "white", canvas_size=(768, 1024))
    mask_canvas, mask_bounds = fit_canvas(mask, 0, nearest=True, canvas_size=(768, 1024))
    assert canvas.size == mask_canvas.size == (768, 1024)
    assert bounds == mask_bounds
    assert bounds[2] - bounds[0] == 768
    assert bounds[3] - bounds[1] == 512


def test_missing_pretrained_assets_fail_without_creating_result(tmp_path):
    service = PretrainedTryOn(tmp_path, "cpu")
    state = service.availability()
    assert state["available"] is False
    assert state["reason"]
    with pytest.raises(PipelineError) as error:
        service.render(None, b"unused", "t-shirt", tmp_path)
    assert error.value.status_code == 503
    assert not (tmp_path / "tryon-2d.png").exists()


@pytest.mark.parametrize("category", ["dress", "trouser"])
def test_untrained_categories_fail_before_model_loading(tmp_path, category):
    service = PretrainedTryOn(tmp_path)
    with pytest.raises(PipelineError) as error:
        service.render(None, b"unused", category, tmp_path)
    assert error.value.code == "vton_category"


def test_no_production_route_imports_legacy_pixel_overlay():
    root = Path(__file__).resolve().parents[1]
    for path in (root / "backend/app").glob("*.py"):
        assert "from ml.tryon2d" not in path.read_text(encoding="utf-8")
