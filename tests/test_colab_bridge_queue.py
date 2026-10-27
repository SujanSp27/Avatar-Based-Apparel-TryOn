"""Exercise the local queue without a browser, model or installed MCP package."""
import asyncio
import importlib.util
import json
import sys
import types
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from backend.app.config import ROOT


@pytest.mark.parametrize("tool,minimum,maximum", [("run_code_cell", 180, 300), ("open_colab_browser_connection", 60, 90)])
def test_completed_call_survives_broken_discovery_and_has_appropriate_deadline(tmp_path, monkeypatch, tool, minimum, maximum):
    calls = []
    stopped = tmp_path / "stop.request"

    class Session:
        def __init__(self, *args, **kwargs):
            self.list_count = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def initialize(self):
            return SimpleNamespace(serverInfo={})

        async def list_tools(self, **kwargs):
            self.list_count += 1
            if self.list_count > 2:
                raise TimeoutError("Browser disappeared after the successful cell")
            return SimpleNamespace(tools=[SimpleNamespace(name=tool)], nextCursor=None)

        async def call_tool(self, name, arguments):
            stopped.touch()
            return {"structuredContent": {"result": "completed cell evidence"}}

    @asynccontextmanager
    async def transport(*args, **kwargs):
        yield None, None

    for name in ("mcp", "mcp.client", "mcp.client.stdio"):
        monkeypatch.setitem(sys.modules, name, types.ModuleType(name))
    sys.modules["mcp"].ClientSession = Session
    sys.modules["mcp"].StdioServerParameters = lambda **kwargs: kwargs
    sys.modules["mcp.client.stdio"].stdio_client = transport
    spec = importlib.util.spec_from_file_location("bridge_queue_fixture", ROOT / "scripts/colab_bridge.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "STATE", tmp_path)
    monkeypatch.setattr(module, "SERVER", tmp_path / "server.exe")
    monkeypatch.setattr(module, "as_json", lambda v: vars(v) if isinstance(v, SimpleNamespace) else v)
    (tmp_path / "server.exe").touch()
    (tmp_path / "requests").mkdir()
    (tmp_path / "requests/trial.json").write_text(json.dumps({"method": "call_tool", "name": tool, "arguments": {}}))
    wait_for = asyncio.wait_for

    async def record_deadline(awaitable, timeout):
        calls.append(timeout)
        return await wait_for(awaitable, timeout=timeout)

    monkeypatch.setattr(module.asyncio, "wait_for", record_deadline)
    asyncio.run(module.serve())
    reply = json.loads((tmp_path / "responses/trial.json").read_text())
    assert reply["status"] == "completed"
    assert reply["result"]["structuredContent"]["result"] == "completed cell evidence"
    assert minimum <= calls[-1] <= maximum
    assert (tmp_path / "processed/trial.json").exists()
    assert not list((tmp_path / "inflight").iterdir())
