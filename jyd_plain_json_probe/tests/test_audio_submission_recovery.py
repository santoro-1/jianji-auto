from __future__ import annotations

from copy import deepcopy
import hashlib
import os
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from jyd_probe.auth_center import AuthCenterConnectionError, AuthCenterError
from jyd_probe.audio_submission_recovery import audio_request_key
from jyd_probe.project_audio import ProjectAudioCoordinator
from jyd_probe.project_store import ProjectStore
from test_project_audio_binding import AudioClient


class LookupClient(AudioClient):
    def __init__(self):
        super().__init__()
        self.lookups = []

    def create_workbench_audio_batch(self, token, payload):
        batch = super().create_workbench_audio_batch(token, payload)
        batch['source_channel'] = 'new_workbench'
        for index, row in enumerate(batch['items']):
            row['item_id'] += f'-{index}'
        return batch

    def lookup_workbench_audio_batch(self, token, request_key):
        self.lookups.append(request_key)
        result = {'schema': 'runninghub.workbench-audio-lookup.v1', 'found': False}
        for index, payload in enumerate(self.requests, 1):
            if payload['request_key'] != request_key:
                continue
            batch = self.batches[f'batch-{index}']
            speech = payload['speech_options']
            return {**result, 'found': True, 'request_key': request_key, 'batch': batch,
                    'input_bindings': {
                        remote['item_id']: {
                            'script_sha256': hashlib.sha256(source['speech_script'].encode()).hexdigest(),
                            'voice_asset_id': speech['voiceAssetId'],
                            'speech_settings': {key: speech[key] for key in (
                                'model', 'speed', 'volume', 'pitch', 'languageBoost', 'outputFormat'
                            )},
                        } for source, remote in zip(payload['rows'], batch['items'])
                    }}
        return result


@pytest.fixture
def setup(tmp_path):
    store = ProjectStore(tmp_path / 'control.db')
    client = LookupClient()
    coordinator = ProjectAudioCoordinator(store, client, storage_root=tmp_path / 'storage', max_audio_bytes=1024)
    project = store.create_project(owner_user_id='user', owner_username='user', name='recovery',
                                   items=[{'row_key': str(i), 'script_text': f'测试{i}。'} for i in (1, 2)])
    project = coordinator.start('user', project['project_id'], 'mock-token', default_voice_asset_id='voice-1',
                                voice_assignments=None, settings={}, idempotency_key='first')
    return store, client, coordinator, project


def retry(coordinator, project, key='again'):
    return coordinator.retry('user', project['project_id'], project['items'][0]['item_id'],
                             'mock-token', idempotency_key=key, settings={'speed': 1.05})


def restart(store, client):
    return ProjectAudioCoordinator(ProjectStore(store.path), client, storage_root=store.path.parent / 'storage', max_audio_bytes=1024)


def lose_response(client, monkeypatch, *, accepted=True, exception=SystemExit):
    original = client.create_workbench_audio_batch
    def interrupted(token, payload):
        if accepted:
            original(token, payload)
        raise exception('simulated exit or lost response')
    monkeypatch.setattr(client, 'create_workbench_audio_batch', interrupted)
    return original


@pytest.mark.parametrize('exception', [SystemExit, AuthCenterConnectionError])
def test_lost_receipt_recovers_original_task_without_paid_resubmission(setup, monkeypatch, exception):
    store, client, coordinator, project = setup
    original_audio = project['items'][0]['outputs']['audio']
    lose_response(client, monkeypatch, exception=exception)
    with pytest.raises((SystemExit, AuthCenterError)):
        retry(coordinator, project)
    restarted = restart(store, client)
    recovered = restarted.sync('user', project['project_id'], 'mock-token')
    assert recovered['operations'][-1]['status'] == 'SUCCEEDED'
    assert recovered['items'][0]['outputs']['audio']['external_ref']['batch_id'] == 'batch-2'
    assert recovered['items'][0]['audio_submission'] is None
    assert Path(original_audio['managed_path']).is_file()
    assert len(client.requests) == 2
    repeated = retry(restarted, recovered)
    assert repeated['items'][0]['outputs'] == recovered['items'][0]['outputs']
    assert len(client.requests) == 2
    assert recovered['items'][1]['outputs'] == project['items'][1]['outputs']


