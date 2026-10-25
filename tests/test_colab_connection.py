"""Automatic reconnection contracts; no GPU or notebook is used by these tests."""
import ast
import json
from unittest.mock import Mock

import pytest

from backend.app.colab_connection import ColabConnection
from backend.app.config import settings
from scripts import auto_connect_colab as recovery_module
from scripts.auto_connect_colab import ColabRecovery
from scripts.connect_online_worker import save_connection


def test_saved_url_is_not_ready_until_live_check_passes(monkeypatch):
    monkeypatch.setattr(settings, 'online_auto_connect', True)
    worker = Mock()
    worker.availability.return_value = {'available': True, 'localGpuUsed': False}
    recovery = Mock()
    manager = ColabConnection(worker, recovery)
    assert not manager.snapshot()['available']
    manager.check()
    assert manager.snapshot()['connectionState'] == 'ready'
    recovery.tick.assert_not_called()
    worker.availability.return_value = {'available': False, 'localGpuUsed': False}
    recovery.tick.return_value = 'loading'
    manager.check()
    assert not manager.snapshot()['available']
    assert manager.snapshot()['connectionState'] == 'loading'
    assert manager.snapshot()['localGpuUsed'] is False
    worker.availability.return_value = {'available': True}
    manager.check()
    assert manager.snapshot()['available']


def test_adopted_url_still_requires_live_validation():
    worker = Mock()
    worker.availability.return_value = {'available': False}
    recovery = Mock()
    recovery.tick.return_value = 'ready'
    manager = ColabConnection(worker, recovery)
    manager.check()
    assert not manager.snapshot()['available']
    assert manager.snapshot()['connectionState'] == 'checking_tunnel'


@pytest.mark.parametrize('state', ['runtime_expired', 'gpu_unavailable', 'browser_required', 'runtime_changed', 'recovery_failed'])
def test_external_runtime_constraints_are_reported_honestly(state):
    worker = Mock()
    worker.availability.return_value = {'available': False}
    manager = ColabConnection(worker, Mock(tick=Mock(return_value=state)))
    manager.check()
    assert not manager.snapshot()['available']
    assert manager.snapshot()['connectionState'] == state
    assert manager.snapshot()['reason']


def test_notebook_exception_overrides_stale_progress(tmp_path, bridge):
    _, requests, reply = bridge
    recovery = ColabRecovery(tmp_path, tmp_path / 'connection.json')
    recovery._submit({}, 'probe', 'run_code_cell', {'cellId': 'owned'})
    reply({'outputs': [
        {'output_type': 'stream', 'text': ['{"state":"loading","hostname":"known"}\n']},
        {'output_type': 'error', 'ename': 'AttributeError', 'evalue': 'private detail'},
    ]})
    assert recovery.tick() == 'recovery_failed'
    assert len(requests) == 1
    saved = recovery.state_path.read_text()
    assert 'private detail' not in saved
    assert json.loads(saved)['lastReplyState'] == 'recovery_failed'
    assert recovery.tick() is None


@pytest.fixture
def bridge(tmp_path, monkeypatch):
    root = tmp_path / '.runtime/colab-bridge'
    (root / 'responses').mkdir(parents=True)
    (root / 'connection.json').write_text(json.dumps({
        'notebookUrl': 'https://colab.research.google.com/drive/existing_notebook_123',
    }))
    monkeypatch.setattr(recovery_module.bridge, 'STATE', root)
    current = {'processAlive': True, 'status': 'ready', 'notebookToolsAvailable': True,
               'createTime': 1234}
    monkeypatch.setattr(recovery_module.bridge, 'status', lambda: current)
    requests = []
    def submit(payload):
        requests.append(payload)
        return str(len(requests))
    monkeypatch.setattr(recovery_module.bridge, 'submit', submit)
    def reply(output):
        request = str(len(requests))
        (root / 'responses' / f'{request}.json').write_text('{}')
        monkeypatch.setattr(recovery_module, 'result', lambda _: output)
    return current, requests, reply


