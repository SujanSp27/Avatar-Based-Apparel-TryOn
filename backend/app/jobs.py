"""One bounded local job with persisted status and idempotent submission.

This is an in-process research worker, not a durable distributed queue. A server
restart marks interrupted work failed instead of silently rerunning inference.
Only job metadata/results are stored here; inputs remain in normal run storage.
"""

import hashlib
import json
import logging
import math
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import RLock
from uuid import UUID, uuid4

from ml.errors import PipelineError
from ml.progress import observe_progress

logger = logging.getLogger(__name__)


class TryOnJobs:
    def __init__(self, directory: Path, capacity):
        self.directory = directory
        self.capacity = capacity
        self.lock = RLock()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="tryon")
        self.active = None

    def _path(self, job_id):
        return self.directory / f"{UUID(str(job_id))}.json"

    def _save(self, data):
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self._path(data["jobId"])
        temporary = path.with_suffix(".partial")
        temporary.write_text(json.dumps(data, allow_nan=False), encoding="utf-8")
        temporary.replace(path)

    def _read(self, job_id):
        path = self._path(job_id)
        if not path.is_file():
            raise PipelineError("job_not_found", "This try-on job was not found.", 404)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if (not isinstance(data, dict) or data.get("jobId") != str(UUID(str(job_id)))
                    or data.get("status") not in {"queued", "processing", "success", "failed"}
                    or not isinstance(data.get("createdAt"), (float, int))
                    or not math.isfinite(data["createdAt"])
                    or not isinstance(data.get("requestHash"), str)):
                raise ValueError("Invalid job metadata")
            return data
        except (OSError, ValueError) as exc:
            raise PipelineError("job_record_unavailable", "The saved job record cannot be read. Its artifacts have been retained; inference was not restarted.", 503) from exc

    def get(self, job_id, *, owner=None):
        with self.lock:
            data = self._read(job_id)
            if owner is not None and data.get("owner") != owner:
                raise PipelineError("job_not_found", "This try-on job was not found in your session.", 404)
            data.pop("requestHash", None)
            data.pop("owner", None)
            if data["status"] in {"queued", "processing"}:
                data["elapsedSeconds"] = round(time.time() - data["createdAt"], 1)
            return data

    def recover_interrupted(self):
        with self.lock:
            for path in self.directory.glob("*.json"):
                try:
                    data = self._read(path.stem)
                except (PipelineError, ValueError):
                    # Retain the corrupt file for recovery without blocking unrelated APIs.
                    logger.error("Skipped unreadable job record during startup: %s", path.name)
                    continue
                if data["status"] in {"queued", "processing"}:
                    data.update(status="failed", error={
                        "code": "job_interrupted",
                        "message": "The server restarted before this job completed. Its existing artifacts were retained; no automatic rerun was started.",
                    })
                    self._save(data)

    def submit(self, person: bytes, garment: bytes, parameters: dict, work, key=None, *, preflight=None):
        try:
            job_id = str(UUID(str(key))) if key else str(uuid4())
        except ValueError as exc:
            raise PipelineError("job_key", "Idempotency-Key must be a UUID.") from exc
        signature = hashlib.sha256(json.dumps({
            "person": hashlib.sha256(person).hexdigest(),
            "garment": hashlib.sha256(garment).hexdigest(),
            "parameters": parameters,
        }, sort_keys=True, allow_nan=False).encode()).hexdigest()
        with self.lock:
            if self._path(job_id).is_file():
                existing = self._read(job_id)
                if existing["requestHash"] != signature:
                    raise PipelineError("job_key_conflict", "This request ID belongs to different inputs.", 409)
                return self.get(job_id)
            if preflight:
                preflight()
            if not self.capacity.acquire(blocking=False):
                raise PipelineError("busy", "Another try-on is running. Wait for the active job to finish.", 429)
            data = {
                "jobId": job_id, "status": "queued", "requestHash": signature,
                "owner": parameters.get("owner"),
                "createdAt": time.time(), "progress": {"stage": "queued"},
                "statusUrl": f"/api/tryon/jobs/{job_id}",
            }
            try:
                self._save(data)
                self.active = job_id
                self.executor.submit(self._run, data, work)
            except Exception:
                self.active = None
                self.capacity.release()
                data.update(status="failed", error={"code": "job_start_failed", "message": "The worker could not start."})
                self._save(data)
                raise
            return self.get(job_id)

    def _run(self, data, work):
        def update(progress):
            with self.lock:
                data.update(status="processing", progress=progress)
                self._save(data)

        try:
            update({"stage": "preprocessing"})
            with observe_progress(update):
                result = work()
            outcome = {"status": "success", "result": result, "progress": {"stage": "complete"}}
        except Exception as exc:
            logger.exception("Try-on job %s failed", data["jobId"])
            outcome = {"status": "failed", "error": {
                    "code": getattr(exc, "code", "internal_error"),
                    "message": str(exc) if isinstance(exc, PipelineError) else "Try-on failed; inspect the server log.",
                }}
        finally:
            with self.lock:
                # Readers cannot observe completion before capacity is released.
                try:
                    data.update(outcome)
                    self._save(data)
                finally:
                    self.active = None
                    self.capacity.release()

    def close(self):
        self.executor.shutdown(wait=True)