def test_unclaimed_queue_is_retired_and_can_be_explicitly_restarted(setup, monkeypatch):
    store, client, coordinator, project = setup
    original_claim = store.claim_audio_submissions
    def exit_before_claim(*args):
        raise SystemExit('exit before cloud call')
    monkeypatch.setattr(store, 'claim_audio_submissions', exit_before_claim)
    with pytest.raises(SystemExit):
        retry(coordinator, project)
    restarted = restart(store, client)
    after = restarted.sync('user', project['project_id'], 'mock-token')
    assert after['operations'][-1]['status'] == 'FAILED'
    assert after['operations'][-1]['error_code'] == 'AUDIO_NOT_SUBMITTED'
    assert after['items'][0]['outputs'] == project['items'][0]['outputs']
    assert len(client.requests) == 1
    assert client.lookups == []
    assert after['items'][0]['allowed_actions']['generate_audio'] is True
    retry(restarted, after, 'new-confirmed-click')
    assert len(client.requests) == 2


def test_missing_receipt_stays_visible_and_blocks_new_key_but_late_commit_recovers(setup, monkeypatch):
    store, client, coordinator, project = setup
    pending = []
    original = client.create_workbench_audio_batch
    def interrupted(token, payload):
        pending.append(payload)
        raise SystemExit('request may still be processing on cloud')
    monkeypatch.setattr(client, 'create_workbench_audio_batch', interrupted)
    with pytest.raises(SystemExit):
        retry(coordinator, project)
    restarted = restart(store, client)
    after = restarted.sync('user', project['project_id'], 'mock-token')
    assert after['operations'][-1]['status'] == 'FAILED'
    assert after['operations'][-1]['error_code'] == 'AUDIO_SUBMISSION_UNKNOWN'
    assert after['items'][0]['status'] not in {'AUDIO_QUEUED', 'AUDIO_RUNNING'}
    assert after['items'][0]['audio_submission']['status'] == 'UNKNOWN'
    assert after['items'][0]['allowed_actions']['generate_audio'] is False
    assert after['items'][0]['outputs'] == project['items'][0]['outputs']
    with pytest.raises(ValueError, match='避免重复计费'):
        retry(restarted, after, 'another-key')
    assert len(client.requests) == 1
    original('mock-token', pending[0])  # Simulates the original server transaction committing later.
    recovered = restarted.sync('user', project['project_id'], 'mock-token')
    assert recovered['operations'][-1]['status'] == 'SUCCEEDED'
    assert len(client.requests) == 2


@pytest.mark.parametrize('broken', ['old_server', 'offline', 'request_key', 'script', 'voice', 'settings', 'correlation', 'duplicate'])
def test_recovery_rejects_unavailable_or_wrong_receipt_without_detaching_old_media(setup, monkeypatch, broken):
    store, client, coordinator, project = setup
    lose_response(client, monkeypatch)
    with pytest.raises(SystemExit):
        retry(coordinator, project)
    lookup = client.lookup_workbench_audio_batch
    def wrong(token, key):
        if broken in {'old_server', 'offline'}:
            raise AuthCenterError('unavailable', status_code=404 if broken == 'old_server' else 503)
        result = deepcopy(lookup(token, key))
        binding = next(iter(result['input_bindings'].values()))
        if broken == 'request_key': result['request_key'] = 'wrong-key'
        if broken == 'script': binding['script_sha256'] = 'wrong-script'
        if broken == 'voice': binding['voice_asset_id'] = 'wrong-voice'
        if broken == 'settings': binding['speech_settings']['speed'] = 2
        if broken == 'correlation': result['batch']['correlation_id'] = 'wrong-correlation'
        if broken == 'duplicate': result['batch']['items'] *= 2
        return result
    monkeypatch.setattr(client, 'lookup_workbench_audio_batch', wrong)
    after = restart(store, client).sync('user', project['project_id'], 'mock-token')
    assert after['operations'][-1]['error_code'] == 'AUDIO_SUBMISSION_UNKNOWN'
    assert after['items'][0]['outputs'] == project['items'][0]['outputs']
    assert after['items'][0]['subtitles'] == project['items'][0]['subtitles']
    assert after['links'] == project['links']
    assert len(client.requests) == 2


