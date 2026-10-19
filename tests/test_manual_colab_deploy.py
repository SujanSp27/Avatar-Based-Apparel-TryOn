"""Manual deployment safety using local fakes only; no notebook or CUDA calls."""
import ast
import json
import os
import subprocess
import sys
from unittest.mock import Mock

import pytest

from scripts import deploy_online_colab as deploy


@pytest.fixture
def project(tmp_path):
    (tmp_path / '.runtime').mkdir()
    (tmp_path / '.runtime/colab-autoconnect.json').write_text(json.dumps({'expectedHostname': 'runtime-a'}))
    (tmp_path / 'config').mkdir()
    (tmp_path / 'config/online-worker.json').write_text(json.dumps({
        'precision': 'fp16', 'resolution': 'native', 'cropPerson': False,
        'guidanceScale': 1.5, 'skipUnusedUnconditional': False, 'segmentationFree': True,
    }))
    return tmp_path


def cell_functions(source):
    """Load the embedded recovery implementation without executing its call."""
    tree = ast.parse(source)
    namespace = {}
    exec(compile(ast.Module(body=tree.body[:-1], type_ignores=[]), '<recovery>', 'exec'), namespace)
    invocation = tree.body[-1].value.args[0].args[0]
    assert invocation.func.id == 'recover'
    kwargs = {item.arg: ast.literal_eval(item.value) for item in invocation.keywords}
    payload = ast.literal_eval(invocation.args[1])
    return namespace, payload, kwargs


@pytest.mark.parametrize('action', ['setup', 'worker'])
def test_manual_commands_embed_pin_and_validated_persistent_profile(project, action):
    source = deploy.deployment_source(action, root=project)
    _, _, kwargs = cell_functions(source)
    assert kwargs['expected_hostname'] == 'runtime-a'
    assert kwargs['worker_profile']['precision'] == 'fp16'
    assert kwargs['worker_profile']['guidanceScale'] == 1.5
    assert not (project / '.runtime/online-worker-token.txt').exists()


@pytest.mark.parametrize('state', [{}, {'expectedHostname': '../unsafe'},
                                   {'expectedHostname': 'runtime-a', 'request': 'unfinished'}])
def test_manual_deployment_rejects_unpinned_or_pending_state(project, state):
    (project / '.runtime/colab-autoconnect.json').write_text(json.dumps(state))
    with pytest.raises(RuntimeError):
        deploy.deployment_source('worker', root=project)
    assert not (project / '.runtime/online-worker-token.txt').exists()


def test_invalid_profile_rejected_before_building_deployment_cell(project):
    with pytest.raises(ValueError, match='precision'):
        deploy.deployment_source('worker', precision='invalid', root=project)


@pytest.mark.parametrize('action', ['setup', 'worker'])
def test_generated_manual_cell_preserves_files_on_another_runtime(project, monkeypatch, action):
    namespace, payload, kwargs = cell_functions(deploy.deployment_source(action, root=project))
    monkeypatch.setattr(namespace['socket'], 'gethostname', lambda: 'different-runtime')
    spawn = Mock()
    monkeypatch.setattr(namespace['subprocess'], 'Popen', spawn)
    root = project / 'remote-project'
    reply = namespace['recover'](root, payload, **kwargs)
    assert reply['state'] == 'runtime_changed'
    assert not root.exists()
    spawn.assert_not_called()


@pytest.mark.parametrize('action', ['setup', 'worker'])
@pytest.mark.parametrize('running_script', ['setup_online_worker.py', 'online_worker.py'])
def test_manual_cell_never_overwrites_active_sources_token_or_profile(project, monkeypatch, action, running_script):
    namespace, payload, kwargs = cell_functions(deploy.deployment_source(action, precision='upstream', root=project))
    monkeypatch.setattr(namespace['socket'], 'gethostname', lambda: 'runtime-a')
    namespace['gpu_available'] = lambda: True
    namespace['running'] = lambda path: path.name == running_script
    namespace['launch'] = Mock()
    root = project / 'remote-project'
    (root / 'scripts').mkdir(parents=True)
    (root / 'scripts/online_worker.py').write_text('# preserve running version')
    (root / 'worker-config.json').write_text('{"precision":"fp16","guidanceScale":1.0}')
    (root / 'worker-token.txt').write_text('private-running-token')
    (root / 'active-generation.json').write_text('{"runPath":"existing-run"}')
    before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
    namespace['recover'](root, payload, **kwargs)
    assert {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()} == before
    namespace['launch'].assert_not_called()


def test_manual_cell_preserves_idle_existing_profile_and_token(project, monkeypatch):
    namespace, payload, kwargs = cell_functions(deploy.deployment_source('worker', precision='upstream', root=project))
    monkeypatch.setattr(namespace['socket'], 'gethostname', lambda: 'runtime-a')
    namespace['gpu_available'] = lambda: True
    namespace['running'] = lambda _: False
    namespace['launch'] = Mock(return_value={'state': 'loading'})
    root = project / 'remote-project'
    root.mkdir()
    (root / 'setup-complete.json').write_text('{}')
    profile = '{"precision":"fp16","guidanceScale":1.0}'
    (root / 'worker-config.json').write_text(profile)
    (root / 'worker-token.txt').write_text('retained-token')
    namespace['recover'](root, payload, **kwargs)
    assert (root / 'worker-config.json').read_text() == profile
    assert (root / 'worker-token.txt').read_text() == 'retained-token'
    namespace['launch'].assert_called_once_with(root, 'worker')


