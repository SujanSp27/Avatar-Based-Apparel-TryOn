"""Colab process recovery uses fakes; these tests never touch CUDA."""
import base64
import json
from unittest.mock import Mock

import pytest

from scripts import colab_worker_recovery as worker


@pytest.fixture(autouse=True)
def runtime_hostname(monkeypatch):
    monkeypatch.setattr(worker.socket, 'gethostname', lambda: 'runtime-a')


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
    gpu_check, spawn = Mock(), Mock()
    monkeypatch.setattr(worker, 'gpu_available', gpu_check)
    monkeypatch.setattr(worker.subprocess, 'Popen', spawn)
    payload = {'scripts/setup_online_worker.py': base64.b64encode(b'raise RuntimeError()').decode()}
    assert worker.recover(root, payload, expected_hostname='runtime-b') == {
        'state': 'runtime_changed', 'hostname': 'runtime-a', 'expectedHostname': 'runtime-b',
    }
    assert {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()} == before
    assert root.exists() is existing_project
    gpu_check.assert_not_called()
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
