"""Transport/preservation contracts. Synthetic fixtures do not assess model quality."""
import base64
import io
import json
from pathlib import Path

import httpx
import numpy as np
import pytest
from PIL import Image
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.app.db import Base
from backend.app.models import Run
from backend.app.online_vton import OnlineTryOn, normalized_image
from backend.app.pipeline import TryOnPipeline
from backend.app.storage import AssetStore
from ml.errors import PipelineError
from ml.vton.categories import MODEL_CATEGORIES
from ml.vton.online_composite import preserve_regions


def png(color="blue"):
    buffer = io.BytesIO()
    Image.new("RGB", (128, 160), color).save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.mark.parametrize("category,mapped", MODEL_CATEGORIES.items())
def test_actual_upload_category_and_remote_image_are_used(tmp_path, category, mapped):
    requests = []
    def transport(request):
        requests.append(request)
        if request.method == "POST":
            payload = json.loads(request.content)["data"]
            assert payload[0] == "x" * 32
            assert base64.b64decode(payload[1]) == normalized_image(png())
            assert base64.b64decode(payload[2]) == normalized_image(png("red"))
            assert payload[3:5] == [mapped, "flat-lay"]
            return httpx.Response(200, json={"event_id": "a" * 32})
        result = {"model": "FASHN VTON 1.5", "device": "cuda", "image": base64.b64encode(png("green")).decode()}
        return httpx.Response(200, text="event: heartbeat\ndata: null\n\nevent: complete\ndata: " + json.dumps([result]) + "\n\n")
    worker = OnlineTryOn("https://private.gradio.live", "x" * 32, transport=httpx.MockTransport(transport))
    result = worker.render(png(), png("red"), category, "flat-lay", tmp_path)
    assert (tmp_path / "tryon-2d.png").read_bytes() == png("green")
    assert result["remoteRoundTripSeconds"] >= 0
    assert len(requests) == 2
    assert "image" not in json.loads((tmp_path / "vton-diagnostics.json").read_text())


def test_missing_cloud_config_fails_without_local_fallback(tmp_path):
    worker = OnlineTryOn("", "")
    assert not worker.availability()["available"]
    with pytest.raises(PipelineError, match="Local GPU inference is disabled"):
        worker.render(png(), png(), "dress", "flat-lay", tmp_path)
    assert not list(tmp_path.iterdir())


def test_rotating_connection_does_not_retarget_an_inflight_generation(tmp_path):
    hosts = []
    worker = None
    def handle(request):
        hosts.append(request.url.host)
        if request.method == 'POST':
            # Simulate the monitor adopting a new worker during the old event.
            worker.url = 'https://new.gradio.live'
            worker.token = 'y' * 32
            return httpx.Response(200, json={'event_id': 'a'})
        result = {'model': 'FASHN VTON 1.5', 'device': 'cuda',
                  'image': base64.b64encode(png()).decode()}
        return httpx.Response(200, text='event: complete\ndata: ' + json.dumps([result]) + '\n\n')
    worker = OnlineTryOn('https://original.gradio.live', 'x' * 32,
                         transport=httpx.MockTransport(handle))
    worker.render(png(), png(), 'shirt', 'flat-lay', tmp_path)
    assert hosts == ['original.gradio.live', 'original.gradio.live']


@pytest.mark.parametrize("reply", ["event: error\ndata: null\n\n", "event: complete\ndata: [{}]\n\n"])
def test_bad_worker_response_is_not_success_or_retry(tmp_path, reply):
    calls = []
    def handle(request):
        calls.append(request.method)
        return httpx.Response(200, json={"event_id": "a"}) if request.method == "POST" else httpx.Response(200, text=reply)
    worker = OnlineTryOn("https://private.gradio.live", "x" * 32, transport=httpx.MockTransport(handle))
    with pytest.raises(PipelineError):
        worker.render(png(), png(), "dress", "model", tmp_path)
    assert calls == ["POST", "GET"]
    assert not (tmp_path / "tryon-2d.png").exists()
    assert (tmp_path / "remote-event.json").is_file()


def test_upload_normalization_rejects_invalid_data_and_flattens_transparency():
    with pytest.raises(PipelineError):
        normalized_image(b"not an image")
    buffer = io.BytesIO()
    Image.new("RGBA", (128, 128), (0, 0, 0, 0)).save(buffer, format="PNG")
    assert Image.open(io.BytesIO(normalized_image(buffer.getvalue()))).getpixel((0, 0)) == (255, 255, 255)


@pytest.mark.parametrize("category,old_label,new_label", [("tops", 3, 3), ("bottoms", 6, 5), ("one-pieces", 3, 4)])
def test_clothing_replacement_preserves_face_hands_and_unrelated_pixels(category, old_label, new_label):
    source = np.zeros((100, 80), dtype=np.uint8)
    source[5:20, 30:50] = 1
    source[25:80, 25:55] = old_label
    source[40:50, 20:25] = 13
    target = source.copy()
    target[25:85, 24:56] = new_label
    original = np.full((100, 80, 3), 180, dtype=np.uint8)
    generated = np.full_like(original, 40)
    image, alpha, report = preserve_regions(original, generated, source, target, category)
    assert np.all(alpha[source == old_label] == 1)
    assert np.array_equal(image[source == 1], original[source == 1])
    assert np.array_equal(image[source == 13], original[source == 13])
    assert np.array_equal(image[alpha == 0], original[alpha == 0])
    assert report["identityPreservedExactly"]


def test_failed_remote_job_is_persisted_without_success(tmp_path):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    pipeline = TryOnPipeline(AssetStore(tmp_path), OnlineTryOn("", ""))
    with Session(engine) as db:
        with pytest.raises(PipelineError):
            pipeline.run(db, png(), png(), None, "dress")
        record = db.scalar(select(Run))
        assert record.status == "failed"
        assert (tmp_path / record.id / "failure.json").exists()
        assert not (tmp_path / record.id / "result.json").exists()
    engine.dispose()


def test_application_import_does_not_load_local_ml_runtime():
    import subprocess
    import sys
    command = "import backend.app.main,sys; assert 'torch' not in sys.modules; assert 'mediapipe' not in sys.modules"
    subprocess.run([sys.executable, "-c", command], cwd=Path(__file__).resolve().parents[1], check=True)
