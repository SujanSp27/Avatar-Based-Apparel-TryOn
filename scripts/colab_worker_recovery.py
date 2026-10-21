"""Colab-side recovery of our worker only. Does not run image inference."""
import base64
import json
import os
import secrets
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlparse


def validate_worker_profile(profile: dict | None) -> dict | None:
    """Accept only supported operator settings, without coercing unsafe values."""
    if profile is None:
        # Older callers recover sources without changing runtime configuration.
        return None
    expected = {'precision', 'resolution', 'cropPerson', 'guidanceScale',
                'skipUnusedUnconditional', 'segmentationFree'}
    if not isinstance(profile, dict) or set(profile) != expected:
        raise ValueError('Worker profile must contain exactly the supported settings')
    if type(profile['precision']) is not str or profile['precision'] not in {'upstream', 'fp16'}:
        raise ValueError('Unsupported worker precision profile')
    if type(profile['resolution']) is not str or profile['resolution'] not in {'native', 'balanced', 'fast'}:
        raise ValueError('Unsupported worker resolution profile')
    for name in ('cropPerson', 'skipUnusedUnconditional', 'segmentationFree'):
        if type(profile[name]) is not bool:
            raise ValueError(f'Worker profile {name} must be a boolean')
    if type(profile['guidanceScale']) not in (int, float) or profile['guidanceScale'] not in {1.0, 1.5}:
        raise ValueError('Unsupported worker guidance profile')
    return dict(profile)


def running(script: Path) -> bool:
    """Check the actual command, not a stale PID that another process can reuse."""
    for command in Path('/proc').glob('[0-9]*/cmdline'):
        try:
            if str(script).encode() in command.read_bytes().split(b'\0'):
                return True
        except OSError:
            continue
    return False


def launch(root: Path, kind: str):
    attempts_path = root / 'recovery-attempts.json'
    attempts = json.loads(attempts_path.read_text()) if attempts_path.exists() else {}
    recent = [t for t in attempts.get(kind, []) if time.time() - t < 3600]
    if len(recent) >= 3:
        return {'state': f'{kind}_failed'}
    attempts[kind] = recent + [time.time()]
    attempts_path.write_text(json.dumps(attempts))
    python = sys.executable if kind == 'setup' else str(root / '.venv/bin/python')
    script = 'setup_online_worker.py' if kind == 'setup' else 'online_worker.py'
    with (root / f'{kind}.log').open('ab') as log:
        proc = subprocess.Popen([python, '-u', str(root / 'scripts' / script)],
                                cwd=root, stdout=log, stderr=log, start_new_session=True)
    (root / f'{kind}-pid.json').write_text(json.dumps({'pid': proc.pid}))
    return {'state': 'setting_up' if kind == 'setup' else 'loading'}


def gpu_available():
    return sys.platform == 'linux' and bool(list(Path('/dev').glob('nvidia[0-9]*')))


def worker_reachable(connection):
    """Check the loaded model through the actual tunnel, without running inference."""
    try:
        url = connection['url']
        parsed = urlparse(url)
        if (parsed.scheme != 'https' or not (parsed.hostname or '').endswith('.gradio.live')
                or parsed.username or parsed.password or parsed.query or parsed.fragment):
            return False
        request = Request(url.rstrip('/') + '/gradio_api/run/status',
                          data=json.dumps({'data': [connection['token']]}).encode(),
                          headers={'Content-Type': 'application/json'})
        with urlopen(request, timeout=4) as response:
            status = json.load(response)['data'][0]
        return status.get('ready') is True and status.get('device') == 'cuda'
    except (OSError, ValueError, KeyError, IndexError, TypeError):
        return False


def repair_stale_worker(root):
    """Only terminate our idle worker after three spaced failed tunnel checks.

    Inputs, outputs, weights, token and configuration remain on disk. The next
    recovery tick installs current sources and launches through bounded retries.
    """
    if (root / 'active-generation.json').exists():
        return {'state': 'notebook_busy'}
    path = root / 'tunnel-failures.json'
    state = json.loads(path.read_text()) if path.exists() else {}
    now = time.time()
    failures = [t for t in state.get('attempts', []) if now - t < 600]
    if not failures or now - failures[-1] >= 30:
        failures.append(now)
    path.write_text(json.dumps({'attempts': failures}))
    if len(failures) < 3:
        return {'state': 'recovering_tunnel'}
    for command in Path('/proc').glob('[0-9]*/cmdline'):
        try:
            if str(root / 'scripts/online_worker.py').encode() in command.read_bytes().split(b'\0'):
                # Recheck the marker immediately before signalling the owned PID.
                if (root / 'active-generation.json').exists():
                    return {'state': 'notebook_busy'}
                os.kill(int(command.parent.name), signal.SIGTERM)
        except (OSError, ValueError):
            continue
    path.unlink(missing_ok=True)
    return {'state': 'recovering_tunnel'}


