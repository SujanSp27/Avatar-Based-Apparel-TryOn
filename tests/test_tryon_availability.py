"""Recovery/health failures are simulated; these tests never initialize CUDA."""
import json
from unittest.mock import Mock

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app import colab_connection, main
from backend.app.colab_connection import ColabConnection
from backend.app.online_vton import OnlineTryOn
from ml.errors import PipelineError
from scripts import auto_connect_colab as module
from scripts.auto_connect_colab import ColabRecovery

REVISION = '7720683168567eb5a2a4c67f15116c6e29c83ded'


def test_replacement_requires_repeated_spaced_gpu_identity(tmp_path, monkeypatch):
    clock = [1000.]
    monkeypatch.setattr(module.time, 'time', lambda: clock[0])
    recovery = ColabRecovery(tmp_path, tmp_path / 'connection.json')
    state = {'expectedHostname': 'old'}
    bridge = {'createTime': 100}
    reply = {'hostname': 'new', 'state': 'runtime_changed', 'gpuAvailable': True}
    recovery._verify_replacement(state, reply, bridge)
    assert state['expectedHostname'] == 'old'
    recovery._verify_replacement(state, reply, bridge)
    assert state['candidate']['observations'] == 1
    clock[0] += 15
    recovery._verify_replacement(state, reply, bridge)
    assert state['expectedHostname'] == 'new'
    assert state['pinSource'] == 'verified_replacement'
    assert not recovery.connection_path.exists()  # Never trusts mismatching credentials.


@pytest.mark.parametrize('change', ['hostname', 'bridge', 'no_gpu', 'busy'])
def test_replacement_never_switches_unverified_or_active_work(tmp_path, monkeypatch, change):
    clock = [1000.]
    monkeypatch.setattr(module.time, 'time', lambda: clock[0])
    recovery = ColabRecovery(tmp_path, tmp_path / 'connection.json')
    state, bridge = {'expectedHostname': 'old'}, {'createTime': 100}
    reply = {'hostname': 'new', 'state': 'runtime_changed', 'gpuAvailable': True}
    recovery._verify_replacement(state, reply, bridge)
    clock[0] += 15
    if change == 'hostname':
        reply['hostname'] = 'another'
    elif change == 'bridge':
        bridge['createTime'] += 1
    elif change == 'no_gpu':
        reply['gpuAvailable'] = False
    else:
        path = tmp_path / '.runtime/tryon-jobs/job.json'
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({'status': 'processing'}))
    recovery._verify_replacement(state, reply, bridge)
    assert state['expectedHostname'] == 'old'


def test_delayed_request_is_retained_without_replay(tmp_path, monkeypatch):
    recovery = ColabRecovery(tmp_path, tmp_path / 'connection.json')
    recovery._save({'request': 'pending', 'stage': 'probe', 'submittedAt': 1})
    monkeypatch.setattr(module.bridge, 'STATE', tmp_path)
    monkeypatch.setattr(module.bridge, 'status', lambda: {'processAlive': True, 'status': 'processing'})
    submit = Mock()
    monkeypatch.setattr(module.bridge, 'submit', submit)
    assert recovery.tick() == 'recovery_delayed'
    assert json.loads(recovery.state_path.read_text())['request'] == 'pending'
    submit.assert_not_called()


def test_stale_ready_expires_and_retry_is_coalesced(monkeypatch):
    worker = Mock(availability=Mock(return_value={'available': True}))
    recovery = Mock()
    manager = ColabConnection(worker, recovery)
    manager.check()
    assert manager.snapshot()['displayState'] == 'Ready'
    manager._updated_at -= 31
    assert not manager.snapshot()['available']
    assert manager.snapshot()['connectionState'] == 'stale'
    manager.retry()
    first = manager._last_retry
    manager.retry()
    assert manager._last_retry == first
    assert manager._wake.is_set()
    manager.check()
    assert manager.snapshot()['available']
    assert recovery.next_attempt == 0


def test_prolonged_preparation_is_an_honest_outage():
    manager = ColabConnection(Mock(availability=Mock(return_value={'available': False})), Mock())
    manager._unavailable_since -= 181
    assert manager.snapshot()['displayState'] == 'Temporarily unavailable'


@pytest.mark.parametrize('body', [
    {'named_endpoints': {'/generate': {}}}, {'data': [{'ready': False}]},
    {'data': [{'ready': True, 'device': 'cpu', 'modelRevision': REVISION}]},
    {'data': [{'ready': True, 'device': 'cuda', 'modelRevision': 'wrong'}]},
    {'data': []}, None,
])
def test_endpoint_existence_is_not_model_readiness(body):
    worker = OnlineTryOn('https://private.gradio.live', 'x' * 48,
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=body)))
    assert not worker.availability(check_connection=True)['available']


def test_readiness_checks_auth_and_invalidates_on_rotated_credentials():
    calls = []
    def respond(request):
        calls.append(request)
        assert request.url.path == '/gradio_api/run/status'
        ready = json.loads(request.content)['data'][0] == 'x' * 48
        return httpx.Response(200, json={'data': [{'ready': ready, 'device': 'cuda', 'modelRevision': REVISION}]})
    worker = OnlineTryOn('https://private.gradio.live', 'x' * 48, transport=httpx.MockTransport(respond))
    assert worker.availability(check_connection=True)['available']
    assert worker.availability(check_connection=True)['available']
    assert len(calls) == 1
    worker.token = 'y' * 48
    assert not worker.availability(check_connection=True)['available']
    worker.url, worker.token = 'https://replacement.gradio.live', 'x' * 48
    assert worker.availability(check_connection=True)['available']
    assert len(calls) == 3


def test_health_timeout_is_bounded_and_unavailable():
    def timeout(request):
        assert request.extensions['timeout']['read'] == 4
        raise httpx.ReadTimeout('simulated offline worker')
    worker = OnlineTryOn('https://private.gradio.live', 'x' * 48, transport=httpx.MockTransport(timeout))
    assert not worker.availability(check_connection=True)['available']


def test_retry_and_availability_do_not_require_database(monkeypatch):
    manager = ColabConnection(Mock(availability=Mock(return_value={'available': False})), Mock())
    monkeypatch.setattr(main, 'connection', manager)
    client = TestClient(main.app)
    try:
        assert client.get('/api/tryon/availability').status_code == 200
        assert client.post('/api/tryon/retry').status_code == 202
        assert not client.get('/api/tryon/availability').json()['available']
    finally:
        client.close()


def test_new_job_rejected_until_live_model_ready(monkeypatch):
    monkeypatch.setattr(main.pipeline.worker, 'availability', lambda **_: {'available': False})
    manager = Mock(snapshot=Mock(return_value={'reason': 'GPU unavailable'}))
    monkeypatch.setattr(main, 'connection', manager)
    with pytest.raises(PipelineError) as error:
        main.require_tryon_ready()
    assert error.value.status_code == 503
    manager.retry.assert_called_once()
