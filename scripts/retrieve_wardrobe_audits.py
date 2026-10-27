"""Retrieve existing private Colab audit artifacts without starting inference."""
import argparse
import base64
import json
import re
from pathlib import Path

from backend.app.config import ROOT
from scripts import deploy_online_colab as deployment
from scripts.colab_control import wait_for
from scripts.colab_notebook_control import result
from scripts.evaluate_wardrobe import DEFAULT, PEOPLE, save
from scripts.worker_audits import retrieve_http

NAMES = ["raw.png", "garment-labels.png", "source-labels.png", "target-labels.png", "edit-mask.png",
         "garment-input.png", "person-input.png", "conditioning.json", "garment-conditioning.png",
         "person-conditioning.png", "reference-preparation.json", "inputs.json"]


def saved_call(tool, arguments, journal, state):
    """Resume a saved read-only artifact call instead of replaying its cell."""
    if "reply" in state:
        return state["reply"]
    request = state.get("request")
    if request:
        outcome = wait_for(request, 0)
        if outcome["status"] == "pending":
            raise RuntimeError(f"Artifact request {request} is still pending; resume retrieval later.")
        # Another operator may already have consumed the deployment journal.
        # The immutable bridge response still belongs to this same request.
        reply = (deployment.recover_pending() if deployment._state().get("pendingRequest") == request
                 else result(request))
    else:
        # Do not accidentally associate another operator's pending call with ours.
        if deployment._state().get("pendingRequest"):
            raise RuntimeError("Another Colab operation is pending; recover it before retrieving artifacts.")
        try:
            reply = deployment.call(tool, arguments)
        except RuntimeError:
            pending = deployment._state().get("pendingRequest")
            if pending:
                state["request"] = pending
                save(journal, state)
            raise
    state["reply"] = reply
    save(journal, state)
    return reply


def decode_artifacts(reply, names):
    if any(row.get("output_type") == "error" for row in reply.get("outputs", [])):
        raise RuntimeError("Colab artifact read failed. Check runtime identity; no inference was replayed.")
    streams = "".join("".join(row.get("text", [])) for row in reply.get("outputs", [])
                      if row.get("output_type") == "stream")
    data = json.loads(streams.strip())
    if not isinstance(data, dict) or set(data) != set(names):
        raise ValueError("Unexpected artifact response; no files were written")
    # Validate every item before writing any of this batch.
    return {name: base64.b64decode(value, validate=True) if value is not None else None
            for name, value in data.items()}


def retrieve(folder: Path, ids=None, people=None, transport="notebook"):
    pin = json.loads((ROOT / ".runtime/colab-autoconnect.json").read_text())["expectedHostname"]
    for trial_file in sorted(folder.glob("cases/*/*/trial.json")):
        trial = json.loads(trial_file.read_text())
        if ids and trial["productId"] not in ids:
            continue
        if people and trial["personId"] not in people:
            continue
        if trial["status"] != "generated":
            continue
        case = trial_file.parent
        if transport == "http":
            outcome = retrieve_http(case, trial, ROOT / ".runtime/online-connection.json")
            print(json.dumps({"productId": trial["productId"], "person": trial["personId"], **outcome}), flush=True)
            continue
        journal = case / "artifact-retrieval-pending.json"
        pending = json.loads(journal.read_text()) if journal.exists() else None
        needed = [name for name in NAMES if not (case / name).exists()]
        if pending:
            needed = pending["names"] + [name for name in needed if name not in pending["names"]]
        if not needed:
            continue
        run = trial["diagnostics"]["runPath"]
        if not re.fullmatch(r"/content/formfit-online/runs/[0-9]+", run):
            raise ValueError("Invalid saved remote run")
        # Two bounded replies keep the original PNGs below the helper message limit.
        remaining = [name for name in needed if not pending or name not in pending["names"]]
        batches = ([pending["names"]] if pending else []) + [remaining[i:i + 6] for i in range(0, len(remaining), 6)]
        for names in batches:
            source = f"""import pathlib,socket,json,base64
if socket.gethostname()!={pin!r}:raise RuntimeError('Runtime changed; preserve artifacts')
p=pathlib.Path({run!r})
print(json.dumps({{n:base64.b64encode((p/n).read_bytes()).decode() if (p/n).is_file() else None for n in {names!r}}}))
"""
            state = pending or {"names": names, "run": run, "hostname": pin, "phase": "insert"}
            if state["names"] != names or state["run"] != run:
                raise ValueError("Saved artifact request does not match this trial")
            if state["hostname"] != pin and not state.get("request") and "reply" not in state:
                raise RuntimeError("Runtime changed before retrieval; preserve the saved artifact request")
            save(journal, state)
            if state["phase"] == "insert":
                reply = saved_call("add_code_cell", {"cellIndex": 0, "language": "python", "code": source}, journal, state)
                state = {"names": names, "run": run, "hostname": state["hostname"], "phase": "read", "cellId": reply["newCellId"]}
                save(journal, state)
            reply = saved_call("run_code_cell", {"cellId": state["cellId"]}, journal, state)
            data = decode_artifacts(reply, names)
            for name in names:
                if data[name] is not None:
                    (case / name).write_bytes(data[name])
            recovered = [name for name in names if data[name] is not None]
            missing = [name for name in names if data[name] is None]
            save(case / "artifact-retrieval.json", {"hostname": state["hostname"], "run": run,
                 "retrieved": [name for name in NAMES if (case / name).is_file()], "missingInLastBatch": missing})
            journal.unlink()
            pending = None
            print(f"Recovered {len(recovered)}/{len(names)} audit records for {trial['productId']}/{trial['personId']}"
                  + (f"; absent: {', '.join(missing)}" if missing else ""), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folder", type=Path, default=DEFAULT)
    parser.add_argument("--ids", nargs="+", help="Retrieve only these existing trial IDs")
    parser.add_argument("--people", nargs="+", choices=list(PEOPLE), help="Retrieve only these test-person cases")
    parser.add_argument("--transport", choices=["notebook", "http"], default="notebook",
                        help="HTTP reads the authenticated worker directly without needing a notebook connection")
    args = parser.parse_args()
    if not args.folder.resolve().is_relative_to((ROOT / "experiments").resolve()):
        parser.error("Use the private experiments directory")
    retrieve(args.folder, args.ids, args.people, args.transport)