def installation_complete(root):
    required = ['setup-complete.json', '.venv/bin/python', 'weights/model.safetensors',
                'weights/dwpose/yolox_l.onnx', 'weights/dwpose/dw-ll_ucoco_384.onnx',
                'weights/parser/config.json', 'weights/parser/model.safetensors']
    return all((root / name).is_file() and (root / name).stat().st_size > 0 for name in required)


def recover(root: Path, payload: dict, expected_hostname: str | None = None,
            worker_profile: dict | None = None):
    """Identify first; only a caller-pinned runtime may change worker files.

    Colab's browser connection can switch between duplicate notebook tabs. The
    identity comparison must run in this same cell, before even creating root.
    A missing pin is deliberately read-only, including on a GPU runtime.
    """
    hostname = socket.gethostname()
    if expected_hostname is None:
        return {'state': 'identified', 'hostname': hostname,
                'gpuAvailable': gpu_available(), 'projectExists': root.is_dir()}
    if hostname != expected_hostname:
        return {'state': 'runtime_changed', 'hostname': hostname,
                'expectedHostname': expected_hostname, 'gpuAvailable': gpu_available(),
                'projectExists': root.is_dir()}
    # Serialize independent notebook executions without a stale lock-file problem.
    # GPU and profile checks precede all writes, including creating the lock.
    validate_worker_profile(worker_profile)
    if not gpu_available():
        return {'state': 'gpu_unavailable', 'hostname': hostname}
    # Validate paths before even creating the lock directory.
    validated_sources(root, payload)
    if sys.platform == 'linux':
        import fcntl
        root.mkdir(exist_ok=True)
        with (root / '.recovery.lock').open('a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return {'state': 'notebook_busy', 'hostname': hostname}
            reply = _recover_pinned(root, payload, worker_profile)
    else:  # CPU-only unit tests; production execution above requires Linux GPU.
        reply = _recover_pinned(root, payload, worker_profile)
    return {**reply, 'hostname': hostname}


def validated_sources(root, payload):
    sources = {}
    for name, data in payload.items():
        target = (root / name).resolve()
        if not target.is_relative_to(root.resolve()) or not name.endswith('.py'):
            raise ValueError('Invalid worker source path')
        sources[target] = base64.b64decode(data, validate=True)
    return sources


def _recover_pinned(root: Path, payload: dict, worker_profile: dict | None = None):
    profile = validate_worker_profile(worker_profile)
    if not gpu_available():
        return {'state': 'gpu_unavailable'}
    if running(root / 'scripts/setup_online_worker.py'):
        return {'state': 'setting_up'}
    if running(root / 'scripts/online_worker.py'):
        if (root / 'connection.json').is_file():
            connection = json.loads((root / 'connection.json').read_text())
            connection['token'] = (root / 'worker-token.txt').read_text().strip()
            if not worker_reachable(connection):
                return repair_stale_worker(root)
            (root / 'tunnel-failures.json').unlink(missing_ok=True)
            return {'state': 'ready', 'connection': connection}
        return {'state': 'loading'}
    # Validate everything before creating files or starting a process.
    sources = validated_sources(root, payload)
    root.mkdir(exist_ok=True)
    if profile is not None:
        # Seed once: setup and subsequent recovery ticks retain the same profile.
        # Exclusive creation also protects an operator's concurrent config write.
        try:
            with (root / 'worker-config.json').open('x', encoding='utf-8') as config:
                config.write(json.dumps(profile, indent=2, sort_keys=True) + '\n')
        except FileExistsError:
            pass
    # No owned process is running. Only overwrite our allowlisted worker sources.
    for target, data in sources.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    if not (root / 'worker-token.txt').exists():
        token_path = root / 'worker-token.txt'
        token_path.write_text(secrets.token_urlsafe(48))
        token_path.chmod(0o600)
    if not installation_complete(root):
        return launch(root, 'setup')
    (root / 'connection.json').unlink(missing_ok=True)
    return launch(root, 'worker')
