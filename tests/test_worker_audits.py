"""Real byte-transfer/security contracts with an HTTP fixture; no GPU simulation claim."""
import json

import httpx
import pytest

from ml.vton import audit_export as export
from scripts import worker_audits as client

TOKEN, RUN, PERSON, GARMENT = "x" * 48, "1793107970270386700", "a" * 64, "b" * 64


@pytest.fixture
def completed(tmp_path):
    remote = tmp_path / "remote"
    case = remote / "runs" / RUN
    case.mkdir(parents=True)
    (case / "inputs.json").write_text(json.dumps({
        "person": {"rgbSha256": PERSON}, "garment": {"rgbSha256": GARMENT},
    }))
    (case / "report.json").write_text('{"completed": true}')
    (case / "raw.png").write_bytes(b"image bytes verified without running inference")
    (case / "private-token.txt").write_text("must never export this")
    return remote, case


def response(root):
    return export.export_audit(root, TOKEN, TOKEN, RUN, PERSON, GARMENT)


@pytest.mark.parametrize("supplied", [None, "", "wrong", 123, "\u2603" * 48])
def test_authentication_precedes_path_or_existence_disclosure(tmp_path, supplied):
    assert export.export_audit(tmp_path, TOKEN, supplied, "../../secret", "", "") == {"error": "unauthorized"}


@pytest.mark.parametrize("run_id", ["../1234567890", "/content/1234567890", "12345\\67890", "12", "1" * 30, 123])
def test_only_bounded_numeric_run_ids_are_accepted(tmp_path, run_id):
    assert export.export_audit(tmp_path, TOKEN, TOKEN, run_id, PERSON, GARMENT)["error"] == "invalid_audit_request"


def test_export_requires_completed_run_and_exact_saved_input_hashes(completed):
    root, case = completed
    assert export.export_audit(root, TOKEN, TOKEN, RUN, "c" * 64, GARMENT)["error"] == "audit_input_mismatch"
    (case / "report.json").unlink()
    assert response(root)["error"] == "audit_not_complete"
    (case / "failure.json").write_text('{"code": "coverage_change_too_large"}')
    assert response(root)["files"]["failure.json"] is not None


def test_export_returns_only_allowlisted_bounded_files_with_hashes(completed, monkeypatch):
    root, case = completed
    payload = response(root)
    assert set(payload["files"]) == set(export.ARTIFACT_NAMES)
    assert payload["files"]["edit-mask.png"] is None
    decoded, error = client.validate_export(payload, RUN, PERSON, GARMENT)
    assert error is None
    assert decoded["raw.png"] == (case / "raw.png").read_bytes()
    monkeypatch.setattr(export, "MAX_FILE_BYTES", 4)
    assert response(root)["error"] == "audit_size_limit"


@pytest.mark.parametrize("corruption", ["hash", "bytes", "run", "filename", "base64"])
def test_client_rejects_corrupted_or_wrong_trial_export_before_writing(completed, corruption):
    root, _ = completed
    payload = response(root)
    if corruption == "hash":
        payload["files"]["raw.png"]["sha256"] = "f" * 64
    elif corruption == "bytes":
        payload["files"]["raw.png"]["bytes"] = True
    elif corruption == "run":
        payload["runId"] = "1234567890"
    elif corruption == "filename":
        payload["files"]["../../.env"] = payload["files"].pop("raw.png")
    else:
        payload["files"]["raw.png"]["base64"] = "invalid***"
    with pytest.raises(ValueError):
        client.validate_export(payload, RUN, PERSON, GARMENT)


def test_http_retrieval_is_authenticated_read_only_and_preserves_existing_evidence(completed, tmp_path):
    root, remote_case = completed
    connection = tmp_path / "connection.json"
    connection.write_text(json.dumps({"url": "https://private-worker.gradio.live", "token": TOKEN}))
    trial = {"diagnostics": {"runPath": "/content/formfit-online/runs/" + RUN,
        "inputAudit": {"person": {"rgbSha256": PERSON}, "garment": {"rgbSha256": GARMENT}}}}
    local = tmp_path / "local"
    local.mkdir()
    # A prior interruption after writing, before rename, resumes verified bytes.
    (local / "raw.png.partial").write_bytes((remote_case / "raw.png").read_bytes())
    calls = []

    def handler(request):
        calls.append(request.url.path)
        assert request.method == "POST" and request.url.path == "/gradio_api/run/audit"
        assert json.loads(request.content)["data"] == [TOKEN, RUN, PERSON, GARMENT]
        return httpx.Response(200, json={"data": [json.dumps(response(root))]})

    transport = httpx.MockTransport(handler)
    outcome = client.retrieve_http(local, trial, connection, transport=transport)
    assert outcome["status"] == "retrieved"
    assert "edit-mask.png" in outcome["missing"]
    assert (local / "raw.png").read_bytes() == (remote_case / "raw.png").read_bytes()
    assert not (local / "raw.png.partial").exists()
    assert not (local / "private-token.txt").exists()
    assert TOKEN not in (local / "artifact-http-retrieval.json").read_text()
    assert client.retrieve_http(local, trial, connection, transport=transport)["status"] == "retrieved"
    (local / "raw.png").write_bytes(b"different saved evidence")
    assert client.retrieve_http(local, trial, connection, transport=transport)["status"] == "unavailable"
    assert (local / "raw.png").read_bytes() == b"different saved evidence"
    assert calls == ["/gradio_api/run/audit"] * 3


def test_expired_worker_or_oversized_response_never_starts_inference(completed, tmp_path, monkeypatch):
    root, _ = completed
    connection = tmp_path / "connection.json"
    connection.write_text(json.dumps({"url": "https://private.gradio.live", "token": TOKEN}))
    trial = {"diagnostics": {"runPath": "/content/formfit-online/runs/" + RUN,
        "inputAudit": {"person": {"rgbSha256": PERSON}, "garment": {"rgbSha256": GARMENT}}}}
    missing = httpx.MockTransport(lambda _: httpx.Response(404))
    assert client.retrieve_http(tmp_path, trial, connection, transport=missing)["reason"] == "worker_audit_endpoint_unavailable"
    monkeypatch.setattr(client, "MAX_RESPONSE_BYTES", 30)
    oversized = httpx.MockTransport(lambda _: httpx.Response(200, json={"data": [response(root)]}))
    assert client.retrieve_http(tmp_path, trial, connection, transport=oversized)["status"] == "unavailable"
    assert not (tmp_path / "raw.png").exists()
