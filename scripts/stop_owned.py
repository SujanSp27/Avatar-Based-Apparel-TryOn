"""Stop only recorded project processes, verifying creation times against PID reuse."""

import json
from datetime import datetime
from pathlib import Path

import psutil

root = Path(__file__).resolve().parents[1]
record = root / ".runtime/processes.json"
if record.exists():
    for entry in json.loads(record.read_text(encoding="utf-8-sig")).values():
        try:
            process = psutil.Process(entry["pid"])
            expected = datetime.fromisoformat(entry["startedUtc"]).timestamp()
            if abs(process.create_time() - expected) > 1:
                continue
            command = " ".join(process.cmdline()).lower()
            if (
                "uvicorn backend.app.main:app" not in command
                and str(root / "frontend").lower() not in command
            ):
                continue
            children = process.children(recursive=True)
            for child in children:
                child.terminate()
            process.terminate()
            _, alive = psutil.wait_procs(children + [process], timeout=5)
            for owned in alive:
                owned.kill()
        except psutil.NoSuchProcess:
            pass
