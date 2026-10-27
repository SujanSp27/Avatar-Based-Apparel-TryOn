"""Bounded, authenticated export of a completed run; never invokes a model."""
import base64
import hashlib
import json
import re
import secrets
from pathlib import Path

ARTIFACT_NAMES = (
    "raw.png", "garment-labels.png", "source-labels.png", "target-labels.png", "edit-mask.png",
    "garment-input.png", "person-input.png", "conditioning.json", "garment-conditioning.png",
    "person-conditioning.png", "reference-preparation.json", "inputs.json", "fidelity.json",
    "report.json", "failure.json", "garment-prepared.png",
)
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_TOTAL_BYTES = 16 * 1024 * 1024
RUN_ID = re.compile(r"[0-9]{10,24}")
SHA256 = re.compile(r"[0-9a-f]{64}")


def export_audit(root: Path, token, supplied_token, run_id, person_hash, garment_hash):
    # Authenticate before disclosing even whether a run exists.
    if (not isinstance(token, str) or len(token) < 32 or not token.isascii()
            or not isinstance(supplied_token, str) or not supplied_token.isascii()
            or not secrets.compare_digest(token, supplied_token)):
        return {"error": "unauthorized"}
    if (not isinstance(run_id, str) or not RUN_ID.fullmatch(run_id)
            or any(not isinstance(value, str) or not SHA256.fullmatch(value)
                   for value in (person_hash, garment_hash))):
        return {"error": "invalid_audit_request"}
    runs = (root / "runs").resolve()
    case = runs / run_id
    if case.is_symlink() or case.resolve().parent != runs:
        return {"error": "invalid_audit_request"}
    try:
        inputs_path = case / "inputs.json"
        if (inputs_path.is_symlink() or not inputs_path.is_file()
                or inputs_path.stat().st_size > 64 * 1024):
            return {"error": "audit_unavailable"}
        inputs = json.loads(inputs_path.read_text())
        if any(inputs.get(key, {}).get("rgbSha256") != expected
               for key, expected in (("person", person_hash), ("garment", garment_hash))):
            return {"error": "audit_input_mismatch"}
        if not any((case / name).is_file() for name in ("report.json", "failure.json")):
            return {"error": "audit_not_complete"}
        files, total = {}, 0
        for name in ARTIFACT_NAMES:
            path = case / name
            if path.is_symlink() or path.resolve().parent != case.resolve():
                return {"error": "invalid_audit_file"}
            if not path.is_file():
                files[name] = None
                continue
            size = path.stat().st_size
            if size > MAX_FILE_BYTES or total + size > MAX_TOTAL_BYTES:
                return {"error": "audit_size_limit"}
            with path.open("rb") as stream:
                data = stream.read(MAX_FILE_BYTES + 1)
            total += len(data)
            if len(data) != size or total > MAX_TOTAL_BYTES:
                return {"error": "audit_size_limit"}
            files[name] = {"bytes": size, "sha256": hashlib.sha256(data).hexdigest(),
                           "base64": base64.b64encode(data).decode("ascii")}
        return {"protocol": 1, "runId": run_id, "personSha256": person_hash,
                "garmentSha256": garment_hash, "files": files}
    except (OSError, ValueError, TypeError, AttributeError):
        return {"error": "audit_unavailable"}
