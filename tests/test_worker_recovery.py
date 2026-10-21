"""Colab process recovery uses fakes; these tests never touch CUDA."""
import base64
import json
from unittest.mock import Mock

import pytest

from scripts import colab_worker_recovery as worker

PROFILE = {'precision': 'fp16', 'resolution': 'native', 'cropPerson': False,
           'guidanceScale': 1.5, 'skipUnusedUnconditional': False, 'segmentationFree': True}


def test_balanced_resolution_survives_profile_validation():
    profile = {**PROFILE, 'resolution': 'balanced', 'skipUnusedUnconditional': True}
    assert worker.validate_worker_profile(profile) == profile


@pytest.fixture(autouse=True)
def runtime_hostname(monkeypatch):
    monkeypatch.setattr(worker.socket, 'gethostname', lambda: 'runtime-a')
    monkeypatch.setattr(worker, 'worker_reachable', lambda _: True)
    monkeypatch.setattr(worker, 'installation_complete', lambda root: (root / 'setup-complete.json').exists())


def recover(root, payload):
    return worker.recover(root, payload, expected_hostname='runtime-a')


def test_first_identity_probe_is_read_only_even_with_gpu(tmp_path, monkeypatch):
    monkeypatch.setattr(worker, 'gpu_available', lambda: True)
    spawn = Mock()
    monkeypatch.setattr(worker.subprocess, 'Popen', spawn)
    root = tmp_path / 'new-project'
    assert worker.recover(root, {}) == {
        'state': 'identified', 'hostname': 'runtime-a',
        'gpuAvailable': True, 'projectExists': False,
    }
    assert not root.exists()
    spawn.assert_not_called()


@pytest.mark.parametrize('existing_project', [False, True])
def test_wrong_runtime_never_modifies_files_or_starts_processes(tmp_path, monkeypatch, existing_project):
    root = tmp_path / 'cloud'
    if existing_project:
        root.mkdir()
        (root / 'connection.json').write_text('existing connection')
        (root / 'worker-token.txt').write_text('private token')
    before = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    gpu_check, spawn = Mock(return_value=True), Mock()
    monkeypatch.setattr(worker, 'gpu_available', gpu_check)
    monkeypatch.setattr(worker.subprocess, 'Popen', spawn)
    payload = {'scripts/setup_online_worker.py': base64.b64encode(b'raise RuntimeError()').decode()}
    assert worker.recover(root, payload, expected_hostname='runtime-b') == {
        'state': 'runtime_changed', 'hostname': 'runtime-a', 'expectedHostname': 'runtime-b',
        'gpuAvailable': True, 'projectExists': existing_project,
    }
    assert {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()} == before
    assert root.exists() is existing_project
    gpu_check.assert_called_once()
    spawn.assert_not_called()


def test_no_gpu_means_no_install_or_worker_start(tmp_path, monkeypatch):
    monkeypatch.setattr(worker, 'gpu_available', lambda: False)
    spawn = Mock()
    monkeypatch.setattr(worker.subprocess, 'Popen', spawn)
    assert recover(tmp_path / 'cloud', {})['state'] == 'gpu_unavailable'
    assert not (tmp_path / 'cloud').exists()
    spawn.assert_not_called()


def test_existing_setup_or_inference_is_never_restarted(tmp_path, monkeypatch):
    monkeypatch.setattr(worker, 'gpu_available', lambda: True)
    spawn = Mock()
    monkeypatch.setattr(worker.subprocess, 'Popen', spawn)
    monkeypatch.setattr(worker, 'running', lambda script: script.name == 'setup_online_worker.py')
    assert recover(tmp_path, {})['state'] == 'setting_up'
    monkeypatch.setattr(worker, 'running', lambda script: script.name == 'online_worker.py')
    assert recover(tmp_path, {})['state'] == 'loading'
    (tmp_path / 'connection.json').write_text(json.dumps({'url': 'https://private.gradio.live'}))
    (tmp_path / 'worker-token.txt').write_text('x' * 48)
    assert recover(tmp_path, {})['state'] == 'ready'
    spawn.assert_not_called()


