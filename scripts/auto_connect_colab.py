"""Recover only the user's saved notebook/worker; never run image inference.

Each tick advances one persisted request, so refreshes and API restarts cannot
queue duplicate notebook executions. A busy notebook is left alone.
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import time
from pathlib import Path

from scripts import colab_control as bridge
from scripts.colab_notebook_control import result
from scripts.colab_server import notebook_path

MARKER = "# formfit-automatic-worker-recovery"


def recovery_source():
    names = ['scripts/setup_online_worker.py', 'scripts/online_worker.py',
             'ml/__init__.py', 'ml/vton/__init__.py', 'ml/errors.py',
             'ml/vton/online_composite.py', 'ml/vton/checked_sampler.py']
    payload = {name: base64.b64encode((bridge.ROOT / name).read_bytes()).decode()
               for name in names}
    source = (bridge.ROOT / 'scripts/colab_worker_recovery.py').read_text(encoding='utf-8')
    return (MARKER + '-v2\n' + source + '\nprint(json.dumps(recover('
            f"Path('/content/formfit-online'), {payload!r})))\n")


class ColabRecovery:
    def __init__(self, root: Path, connection_path: Path):
        self.root, self.connection_path = root, connection_path
        self.state_path = root / '.runtime/colab-autoconnect.json'
        self.next_attempt = 0.
        self.bridge_process = None

    def _save(self, state):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix('.partial')
        temporary.write_text(json.dumps(state), encoding='utf-8')
        temporary.replace(self.state_path)

    def _submit(self, state, stage, tool, arguments):
        state.update(stage=stage, request=bridge.submit({
            'method': 'call_tool', 'name': tool, 'arguments': arguments,
        }))
        self._save(state)

    def _start_bridge(self):
        config = self.root / '.runtime/colab-bridge/connection.json'
        if not config.is_file():
            return 'not_configured'
        notebook_path(json.loads(config.read_text(encoding='utf-8'))['notebookUrl'])
        python = self.root / '.runtime/colab-mcp-tools/venv/Scripts/python.exe'
        if os.name != 'nt' or not python.is_file():
            return 'bridge_unavailable'
        if self.bridge_process and self.bridge_process.poll() is None:
            return 'connecting'
        (self.root / '.runtime/colab-bridge/stop.request').unlink(missing_ok=True)
        # Starting the bridge does not allocate or reset a Colab runtime.
        with (self.root / '.runtime/colab-autoconnect.log').open('ab') as log:
            self.bridge_process = subprocess.Popen(
                [str(python), str(self.root / 'scripts/colab_bridge.py')], cwd=self.root,
                stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        self.next_attempt = time.monotonic() + 10
        return 'connecting'

    def tick(self):
        if time.monotonic() < self.next_attempt:
            return None
        state = json.loads(self.state_path.read_text()) if self.state_path.exists() else {}
        current = bridge.status()
        if not current['processAlive']:
            return self._start_bridge()
        if current.get('notebookToolsAvailable') and 'openedBridge' in state:
            # A successful connection permits one automatic reopen if the
            # browser socket is lost later. A pending consent prompt does not.
            state.pop('openedBridge')
            self._save(state)
        request = state.get('request')
        if request:
            response = bridge.STATE / 'responses' / f'{request}.json'
            if not response.is_file():
                return 'browser_required' if state.get('stage') == 'open' else 'connecting'
            try:
                output = result(request)
            except (RuntimeError, ValueError):
                state.pop('request', None)
                self._save(state)
                self.next_attempt = time.monotonic() + 60
                return 'connecting'
            stage = state.pop('stage')
            state.pop('request')
            self._save(state)
            if stage == 'open':
                if output.get('result') is True:
                    state.pop('openedBridge', None)
                    self._save(state)
                    # Allow the successful socket handshake to settle. If the
                    # tab later disconnects, reopen with a bounded cooldown.
                    self.next_attempt = time.monotonic() + 10
                return 'connecting'
            if stage == 'cells':
                source = recovery_source()
                cell = next((c for c in output.get('cells', [])
                             if MARKER in ''.join(c.get('source', []))), None)
                if cell:
                    if ''.join(cell.get('source', [])) != source:
                        state['cellId'] = cell['id']
                        self._submit(state, 'updated', 'update_cell', {'cellId': cell['id'], 'content': source})
                    else:
                        self._submit(state, 'probe', 'run_code_cell', {'cellId': cell['id']})
                else:
                    self._submit(state, 'insert', 'add_code_cell', {
                        'cellIndex': len(output.get('cells', [])), 'language': 'python',
                        'code': source,
                    })
            elif stage == 'insert':
                self._submit(state, 'probe', 'run_code_cell', {'cellId': output['newCellId']})
            elif stage == 'updated':
                self._submit(state, 'probe', 'run_code_cell', {'cellId': state.pop('cellId')})
            elif stage == 'probe':
                lines = ''.join(''.join(o.get('text', [])) for o in output.get('outputs', [])
                                if o.get('output_type') == 'stream')
                self.next_attempt = time.monotonic() + 60
                if not lines.strip():
                    return 'connecting'
                reply = json.loads(lines.strip().splitlines()[-1])
                if reply['state'] == 'ready':
                    from scripts.connect_online_worker import save_connection
                    save_connection(reply['connection'], self.connection_path)
                return reply['state']
            return 'connecting'
        if current.get('status') == 'processing':
            return 'notebook_busy'
        if not current.get('notebookToolsAvailable'):
            # Reopen a dropped successful session with bounded retries. A failed
            # consent/sign-in prompt is never repeatedly opened or bypassed.
            if state.get('openedBridge') == current.get('createTime'):
                return 'browser_required'
            opens = [t for t in state.get('openAttempts', []) if time.time() - t < 900]
            if len(opens) >= 3:
                return 'browser_required'
            if opens and time.time() - opens[-1] < 60:
                return 'connecting'
            config = self.root / '.runtime/colab-bridge/connection.json'
            if not config.is_file():
                return 'not_configured'
            notebook_path(json.loads(config.read_text())['notebookUrl'])
            state['openedBridge'] = current['createTime']
            state['openAttempts'] = opens + [time.time()]
            self._submit(state, 'open', 'open_colab_browser_connection', {})
        else:
            self._submit(state, 'cells', 'get_cells', {'includeOutputs': False})
        return 'connecting'
