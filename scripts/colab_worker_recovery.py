"""Colab-side recovery of our worker only. Does not run image inference."""
import base64
import json
import secrets
import socket
import subprocess
import sys
import time
from pathlib import Path


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
    if type(profile['resolution']) is not str or profile['resolution'] not in {'native', 'fast'}:
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
                'expectedHostname': expected_hostname}
    reply = _recover_pinned(root, payload, worker_profile)
    return {**reply, 'hostname': hostname}


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
            return {'state': 'ready', 'connection': connection}
        return {'state': 'loading'}
    # Validate everything before creating files or starting a process.
    sources = {}
    for name, data in payload.items():
        target = (root / name).resolve()
        if not target.is_relative_to(root.resolve()) or not name.endswith('.py'):
            raise ValueError('Invalid worker source path')
        sources[target] = base64.b64decode(data, validate=True)
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
    if not (root / 'setup-complete.json').exists():
        return launch(root, 'setup')
    (root / 'connection.json').unlink(missing_ok=True)
    return launch(root, 'worker')