def test_expired_files_are_restored_then_worker_started_with_bounded_retries(tmp_path, monkeypatch):
    monkeypatch.setattr(worker, 'gpu_available', lambda: True)
    monkeypatch.setattr(worker, 'running', lambda _: False)
    spawn = Mock(return_value=Mock(pid=123))
    monkeypatch.setattr(worker.subprocess, 'Popen', spawn)
    payload = {'scripts/setup_online_worker.py': base64.b64encode(b'# pinned setup').decode()}
    assert recover(tmp_path, payload)['state'] == 'setting_up'
    assert (tmp_path / 'scripts/setup_online_worker.py').read_text() == '# pinned setup'
    assert len((tmp_path / 'worker-token.txt').read_text()) >= 32
    recover(tmp_path, payload)
    recover(tmp_path, payload)
    assert recover(tmp_path, payload)['state'] == 'setup_failed'
    assert spawn.call_count == 3
    (tmp_path / 'setup-complete.json').write_text('{}')
    (tmp_path / 'connection.json').write_text('{}')
    assert recover(tmp_path, payload)['state'] == 'loading'
    assert spawn.call_count == 4
    assert not (tmp_path / 'connection.json').exists()
    assert spawn.call_args.args[0][-1].endswith('online_worker.py')


@pytest.mark.parametrize('invalid', [
    [], {}, {**PROFILE, 'unknown': True},
    {**PROFILE, 'precision': 'fp32'}, {**PROFILE, 'precision': ['fp16']},
    {**PROFILE, 'resolution': 'tiny'}, {**PROFILE, 'resolution': None},
    {**PROFILE, 'cropPerson': 'false'}, {**PROFILE, 'skipUnusedUnconditional': 0},
    {**PROFILE, 'segmentationFree': 1}, {**PROFILE, 'guidanceScale': True},
    {**PROFILE, 'guidanceScale': '1.5'}, {**PROFILE, 'guidanceScale': float('nan')},
    {**PROFILE, 'guidanceScale': float('inf')}, {**PROFILE, 'guidanceScale': 2.0},
])
def test_invalid_profile_cannot_create_files_or_touch_processes(tmp_path, monkeypatch, invalid):
    gpu, processes, spawn = Mock(), Mock(), Mock()
    monkeypatch.setattr(worker, 'gpu_available', gpu)
    monkeypatch.setattr(worker, 'running', processes)
    monkeypatch.setattr(worker.subprocess, 'Popen', spawn)
    root = tmp_path / 'new-project'
    with pytest.raises(ValueError, match='[Pp]rofile'):
        worker.recover(root, {}, 'runtime-a', invalid)
    assert not root.exists()
    gpu.assert_not_called()
    processes.assert_not_called()
    spawn.assert_not_called()


@pytest.mark.parametrize('script', ['setup_online_worker.py', 'online_worker.py'])
@pytest.mark.parametrize('existing_profile', [False, True])
def test_running_process_prevents_profile_or_source_writes(tmp_path, monkeypatch, script, existing_profile):
    monkeypatch.setattr(worker, 'gpu_available', lambda: True)
    monkeypatch.setattr(worker, 'running', lambda path: path.name == script)
    launch = Mock()
    monkeypatch.setattr(worker, 'launch', launch)
    config = tmp_path / 'worker-config.json'
    if existing_profile:
        config.write_text('{"precision": "upstream"}')
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()}
    payload = {'scripts/online_worker.py': base64.b64encode(b'# new source').decode()}
    worker.recover(tmp_path, payload, 'runtime-a', PROFILE)
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()} == before
    assert not (tmp_path / 'scripts').exists()
    launch.assert_not_called()