def test_status_cell_remains_read_only_without_any_pin(project):
    (project / '.runtime/colab-autoconnect.json').unlink()
    tree = ast.parse(deploy.deployment_source('status', root=project))
    calls = [node.func.attr for node in ast.walk(tree)
             if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)]
    assert not {'write_text', 'write_bytes', 'unlink', 'mkdir', 'Popen', 'chmod'}.intersection(calls)
    assert 'read_text' in calls


@pytest.mark.parametrize('cells', [[], [{'id': 'owned', 'source': ['print("changed")']}],
                                    [{'id': 'other', 'source': ['print("expected")']}]])
def test_changed_or_missing_cell_is_never_executed(monkeypatch, cells):
    call = Mock(return_value={'cells': cells})
    monkeypatch.setattr(deploy, 'call', call)
    with pytest.raises(RuntimeError, match='changed or disappeared'):
        deploy.run_unchanged_cell('owned', 'print("expected")')
    call.assert_called_once_with('get_cells', {'includeOutputs': False})


def test_unchanged_cell_runs_once(monkeypatch):
    call = Mock(side_effect=[{'cells': [{'id': 'owned', 'source': ['print("expected")']}]}, {'outputs': []}])
    monkeypatch.setattr(deploy, 'call', call)
    assert deploy.run_unchanged_cell('owned', 'print("expected")') == {'outputs': []}
    assert call.call_count == 2
    assert call.call_args.args == ('run_code_cell', {'cellId': 'owned'})


def test_pending_manual_call_is_not_replayed(project, monkeypatch):
    monkeypatch.setattr(deploy, 'STATE', project / '.runtime/manual-state.json')
    submit = Mock(return_value='request-a')
    monkeypatch.setattr(deploy, 'submit', submit)
    monkeypatch.setattr(deploy, 'wait_for', lambda *_: {'status': 'pending'})
    for _ in range(2):
        with pytest.raises(RuntimeError, match='Request pending: request-a'):
            deploy.call('run_code_cell', {'cellId': 'owned'})
    submit.assert_called_once()
    assert json.loads(deploy.STATE.read_text())['pendingRequest'] == 'request-a'


def test_completed_manual_call_clears_pending_record(project, monkeypatch):
    monkeypatch.setattr(deploy, 'STATE', project / '.runtime/manual-state.json')
    monkeypatch.setattr(deploy, 'submit', lambda _: 'request-a')
    monkeypatch.setattr(deploy, 'wait_for', lambda *_: {'status': 'completed'})
    monkeypatch.setattr(deploy, 'result', lambda _: {'ok': True})
    assert deploy.call('get_cells', {}) == {'ok': True}
    assert 'pendingRequest' not in json.loads(deploy.STATE.read_text())


def test_private_recovery_tokens_are_not_printed():
    secret = 'private-worker-credential'
    output = {'token': secret, 'outputs': [{'text': [json.dumps({'connection': {'token': secret}})]}]}
    assert secret not in json.dumps(deploy.redacted(output))
    assert '[redacted]' in json.dumps(deploy.redacted(output))


@pytest.mark.parametrize('script', ['auto_connect_colab.py', 'deploy_online_colab.py'])
def test_direct_cli_help_imports_outside_repository(tmp_path, script):
    environment = {**os.environ, 'CUDA_VISIBLE_DEVICES': ''}
    completed = subprocess.run([sys.executable, str(deploy.ROOT / 'scripts' / script), '--help'],
                               cwd=tmp_path, env=environment, capture_output=True, text=True, timeout=30)
    assert completed.returncode == 0, completed.stderr
    assert 'usage:' in completed.stdout


@pytest.mark.parametrize('state', ['pending', 'completed'])
def test_recovering_persisted_response_never_resubmits(project, monkeypatch, state):
    monkeypatch.setattr(deploy, 'STATE', project / '.runtime/manual-state.json')
    deploy._save({'pendingRequest': 'request-a'})
    submit = Mock()
    monkeypatch.setattr(deploy, 'submit', submit)
    monkeypatch.setattr(deploy, 'wait_for', lambda *_: {'status': state})
    monkeypatch.setattr(deploy, 'result', lambda _: {'outputs': ['original response']})
    reply = deploy.recover_pending()
    submit.assert_not_called()
    if state == 'pending':
        assert reply == {'state': 'pending', 'request': 'request-a'}
        assert deploy._state()['pendingRequest'] == 'request-a'
    else:
        assert reply == {'outputs': ['original response']}
        assert 'pendingRequest' not in deploy._state()
