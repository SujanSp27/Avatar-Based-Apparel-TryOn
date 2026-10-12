"""Stage the project notebook through the connected official Colab MCP tools.

Only project-owned cells are tracked. Existing cells are not deleted or replaced.
Execution is explicit; staging never runs installation, inference, or Drive cells.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from colab_control import ROOT, STATE, status, submit, wait_for

MAPPING = STATE / "project-cells.json"


def result(request_id: str) -> dict:
    response = json.loads((STATE / "responses" / f"{request_id}.json").read_text())
    if response["status"] != "completed" or response.get("result", {}).get("isError"):
        raise RuntimeError(f"Colab call failed; inspect response {request_id}")
    output = response["result"]
    if output.get("structuredContent") is not None:
        return output["structuredContent"]
    for block in output.get("content", []):
        if block["type"] == "text":
            return json.loads(block["text"])
    raise RuntimeError(f"No structured result from {request_id}")


def stage(notebook_path: Path) -> None:
    from build_colab_notebook import validate_notebook

    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
    validate_notebook(notebook)
    fingerprint = notebook["metadata"]["avatarVton"]["sourceArchiveSha256"]
    mapping = json.loads(MAPPING.read_text()) if MAPPING.exists() else {
        "sourceArchiveSha256": fingerprint, "cells": {},
    }
    if mapping["sourceArchiveSha256"] != fingerprint:
        raise RuntimeError("Source changed since staging. Preserve the existing mapping and stage a new notebook explicitly.")
    request = submit({"method": "call_tool", "name": "get_cells", "arguments": {}})
    if wait_for(request, 30)["status"] != "completed":
        raise RuntimeError(f"Notebook read pending: {request}")
    current = result(request)["cells"]
    current_ids = {item["id"] for item in current}
    if any(value not in current_ids for value in mapping["cells"].values()):
        raise RuntimeError("The connected notebook does not contain the previously staged cells.")
    index = len(current)
    for cell in notebook["cells"]:
        if cell["id"] in mapping["cells"]:
            continue
        source = "".join(cell["source"])
        code = cell["cell_type"] == "code"
        arguments = {"cellIndex": index}
        arguments.update({"language": "python", "code": source} if code else {"content": source})
        request = submit({"method": "call_tool",
                          "name": "add_code_cell" if code else "add_text_cell",
                          "arguments": arguments})
        if wait_for(request, 30)["status"] != "completed":
            raise RuntimeError(f"Cell insertion pending; inspect {request} before retrying.")
        mapping["cells"][cell["id"]] = result(request)["newCellId"]
        MAPPING.write_text(json.dumps(mapping, indent=2), encoding="utf-8")
        print(f"Staged {cell['id']}", flush=True)
        index += 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    staging = sub.add_parser("stage")
    staging.add_argument("--notebook", type=Path, default=ROOT / "notebooks/Virtual_TryOn_GPU.ipynb")
    run = sub.add_parser("run")
    run.add_argument("cell")
    args = parser.parse_args()
    if not status()["processAlive"]:
        raise RuntimeError("Colab bridge is stopped.")
    if args.action == "stage":
        stage(args.notebook)
    else:
        mapping = json.loads(MAPPING.read_text())
        request = submit({"method": "call_tool", "name": "run_code_cell",
                          "arguments": {"cellId": mapping["cells"][args.cell]}})
        print(json.dumps({"cell": args.cell, "request": request, "status": "submitted"}))


if __name__ == "__main__":
    main()