def test_recovery_resumes_pending_request_after_restart_without_replay(tmp_path, bridge):
    _, requests, reply = bridge
    target = tmp_path / '.runtime/online-connection.json'
    recovery = ColabRecovery(tmp_path, target)
    recovery.tick()
    assert requests[0]['name'] == 'get_cells'
    # Simulate an API restart while this exact notebook call is still pending.
    recovery = ColabRecovery(tmp_path, target)
    recovery.tick()
    assert len(requests) == 1
    reply({'cells': [{'id': 'owned-cell', 'source': [recovery_module.recovery_source()]}]})
    recovery.tick()
    assert requests[-1]['name'] == 'run_code_cell'
    assert requests[-1]['arguments'] == {'cellId': 'owned-cell'}
    reply({'outputs': [{'output_type': 'stream', 'text': [json.dumps({
        'state': 'identified', 'hostname': 'runtime-a', 'gpuAvailable': True,
    })]}]})
    assert recovery.tick() == 'connecting'
    assert not target.exists()
    assert json.loads(recovery.state_path.read_text())['expectedHostname'] == 'runtime-a'
    # A fresh process retains the pin and must send it into the recovery cell.
    recovery = ColabRecovery(tmp_path, target)
    recovery.tick()
    reply({'cells': [{'id': 'owned-cell', 'source': [recovery_module.recovery_source()]}]})
    recovery.tick()
    assert requests[-1]['name'] == 'update_cell'
    assert "expected_hostname='runtime-a'" in requests[-1]['arguments']['content']
    reply({})
    recovery.tick()
    assert requests[-1]['name'] == 'run_code_cell'
    connection = {'url': 'https://private.gradio.live', 'token': 'x' * 48}
    reply({'outputs': [{'output_type': 'stream', 'text': [json.dumps({
        'state': 'ready', 'connection': connection, 'hostname': 'runtime-a',
    })]}]})
    assert recovery.tick() == 'ready'
    assert json.loads(target.read_text()) == connection
    assert 'token' not in recovery.state_path.read_text()
    recovery.tick()
    assert len(requests) == 5


def test_changed_runtime_cannot_replace_pin_or_adopt_credentials(tmp_path, bridge):
    _, requests, reply = bridge
    target = tmp_path / 'worker.json'
    target.write_text('existing private connection')
    recovery = ColabRecovery(tmp_path, target)
    recovery._submit({'expectedHostname': 'runtime-a'}, 'probe', 'run_code_cell', {'cellId': 'owned-cell'})
    reply({'outputs': [{'output_type': 'stream', 'text': [json.dumps({
        'state': 'ready', 'hostname': 'runtime-b',
        'connection': {'url': 'https://other.gradio.live', 'token': 'x' * 48},
    })]}]})
    assert recovery.tick() == 'runtime_changed'
    state = json.loads(recovery.state_path.read_text())
    assert state['expectedHostname'] == 'runtime-a'
    assert state['observedHostname'] == 'runtime-b'
    assert target.read_text() == 'existing private connection'
    assert 'token' not in recovery.state_path.read_text()
    recovery.tick()
    assert len(requests) == 1


def test_old_pending_reply_without_identity_cannot_adopt_credentials(tmp_path, bridge):
    _, _, reply = bridge
    target = tmp_path / 'worker.json'
    recovery = ColabRecovery(tmp_path, target)
    recovery._submit({}, 'probe', 'run_code_cell', {'cellId': 'old-cell'})
    reply({'outputs': [{'output_type': 'stream', 'text': [json.dumps({
        'state': 'ready', 'connection': {'url': 'https://other.gradio.live', 'token': 'x' * 48},
    })]}]})
    assert recovery.tick() == 'connecting'
    assert not target.exists()
    assert 'expectedHostname' not in json.loads(recovery.state_path.read_text())


@pytest.mark.parametrize('stage', ['insert', 'updated'])
@pytest.mark.parametrize('old_protocol', [None, 3])
def test_pre_upgrade_cell_is_never_executed_on_resume(tmp_path, bridge, stage, old_protocol):
    _, requests, reply = bridge
    recovery = ColabRecovery(tmp_path, tmp_path / 'worker.json')
    recovery._submit({}, stage, 'add_code_cell', {})
    state = json.loads(recovery.state_path.read_text())
    state['recoveryProtocol'] = old_protocol
    recovery._save(state)
    reply({'newCellId': 'unsafe-old-cell'})
    assert recovery.tick() == 'connecting'
    assert len(requests) == 1
    recovery.tick()
    assert requests[-1]['name'] == 'get_cells'


