"""Worker lifecycle and duplicate protection without loading a neural model."""

import time
from threading import BoundedSemaphore, Event
from uuid import uuid4

import pytest

from backend.app.jobs import TryOnJobs
from ml.errors import PipelineError
from ml.progress import report_progress
from scripts.colab_server import notebook_path


@pytest.fixture
def worker(tmp_path):
    value = TryOnJobs(tmp_path / "jobs", BoundedSemaphore(1))
    yield value
    value.close()


def finish(worker, job_id):
    deadline = time.monotonic() + 4
    while time.monotonic() < deadline:
        state = worker.get(job_id)
        if state["status"] in {"success", "failed"}:
            return state
        time.sleep(0.01)
    pytest.fail("Controlled worker did not finish")


def test_duplicate_submission_does_not_start_two_model_runs(worker):
    entered, release = Event(), Event()
    calls = []
    def work():
        calls.append(True)
        report_progress("generating", 7, 50)
        entered.set()
        assert release.wait(3)
        return {"status": "success", "runId": "actual-result"}
    key = str(uuid4())
    first = worker.submit(b"person", b"garment", {"mode": "2d"}, work, key)
    try:
        assert entered.wait(2)
        same = worker.submit(b"person", b"garment", {"mode": "2d"}, work, key)
        assert same["jobId"] == first["jobId"]
        assert same["progress"]["completed"] == 7
        assert "requestHash" not in same
        with pytest.raises(PipelineError) as error:
            worker.submit(b"other", b"garment", {}, work)
        assert error.value.code == "busy"
        with pytest.raises(PipelineError) as error:
            worker.submit(b"different", b"garment", {"mode": "2d"}, work, key)
        assert error.value.code == "job_key_conflict"
    finally:
        release.set()
    done = finish(worker, key)
    assert done["result"]["runId"] == "actual-result"
    assert worker.submit(b"person", b"garment", {"mode": "2d"}, work, key)["status"] == "success"
    assert len(calls) == 1


def test_failure_releases_capacity_and_preserves_the_real_error(worker):
    def fail():
        raise PipelineError("vton_garment_fidelity_failed", "The uploaded stripes were lost.")
    job = worker.submit(b"p", b"g", {}, fail)
    failed = finish(worker, job["jobId"])
    assert failed["error"]["code"] == "vton_garment_fidelity_failed"
    assert "result" not in failed
    next_job = worker.submit(b"p2", b"g", {}, lambda: {"status": "success"})
    assert finish(worker, next_job["jobId"])["status"] == "success"


def test_restart_does_not_rerun_abandoned_work(worker):
    key = str(uuid4())
    worker._save({"jobId": key, "requestHash": "unused", "status": "processing", "createdAt": 1})
    worker.recover_interrupted()
    assert worker.get(key)["status"] == "failed"
    assert worker.get(key)["error"]["code"] == "job_interrupted"


@pytest.mark.parametrize("content", ["{truncated", "[]", '{"status":"processing"}'])
def test_corrupt_job_is_preserved_without_blocking_startup(worker, content):
    corrupt_id, valid_id = str(uuid4()), str(uuid4())
    worker.directory.mkdir(parents=True, exist_ok=True)
    path = worker._path(corrupt_id)
    path.write_text(content)
    worker._save({"jobId": valid_id, "requestHash": "original", "status": "processing", "createdAt": 1})
    worker.recover_interrupted()
    assert path.read_text() == content
    assert worker.get(valid_id)["error"]["code"] == "job_interrupted"
    with pytest.raises(PipelineError) as error:
        worker.get(corrupt_id)
    assert error.value.status_code == 503 and error.value.code == "job_record_unavailable"
    with pytest.raises(PipelineError):
        worker.submit(b"p", b"g", {}, lambda: pytest.fail("Never replay corrupt jobs"), key=corrupt_id)
    new = worker.submit(b"new", b"g", {}, lambda: {"status": "success"})
    assert finish(worker, new["jobId"])["status"] == "success"


def test_async_api_acknowledges_and_returns_saved_result(worker, monkeypatch):
    from fastapi.testclient import TestClient

    from backend.app import main

    monkeypatch.setattr(main, "jobs", worker)
    monkeypatch.setattr(main, "latest_chart", lambda *args: None)
    calls = []
    def work(*args, **kwargs):
        calls.append(True)
        return {"status": "success", "mode": "2d", "renderingMethod": "pretrained-vton"}
    monkeypatch.setattr(main.pipeline, "run", work)
    key = str(uuid4())
    client = TestClient(main.app, raise_server_exceptions=True)
    try:
        options = {
            "data": {"garmentCategory": "t-shirt", "tryonMode": "2d"},
            "files": {"personImage": ("p.png", b"p"), "garmentImage": ("g.png", b"g")},
            "headers": {"Prefer": "respond-async", "Idempotency-Key": key},
        }
        response = client.post("/api/tryon", **options)
        assert response.status_code == 202
        assert response.headers["location"] == f"/api/tryon/jobs/{key}"
        finish(worker, key)
        assert client.get(response.headers["location"]).json()["result"]["renderingMethod"] == "pretrained-vton"
        assert client.post("/api/tryon", **options).status_code == 202
    finally:
        client.close()
    assert len(calls) == 1


@pytest.mark.parametrize("url", ["http://colab.research.google.com/drive/12345678901", "https://example.com/drive/12345678901", "https://colab.research.google.com/notebooks/empty.ipynb", "https://colab.research.google.com/drive/12345678901#token=secret"])
def test_reconnect_cannot_open_a_scratch_notebook_or_untrusted_domain(url):
    with pytest.raises(ValueError):
        notebook_path(url)


def test_existing_notebook_url_is_used_exactly():
    assert notebook_path("https://colab.research.google.com/drive/abcdefghijk") == "/drive/abcdefghijk"
