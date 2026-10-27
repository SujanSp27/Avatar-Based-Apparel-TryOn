"""Transport/preservation contracts. Synthetic fixtures do not assess model quality."""
import base64
import io
import json
from pathlib import Path
from unittest.mock import Mock

import httpx
import numpy as np
import pytest
from PIL import Image
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.db import Base
from backend.app.models import Run
from backend.app.online_vton import (
    OnlineTryOn,
    conditioning_image,
    normalized_image,
    transport_image,
)
from backend.app.pipeline import TryOnPipeline
from backend.app.storage import AssetStore
from ml.errors import PipelineError
from ml.vton.categories import MODEL_CATEGORIES
from ml.vton.image_transport import encode_changed_pixels
from ml.vton.online_composite import preserve_regions


def png(color="blue"):
    buffer = io.BytesIO()
    Image.new("RGB", (128, 160), color).save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture(autouse=True)
def lossless_legacy_transport(monkeypatch):
    # Exercise compatibility independently of the application's JPEG preset.
    # JPEG-specific tests override this and require exact changed-pixel output.
    monkeypatch.setattr(settings, "online_vton_input_encoding", "lossless")


@pytest.mark.parametrize("category,mapped", MODEL_CATEGORIES.items())
@pytest.mark.parametrize("json_text", [False, True])
def test_actual_upload_category_and_remote_image_are_used(tmp_path, category, mapped, json_text):
    requests = []
    def transport(request):
        requests.append(request)
        if request.method == "POST":
            payload = json.loads(request.content)["data"]
            assert payload[0] == "x" * 32
            assert Image.open(io.BytesIO(base64.b64decode(payload[1]))).tobytes() == Image.open(io.BytesIO(normalized_image(png()))).tobytes()
            assert Image.open(io.BytesIO(base64.b64decode(payload[2]))).tobytes() == Image.open(io.BytesIO(normalized_image(png("red")))).tobytes()
            assert payload[3:5] == [mapped, "flat-lay"]
            return httpx.Response(200, json={"event_id": "a" * 32})
        result = {"model": "FASHN VTON 1.5", "device": "cuda", "image": base64.b64encode(png("green")).decode()}
        if json_text:
            result = json.dumps(result)
        return httpx.Response(200, text="event: heartbeat\ndata: null\n\nevent: complete\ndata: " + json.dumps([result]) + "\n\n")
    worker = OnlineTryOn("https://private.gradio.live", "x" * 32, transport=httpx.MockTransport(transport))
    result = worker.render(png(), png("red"), category, "flat-lay", tmp_path)
    assert (tmp_path / "tryon-2d.png").read_bytes() == png("green")
    assert result["remoteRoundTripSeconds"] >= 0
    assert result["transport"]["uploadedImageBytes"] <= result["transport"]["normalizedInputBytes"]
    assert result["transport"]["downloadedImageBytes"] == len(png("green"))
    assert len(requests) == 2
    assert "image" not in json.loads((tmp_path / "vton-diagnostics.json").read_text())


def test_missing_cloud_config_fails_without_local_fallback(tmp_path):
    worker = OnlineTryOn("", "")
    assert not worker.availability()["available"]
    with pytest.raises(PipelineError, match="Local GPU inference is disabled"):
        worker.render(png(), png(), "dress", "flat-lay", tmp_path)
    assert not list(tmp_path.iterdir())


def test_stream_interruption_recovers_same_event_without_another_generation(tmp_path, monkeypatch):
    monkeypatch.setattr('backend.app.online_vton.time.sleep', lambda _: None)
    calls = []
    def transport(request):
        calls.append((request.method, str(request.url)))
        if request.method == 'POST':
            return httpx.Response(200, json={'event_id': 'sameevent'})
        if len(calls) == 2:
            raise httpx.RemoteProtocolError('lost connection')
        result = {'model': 'FASHN VTON 1.5', 'device': 'cuda',
                  'image': base64.b64encode(png('green')).decode()}
        return httpx.Response(200, text='event: complete\ndata: ' + json.dumps([result]) + '\n\n')
    worker = OnlineTryOn('https://private.gradio.live', 'x' * 48, transport=httpx.MockTransport(transport))
    worker.render(png(), png('red'), 't-shirt', 'flat-lay', tmp_path)
    assert [call[0] for call in calls] == ['POST', 'GET', 'GET']
    assert calls[1] == calls[2]
    assert (tmp_path / 'tryon-2d.png').read_bytes() == png('green')


