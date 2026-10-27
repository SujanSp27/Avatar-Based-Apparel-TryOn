"""Artifact recovery resumes reads, never submits or repeats inference."""
import base64
import json

import pytest

from scripts import retrieve_wardrobe_audits as retrieval
from scripts.evaluate_wardrobe import save


def reply(data):
    return {"outputs": [{"output_type": "stream", "text": [json.dumps(data)]}]}


def test_artifact_reply_distinguishes_absent_files_and_invalid_content():
    value = reply({"raw.png": base64.b64encode(b"saved image bytes").decode(), "edit-mask.png": None})
    assert retrieval.decode_artifacts(value, ["raw.png", "edit-mask.png"]) == {
        "raw.png": b"saved image bytes", "edit-mask.png": None,
    }
    with pytest.raises(ValueError):
        retrieval.decode_artifacts(reply({"raw.png": "not valid base64!"}), ["raw.png"])
    with pytest.raises(ValueError, match="Unexpected"):
        retrieval.decode_artifacts(reply({"../other.png": None}), ["raw.png"])
    with pytest.raises(RuntimeError, match="runtime identity"):
        retrieval.decode_artifacts({"outputs": [{"output_type": "error"}]}, ["raw.png"])


def test_interrupted_read_resumes_saved_response_without_replaying_cell(tmp_path, monkeypatch):
    deployment_state = {}
    calls = []
    journal = tmp_path / "pending.json"
    state = {"phase": "read", "cellId": "saved-cell"}

    def interrupted(tool, arguments):
        calls.append((tool, arguments))
        deployment_state["pendingRequest"] = "existing-request"
        raise RuntimeError("Still waiting")

    monkeypatch.setattr(retrieval.deployment, "call", interrupted)
    monkeypatch.setattr(retrieval.deployment, "_state", lambda: deployment_state)
    with pytest.raises(RuntimeError, match="Still waiting"):
        retrieval.saved_call("run_code_cell", {"cellId": "saved-cell"}, journal, state)
    saved = json.loads(journal.read_text())
    assert saved["request"] == "existing-request"
    monkeypatch.setattr(retrieval, "wait_for", lambda *_: {"status": "pending"})
    with pytest.raises(RuntimeError, match="still pending"):
        retrieval.saved_call("run_code_cell", {}, journal, saved)
    monkeypatch.setattr(retrieval, "wait_for", lambda *_: {"status": "completed"})
    completed = reply({"raw.png": None})
    monkeypatch.setattr(retrieval.deployment, "recover_pending", lambda: completed)
    assert retrieval.saved_call("run_code_cell", {}, journal, saved) == completed
    assert len(calls) == 1
    # A later interruption while writing files also reuses the persisted reply.
    again = json.loads(journal.read_text())
    assert retrieval.saved_call("run_code_cell", {}, journal, again) == completed
    assert len(calls) == 1


def test_retrieval_records_only_actual_files(tmp_path, monkeypatch, capsys):
    (tmp_path / ".runtime").mkdir()
    save(tmp_path / ".runtime/colab-autoconnect.json", {"expectedHostname": "original-runtime"})
    case = tmp_path / "cases/garment/studio"
    save(case / "trial.json", {"status": "generated", "productId": "garment", "personId": "studio",
        "diagnostics": {"runPath": "/content/formfit-online/runs/123"}})
    monkeypatch.setattr(retrieval, "ROOT", tmp_path)
    monkeypatch.setattr(retrieval, "NAMES", ["raw.png", "edit-mask.png"])
    monkeypatch.setattr(retrieval.deployment, "_state", lambda: {})
    monkeypatch.setattr(retrieval.deployment, "call", lambda tool, args: {"newCellId": "cell"}
                        if tool == "add_code_cell" else reply({"raw.png": base64.b64encode(b"raw").decode(), "edit-mask.png": None}))
    retrieval.retrieve(tmp_path)
    assert "Recovered 1/2" in capsys.readouterr().out
    assert (case / "raw.png").read_bytes() == b"raw"
    report = json.loads((case / "artifact-retrieval.json").read_text())
    assert report["retrieved"] == ["raw.png"]
    assert report["missingInLastBatch"] == ["edit-mask.png"]
    assert not (case / "artifact-retrieval-pending.json").exists()


def test_unrelated_pending_request_is_never_adopted(tmp_path, monkeypatch):
    monkeypatch.setattr(retrieval.deployment, "_state", lambda: {"pendingRequest": "another-operation"})
    with pytest.raises(RuntimeError, match="Another Colab operation"):
        retrieval.saved_call("add_code_cell", {}, tmp_path / "pending.json", {})
    assert not (tmp_path / "pending.json").exists()


def test_ledger_does_not_count_stale_review_or_thirty_seconds_as_pass(tmp_path):
    from scripts.evaluate_wardrobe import digest
    from scripts.report_wardrobe_trials import collect
    case = tmp_path / "cases/product/studio"
    save(case / "trial.json", {"status": "generated", "productId": "product", "personId": "studio",
        "jobId": "saved", "inputs": {}, "outputSha256": digest(b"saved output"), "observedEndToEndSeconds": 30})
    (case / "after.png").write_bytes(b"saved output")
    save(case / "visual-review.json", {"outputSha256": digest(b"previous output"),
        "decision": "visual_pass", "fullResolutionInspected": True})
    row = collect(tmp_path, "experiment")[0]
    assert row["outputHashVerified"] is True
    assert row["visualDecision"] == "pending_or_stale"
    assert row["under30Seconds"] is False
