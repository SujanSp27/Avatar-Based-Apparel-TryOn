"""Colab-side recovery of our worker only. Does not run image inference."""
import base64
import json
import secrets
import subprocess
import sys
import time
from pathlib import Path


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


def recover(root: Path, payload: dict):
    if not gpu_available():
        return {'state': 'gpu_unavailable'}
    root.mkdir(exist_ok=True)
    if running(root / 'scripts/setup_online_worker.py'):
        return {'state': 'setting_up'}
    if running(root / 'scripts/online_worker.py'):
        if (root / 'connection.json').is_file():
            connection = json.loads((root / 'connection.json').read_text())
            connection['token'] = (root / 'worker-token.txt').read_text().strip()
            return {'state': 'ready', 'connection': connection}
        return {'state': 'loading'}
    # No owned process is running. Only overwrite our allowlisted worker sources.
    for name, data in payload.items():
        target = (root / name).resolve()
        if not target.is_relative_to(root.resolve()) or not name.endswith('.py'):
            raise ValueError('Invalid worker source path')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(base64.b64decode(data, validate=True))
    if not (root / 'worker-token.txt').exists():
        token_path = root / 'worker-token.txt'
        token_path.write_text(secrets.token_urlsafe(48))
        token_path.chmod(0o600)
    if not (root / 'setup-complete.json').exists():
        return launch(root, 'setup')
    (root / 'connection.json').unlink(missing_ok=True)
    return launch(root, 'worker')
