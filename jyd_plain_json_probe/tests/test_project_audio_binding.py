from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jyd_probe.project_audio import ProjectAudioCoordinator
from jyd_probe.project_store import ProjectStore


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


def test_speed_only_retry_reuses_same_immutable_remote_task(audio_setup):
    store, client, coordinator, project = audio_setup
    updated = coordinator.retry("user", project["project_id"], project["items"][0]["item_id"], "token", idempotency_key="speed", settings={"speed": 1.05})
    assert len(client.requests) == 1
    assert client.retries == [("batch-1", "remote-1", 1.05)]
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
