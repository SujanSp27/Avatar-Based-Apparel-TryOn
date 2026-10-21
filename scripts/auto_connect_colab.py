"""Recover only the user's saved notebook/worker; never run image inference.

Each tick advances one persisted request, so refreshes and API restarts cannot
queue duplicate notebook executions. A busy notebook is left alone.
"""
from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import colab_control as bridge
from scripts.colab_notebook_control import result
from scripts.colab_server import notebook_path
from scripts.colab_worker_recovery import validate_worker_profile

MARKER = "# formfit-automatic-worker-recovery"
RECOVERY_PROTOCOL = 7


def recovery_source(expected_hostname: str | None = None, worker_profile: dict | None = None):
    if worker_profile is None:
        worker_profile = json.loads((bridge.ROOT / 'config/online-worker.json').read_text(encoding='utf-8'))
    worker_profile = validate_worker_profile(worker_profile)
    names = ['scripts/setup_online_worker.py', 'scripts/online_worker.py',
             'ml/__init__.py', 'ml/vton/__init__.py', 'ml/errors.py',
             'ml/vton/online_composite.py', 'ml/vton/checked_sampler.py', 'ml/vton/region.py',
             'ml/vton/image_transport.py']
    payload = {name: base64.b64encode((bridge.ROOT / name).read_bytes()).decode()
               for name in names}
    source = (bridge.ROOT / 'scripts/colab_worker_recovery.py').read_text(encoding='utf-8')
    return (MARKER + f'-v{RECOVERY_PROTOCOL}\n' + source + '\nprint(json.dumps(recover('
            f"Path('/content/formfit-online'), {payload!r}, "
            f"expected_hostname={expected_hostname!r}, worker_profile={worker_profile!r}, supervise_seconds=180)))\n")


