"""Submit commands to the local Colab bridge; print metadata, never cell contents."""

from __future__ import annotations

import argparse
import json
import time
import uuid
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".runtime" / "colab-bridge"


def status() -> dict:
    path = STATE / "readiness.json"
    if not path.is_file():
        return {"status": "not_started", "processAlive": False}
    saved = json.loads(path.read_text(encoding="utf-8"))
    alive = False
    try:
        process = psutil.Process(saved["pid"])
        alive = abs(process.create_time() - saved["createTime"]) < 0.01
    except (KeyError, psutil.Error):
        pass
    if not alive:
        saved["lastRecordedStatus"] = saved.get("status")
        saved["status"] = "stopped"
    saved["processAlive"] = alive
    return saved


def submit(payload: dict, request_id: str | None = None) -> str:
    if payload.get("method") not in {"list_tools", "call_tool"}:
        raise ValueError("Only list_tools and call_tool methods are supported")
    request_id = request_id or str(uuid.uuid4())
    if not request_id or not all(char.isalnum() or char in "_-" for char in request_id):
        raise ValueError("Invalid request ID")
    if len(request_id) > 100:
        raise ValueError("Request ID is too long")
    for directory in ("requests", "responses", "inflight", "processed"):
        if (STATE / directory / f"{request_id}.json").exists():
            raise ValueError("Request ID already exists; use a unique ID")
    folder = STATE / "requests"
    folder.mkdir(parents=True, exist_ok=True)
    temporary = folder / f"{request_id}.partial"
    temporary.write_text(json.dumps(payload), encoding="utf-8")
    temporary.replace(folder / f"{request_id}.json")
    return request_id


def wait_for(request_id: str, timeout: float) -> dict:
    if not request_id or not all(char.isalnum() or char in "_-" for char in request_id):
        raise ValueError("Invalid request ID")
    path = STATE / "responses" / f"{request_id}.json"
    deadline = time.monotonic() + timeout
    while True:
        if path.is_file():
            result = json.loads(path.read_text(encoding="utf-8"))
            return {
                "id": request_id,
                "status": result.get("status"),
                "responseFile": str(path.relative_to(ROOT)),
                "toolError": result.get("result", {}).get("isError", False),
                "artifacts": result.get("artifacts", []),
            }
        if time.monotonic() >= deadline:
            return {"id": request_id, "status": "pending", "bridge": status()["status"]}
        time.sleep(0.5)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    subs.add_parser("status")
    listing = subs.add_parser("list")
    call = subs.add_parser("call")
    call.add_argument("tool")
    call.add_argument("--arguments-file", type=Path)
    request = subs.add_parser("submit")
    request.add_argument("request_file", type=Path)
    for item in (listing, call, request):
        item.add_argument("--id")
        item.add_argument("--wait", type=float, default=0)
    wait = subs.add_parser("wait")
    wait.add_argument("id")
    wait.add_argument("--timeout", type=float, default=30)
    args = parser.parse_args()
    if args.command == "status":
        output = status()
    elif args.command == "wait":
        if not 0 <= args.timeout <= 60:
            parser.error("Timeout must be between 0 and 60 seconds")
        output = wait_for(args.id, args.timeout)
    else:
        if not 0 <= args.wait <= 60:
            parser.error("Wait must be between 0 and 60 seconds")
        if not status()["processAlive"]:
            parser.error("The local Colab bridge is not running")
        if args.command == "list":
            payload = {"method": "list_tools"}
        elif args.command == "call":
            arguments = (
                json.loads(args.arguments_file.read_text(encoding="utf-8-sig"))
                if args.arguments_file else {}
            )
            payload = {"method": "call_tool", "name": args.tool, "arguments": arguments}
        else:
            payload = json.loads(args.request_file.read_text(encoding="utf-8-sig"))
        request_id = submit(payload, args.id)
        output = wait_for(request_id, args.wait)
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
