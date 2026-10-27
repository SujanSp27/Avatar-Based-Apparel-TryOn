"""Queue client for the pinned official Google Colab MCP server.

Start with the isolated interpreter installed by setup_colab_bridge.py. On
startup this only lists tools: browser opening requires an explicit queued
call to the real open_colab_browser_connection tool. Requests and responses
remain in ignored .runtime/colab-bridge; no credentials are printed.

Submit JSON atomically as requests/<unique-id>.json, for example:
    {"method": "list_tools"}
    {"method": "call_tool", "name": "ACTUAL_TOOL_NAME", "arguments": {}}
Read responses/<unique-id>.json and tools.json for the current real schema.
Create stop.request for graceful shutdown; no hosted runtime is stopped by it.
"""

from __future__ import annotations

import asyncio
import base64
import json
import msvcrt
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import psutil
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".runtime" / "colab-bridge"
TOOLS = ROOT / ".runtime" / "colab-mcp-tools"
SERVER = TOOLS / "venv" / "Scripts" / "colab-mcp.exe"
IDENTIFIER = re.compile(r"^[A-Za-z0-9_-]{1,100}$")
MAX_REQUEST_BYTES = 64 * 1024 * 1024


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(".partial")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def as_json(value: Any) -> Any:
    return value.model_dump(mode="json", by_alias=True) if hasattr(value, "model_dump") else value


def extract_images(result: Any, request_id: str) -> list[str]:
    """Preserve returned MCP image blocks locally without printing their data."""
    if not isinstance(result, dict):
        return []
    files = []
    suffixes = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
    for index, block in enumerate(result.get("content", [])):
        if not isinstance(block, dict) or block.get("type") != "image":
            continue
        suffix = suffixes.get(block.get("mimeType"))
        if not suffix:
            continue
        image_path = STATE / "artifacts" / f"{request_id}-{index}{suffix}"
        image_path.write_bytes(base64.b64decode(block["data"], validate=True))
        files.append(str(image_path.relative_to(ROOT)))
    return files