def test_restart_after_one_row_accepted_recovers_remaining_row_only(setup, monkeypatch):
    store, client, coordinator, project = setup
    original_accept = store.accept_audio_submission
    count = 0
    def interrupted(*args, **kwargs):
        nonlocal count
        count += 1
        if count == 2:
            raise SystemExit('exit halfway through local row receipts')
        return original_accept(*args, **kwargs)
    monkeypatch.setattr(store, 'accept_audio_submission', interrupted)
    with pytest.raises(SystemExit):
        coordinator.start('user', project['project_id'], 'mock-token', default_voice_asset_id='voice-1',
                           voice_assignments=None, settings={}, idempotency_key='multi')
    after = restart(store, client).sync('user', project['project_id'], 'mock-token')
    assert len(client.requests) == 2
    assert all(op['status'] == 'SUCCEEDED' for op in after['operations'])
    assert all(item['outputs']['audio']['external_ref']['batch_id'] == 'batch-2' for item in after['items'])
    assert len(after['links']) == 6  # Two batch receipts and four immutable row links.


def test_request_key_remains_compatible_with_existing_v1_operations():
    expected = 'workbench-audio-' + hashlib.sha256(b'project\0click\0voice').hexdigest()[:48]
    assert audio_request_key('project', ' click ', 'voice') == expected


def test_receipt_acceptance_rolls_back_links_and_media_together(setup, monkeypatch):
    store, client, coordinator, project = setup
    from jyd_probe import project_store
    original_invalidate = project_store._invalidate_auto_music_selection
    def fail_after_links(*args):
        raise OSError('simulated interruption inside acceptance transaction')
    monkeypatch.setattr(project_store, '_invalidate_auto_music_selection', fail_after_links)
    with pytest.raises(AuthCenterError):
        retry(coordinator, project)
    before = store.get_project('user', project['project_id'])
    assert before['links'] == project['links']
    assert before['items'][0]['outputs'] == project['items'][0]['outputs']
    assert before['operations'][-1]['error_code'] == 'AUDIO_SUBMISSION_UNKNOWN'
    monkeypatch.setattr(project_store, '_invalidate_auto_music_selection', original_invalidate)
    recovered = restart(store, client).sync('user', project['project_id'], 'mock-token')
    operation = recovered['operations'][-1]
    assert operation['status'] == 'SUCCEEDED'
    assert store.accept_audio_submission(
        'user', project['project_id'], project['items'][0]['item_id'],
        operation_id=operation['operation_id'], result=operation['result'], recovering=True,
    ) is False
    assert store.get_project('user', project['project_id'])['items'][0]['outputs'] == recovered['items'][0]['outputs']
    assert len(client.requests) == 2


@pytest.mark.parametrize('stage', ['pending', 'starting'])
def test_actual_process_exit_does_not_leave_audio_running_forever(tmp_path, stage):
    """os._exit skips finally blocks, as a killed packaged process would."""
    database = tmp_path / 'killed.db'
    script = '''
import os, sys
from pathlib import Path
from jyd_probe.project_store import ProjectStore
from jyd_probe.project_audio import ProjectAudioCoordinator
store = ProjectStore(Path(sys.argv[1]))
project = store.create_project(owner_user_id='user', owner_username='user', name='killed',
                               items=[{'row_key':'1','script_text':'测试。'}])
class Client:
    def list_workbench_voices(self, token):
        return {'voices':[{'voice_asset_id':'voice-1'}]}
    def create_workbench_audio_batch(self, token, payload):
        os._exit(42)
if sys.argv[2] == 'pending':
    store.claim_audio_submissions = lambda *args: os._exit(42)
coordinator = ProjectAudioCoordinator(store, Client(), storage_root=store.path.parent/'storage', max_audio_bytes=1024)
coordinator.start('user', project['project_id'], 'mock-token', default_voice_asset_id='voice-1',
                  voice_assignments=None, settings={}, idempotency_key='process-exit')
'''
    child_environment = os.environ.copy()
    source_root = str(Path(__file__).resolve().parents[1] / 'src')
    child_environment['PYTHONPATH'] = os.pathsep.join(
        value for value in (source_root, child_environment.get('PYTHONPATH', '')) if value
    )
    result = subprocess.run([sys.executable, '-c', script, str(database), stage],
                            capture_output=True, timeout=30, env=child_environment)
    assert result.returncode == 42, result.stderr.decode(errors='replace')
    store = ProjectStore(database)
    with store._connect() as connection:
        project_id = connection.execute('SELECT project_id FROM projects').fetchone()[0]
    after = restart(store, LookupClient()).sync('user', project_id, 'mock-token')
    assert after['operations'][-1]['status'] == 'FAILED'
    assert after['items'][0]['status'] == 'AUDIO_FAILED'
    expected_code = 'AUDIO_NOT_SUBMITTED' if stage == 'pending' else 'AUDIO_SUBMISSION_UNKNOWN'
    assert after['operations'][-1]['error_code'] == expected_code
