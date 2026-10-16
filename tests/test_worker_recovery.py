"""Colab process recovery uses fakes; these tests never touch CUDA."""
import base64
import json
from unittest.mock import Mock

from scripts import colab_worker_recovery as worker


def test_no_gpu_means_no_install_or_worker_start(tmp_path, monkeypatch):
    monkeypatch.setattr(worker, 'gpu_available', lambda: False)
    spawn = Mock()
    monkeypatch.setattr(worker.subprocess, 'Popen', spawn)
    assert worker.recover(tmp_path / 'cloud', {})['state'] == 'gpu_unavailable'
    assert not (tmp_path / 'cloud').exists()
    spawn.assert_not_called()


def test_existing_setup_or_inference_is_never_restarted(tmp_path, monkeypatch):
    monkeypatch.setattr(worker, 'gpu_available', lambda: True)
    spawn = Mock()
    monkeypatch.setattr(worker.subprocess, 'Popen', spawn)
    monkeypatch.setattr(worker, 'running', lambda script: script.name == 'setup_online_worker.py')
    assert worker.recover(tmp_path, {})['state'] == 'setting_up'
    monkeypatch.setattr(worker, 'running', lambda script: script.name == 'online_worker.py')
    assert worker.recover(tmp_path, {})['state'] == 'loading'
    (tmp_path / 'connection.json').write_text(json.dumps({'url': 'https://private.gradio.live'}))
    (tmp_path / 'worker-token.txt').write_text('x' * 48)
    assert worker.recover(tmp_path, {})['state'] == 'ready'
    spawn.assert_not_called()


def test_expired_files_are_restored_then_worker_started_with_bounded_retries(tmp_path, monkeypatch):
    monkeypatch.setattr(worker, 'gpu_available', lambda: True)
    monkeypatch.setattr(worker, 'running', lambda _: False)
    spawn = Mock(return_value=Mock(pid=123))
    monkeypatch.setattr(worker.subprocess, 'Popen', spawn)
    payload = {'scripts/setup_online_worker.py': base64.b64encode(b'# pinned setup').decode()}
    assert worker.recover(tmp_path, payload)['state'] == 'setting_up'
    assert (tmp_path / 'scripts/setup_online_worker.py').read_text() == '# pinned setup'
    assert len((tmp_path / 'worker-token.txt').read_text()) >= 32
    worker.recover(tmp_path, payload)
    worker.recover(tmp_path, payload)
    assert worker.recover(tmp_path, payload)['state'] == 'setup_failed'
    assert spawn.call_count == 3
    (tmp_path / 'setup-complete.json').write_text('{}')
    (tmp_path / 'connection.json').write_text('{}')
    assert worker.recover(tmp_path, payload)['state'] == 'loading'
    assert spawn.call_count == 4
    assert not (tmp_path / 'connection.json').exists()
    assert spawn.call_args.args[0][-1].endswith('online_worker.py')
