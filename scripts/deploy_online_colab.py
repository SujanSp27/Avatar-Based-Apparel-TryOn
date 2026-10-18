"""Deploy only to the already-connected notebook; never opens or resets Colab."""
import argparse
import base64
import json
import secrets

from colab_control import ROOT, status, submit, wait_for
from colab_notebook_control import result

STATE = ROOT / ".runtime/online-deployment.json"


def call(tool, arguments):
    request = submit({"method": "call_tool", "name": tool, "arguments": arguments})
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    state.setdefault("requests", []).append({"tool": tool, "id": request})
    STATE.write_text(json.dumps(state, indent=2))
    outcome = wait_for(request, 30)
    if outcome["status"] == "pending":
        raise RuntimeError(f"Request pending: {request}. Recover it before rerunning this command.")
    if outcome["status"] != "completed" or outcome.get("toolError"):
        raise RuntimeError(f"Colab call {request} ended with status {outcome['status']}; inspect its saved response before retrying.")
    return result(request)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["setup", "worker", "status"])
    parser.add_argument("--precision", choices=["upstream", "fp16"], default="upstream")
    args = parser.parse_args()
    if not status()["processAlive"]:
        raise RuntimeError("Reconnect the existing Colab bridge first.")
    if args.action == "status":
        source = """import pathlib,json,subprocess
p=pathlib.Path('/content/formfit-online')
print(json.dumps({'gpu':subprocess.run(['nvidia-smi','--query-gpu=name,memory.used','--format=csv,noheader'],capture_output=True,text=True).stdout.strip(),'setupComplete':(p/'setup-complete.json').exists(),'connection':json.loads((p/'connection.json').read_text()) if (p/'connection.json').exists() else None,'environment':json.loads((p/'worker-environment.json').read_text()) if (p/'worker-environment.json').exists() else None,'activeGeneration':json.loads((p/'active-generation.json').read_text()) if (p/'active-generation.json').exists() else None,'setupTail':(p/'setup.log').read_text()[-1800:] if (p/'setup.log').exists() else 'absent','workerTail':(p/'worker.log').read_text()[-1800:] if (p/'worker.log').exists() else 'absent'}))
"""
    else:
        names = ["scripts/setup_online_worker.py"] if args.action == "setup" else [
            "scripts/online_worker.py", "ml/__init__.py", "ml/vton/__init__.py", "ml/errors.py", "ml/vton/online_composite.py", "ml/vton/checked_sampler.py", "ml/vton/region.py"]
        payload = {name: base64.b64encode((ROOT / name).read_bytes()).decode() for name in names}
        token_file = ROOT / ".runtime/online-worker-token.txt"
        if not token_file.exists():
            token_file.write_text(secrets.token_urlsafe(48))
        # The private token is transported in the cell source, never printed.
        # Do not share this notebook publicly; it belongs to the user's session.
        token = token_file.read_text().strip()
        source = f"""import pathlib,json,base64,subprocess,sys,os
p=pathlib.Path('/content/formfit-online');p.mkdir(exist_ok=True)
for name,data in {payload!r}.items():
 target=p/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(base64.b64decode(data))
action={args.action!r}
pidfile=p/(action+'-pid.json')
if pidfile.exists() and pathlib.Path('/proc/'+str(json.loads(pidfile.read_text())['pid'])).exists():
 raise RuntimeError('Existing '+action+' process is still running; inspect it before restarting.')
(p/'worker-token.txt').write_text({token!r})
if action=='worker':
 (p/'worker-config.json').write_text(json.dumps({{'precision':{args.precision!r}}}))
python=sys.executable if action=='setup' else str(p/'.venv/bin/python')
script='setup_online_worker.py' if action=='setup' else 'online_worker.py'
log=(p/(action+'.log')).open('ab')
if action=='setup':
 completed=subprocess.run([python,'-u',str(p/'scripts'/script)],cwd=p,stdout=log,stderr=log)
 print(json.dumps({{'action':action,'returnCode':completed.returncode,'tail':(p/'setup.log').read_text()[-2400:]}}))
else:
 job=subprocess.Popen([python,'-u',str(p/'scripts'/script)],cwd=p,stdout=log,stderr=log)
 pidfile.write_text(json.dumps({{'pid':job.pid}}))
 print(json.dumps({{'action':action,'pid':job.pid}}))
"""
    cells = call("get_cells", {"includeOutputs": False})["cells"]
    cell_id = call("add_code_cell", {"cellIndex": len(cells), "language": "python", "code": source})["newCellId"]
    state = json.loads(STATE.read_text())
    state[args.action + "Cell"] = cell_id
    STATE.write_text(json.dumps(state, indent=2))
    output = call("run_code_cell", {"cellId": cell_id})
    print(json.dumps(output, ensure_ascii=True)[:6000])


if __name__ == "__main__":
    main()
