import base64
import hashlib
import json
import re

import pytest

from scripts import retrieve_colab_archive as transfer


def chunk_output(payload, offset=0):
    chunk = payload[offset:offset + transfer.CHUNK_BYTES]
    record = {
        "type": "avatar-vton-archive-chunk", "offset": offset,
        "archiveBytes": len(payload), "archiveSha256": hashlib.sha256(payload).hexdigest(),
        "chunkSha256": hashlib.sha256(chunk).hexdigest(),
        "data": base64.b64encode(chunk).decode(),
    }
    return {"outputs": [{"output_type": "stream", "text": [json.dumps(record)]}]}


def test_transfer_detects_corrupt_chunks_and_changed_archive():
    output = chunk_output(b"actual archive")
    data, identity = transfer.decode_chunk(output, 0)
    assert data == b"actual archive"
    with pytest.raises(ValueError, match="changed during transfer"):
        transfer.decode_chunk(chunk_output(b"other archive"), 0, identity)
    record = json.loads(output["outputs"][0]["text"][0])
    record["data"] = base64.b64encode(b"tampered bytes").decode()
    output["outputs"][0]["text"] = [json.dumps(record)]
    with pytest.raises(ValueError, match="checksum or length"):
        transfer.decode_chunk(output, 0)


def test_transfer_rejects_wrong_offset_and_remote_error():
    with pytest.raises(ValueError, match="chunk position"):
        transfer.decode_chunk(chunk_output(b"data"), 4)
    with pytest.raises(ValueError, match="unavailable"):
        transfer.decode_chunk({"outputs": [{"output_type": "error", "ename": "AssertionError",
                                            "evalue": "Archive unavailable"}]}, 0)


@pytest.mark.parametrize("digest, offset", [("../bad", 0), ("a" * 64, -1), ("a" * 64, 5)])
def test_export_code_accepts_only_source_hash_and_bounded_offsets(digest, offset):
    with pytest.raises(ValueError):
        transfer.export_code(digest, offset)


def test_export_code_reads_exact_existing_archive_without_running_inference():
    source = transfer.export_code("a" * 64, 0)
    compile(source, "<export>", "exec")
    assert "/content/avatar-vton-aaaaaaaaaaaa/colab-tryon-results.zip" in source
    assert "subprocess" not in source and "torch" not in source and "exec(" not in source


def test_resume_reuses_pending_requests_and_checks_complete_archive(tmp_path, monkeypatch):
    payload = b"a" * transfer.CHUNK_BYTES + b"final chunk"
    calls, responses = [], {}
    offset = 0
    pending_once = True

    def submit(command):
        nonlocal offset
        key = str(len(calls))
        calls.append(command)
        if command["name"] == "add_code_cell":
            responses[key] = {"newCellId": "export-cell"}
        elif command["name"] == "update_cell":
            offset = int(re.search(r"chunk = payload\[(\d+):", command["arguments"]["content"])[1])
            responses[key] = {}
        else:
            assert command["name"] == "run_code_cell"
            assert command["arguments"] == {"cellId": "export-cell"}
            responses[key] = chunk_output(payload, offset)
        return key

    def wait(key, timeout):
        nonlocal pending_once
        if key == "1" and pending_once:
            pending_once = False
            return {"status": "pending"}
        return {"status": "completed"}

    monkeypatch.setattr(transfer, "submit", submit)
    monkeypatch.setattr(transfer, "wait_for", wait)
    monkeypatch.setattr(transfer, "result", lambda key: responses[key])
    output, state = tmp_path / "result.zip", tmp_path / "state.json"
    with pytest.raises(TimeoutError, match="resume"):
        transfer.retrieve("a" * 64, output, state, 4)
    assert not output.exists()
    assert len(calls) == 2
    completed = transfer.retrieve("a" * 64, output, state, 4)
    assert len(calls) == 4
    assert output.read_bytes() == payload
    assert completed["status"] == "complete"
    transfer.retrieve("a" * 64, output, state, 4)
    assert len(calls) == 4
    # A crash after the ZIP was written but before the marker was committed
    # must not strand the evidence or create another remote export cell.
    interrupted = json.loads(state.read_text())
    interrupted.pop("status")
    state.write_text(json.dumps(interrupted))
    assert transfer.retrieve("a" * 64, output, state, 4)["status"] == "complete"
    assert len(calls) == 4
    output.write_bytes(b"corrupted")
    with pytest.raises(ValueError, match="missing or changed"):
        transfer.retrieve("a" * 64, output, state, 4)
