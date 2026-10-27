"""Retrieve existing private Colab audit artifacts without starting inference."""
import argparse
import base64
import json
import re
from pathlib import Path

from backend.app.config import ROOT
from scripts.deploy_online_colab import call
from scripts.evaluate_wardrobe import DEFAULT

NAMES = ["raw.png", "garment-labels.png", "source-labels.png", "target-labels.png", "edit-mask.png",
         "garment-input.png", "person-input.png", "conditioning.json", "garment-conditioning.png",
         "person-conditioning.png", "reference-preparation.json", "inputs.json"]


def retrieve(folder: Path, ids=None):
    pin = json.loads((ROOT / ".runtime/colab-autoconnect.json").read_text())["expectedHostname"]
    for trial_file in sorted(folder.glob("cases/*/*/trial.json")):
        trial = json.loads(trial_file.read_text())
        if ids and trial["productId"] not in ids:
            continue
        if trial["status"] != "generated":
            continue
        case = trial_file.parent
        needed = [name for name in NAMES if not (case / name).exists()]
        if not needed:
            continue
        run = trial["diagnostics"]["runPath"]
        if not re.fullmatch(r"/content/formfit-online/runs/[0-9]+", run):
            raise ValueError("Invalid saved remote run")
        # Two bounded replies keep the original PNGs below the helper message limit.
        for start in range(0, len(needed), 6):
            names = needed[start:start + 6]
            source = f"""import pathlib,socket,json,base64
if socket.gethostname()!={pin!r}:raise RuntimeError('Runtime changed; preserve artifacts')
p=pathlib.Path({run!r})
print(json.dumps({{n:base64.b64encode((p/n).read_bytes()).decode() if (p/n).is_file() else None for n in {names!r}}}))
"""
            cell = call("add_code_cell", {"cellIndex": 0, "language": "python", "code": source})["newCellId"]
            reply = call("run_code_cell", {"cellId": cell})
            streams = "".join("".join(o.get("text", [])) for o in reply.get("outputs", []) if o.get("output_type") == "stream")
            data = json.loads(streams.strip())
            for name in names:
                if data[name] is not None:
                    (case / name).write_bytes(base64.b64decode(data[name], validate=True))
            print(f"Recovered {len(names)} audit records for {trial['productId']}/{trial['personId']}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folder", type=Path, default=DEFAULT)
    parser.add_argument("--ids", nargs="+", help="Retrieve only these existing trial IDs")
    args = parser.parse_args()
    if not args.folder.resolve().is_relative_to((ROOT / "experiments").resolve()):
        parser.error("Use the private experiments directory")
    retrieve(args.folder, args.ids)
