from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jyd_probe.project_audio import ProjectAudioCoordinator
from jyd_probe.project_store import ProjectStore
from jyd_probe.auth_center import AuthCenterError, AuthCenterConnectionError


class AudioClient:
    def __init__(self):
        self.requests = []
        self.retries = []
        self.batches = {}

    def list_workbench_voices(self, token):
        return {"voices": [{"voice_asset_id": "voice-1"}, {"voice_asset_id": "voice-2"}]}

    def create_workbench_audio_batch(self, token, payload):
        self.requests.append(payload)
        batch_id = f"batch-{len(self.requests)}"
        batch = {"batch_id": batch_id, "correlation_id": payload["correlation_id"], "items": [
            {"item_id": f"remote-{len(self.requests)}", "row_key": row["row_id"], "status": "AWAITING_REVIEW", "generation_version": 1, "audio_ready": True,
             "captions": {"cues": [{"text": row["speech_script"], "start_us": 0, "end_us": 1_000_000, "duration_us": 1_000_000}]}}
            for row in payload["rows"]
        ]}
        self.batches[batch_id] = batch
        return batch

    def get_workbench_audio_batch(self, token, batch_id):
        return self.batches[batch_id]

    def download_workbench_audio(self, token, batch_id, item_id, target, **kwargs):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(f"audio:{batch_id}:{item_id}".encode())

    def retry_workbench_audio(self, token, batch_id, item_id, *, speed):
        self.retries.append((batch_id, item_id, speed))
        self.batches[batch_id]["items"][0]["generation_version"] += 1


@pytest.fixture
def audio_setup(tmp_path):
    store = ProjectStore(tmp_path / "control.db")
    project = store.create_project(owner_user_id="user", owner_username="tester", name="声音绑定", items=[{"row_key": "1", "script_text": "原来脚本。"}])
    client = AudioClient()
    coordinator = ProjectAudioCoordinator(store, client, storage_root=tmp_path / "storage", max_audio_bytes=1024)
    project = coordinator.start("user", project["project_id"], "token", default_voice_asset_id="voice-1", voice_assignments=None, settings={"speed": 1.04}, idempotency_key="first")
    return store, client, coordinator, project


@pytest.mark.parametrize("change", ["script", "voice", "volume"])
def test_changed_inputs_retry_creates_new_audio_and_preserves_old_file(audio_setup, change):
    store, client, coordinator, project = audio_setup
    project_id = project["project_id"]
    item = project["items"][0]
    item_id = item["item_id"]
    old_path = Path(item["outputs"]["audio"]["managed_path"])
    old_bytes = old_path.read_bytes()
    if change == "script":
        store.update_item("user", project_id, item_id, script_text="全新的脚本。")
    if change == "voice":
        store.configure_item_voice("user", project_id, item_id, voice_asset_id="voice-2")
    settings = {"speed": 1.04, "volume": 2.0 if change == "volume" else 1.0}
    updated = coordinator.retry("user", project_id, item_id, "token", idempotency_key="changed", settings=settings)
    assert len(client.requests) == 2
    assert client.retries == []
    assert client.requests[-1]["rows"][0]["speech_script"] == ("全新的脚本。" if change == "script" else "原来脚本。")
    assert client.requests[-1]["speech_options"]["voiceAssetId"] == ("voice-2" if change == "voice" else "voice-1")
    assert client.requests[-1]["speech_options"]["volume"] == settings["volume"]
    current = updated["items"][0]["outputs"]["audio"]
    assert current["version"] == 2
    assert current["managed_path"] != str(old_path)
    assert old_path.read_bytes() == old_bytes
    assert updated["items"][0]["subtitles"]["raw_cues"][0]["text"] == client.requests[-1]["rows"][0]["speech_script"]


def test_speed_only_retry_creates_an_independent_idempotent_batch(audio_setup):
    store, client, coordinator, project = audio_setup
    updated = coordinator.retry("user", project["project_id"], project["items"][0]["item_id"], "token", idempotency_key="speed", settings={"speed": 1.05})
    assert len(client.requests) == 2
    assert client.retries == []
    assert updated["items"][0]["outputs"]["audio"]["metadata"]["speed"] == 1.05