def test_recovery_cell_embeds_persistent_profile_and_runtime_pin():
    source = recovery_module.recovery_source('runtime-a')
    tree = ast.parse(source)
    call = next(node for node in ast.walk(tree) if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name) and node.func.id == 'recover')
    keywords = {kw.arg: ast.literal_eval(kw.value) for kw in call.keywords}
    assert keywords['expected_hostname'] == 'runtime-a'
    assert keywords['worker_profile'] == {
        'precision': 'fp16', 'resolution': 'native', 'cropPerson': False,
        'guidanceScale': 1.5, 'skipUnusedUnconditional': True, 'segmentationFree': True,
    }
    # Stable source avoids repeated cell updates between recovery cycles.
    assert recovery_module.recovery_source('runtime-a') == source


def test_recovery_rejects_invalid_local_profile_before_reading_payload(monkeypatch):
    root = Mock()
    monkeypatch.setattr(recovery_module.bridge, 'ROOT', root)
    with pytest.raises(ValueError, match='profile'):
        recovery_module.recovery_source('runtime-a', {'precision': 'fp16'})
    root.assert_not_called()


def test_recovery_supports_explicit_valid_profile_for_operator_experiments():
    profile = {'precision': 'fp16', 'resolution': 'fast', 'cropPerson': True,
               'guidanceScale': 1.0, 'skipUnusedUnconditional': True, 'segmentationFree': False}
    tree = ast.parse(recovery_module.recovery_source('runtime-a', profile))
    call = next(node for node in ast.walk(tree) if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name) and node.func.id == 'recover')
    assert ast.literal_eval(next(kw.value for kw in call.keywords if kw.arg == 'worker_profile')) == profile


def test_runtime_pin_only_changes_by_explicit_operator_action(tmp_path, bridge):
    current, _, _ = bridge
    recovery = ColabRecovery(tmp_path, tmp_path / 'worker.json')
    recovery._save({'expectedHostname': 'runtime-a', 'request': 'pending'})
    with pytest.raises(RuntimeError, match='pending'):
        recovery.pin_runtime('runtime-b')
    assert json.loads(recovery.state_path.read_text())['expectedHostname'] == 'runtime-a'
    recovery._save({'expectedHostname': 'runtime-a'})
    current['status'] = 'processing'
    with pytest.raises(RuntimeError, match='pending'):
        recovery.pin_runtime('runtime-b')
    current['status'] = 'ready'
    recovery.pin_runtime('runtime-b')
    state = json.loads(recovery.state_path.read_text())
    assert state['expectedHostname'] == 'runtime-b'
    assert state['previousHostname'] == 'runtime-a'
    assert state['pinSource'] == 'operator'
    with pytest.raises(ValueError, match='hostname'):
        recovery.pin_runtime('')


def test_busy_notebook_and_existing_open_prompt_are_not_duplicated(tmp_path, bridge):
    current, requests, reply = bridge
    recovery = ColabRecovery(tmp_path, tmp_path / 'worker.json')
    current['status'] = 'processing'
    assert recovery.tick() == 'notebook_busy'
    assert not requests
    current.update(status='ready', notebookToolsAvailable=False)
    recovery.tick()
    assert requests[-1]['name'] == 'open_colab_browser_connection'
    reply({'result': False})
    recovery.tick()
    assert recovery.tick() == 'browser_required'
    assert len(requests) == 1


def test_recovery_adds_only_its_own_cell(tmp_path, bridge):
    _, requests, reply = bridge
    recovery = ColabRecovery(tmp_path, tmp_path / 'worker.json')
    recovery.tick()
    reply({'cells': [{'id': 'user-cell', 'source': ['print("keep")']}]})
    recovery.tick()
    assert requests[-1]['name'] == 'add_code_cell'
    assert requests[-1]['arguments']['cellIndex'] == 1
    compile(requests[-1]['arguments']['code'], '<recovery-cell>', 'exec')
    reply({'newCellId': 'owned-cell'})
    recovery.tick()
    assert requests[-1]['arguments'] == {'cellId': 'owned-cell'}


