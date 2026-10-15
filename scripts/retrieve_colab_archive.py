"""Resume bounded, verified ZIP reads through the existing notebook connection.

Only an existing /content/avatar-vton-<source hash>/colab-tryon-results.zip is
read. This helper never installs packages, starts inference or restarts a runtime.
Request IDs persist before waiting, so resuming does not repeat pending commands.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
from pathlib import Path

from scripts.colab_control import ROOT, submit, wait_for
from scripts.colab_notebook_control import result

CHUNK_BYTES = 512 * 1024
MAX_BYTES = 200 * 1024 * 1024


def export_code(source_hash: str, offset: int) -> str:
    if not re.fullmatch(r"[a-f0-9]{64}", source_hash):
        raise ValueError("Expected the executed source archive SHA-256")
    if offset < 0 or offset % CHUNK_BYTES or offset >= MAX_BYTES:
        raise ValueError("Invalid chunk offset")
    # All interpolated fields are validated, not arbitrary notebook code/paths.
    return f'''import base64, hashlib, json
from pathlib import Path
archive = Path('/content/avatar-vton-{source_hash[:12]}/colab-tryon-results.zip')
assert archive.is_file(), 'Existing result ZIP is unavailable; no inference was started'
assert 0 < archive.stat().st_size <= {MAX_BYTES}, 'Result archive exceeds the transfer limit'
payload = archive.read_bytes()
assert 0 < len(payload) <= {MAX_BYTES}, 'Result archive exceeds the transfer limit'
chunk = payload[{offset}:{offset + CHUNK_BYTES}]
assert chunk, 'Offset is beyond the end of the result archive'
print(json.dumps({{'type': 'avatar-vton-archive-chunk', 'offset': {offset},
                  'archiveBytes': len(payload), 'archiveSha256': hashlib.sha256(payload).hexdigest(),
                  'chunkSha256': hashlib.sha256(chunk).hexdigest(),
                  'data': base64.b64encode(chunk).decode('ascii')}}))
'''


def decode_chunk(output: dict, offset: int, expected: dict | None = None) -> tuple[bytes, dict]:
    records = []
    for block in output.get("outputs", []):
        if block.get("output_type") == "error":
            raise ValueError(f"Archive read failed: {block.get('ename')}: {block.get('evalue')}")
        if block.get("output_type") == "stream":
            lines = block.get("text", [])
            for line in (lines if isinstance(lines, str) else "".join(lines)).splitlines():
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(record, dict) and record.get("type") == "avatar-vton-archive-chunk":
                    records.append(record)
    if len(records) != 1:
        raise ValueError("Expected one archive chunk record")
    record = records[0]
    size, digest = record.get("archiveBytes"), record.get("archiveSha256", "")
    if (record.get("offset") != offset or type(size) is not int
            or not offset < size <= MAX_BYTES or not re.fullmatch(r"[a-f0-9]{64}", digest)):
        raise ValueError("Invalid archive identity or chunk position")
    identity = {"archiveBytes": size, "archiveSha256": digest}
    if expected is not None and identity != expected:
        raise ValueError("Archive changed during transfer")
    encoded = record.get("data", "")
    if not isinstance(encoded, str) or len(encoded) > (CHUNK_BYTES + 2) // 3 * 4:
        raise ValueError("Chunk exceeds transfer limit")
    chunk = base64.b64decode(encoded, validate=True)
    if (len(chunk) != min(CHUNK_BYTES, size - offset)
            or hashlib.sha256(chunk).hexdigest() != record.get("chunkSha256")):
        raise ValueError("Chunk checksum or length mismatch")
    return chunk, identity


def save(path: Path, value: dict) -> None:
    temporary = path.with_suffix(".partial")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def retrieve(source_hash: str, output: Path, state_path: Path, cell_index: int) -> dict:
    export_code(source_hash, 0)  # Validate before any tool call or filesystem write.
    output = output.resolve()
    config = {"sourceArchiveSha256": source_hash, "output": str(output), "cellIndex": cell_index}
    state = json.loads(state_path.read_text()) if state_path.exists() else {"config": config, "requests": {}}
    if state["config"] != config:
        raise ValueError("Transfer state belongs to a different archive or output")
    if state.get("status") == "complete":
        if not output.is_file() or hashlib.sha256(output.read_bytes()).hexdigest() != state["identity"]["archiveSha256"]:
            raise ValueError("Completed local archive is missing or changed")
        return state
    if output.exists():
        identity = state.get("identity", {})
        if (state.get("verifiedBytes") == identity.get("archiveBytes")
                and hashlib.sha256(output.read_bytes()).hexdigest() == identity.get("archiveSha256")):
            # Recover a process exit between publishing the verified ZIP and
            # persisting its completion marker; no remote commands are needed.
            state["status"] = "complete"
            save(state_path, state)
            return state
        raise ValueError("Refusing to overwrite an existing archive")
    state_path.parent.mkdir(parents=True, exist_ok=True)

    def command(key: str, name: str, arguments: dict) -> dict:
        if key not in state["requests"]:
            state["requests"][key] = submit({"method": "call_tool", "name": name, "arguments": arguments})
            save(state_path, state)
        request = state["requests"][key]
        if wait_for(request, 30)["status"] == "pending":
            raise TimeoutError(f"Archive transfer is pending at {key}; resume using the same state file. Request {request}")
        return result(request)

    cell = command("create", "add_code_cell", {
        "cellIndex": cell_index, "language": "python", "code": export_code(source_hash, 0),
    })["newCellId"]
    state["cellId"] = cell
    chunks = []
    offset = 0
    while True:
        if offset:
            command(f"update-{offset}", "update_cell", {"cellId": cell, "content": export_code(source_hash, offset)})
        response = command(f"read-{offset}", "run_code_cell", {"cellId": cell})
        chunk, identity = decode_chunk(response, offset, state.get("identity"))
        state["identity"] = identity
        chunks.append(chunk)
        offset += len(chunk)
        state["verifiedBytes"] = offset
        save(state_path, state)
        print(f"Verified {offset}/{identity['archiveBytes']} bytes", flush=True)
        if offset == identity["archiveBytes"]:
            break
    payload = b"".join(chunks)
    if hashlib.sha256(payload).hexdigest() != state["identity"]["archiveSha256"]:
        raise ValueError("Full archive checksum mismatch")
    output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation protects evidence if another process wrote this path.
    with output.open("xb") as stream:
        stream.write(payload)
    state["status"] = "complete"
    save(state_path, state)
    return state


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-hash", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--cell-index", type=int, required=True)
    args = parser.parse_args()
    if not all(path.resolve().is_relative_to(ROOT) for path in (args.output, args.state)):
        parser.error("Store recovered evidence inside this project")
    try:
        state = retrieve(args.source_hash, args.output, args.state, args.cell_index)
    except TimeoutError as exc:
        print(str(exc))
        raise SystemExit(3) from exc
    print(json.dumps({"status": state["status"], **state["identity"]}))


if __name__ == "__main__":
    main()