def test_stream_retry_exhaustion_retains_event_without_fake_result(tmp_path, monkeypatch):
    monkeypatch.setattr('backend.app.online_vton.time.sleep', lambda _: None)
    calls = []
    def transport(request):
        calls.append(request.method)
        if request.method == 'POST':
            return httpx.Response(200, json={'event_id': 'preserved'})
        raise httpx.ReadTimeout('offline worker')
    worker = OnlineTryOn('https://private.gradio.live', 'x' * 48, transport=httpx.MockTransport(transport))
    with pytest.raises(PipelineError) as error:
        worker.render(png(), png(), 't-shirt', 'flat-lay', tmp_path)
    assert error.value.status_code == 504
    assert calls == ['POST', 'GET', 'GET', 'GET']
    assert json.loads((tmp_path / 'remote-event.json').read_text())['eventId'] == 'preserved'
    assert not (tmp_path / 'tryon-2d.png').exists()


def test_lossless_webp_response_is_saved_as_actual_png_without_pixel_changes(tmp_path):
    pixels = np.random.default_rng(11).integers(0, 256, (160, 128, 3), dtype=np.uint8)
    buffer = io.BytesIO()
    Image.fromarray(pixels).save(buffer, format="WEBP", lossless=True, quality=0, method=0)
    def handle(request):
        if request.method == "POST":
            return httpx.Response(200, json={"event_id": "b"})
        payload = {"model": "FASHN VTON 1.5", "device": "cuda", "imageFormat": "webp",
                   "image": base64.b64encode(buffer.getvalue()).decode()}
        return httpx.Response(200, text="event: complete\ndata: " + json.dumps([payload]) + "\n\n")
    worker = OnlineTryOn("https://private.gradio.live", "x" * 32, transport=httpx.MockTransport(handle))
    worker.render(png(), png(), "t-shirt", "flat-lay", tmp_path)
    with Image.open(tmp_path / "tryon-2d.png") as saved:
        assert saved.format == "PNG"
        np.testing.assert_array_equal(np.asarray(saved), pixels)


def test_patch_response_preserves_original_pixels_and_reconstructs_actual_image(tmp_path):
    original = Image.open(io.BytesIO(png()))
    expected = original.copy()
    expected.paste((220, 40, 50), (35, 50, 90, 100))
    encoded, metadata = encode_changed_pixels(original, expected)
    def handle(request):
        if request.method == "POST":
            return httpx.Response(200, json={"event_id": "c"})
        payload = {"model": "FASHN VTON 1.5", "device": "cuda", "imageFormat": "webp",
                   **metadata, "image": base64.b64encode(encoded).decode()}
        return httpx.Response(200, text="event: complete\ndata: " + json.dumps([payload]) + "\n\n")
    worker = OnlineTryOn("https://private.gradio.live", "x" * 32, transport=httpx.MockTransport(handle))
    worker.render(png(), png(), "t-shirt", "flat-lay", tmp_path)
    with Image.open(tmp_path / "tryon-2d.png") as saved:
        assert saved.format == "PNG"
        assert saved.tobytes() == expected.tobytes()


def test_compressed_conditioning_keeps_original_face_and_background_exact(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "online_vton_input_encoding", "jpeg95")
    pixels = np.random.default_rng(57).integers(0, 256, (160, 128, 3), dtype=np.uint8)
    source = Image.fromarray(pixels)
    buffer = io.BytesIO()
    source.save(buffer, format="PNG")
    payload = {}
    def handle(request):
        if request.method == "POST":
            image_bytes = base64.b64decode(json.loads(request.content)["data"][1])
            received = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            assert received.size == source.size
            assert received.tobytes() != source.tobytes()  # Explicitly lossy input.
            generated = received.copy()
            generated.paste((200, 30, 50), (30, 60, 90, 110))
            encoded, metadata = encode_changed_pixels(received, generated)
            payload.update(model="FASHN VTON 1.5", device="cuda", imageFormat="webp",
                           image=base64.b64encode(encoded).decode(), **metadata)
            return httpx.Response(200, json={"event_id": "d"})
        return httpx.Response(200, text="event: complete\ndata: " + json.dumps([payload]) + "\n\n")
    worker = OnlineTryOn("https://private.gradio.live", "x" * 32, transport=httpx.MockTransport(handle))
    result = worker.render(buffer.getvalue(), png(), "t-shirt", "flat-lay", tmp_path)
    expected = source.copy()
    expected.paste((200, 30, 50), (30, 60, 90, 110))
    assert Image.open(tmp_path / "tryon-2d.png").tobytes() == expected.tobytes()
    assert result["transport"]["inputEncoding"] == "jpeg95"


