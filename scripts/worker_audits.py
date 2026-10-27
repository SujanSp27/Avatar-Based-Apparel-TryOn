"""Save private GPU audit files after evaluation, independently of the notebook socket."""
import base64
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

import httpx

from ml.vton.audit_export import ARTIFACT_NAMES, MAX_FILE_BYTES, MAX_TOTAL_BYTES, RUN_ID

MAX_RESPONSE_BYTES = 24 * 1024 * 1024


def validate_export(payload, run_id, person_hash, garment_hash):
    """Validate the whole response before writing any file; no archive extraction."""
    if not isinstance(payload, dict):
        raise ValueError("Invalid worker audit response")
    if payload.get("error"):
        return None, str(payload["error"])[:80]
    if (payload.get("protocol") != 1 or payload.get("runId") != run_id
            or payload.get("personSha256") != person_hash or payload.get("garmentSha256") != garment_hash
            or not isinstance(payload.get("files"), dict) or set(payload["files"]) != set(ARTIFACT_NAMES)):
        raise ValueError("Worker audit does not match this saved trial")
    files, total = {}, 0
    for name, record in payload["files"].items():
        if record is None:
            files[name] = None
            continue
        if (not isinstance(record, dict) or type(record.get("bytes")) is not int
                or not 0 <= record["bytes"] <= MAX_FILE_BYTES or not isinstance(record.get("base64"), str)
                or len(record["base64"]) > (MAX_FILE_BYTES + 2) // 3 * 4):
            raise ValueError("Invalid worker audit file")
        data = base64.b64decode(record["base64"], validate=True)
        total += len(data)
        if (len(data) != record["bytes"] or hashlib.sha256(data).hexdigest() != record.get("sha256")
                or total > MAX_TOTAL_BYTES):
            raise ValueError("Worker audit checksum or size mismatch")
        files[name] = data
    return files, None


def retrieve_http(case: Path, trial: dict, connection_path: Path, *, transport=None):
    diagnostic = trial.get("diagnostics", {})
    remote_path = diagnostic.get("runPath", "")
    run_id = remote_path.removeprefix("/content/formfit-online/runs/")
    audit = diagnostic.get("inputAudit", {})
    person_hash, garment_hash = (audit.get(key, {}).get("rgbSha256") for key in ("person", "garment"))
    if not remote_path.startswith("/content/formfit-online/runs/") or not RUN_ID.fullmatch(run_id):
        return {"status": "unavailable", "reason": "missing_saved_run"}
    if not person_hash or not garment_hash:
        return {"status": "unavailable", "reason": "missing_input_hashes"}
    try:
        connection = json.loads(connection_path.read_text())
        url, token = connection.get("url", "").rstrip("/"), connection.get("token")
        parsed = urlparse(url)
        if (parsed.scheme != "https" or not (parsed.hostname or "").endswith(".gradio.live")
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path or parsed.port not in (None, 443) or not isinstance(token, str) or len(token) < 32):
            raise ValueError("Invalid private worker connection")
        with httpx.Client(timeout=httpx.Timeout(30, connect=5), follow_redirects=False,
                          trust_env=False, transport=transport) as client:
            with client.stream("POST", url + "/gradio_api/run/audit", json={
                "data": [token, run_id, person_hash, garment_hash],
            }) as response:
                if response.status_code in (404, 405):
                    return {"status": "unavailable", "reason": "worker_audit_endpoint_unavailable"}
                response.raise_for_status()
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > MAX_RESPONSE_BYTES:
                        raise ValueError("Worker audit response exceeds limit")
        values = json.loads(body).get("data")
        if not isinstance(values, list) or len(values) != 1:
            raise ValueError("Unexpected worker audit response")
        payload = json.loads(values[0]) if isinstance(values[0], str) else values[0]
        files, reason = validate_export(payload, run_id, person_hash, garment_hash)
        if files is None:
            return {"status": "unavailable", "reason": reason}
        # Refuse symlinks or changed existing evidence instead of overwriting it.
        for name, data in files.items():
            target = case / name
            if target.is_symlink() or target.resolve().parent != case.resolve():
                raise ValueError("Invalid local audit path")
            if data is not None and target.exists() and target.read_bytes() != data:
                raise ValueError("Retrieved artifact conflicts with saved evidence")
        for name, data in files.items():
            if data is not None and not (case / name).exists():
                temporary = case / (name + ".partial")
                if temporary.is_symlink() or temporary.resolve().parent != case.resolve():
                    raise ValueError("Invalid temporary audit path")
                if temporary.exists():
                    if temporary.read_bytes() != data:
                        raise ValueError("Interrupted audit differs from verified response")
                else:
                    with temporary.open("xb") as stream:
                        stream.write(data)
                temporary.replace(case / name)
        report = {"status": "retrieved", "transport": "authenticated_worker_http", "runId": run_id,
                  "retrieved": [name for name, data in files.items() if data is not None],
                  "missing": [name for name, data in files.items() if data is None]}
        (case / "artifact-http-retrieval.json").write_text(json.dumps(report, indent=2))
        return report
    except (OSError, ValueError, TypeError, AttributeError, httpx.HTTPError) as exc:
        # Exception messages may contain internal URLs: log only the exception type.
        return {"status": "unavailable", "reason": type(exc).__name__}