def test_stale_audio_sync_does_not_attach_old_script(audio_setup):
    store, client, coordinator, project = audio_setup
    project_id, item_id = project["project_id"], project["items"][0]["item_id"]
    store.update_item("user", project_id, item_id, script_text="改后的脚本。")
    store.create_operation(owner_user_id="user", project_id=project_id, item_id=item_id, operation_type="AUDIO_GENERATE", idempotency_key="legacy-retry", payload={})
    store.transition_audio_operation("user", project_id, item_id, status="RUNNING", item_status="AUDIO_RUNNING")
    updated = coordinator.sync("user", project_id, "token")
    assert updated["items"][0]["outputs"]["audio"] is None
    assert updated["items"][0]["status"] == "AUDIO_FAILED"
    assert updated["operations"][-1]["error_code"] == "AUDIO_SCRIPT_MISMATCH"


@pytest.mark.parametrize("status", ["SUCCESS", "AWAITING_REVIEW", "FAILED"])
def test_explicit_regeneration_never_mutates_old_remote_task(audio_setup, status):
    store, client, coordinator, project = audio_setup
    old_remote = client.batches["batch-1"]["items"][0]
    old_remote["status"] = status
    old_audio = project["items"][0]["outputs"]["audio"]
    updated = coordinator.retry("user", project["project_id"], project["items"][0]["item_id"],
                                "token", idempotency_key="regenerate", settings={"speed": 1.04})
    assert len(client.requests) == 2
    assert client.retries == []
    assert old_remote["status"] == status
    assert old_remote["generation_version"] == 1
    assert updated["items"][0]["outputs"]["audio"]["asset_id"] != old_audio["asset_id"]
    assert Path(old_audio["managed_path"]).exists()
    assert updated["operations"][-1]["status"] == "SUCCEEDED"


def _with_video_outputs(store, project):
    for asset_type in ("base_video", "composition_video"):
        store.add_asset(owner_user_id="user", project_id=project["project_id"],
                        item_id=project["items"][0]["item_id"], asset_type=asset_type,
                        source_type="test", status="READY", filename=f"{asset_type}.mp4",
                        make_current=True)
    return store.get_project("user", project["project_id"])


@pytest.mark.parametrize("http_status", [401, 403, 409, 422, 429])
def test_rejected_regeneration_keeps_existing_outputs_and_finishes_operation(audio_setup, monkeypatch, http_status):
    store, client, coordinator, project = audio_setup
    project = _with_video_outputs(store, project)
    before = project["items"][0]

    def reject(token, payload):
        during = coordinator.sync("user", project["project_id"], token)
        assert during["items"][0]["outputs"] == before["outputs"]
        assert during["items"][0]["subtitles"] == before["subtitles"]
        assert during["operations"][-1]["status"] == "STARTING"
        raise AuthCenterError("拒绝生成", status_code=http_status)

    monkeypatch.setattr(client, "create_workbench_audio_batch", reject)
    with pytest.raises(AuthCenterError):
        coordinator.retry("user", project["project_id"], before["item_id"], "token",
                          idempotency_key="rejected", settings={"speed": 1.04})
    after = coordinator.sync("user", project["project_id"], "token")
    assert after["items"][0]["outputs"] == before["outputs"]
    assert after["items"][0]["subtitles"] == before["subtitles"]
    assert after["items"][0]["settings"] == before["settings"]
    assert after["items"][0]["status"] == before["status"]
    assert after["operations"][-1]["status"] == "FAILED"
    assert after["operations"][-1]["finished_at"]
    assert after["operations"][-1]["error_message"] == "拒绝生成"
    assert client.retries == []