def test_compressed_input_rejects_legacy_full_frame_response(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "online_vton_input_encoding", "jpeg95")
    def handle(request):
        if request.method == "POST":
            return httpx.Response(200, json={"event_id": "e"})
        payload = {"model": "FASHN VTON 1.5", "device": "cuda", "image": base64.b64encode(png()).decode()}
        return httpx.Response(200, text="event: complete\ndata: " + json.dumps([payload]) + "\n\n")
    worker = OnlineTryOn("https://private.gradio.live", "x" * 32, transport=httpx.MockTransport(handle))
    with pytest.raises(PipelineError):
        worker.render(png(), png(), "t-shirt", "flat-lay", tmp_path)
    assert not (tmp_path / "tryon-2d.png").exists()


def test_compressed_conditioning_keeps_small_flat_graphics_lossless():
    source = png()
    assert conditioning_image(source, "jpeg95") == transport_image(source)
    with pytest.raises(ValueError):
        conditioning_image(source, "unrecognized")


@pytest.mark.parametrize('code', ['garment_length_changed', 'garment_reference_mismatch',
                                 'coverage_change_too_large'])
def test_rejected_run_keeps_artifact_address_without_an_image_or_credentials(tmp_path, code):
    run_path = "/content/formfit-online/runs/123456789"
    def handle(request):
        if request.method == "POST":
            return httpx.Response(200, json={"event_id": "f"})
        payload = {"error": "The generated top is distorted", "code": code,
                   "runPath": run_path, "workerSeconds": 13.2,
                   "token": "must-not-be-persisted", "image": base64.b64encode(png()).decode()}
        return httpx.Response(200, text="event: complete\ndata: " + json.dumps([payload]) + "\n\n")
    worker = OnlineTryOn("https://private.gradio.live", "x" * 32, transport=httpx.MockTransport(handle))
    with pytest.raises(PipelineError) as failure:
        worker.render(png(), png(), "t-shirt", "flat-lay", tmp_path)
    assert failure.value.code == code
    recorded = json.loads((tmp_path / "remote-failure.json").read_text())
    assert recorded["runPath"] == run_path
    assert recorded["workerSeconds"] == 13.2
    assert "token" not in recorded and "image" not in recorded
    assert not (tmp_path / "tryon-2d.png").exists()


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


@pytest.mark.parametrize("reply", ["event: error\ndata: null\n\n", "event: complete\ndata: [{}]\n\n", "event: complete\ndata: [null]\n\n"])
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


@pytest.mark.parametrize("image_format", [None, 42, [], "jpeg", "webp"])
def test_invalid_or_mismatched_image_format_is_a_meaningful_failure(tmp_path, image_format):
    methods = []
    def handle(request):
        methods.append(request.method)
        if request.method == "POST":
            return httpx.Response(200, json={"event_id": "a"})
        payload = {"model": "FASHN VTON 1.5", "device": "cuda", "imageFormat": image_format,
                   "image": base64.b64encode(png()).decode()}
        return httpx.Response(200, text="event: complete\ndata: " + json.dumps([payload]) + "\n\n")
    worker = OnlineTryOn("https://private.gradio.live", "x" * 32, transport=httpx.MockTransport(handle))
    with pytest.raises(PipelineError) as failure:
        worker.render(png(), png(), "t-shirt", "flat-lay", tmp_path)
    assert failure.value.code == "online_gpu_connection"
    assert methods == ["POST", "GET"]
    assert (tmp_path / "remote-event.json").is_file()
    assert not (tmp_path / "tryon-2d.png").exists()