def test_successful_browser_connection_can_reopen_after_socket_loss(tmp_path, bridge):
    current, requests, reply = bridge
    current['notebookToolsAvailable'] = False
    recovery = ColabRecovery(tmp_path, tmp_path / 'worker.json')
    recovery.tick()
    reply({'result': True})
    recovery.tick()
    state = json.loads(recovery.state_path.read_text())
    assert 'openedBridge' not in state
    assert len(state['openAttempts']) == 1
    # A transient disconnect cannot create a burst of browser tabs.
    recovery.next_attempt = 0
    recovery.tick()
    assert len(requests) == 1


@pytest.mark.parametrize(('stage', 'expected'), [
    ('open', 'browser_required'), ('cells', 'checking_notebook'),
    ('insert', 'checking_notebook'), ('updated', 'checking_notebook'),
    ('probe', 'restoring_worker'),
])
def test_pending_stage_is_specific_and_never_replayed(tmp_path, bridge, stage, expected):
    _, requests, _ = bridge
    recovery = ColabRecovery(tmp_path, tmp_path / 'worker.json')
    recovery._submit({}, stage, 'run_code_cell', {'cellId': 'owned'})
    assert recovery.tick() == expected
    assert recovery.tick() == expected
    assert len(requests) == 1
    assert json.loads(recovery.state_path.read_text())['request'] == '1'


@pytest.mark.parametrize('connected', [False, True])
def test_failed_bridge_step_reports_real_state_and_backs_off(tmp_path, bridge, monkeypatch, connected):
    current, requests, reply = bridge
    recovery = ColabRecovery(tmp_path, tmp_path / 'worker.json')
    recovery._submit({}, 'insert', 'add_code_cell', {})
    reply({})
    current['notebookToolsAvailable'] = connected
    def failed(_):
        raise RuntimeError('private notebook details must not reach UI or state')
    monkeypatch.setattr(recovery_module, 'result', failed)
    expected = 'recovery_failed' if connected else 'browser_required'
    assert recovery.tick() == expected
    state = json.loads(recovery.state_path.read_text())
    assert state['lastFailedStage'] == 'insert'
    assert state['lastReplyState'] == expected
    assert 'private notebook details' not in recovery.state_path.read_text()
    assert 'request' not in state
    assert recovery.tick() is None
    assert len(requests) == 1
    # A completed failure can be safely reconciled by reading the notebook,
    # instead of blindly replaying the failed insert or execution.
    current['notebookToolsAvailable'] = True
    recovery.next_attempt = 0
    assert recovery.tick() == 'checking_notebook'
    assert requests[-1]['name'] == 'get_cells'


def test_restoring_state_becomes_ready_only_after_live_gpu_check():
    worker = Mock(availability=Mock(return_value={'available': False}))
    manager = ColabConnection(worker, Mock(tick=Mock(return_value='restoring_worker')))
    manager.check()
    assert manager.snapshot()['displayState'] == 'Recovering'
    assert 'restoring' in manager.snapshot()['reason']
    manager._unavailable_since -= 181
    assert manager.snapshot()['displayState'] == 'Temporarily unavailable'
    assert manager.snapshot()['unavailableSeconds'] >= 181
    worker.availability.return_value = {'available': True}
    manager.check()
    assert manager.snapshot()['displayState'] == 'Ready'
    assert manager.snapshot()['unavailableSeconds'] == 0


@pytest.mark.parametrize(('state', 'seconds'), [
    ('checking_notebook', 1), ('restoring_worker', 3), ('ready', 10), ('recovery_failed', 10),
])
def test_monitor_advances_staging_quickly_without_busy_polling(state, seconds):
    manager = ColabConnection(Mock(availability=Mock(return_value={'available': False})), Mock())
    manager._snapshot['connectionState'] = state
    manager.check = Mock()
    manager._wake = Mock()
    manager._wake.wait.side_effect = lambda _: manager._stop.set()
    manager._run()
    manager._wake.wait.assert_called_once_with(seconds)
    manager.check.assert_called_once()


@pytest.mark.parametrize('url', ['http://private.gradio.live', 'https://attacker.test',
                                'https://private.gradio.live?token=secret',
                                'https://user:password@private.gradio.live'])
def test_invalid_recovered_url_cannot_replace_working_credentials(tmp_path, url):
    path = tmp_path / 'connection.json'
    path.write_text('existing credentials')
    with pytest.raises(ValueError):
        save_connection({'url': url, 'token': 'x' * 40}, path)
    assert path.read_text() == 'existing credentials'
