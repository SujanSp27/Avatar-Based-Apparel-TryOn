"""Deploy only to the already-connected notebook; never opens or resets Colab."""
import argparse
import json
import re
import sys
from pathlib import Path

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.auto_connect_colab import recovery_source, valid_hostname
from scripts.colab_control import ROOT, status, submit, wait_for
from scripts.colab_notebook_control import result

STATE = ROOT / ".runtime/online-deployment.json"


def _state():
    return json.loads(STATE.read_text()) if STATE.exists() else {}


def _save(state):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    temporary = STATE.with_suffix('.partial')
    temporary.write_text(json.dumps(state, indent=2), encoding='utf-8')
    temporary.replace(STATE)


def call(tool, arguments):
    state = _state()
    if state.get('pendingRequest'):
        raise RuntimeError(f"Request pending: {state['pendingRequest']}. Run the recover command before submitting another command.")
    request = submit({"method": "call_tool", "name": tool, "arguments": arguments})
    state.setdefault("requests", []).append({"tool": tool, "id": request})
    state['pendingRequest'] = request
    _save(state)
    outcome = wait_for(request, 30)
    if outcome["status"] == "pending":
        raise RuntimeError(f"Request pending: {request}. Recover it before rerunning this command.")
    state.pop('pendingRequest')
    _save(state)
    if outcome["status"] != "completed" or outcome.get("toolError"):
        raise RuntimeError(f"Colab call {request} ended with status {outcome['status']}; inspect its saved response before retrying.")
    return result(request)


def recover_pending():
    """Read a persisted response without resubmitting the notebook operation."""
    state = _state()
    request = state.get('pendingRequest')
    if not request:
        return {'state': 'no_pending_request'}
    outcome = wait_for(request, 0)
    if outcome['status'] == 'pending':
        return {'state': 'pending', 'request': request}
    state.pop('pendingRequest')
    _save(state)
    if outcome['status'] != 'completed' or outcome.get('toolError'):
        raise RuntimeError(f"Saved Colab request {request} ended with status {outcome['status']}; no operation was retried.")
    return result(request)


def deployment_source(action: str, precision: str | None = None, root: Path | None = None):
    """Build a read-only check or an idempotent, runtime-pinned recovery cell."""
    root = root or ROOT
    if action == 'status':
        if precision is not None:
            raise ValueError('Precision applies only to a missing worker profile, not status')
        return """import pathlib,json,subprocess,socket,shutil
p=pathlib.Path('/content/formfit-online')
print(json.dumps({'hostname':socket.gethostname(),'gpu':subprocess.run(['nvidia-smi','--query-gpu=name,memory.used','--format=csv,noheader'],capture_output=True,text=True).stdout.strip() if shutil.which('nvidia-smi') else 'unavailable','setupComplete':(p/'setup-complete.json').exists(),'connection':json.loads((p/'connection.json').read_text()) if (p/'connection.json').exists() else None,'environment':json.loads((p/'worker-environment.json').read_text()) if (p/'worker-environment.json').exists() else None,'activeGeneration':json.loads((p/'active-generation.json').read_text()) if (p/'active-generation.json').exists() else None,'setupTail':(p/'setup.log').read_text()[-1800:] if (p/'setup.log').exists() else 'absent','workerTail':(p/'worker.log').read_text()[-1800:] if (p/'worker.log').exists() else 'absent'}))
"""
    if action not in {'setup', 'worker'}:
        raise ValueError('Unknown deployment action')
    pin_path = root / '.runtime/colab-autoconnect.json'
    state = json.loads(pin_path.read_text()) if pin_path.exists() else {}
    hostname = state.get('expectedHostname')
    if not valid_hostname(hostname):
        raise RuntimeError('Pin the hostname from a read-only Colab runtime check before deployment')
    if state.get('request'):
        raise RuntimeError('Automatic recovery has a pending request; preserve it before manual deployment')
    profile = json.loads((root / 'config/online-worker.json').read_text(encoding='utf-8'))
    if precision is not None:
        profile['precision'] = precision
    # Both commands resume the same state machine. An existing setup, worker,
    # token, or operator profile is preserved; no forced restart is performed.
    return recovery_source(expected_hostname=hostname, worker_profile=profile)


def run_unchanged_cell(cell_id: str, expected_source: str):
    cells = call('get_cells', {'includeOutputs': False}).get('cells', [])
    cell = next((item for item in cells if item.get('id') == cell_id), None)
    if cell is None or ''.join(cell.get('source', [])) != expected_source:
        raise RuntimeError('The staged deployment cell changed or disappeared; refusing to execute it')
    return call('run_code_cell', {'cellId': cell_id})


def redacted(value):
    """Recovery replies may contain private credentials: never print them."""
    if isinstance(value, dict):
        return {key: '[redacted]' if key.lower() in {'token', 'authorization'} else redacted(item)
                for key, item in value.items()}
    if isinstance(value, list):
        return [redacted(item) for item in value]
    if isinstance(value, str):
        return re.sub(r'("(?:token|authorization)"\s*:\s*)"[^"\\]*(?:\\.[^"\\]*)*"',
                      r'\1"[redacted]"', value, flags=re.IGNORECASE)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["setup", "worker", "status", "recover"],
                        help='Setup/worker resume guarded recovery; recover reads a pending response without replay')
    parser.add_argument("--precision", choices=["upstream", "fp16"], default=None,
                        help='Seed only a missing runtime profile; existing profiles remain unchanged')
    args = parser.parse_args()
    if args.action == 'recover':
        if args.precision is not None:
            parser.error('--precision does not apply to recovering a saved response')
        print(json.dumps(redacted(recover_pending()), ensure_ascii=True)[:6000])
        return
    current = status()
    if not current["processAlive"]:
        raise RuntimeError("Reconnect the existing Colab bridge first.")
    if current.get('status') == 'processing':
        raise RuntimeError('The notebook is busy; preserve the current call before manual deployment')
    source = deployment_source(args.action, args.precision)
    cells = call("get_cells", {"includeOutputs": False})["cells"]
    cell_id = call("add_code_cell", {"cellIndex": len(cells), "language": "python", "code": source})["newCellId"]
    state = _state()
    state[args.action + "Cell"] = cell_id
    _save(state)
    output = run_unchanged_cell(cell_id, source)
    print(json.dumps(redacted(output), ensure_ascii=True)[:6000])


if __name__ == "__main__":
    main()