def test_upload_normalization_rejects_invalid_data_and_flattens_transparency():
    with pytest.raises(PipelineError):
        normalized_image(b"not an image")
    buffer = io.BytesIO()
    Image.new("RGBA", (128, 128), (0, 0, 0, 0)).save(buffer, format="PNG")
    assert Image.open(io.BytesIO(normalized_image(buffer.getvalue()))).getpixel((0, 0)) == (255, 255, 255)


def test_wide_gamut_photo_is_converted_before_profile_is_stripped():
    profile = (Path(__file__).parent / "fixtures/prophoto-rgb.icc").read_bytes()
    source = Image.new("RGB", (128, 160), (100, 80, 60))
    buffer = io.BytesIO()
    source.save(buffer, format="PNG", icc_profile=profile)
    with Image.open(io.BytesIO(normalized_image(buffer.getvalue()))) as normalized:
        # Reference conversion of these ProPhoto samples to sRGB via LittleCMS.
        assert normalized.getpixel((0, 0)) == (140, 93, 72)
        assert "icc_profile" not in normalized.info
        assert normalized.size == source.size


def test_profile_conversion_retains_transparent_background_compositing():
    profile = (Path(__file__).parent / "fixtures/prophoto-rgb.icc").read_bytes()
    source = Image.new("RGBA", (128, 160), (100, 80, 60, 0))
    source.putpixel((64, 80), (100, 80, 60, 255))
    buffer = io.BytesIO()
    source.save(buffer, format="PNG", icc_profile=profile)
    with Image.open(io.BytesIO(normalized_image(buffer.getvalue()))) as normalized:
        assert normalized.getpixel((0, 0)) == (255, 255, 255)
        assert normalized.getpixel((64, 80)) == (140, 93, 72)


def test_invalid_colour_profile_is_reported_as_input_error():
    buffer = io.BytesIO()
    Image.new("RGB", (128, 160)).save(buffer, format="PNG", icc_profile=b"not a profile")
    with pytest.raises(PipelineError) as failure:
        normalized_image(buffer.getvalue())
    assert failure.value.code == "invalid_image"


def test_transport_compression_preserves_sanitized_pixels_exactly():
    pixels = np.random.default_rng(41).integers(0, 256, (240, 160, 3), dtype=np.uint8)
    buffer = io.BytesIO()
    Image.fromarray(pixels).save(buffer, format="PNG")
    clean = normalized_image(buffer.getvalue())
    encoded = transport_image(clean)
    assert len(encoded) <= len(clean)
    np.testing.assert_array_equal(np.asarray(Image.open(io.BytesIO(encoded)).convert("RGB")), pixels)


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


def test_successful_remote_job_persists_result_and_artifacts(tmp_path):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    worker = Mock()

    def fake_render(person, garment, category, photo_type, folder):
        (folder / "original-person.png").write_bytes(person)
        (folder / "garment-reference.png").write_bytes(normalized_image(garment))
        (folder / "tryon-2d.png").write_bytes(garment)
        (folder / "vton-diagnostics.json").write_text("{}")
        return {"remoteRoundTripSeconds": 1.2, "inferenceSeconds": 1.0}

    worker.render = fake_render
    pipeline = TryOnPipeline(AssetStore(tmp_path), worker)
    with Session(engine) as db:
        result = pipeline.run(db, png(), png("green"), None, "t-shirt")
        assert result["status"] == "success"
        record = db.scalar(select(Run))
        assert record.status == "success"
        assert (tmp_path / record.id / "result.json").exists()
        assert result["artifacts"]["result"] == f"/assets/{record.id}/result.json"
        assert result["previewUrl"] == f"/assets/{record.id}/tryon-2d.png"
        assert result["garmentUrl"] == f"/assets/{record.id}/garment-reference.png"
    engine.dispose()


def test_application_import_does_not_load_local_ml_runtime():
    import subprocess
    import sys
    command = "import backend.app.main,sys; assert 'torch' not in sys.modules; assert 'mediapipe' not in sys.modules"
    subprocess.run([sys.executable, "-c", command], cwd=Path(__file__).resolve().parents[1], check=True)