async def serve() -> None:
    for name in ("requests", "responses", "inflight", "processed", "logs", "artifacts"):
        (STATE / name).mkdir(parents=True, exist_ok=True)
    process = psutil.Process()
    metadata = {
        "pid": process.pid,
        "createTime": process.create_time(),
        "executable": process.exe(),
        "script": str(Path(__file__).resolve()),
        "startedAt": now(),
        "serverExecutable": str(SERVER),
    }
    write_json(STATE / "process.json", metadata)
    write_json(STATE / "readiness.json", {**metadata, "status": "starting"})
    for abandoned in (STATE / "inflight").glob("*.json"):
        write_json(STATE / "responses" / abandoned.name, {
            "id": abandoned.stem,
            "status": "indeterminate",
            "message": "The previous bridge stopped during this request. It was not replayed.",
            "finishedAt": now(),
        })
        abandoned.replace(STATE / "processed" / abandoned.name)
    if not SERVER.is_file():
        raise RuntimeError("Run scripts/setup_colab_bridge.py before starting this client.")
    changed = asyncio.Event()

    async def on_message(message: Any) -> None:
        notification = getattr(message, "root", None)
        if getattr(notification, "method", None) == "notifications/tools/list_changed":
            changed.set()

    env = os.environ.copy()
    env.update({
        "PYTHONUTF8": "1",
        "PYTHONUNBUFFERED": "1",
        "FASTMCP_SHOW_CLI_BANNER": "false",
    })
    existing_notebook = (STATE / "connection.json").is_file()
    params = StdioServerParameters(
        command=sys.executable if existing_notebook else str(SERVER),
        args=([str(ROOT / "scripts/colab_server.py")] if existing_notebook else [])
        + ["--log", str(STATE / "logs")], env=env,
        cwd=str(ROOT),
    )
    with (STATE / "logs" / "server-stderr.log").open("a", encoding="utf-8") as errlog:
        async with stdio_client(params, errlog=errlog) as (read_stream, write_stream):
            async with ClientSession(
                read_stream, write_stream,
                read_timeout_seconds=timedelta(seconds=900),
                message_handler=on_message,
            ) as session:
                initialized = await session.initialize()
                tool_names: set[str] = set()

                async def list_tools() -> dict[str, Any]:
                    nonlocal tool_names
                    all_tools = []
                    cursor = None
                    while True:
                        # A dropped browser socket can leave proxy discovery
                        # waiting for the 15-minute transport deadline.
                        page = await asyncio.wait_for(session.list_tools(cursor=cursor), timeout=20)
                        all_tools.extend(page.tools)
                        cursor = page.nextCursor
                        if not cursor:
                            break
                    tool_names = {tool.name for tool in all_tools}
                    data = {"updatedAt": now(), "tools": [as_json(tool) for tool in all_tools]}
                    write_json(STATE / "tools.json", data)
                    return data

                def readiness(status: str = "ready", **extra: Any) -> None:
                    write_json(STATE / "readiness.json", {
                        **metadata,
                        "updatedAt": now(),
                        "status": status,
                        "toolNames": sorted(tool_names),
                        "notebookToolsAvailable": bool(tool_names - {"open_colab_browser_connection"}),
                        "serverInfo": as_json(initialized.serverInfo),
                        **extra,
                    })

                await list_tools()
                readiness()
                heartbeat = time.monotonic()
                while not (STATE / "stop.request").exists():
                    if changed.is_set():
                        changed.clear()
                        await list_tools()
                        readiness()
                    for request in sorted((STATE / "requests").glob("*.json")):
                        if not IDENTIFIER.fullmatch(request.stem):
                            continue
                        inflight = STATE / "inflight" / request.name
                        response_path = STATE / "responses" / request.name
                        if response_path.exists():
                            # Unique IDs prevent accidental replay of an already completed call.
                            request.replace(STATE / "processed" / request.name)
                            continue
                        request.replace(inflight)
                        readiness("processing", currentRequest=request.stem)
                        outcome: dict[str, Any] = {"id": request.stem, "startedAt": now()}
                        try:
                            if inflight.stat().st_size > MAX_REQUEST_BYTES:
                                raise ValueError("Request exceeds 64 MiB")
                            payload = json.loads(inflight.read_text(encoding="utf-8-sig"))
                            if not isinstance(payload, dict):
                                raise ValueError("Request must be a JSON object")
                            if payload.get("method") == "list_tools":
                                result = await list_tools()
                            elif payload.get("method") == "call_tool":
                                # A browser can connect after the previous snapshot was written.
                                await list_tools()
                                name = payload.get("name")
                                arguments = payload.get("arguments", {})
                                if name not in tool_names:
                                    raise ValueError("Unknown tool. Read tools.json for the current schema.")
                                if not isinstance(arguments, dict):
                                    raise ValueError("Tool arguments must be a JSON object")
                                # Recovery supervises setup for up to 180 seconds.
                                # Browser consent/discovery stays short; cancelling
                                # a healthy recovery at 75 s loses its final reply.
                                timeout = 240 if name == "run_code_cell" else 75
                                result = as_json(await asyncio.wait_for(session.call_tool(name, arguments=arguments), timeout=timeout))
                                # Persist the completed operation before refreshing
                                # discovery. A discovery failure must not discard a
                                # successful cell result or make it look replayable.
                                changed.set()
                            else:
                                raise ValueError("Only list_tools and call_tool methods are supported")
                            outcome.update(
                                status="completed", result=result,
                                artifacts=extract_images(result, request.stem),
                            )
                        except Exception as exc:
                            outcome.update(status="error", errorType=type(exc).__name__, message=str(exc))
                        outcome["finishedAt"] = now()
                        write_json(response_path, outcome)
                        inflight.replace(STATE / "processed" / request.name)
                        readiness()
                    if time.monotonic() - heartbeat >= 10:
                        readiness()
                        heartbeat = time.monotonic()
                    await asyncio.sleep(0.5)
                readiness("stopped")


def main() -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    with (STATE / "instance.lock").open("a+b") as lock:
        if lock.tell() == 0:
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            raise SystemExit("A workspace Colab bridge is already running.") from None
        try:
            asyncio.run(serve())
        except Exception as exc:
            write_json(STATE / "readiness.json", {
                "status": "failed", "updatedAt": now(),
                "errorType": type(exc).__name__, "message": str(exc),
            })
            # Keep potentially sensitive MCP transport details out of stdout/stderr.
            raise SystemExit(1) from None
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


if __name__ == "__main__":
    main()