def valid_hostname(value):
    return isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]{0,252}', value) is not None


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
        state.update(stage=stage, submittedAt=time.time(), recoveryProtocol=RECOVERY_PROTOCOL, request=bridge.submit({
            'method': 'call_tool', 'name': tool, 'arguments': arguments,
        }))
        self._save(state)

    def _verify_replacement(self, state, reply, current):
        """Two independent, spaced read-only observations before any mutation.

        Never adopt credentials from the mismatching cell. The following cell
        must verify the new pin again before recovering our own worker.
        """
        hostname = reply['hostname']
        state['observedHostname'] = hostname
        candidate = state.get('candidate', {})
        identity = [hostname, current.get('createTime')]
        now = time.time()
        # A disappearing machine during setup can be a runtime crash/quota
        # failure. Do not reinstall indefinitely on rapidly replaced machines.
        recent = [item for item in state.get('runtimeHistory', []) if now - item['verifiedAt'] < 900]
        if len(recent) >= 3:
            self.next_attempt = time.monotonic() + 60
            self._save(state)
            return 'runtime_unstable'
        if reply.get('state') != 'runtime_changed' or reply.get('gpuAvailable') is not True:
            state.pop('candidate', None)
            self._save(state)
            return 'gpu_unavailable' if reply.get('gpuAvailable') is False else 'runtime_changed'
        if candidate.get('identity') != identity or now - candidate.get('lastSeen', 0) > 300:
            candidate = {'identity': identity, 'firstSeen': now, 'lastSeen': now, 'observations': 1}
        elif now - candidate['lastSeen'] >= 10:
            candidate['observations'] += 1
            candidate['lastSeen'] = now
        state['candidate'] = candidate
        # An inference request retains its original runtime and event URL.
        active = False
        for path in (self.root / '.runtime/tryon-jobs').glob('*.json'):
            try:
                active |= json.loads(path.read_text()).get('status') in {'queued', 'processing'}
            except (OSError, ValueError):
                active = True  # Do not switch while job ownership is uncertain.
        if candidate['observations'] >= 2 and not active:
            state['runtimeHistory'] = (state.get('runtimeHistory', []) + [{
                'from': state.get('expectedHostname'), 'to': hostname, 'verifiedAt': now,
            }])[-20:]
            state.update(previousHostname=state.get('expectedHostname'), expectedHostname=hostname,
                         pinSource='verified_replacement', pinChangedAt=now)
            state.pop('candidate', None)
            state.pop('observedHostname', None)
        self._save(state)
        self.next_attempt = time.monotonic() + 10
        return 'notebook_busy' if active else 'runtime_changed'

    def pin_runtime(self, hostname: str):
        """Explicit operator action after verifying a replacement runtime.

        Stop the app first. Never discard a pending call. Automatic replacement
        adoption uses the separate, repeated identity-verification path.
        """
        if not valid_hostname(hostname):
            raise ValueError('Provide the hostname from a read-only Colab identity check')
        state = json.loads(self.state_path.read_text()) if self.state_path.exists() else {}
        if state.get('request') or bridge.status().get('status') == 'processing':
            raise RuntimeError('A Colab request is still pending; preserve it before changing the runtime pin')
        previous = state.get('expectedHostname')
        state.update(expectedHostname=hostname, pinSource='operator',
                     pinChangedAt=time.time(), previousHostname=previous)
        state.pop('observedHostname', None)
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
                limit = 240 if state.get('stage') == 'probe' and state.get('recoveryProtocol') == RECOVERY_PROTOCOL else 90
                if time.time() - state.get('submittedAt', 0) > limit:
                    # Keep the pending ID: a delayed mutating call must not be replayed.
                    return 'recovery_delayed'
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
            if stage in {'insert', 'updated'} and state.get('recoveryProtocol') != RECOVERY_PROTOCOL:
                # A pre-upgrade cell may contain unguarded recovery code. Read
                # and replace it on the next tick instead of executing it.
                state.pop('cellId', None)
                self._save(state)
                return 'connecting'
            if stage == 'open':
                if output.get('result') is True:
                    state.pop('openedBridge', None)
                    self._save(state)
                    # Allow the successful socket handshake to settle. If the
                    # tab later disconnects, reopen with a bounded cooldown.
                    self.next_attempt = time.monotonic() + 10
                return 'connecting'
            if stage == 'cells':
                source = recovery_source(state.get('expectedHostname'))
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
                if any(o.get('output_type') == 'error' for o in output.get('outputs', [])):
                    # A final exception supersedes earlier progress lines. Do
                    # not mistake a crashed check for a still-loading worker.
                    state['lastReplyState'] = 'recovery_failed'
                    state['lastReplyAt'] = time.time()
                    self._save(state)
                    self.next_attempt = time.monotonic() + 60
                    return 'recovery_failed'
                lines = ''.join(''.join(o.get('text', [])) for o in output.get('outputs', [])
                                if o.get('output_type') == 'stream')
                self.next_attempt = time.monotonic() + 60
                if not lines.strip():
                    return 'connecting'
                reply = json.loads(lines.strip().splitlines()[-1])
                # Persist diagnostic state only, never worker credentials or logs.
                state['lastReplyState'] = reply.get('state')
                state['lastReplyAt'] = time.time()
                self._save(state)
                hostname = reply.get('hostname')
                if not valid_hostname(hostname):
                    # Old, pending recovery cells predate the identity protocol.
                    # Ignore their credentials; next tick installs our safe cell.
                    return 'connecting'
                expected = state.get('expectedHostname')
                if expected and hostname != expected:
                    return self._verify_replacement(state, reply, current)
                if reply['state'] == 'identified':
                    if not expected:
                        state.update(expectedHostname=hostname, pinSource='identity_probe',
                                     pinChangedAt=time.time())
                        self._save(state)
                    # The next cell rechecks this pin in the executing runtime
                    # before installing sources or starting any process.
                    self.next_attempt = time.monotonic() + 10
                    return 'connecting'
                if not expected:
                    return 'connecting'
                if state.pop('observedHostname', None) is not None:
                    state.pop('candidate', None)
                    self._save(state)
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
            opens = [t for t in state.get('openAttempts', []) if time.time() - t < 900]
            if (state.get('openedBridge') == current.get('createTime')
                    and opens and time.time() - opens[-1] < 60):
                return 'browser_required'
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


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Explicitly pin a verified replacement Colab runtime. Stop the app first.')
    parser.add_argument('--pin-runtime', required=True, metavar='HOSTNAME')
    args = parser.parse_args()
    try:
        ColabRecovery(bridge.ROOT, bridge.ROOT / '.runtime/online-connection.json').pin_runtime(args.pin_runtime)
    except (ValueError, RuntimeError) as exc:
        parser.error(str(exc))
    print('Runtime pin saved. Automatic recovery will verify it before changing the worker.')