def test_profile_seed_persists_across_setup_worker_and_operator_changes(tmp_path, monkeypatch):
    monkeypatch.setattr(worker, 'gpu_available', lambda: True)
    monkeypatch.setattr(worker, 'running', lambda _: False)
    launches = []
    def launch(root, kind):
        # The configured profile is already on disk when either process starts.
        launches.append((kind, json.loads((root / 'worker-config.json').read_text())))
        return {'state': 'setting_up' if kind == 'setup' else 'loading'}
    monkeypatch.setattr(worker, 'launch', launch)
    assert worker.recover(tmp_path, {}, 'runtime-a', PROFILE)['state'] == 'setting_up'
    config = tmp_path / 'worker-config.json'
    original = config.read_bytes()
    original_mtime = config.stat().st_mtime_ns
    (tmp_path / 'setup-complete.json').write_text('{}')
    assert worker.recover(tmp_path, {}, 'runtime-a', PROFILE)['state'] == 'loading'
    assert config.read_bytes() == original
    assert config.stat().st_mtime_ns == original_mtime
    assert launches == [('setup', PROFILE), ('worker', PROFILE)]
    # Explicit experimental settings already in Colab must remain untouched.
    override = {**PROFILE, 'guidanceScale': 1.0, 'resolution': 'fast', 'cropPerson': True}
    config.write_text(json.dumps(override))
    modified = config.read_bytes()
    worker.recover(tmp_path, {}, 'runtime-a', PROFILE)
    assert config.read_bytes() == modified
    assert launches[-1] == ('worker', override)


def test_invalid_sources_do_not_partially_seed_worker_profile(tmp_path, monkeypatch):
    monkeypatch.setattr(worker, 'gpu_available', lambda: True)
    monkeypatch.setattr(worker, 'running', lambda _: False)
    root = tmp_path / 'new-project'
    payload = {'scripts/online_worker.py': base64.b64encode(b'# valid').decode(),
               '../outside.py': base64.b64encode(b'# invalid path').decode()}
    with pytest.raises(ValueError, match='source path'):
        worker.recover(root, payload, 'runtime-a', PROFILE)
    assert not root.exists()


def test_legacy_recovery_does_not_create_a_profile(tmp_path, monkeypatch):
    monkeypatch.setattr(worker, 'gpu_available', lambda: True)
    monkeypatch.setattr(worker, 'running', lambda _: False)
    monkeypatch.setattr(worker, 'launch', lambda *_: {'state': 'setting_up'})
    recover(tmp_path, {})
    assert not (tmp_path / 'worker-config.json').exists()


def test_stale_tunnel_never_restarts_an_active_inference(tmp_path, monkeypatch):
    (tmp_path / 'active-generation.json').write_text('{"runPath":"preserved"}')
    kill = Mock()
    monkeypatch.setattr(worker.os, 'kill', kill)
    assert worker.repair_stale_worker(tmp_path)['state'] == 'notebook_busy'
    assert not (tmp_path / 'tunnel-failures.json').exists()
    kill.assert_not_called()


def test_idle_stale_tunnel_needs_three_spaced_failures(tmp_path, monkeypatch):
    clock = [1000.]
    monkeypatch.setattr(worker.time, 'time', lambda: clock[0])
    command = tmp_path / '123' / 'cmdline'
    command.parent.mkdir()
    command.write_bytes(b'python\0' + str(tmp_path / 'scripts/online_worker.py').encode() + b'\0')
    monkeypatch.setattr(worker.Path, 'glob', lambda *_: [command])
    kill = Mock()
    monkeypatch.setattr(worker.os, 'kill', kill)
    worker.repair_stale_worker(tmp_path)
    worker.repair_stale_worker(tmp_path)
    clock[0] += 31
    worker.repair_stale_worker(tmp_path)
    kill.assert_not_called()
    clock[0] += 31
    worker.repair_stale_worker(tmp_path)
    kill.assert_called_once_with(123, worker.signal.SIGTERM)


def test_stale_pid_cannot_kill_an_unrelated_process(tmp_path, monkeypatch):
    command = tmp_path / '123' / 'cmdline'
    command.parent.mkdir()
    command.write_bytes(b'python\0someone-elses-project.py\0')
    (tmp_path / 'tunnel-failures.json').write_text(json.dumps({'attempts': [worker.time.time()-90, worker.time.time()-45]}))
    monkeypatch.setattr(worker.Path, 'glob', lambda *_: [command])
    kill = Mock()
    monkeypatch.setattr(worker.os, 'kill', kill)
    worker.repair_stale_worker(tmp_path)
    kill.assert_not_called()