@pytest.mark.parametrize("error", [AuthCenterConnectionError("连接断开"), AuthCenterError("超时", status_code=504)])
def test_unknown_submission_is_visible_and_blocks_fresh_paid_request(audio_setup, monkeypatch, error):
    store, client, coordinator, project = audio_setup
    before = project["items"][0]
    calls = []

    def uncertain(token, payload):
        calls.append(payload)
        raise error

    monkeypatch.setattr(client, "create_workbench_audio_batch", uncertain)
    with pytest.raises(AuthCenterError):
        coordinator.retry("user", project["project_id"], before["item_id"], "token",
                          idempotency_key="uncertain", settings={"speed": 1.04})
    after = coordinator.sync("user", project["project_id"], "token")
    assert after["operations"][-1]["status"] == "FAILED"
    assert after["operations"][-1]["error_code"] == "AUDIO_SUBMISSION_UNKNOWN"
    assert after["items"][0]["outputs"] == before["outputs"]
    with pytest.raises(ValueError, match="避免重复计费"):
        coordinator.retry("user", project["project_id"], before["item_id"], "token",
                          idempotency_key="new-click", settings={"speed": 1.04})
    assert len(calls) == 1


def test_repeated_key_does_not_generate_or_detach_audio_again(audio_setup):
    store, client, coordinator, project = audio_setup
    args = ("user", project["project_id"], project["items"][0]["item_id"], "token")
    first = coordinator.retry(*args, idempotency_key="same", settings={"speed": 1.04})
    again = coordinator.retry(*args, idempotency_key="same", settings={"speed": 1.04})
    assert len(client.requests) == 2
    assert first["items"][0]["outputs"] == again["items"][0]["outputs"]
    assert len(again["operations"]) == 2


def test_reentrant_retry_and_poll_during_submit_do_not_use_old_audio(audio_setup, monkeypatch):
    store, client, coordinator, project = audio_setup
    args = ("user", project["project_id"], project["items"][0]["item_id"], "token")
    original_create = client.create_workbench_audio_batch

    def create(token, payload):
        duplicate = coordinator.retry(*args, idempotency_key="in-flight", settings={"speed": 1.04})
        assert duplicate["operations"][-1]["status"] == "STARTING"
        with pytest.raises(ValueError, match="正在生成"):
            coordinator.retry(*args, idempotency_key="another-click", settings={"speed": 1.04})
        result = original_create(token, payload)
        result["items"][0]["status"] = "PENDING"
        result["items"][0]["audio_ready"] = False
        return result

    monkeypatch.setattr(client, "create_workbench_audio_batch", create)
    after = coordinator.retry(*args, idempotency_key="in-flight", settings={"speed": 1.04})
    assert len(client.requests) == 2
    assert after["items"][0]["outputs"]["audio"] is None
    assert after["operations"][-1]["status"] == "RUNNING"


def test_exact_new_success_can_be_downloaded_without_reusing_old_h3_audio(audio_setup, monkeypatch):
    store, client, coordinator, project = audio_setup
    original_create = client.create_workbench_audio_batch

    def create(token, payload):
        result = original_create(token, payload)
        result["items"][0]["status"] = "SUCCESS"
        return result

    monkeypatch.setattr(client, "create_workbench_audio_batch", create)
    after = coordinator.retry("user", project["project_id"], project["items"][0]["item_id"],
                              "token", idempotency_key="success", settings={"speed": 1.04})
    assert after["operations"][-1]["status"] == "SUCCEEDED"
    assert after["items"][0]["outputs"]["audio"]["external_ref"]["batch_id"] == "batch-2"


@pytest.mark.parametrize("failure", ["rejected", "unknown", "malformed"])
def test_group_failure_does_not_leave_unsubmitted_rows_generating(tmp_path, failure):
    store = ProjectStore(tmp_path / "groups.db")
    project = store.create_project(owner_user_id="user", owner_username="tester", name="分组",
                                   items=[{"row_key": str(i), "script_text": "测试。"} for i in range(3)])
    client = AudioClient()
    calls = []

    def create(token, payload):
        calls.append(payload)
        if failure == "rejected":
            raise AuthCenterError("拒绝", status_code=409)
        if failure == "unknown":
            raise AuthCenterConnectionError("断开")
        return {"batch_id": "bad", "items": []}

    client.create_workbench_audio_batch = create
    coordinator = ProjectAudioCoordinator(store, client, storage_root=tmp_path / "storage", max_audio_bytes=1024)
    with pytest.raises(AuthCenterError):
        coordinator.start("user", project["project_id"], "token", default_voice_asset_id="voice-1",
                          voice_assignments={project["items"][-1]["item_id"]: "voice-2"},
                          settings={}, idempotency_key="groups")
    after = store.get_project("user", project["project_id"])
    assert len(calls) == 1
    assert all(op["status"] == "FAILED" for op in after["operations"])
    assert all(item["status"] == "AUDIO_FAILED" for item in after["items"])
    assert after["operations"][-1]["error_code"] == "AUDIO_NOT_SUBMITTED"
    assert after["links"] == []


