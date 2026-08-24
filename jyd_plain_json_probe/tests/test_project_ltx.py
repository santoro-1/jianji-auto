from __future__ import annotations

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from jyd_probe.project_ltx import ProjectLtxCoordinator  # noqa: E402
from jyd_probe.project_store import ProjectStore  # noqa: E402


class FakeLtxClient:
    def __init__(self) -> None:
        self.sync_payload = None
        self.download_calls = 0

    def sync(self, token, project_id, payload):
        assert token == "cloud-token"
        assert project_id
        self.sync_payload = payload
        return {"state": {"items": [], "active": False}}

    def refresh(self, token, project_id, item_ids):
        assert token == "cloud-token"
        return {
            "active": False,
            "items": [
                {
                    "item_id": item_ids[0],
                    "status": "COMPLETED",
                    "source_video": {
                        "filename": "source.mp4",
                        "sha256": "source-sha",
                        "version": 1,
                    },
                    "remote_batch_id": "ltx-batch",
                    "remote_item_id": "ltx-item",
                    "segments": [{"segment_id": "segment-1"}],
                    "base_video_ready": True,
                }
            ],
        }

    def upload_source_video(self, token, project_id, item_id, path, *, filename):
        assert token == "cloud-token"
        assert Path(path).read_bytes()
        return {
            "active": False,
            "items": [
                {
                    "item_id": item_id,
                    "status": "READY",
                    "source_video": {"filename": filename, "version": 2},
                }
            ],
        }

    def download_base_video(self, token, project_id, item_id, destination):
        assert token == "cloud-token"
        self.download_calls += 1
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"ltx-seedvr2-video")
        return destination


def test_ltx_is_a_third_pipeline_and_reuses_the_unmodified_minimax_source(tmp_path):
    store = ProjectStore(tmp_path / "projects.sqlite3")
    project = store.create_project(
        owner_user_id="user-1",
        owner_username="tester",
        name="三引擎项目",
        items=[{"row_key": "1", "script_text": "测试对口型。"}],
        settings={"generation_mode": "runninghub_digital_human"},
    )
    project_id = project["project_id"]
    item_id = project["items"][0]["item_id"]
    audio_path = tmp_path / "speech.mp3"
    audio_path.write_bytes(b"original-minimax-speech-without-provider-tail")
    audio = store.add_asset(
        owner_user_id="user-1",
        project_id=project_id,
        item_id=item_id,
        asset_type="audio",
        source_type="minimax",
        status="READY",
        filename="speech.mp3",
        managed_path=str(audio_path),
        external_ref={
            "batch_id": "audio-batch",
            "remote_item_id": "audio-item",
            "generation_version": 3,
        },
        metadata={
            "provider_status": "SUCCESS",
            "subtitle_cues": [
                {
                    "start_us": 0,
                    "duration_us": 900_000,
                    "text": "测试对口型。",
                }
            ],
        },
        make_current=True,
    )
    subtitles = store.get_project("user-1", project_id)["items"][0]["subtitles"]
    subtitles["raw_cues"] = [{"start_us": 0, "duration_us": 900_000, "text": "测试对口型。"}]
    subtitles["bound_audio_asset_id"] = audio["asset_id"]
    subtitles["status"] = "READY"
    store.set_item_subtitles("user-1", project_id, item_id, subtitles)

    # H3 owns a different authoritative audio while its route is active.  When
    # switching to LTX, the original MiniMax source and its cues must be restored.
    h3_path = tmp_path / "h3.wav"
    h3_path.write_bytes(b"h3-authoritative-audio")
    h3_audio = store.add_asset(
        owner_user_id="user-1",
        project_id=project_id,
        item_id=item_id,
        asset_type="audio",
        source_type="h3",
        status="READY",
        filename="h3.wav",
        managed_path=str(h3_path),
        make_current=True,
    )
    h3_subtitles = store.get_project("user-1", project_id)["items"][0]["subtitles"]
    h3_subtitles.update(
        {
            "source": "h3_generated_audio",
            "raw_cues": [
                {"start_us": 0, "duration_us": 800_000, "text": "H3 字幕。"}
            ],
            "bound_audio_asset_id": h3_audio["asset_id"],
            "status": "READY",
        }
    )
    store.set_item_subtitles("user-1", project_id, item_id, h3_subtitles)

    ltx_project = store.set_generation_mode("user-1", project_id, "ltx_lip_sync")
    assert ltx_project["settings"]["generation_mode"] == "ltx_lip_sync"
    assert ltx_project["items"][0]["outputs"]["audio"]["asset_id"] == audio["asset_id"]
    assert ltx_project["items"][0]["subtitles"]["raw_cues"][0]["text"] == "测试对口型。"

    client = FakeLtxClient()
    result = ProjectLtxCoordinator(
        store, client, storage_root=tmp_path / "storage"
    ).refresh("user-1", project_id, "cloud-token")

    synced_audio = client.sync_payload["items"][0]["audio"]
    assert synced_audio == {
        "batch_id": "audio-batch",
        "item_id": "audio-item",
        "generation_version": 3,
    }
    item = result["project"]["items"][0]
    assert item["outputs"]["audio"]["asset_id"] == audio["asset_id"]
    assert item["outputs"]["base_video"]["source_type"] == "ltx"
    assert item["outputs"]["base_video"]["metadata"]["enhanced_by"] == "seedvr2"
    assert item["subtitles"]["raw_cues"][0]["text"] == "测试对口型。"
    assert client.download_calls == 1

    # Completed LTX results are idempotent, while normal/H3 remain separate modes.
    ProjectLtxCoordinator(store, client, storage_root=tmp_path / "storage").refresh(
        "user-1", project_id, "cloud-token"
    )
    assert client.download_calls == 1
    replacement = tmp_path / "replacement.mp4"
    replacement.write_bytes(b"replacement-source-video")
    replaced = ProjectLtxCoordinator(
        store, client, storage_root=tmp_path / "storage"
    ).upload_source_video(
        "user-1",
        project_id,
        item_id,
        "cloud-token",
        replacement,
        filename="replacement.mp4",
    )
    assert replaced["project"]["items"][0]["outputs"]["base_video"] is None
    assert (
        replaced["project"]["items"][0]["settings"][
            "composition_invalidated_reason"
        ]
        == "LTX_SOURCE_VIDEO_CHANGED"
    )
    normal = store.set_generation_mode(
        "user-1", project_id, "runninghub_digital_human"
    )
    assert normal["settings"]["generation_mode"] == "runninghub_digital_human"