def test_preflight_failure_finishes_previously_reserved_rows(tmp_path, monkeypatch):
    store = ProjectStore(tmp_path / "reserve.db")
    project = store.create_project(owner_user_id="user", owner_username="tester", name="预检",
                                   items=[{"row_key": str(i), "script_text": "测试。"} for i in range(2)])
    client = AudioClient()
    coordinator = ProjectAudioCoordinator(store, client, storage_root=tmp_path / "storage", max_audio_bytes=1024)
    original = store.create_operation
    calls = []

    def reserve(**kwargs):
        calls.append(kwargs)
        if len(calls) == 2:
            raise ValueError("脚本已改变")
        return original(**kwargs)

    monkeypatch.setattr(store, "create_operation", reserve)
    with pytest.raises(ValueError, match="脚本已改变"):
        coordinator.start("user", project["project_id"], "token", default_voice_asset_id="voice-1",
                          voice_assignments=None, settings={}, idempotency_key="reserve")
    after = store.get_project("user", project["project_id"])
    assert after["operations"][0]["status"] == "FAILED"
    assert all(item["status"] not in {"AUDIO_QUEUED", "AUDIO_RUNNING"} for item in after["items"])
    assert client.requests == []


def test_download_failure_keeps_accepted_operation_recoverable(audio_setup, monkeypatch):
    store, client, coordinator, project = audio_setup
    original = client.download_workbench_audio

    def fail_download(*args, **kwargs):
        raise AuthCenterConnectionError("下载断开")

    monkeypatch.setattr(client, "download_workbench_audio", fail_download)
    with pytest.raises(AuthCenterConnectionError):
        coordinator.retry("user", project["project_id"], project["items"][0]["item_id"],
                          "token", idempotency_key="download", settings={"speed": 1.04})
    pending = store.get_project("user", project["project_id"])
    assert pending["operations"][-1]["status"] == "RUNNING"
    monkeypatch.setattr(client, "download_workbench_audio", original)
    after = coordinator.sync("user", project["project_id"], "token")
    assert after["operations"][-1]["status"] == "SUCCEEDED"
    assert len(client.requests) == 2


@pytest.mark.parametrize("same_key", [True, False])
def test_simultaneous_clicks_submit_only_one_new_batch(audio_setup, monkeypatch, same_key):
    store, client, coordinator, project = audio_setup
    barrier = Barrier(2)
    original = client.list_workbench_voices

    def voices(token):
        barrier.wait(timeout=10)
        return original(token)

    monkeypatch.setattr(client, "list_workbench_voices", voices)

    def click(index):
        try:
            coordinator.retry("user", project["project_id"], project["items"][0]["item_id"],
                              "token", idempotency_key="race" if same_key else f"race-{index}",
                              settings={"speed": 1.04})
            return True
        except ValueError:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(click, [1, 2]))
    assert sum(results) == 1
    assert len(client.requests) == 2
    after = store.get_project("user", project["project_id"])
    assert after["operations"][-1]["status"] == "SUCCEEDED"
    assert len(after["operations"]) == 2


def test_stale_click_cannot_submit_again_after_overlapping_request_finishes(audio_setup, monkeypatch):
    store, client, coordinator, project = audio_setup
    original = client.list_workbench_voices
    nested = False
    args = ("user", project["project_id"], project["items"][0]["item_id"], "token")

    def voices(token):
        nonlocal nested
        if not nested:
            nested = True
            coordinator.retry(*args, idempotency_key="finished-first", settings={"speed": 1.04})
        return original(token)

    monkeypatch.setattr(client, "list_workbench_voices", voices)
    with pytest.raises(ValueError, match="声音版本已改变"):
        coordinator.retry(*args, idempotency_key="stale-click", settings={"speed": 1.04})
    assert len(client.requests) == 2
    assert store.get_project("user", project["project_id"])["operations"][-1]["status"] == "SUCCEEDED"
