from __future__ import annotations

from pathlib import Path
import sys

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from jyd_probe.project_h3 import ProjectH3Coordinator  # noqa: E402
from jyd_probe.project_h3_media import H3MediaAssets  # noqa: E402
from jyd_probe.project_store import ProjectStore  # noqa: E402


class FakeH3Client:
    def __init__(self) -> None:
        self.uploads: list[tuple[str, str]] = []
        self.prepared: dict | None = None
        self.snapshot = {
            "batch_id": "h3-batch-1",
            "status": "AWAITING_COST_CONFIRMATION",
            "fee_snapshot": {
                "segment_count": 2,
                "estimated_paid_calls": 2,
            },
            "items": [
                {
                    "item_id": "remote-row-1",
                    "row_id": "1",
                    "status": "AWAITING_COST_CONFIRMATION",
                    "segments": [],
                }
            ],
        }

    def list_h3_execution_accounts(self, token: str) -> dict:
        return {"accounts": [{"id": 7}], "token_seen": token}

    def approve_h3_audio_source(self, token: str, **kwargs: object) -> dict:
        return {
            **kwargs,
            "status": "SUCCESS",
            "reviewed_at": "2026-08-23T00:00:00+00:00",
        }

    def upload_workbench_batch_asset(
        self,
        token: str,
        path: Path,
        *,
        kind: str,
        filename: str,
    ) -> dict:
        self.uploads.append((kind, filename))
        return {"asset_id": f"cloud-{kind}-{len(self.uploads)}"}

    def prepare_h3_batch(self, token: str, payload: dict) -> dict:
        self.prepared = payload
        return dict(self.snapshot)

    def confirm_h3_batch(self, token: str, batch_id: str) -> dict:
        assert batch_id == "h3-batch-1"
        self.snapshot = {
            **self.snapshot,
            "status": "ACTIVE",
            "items": [
                {
                    "item_id": "remote-row-1",
                    "row_id": "1",
                    "status": "PENDING",
                    "segments": [],
                }
            ],
        }
        return dict(self.snapshot)

    def get_h3_batch(self, token: str, batch_id: str) -> dict:
        assert batch_id == "h3-batch-1"
        return dict(self.snapshot)

    def download_h3_segment_video(
        self,
        token: str,
        segment_id: str,
        target: Path,
        *,
        max_bytes: int,
    ) -> int:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(f"video:{segment_id}".encode())
        return target.stat().st_size


class FakeCaptionAligner:
    def align(self, audio_path: Path, **kwargs: object) -> dict:
        assert audio_path.is_file()
        return {
            "status": "SUCCESS",
            "audio_asset_id": kwargs["audio_asset_id"],
            "audio_version": kwargs["audio_version"],
            "script_sha256": "fake",
            "words": [],
        }


def fake_media_preparer(
    *,
    segment_paths: list[Path],
    segment_texts: list[str],
    script_text: str,
    target_dir: Path,
) -> H3MediaAssets:
    assert len(segment_paths) == len(segment_texts) == 2
    assert "".join(segment_texts) == script_text
    target_dir.mkdir(parents=True, exist_ok=True)
    master = target_dir / "h3-master-av.mp4"
    audio = target_dir / "h3-authoritative-full.wav"
    base = target_dir / "h3-base-video-silent.mp4"
    master.write_bytes(b"master-av")
    audio.write_bytes(b"h3-audio")
    base.write_bytes(b"silent-base")
    return H3MediaAssets(
        master_av_path=master,
        silent_base_video_path=base,
        authoritative_audio_path=audio,
        raw_cues=(
            {
                "text": segment_texts[0],
                "start_us": 0,
                "duration_us": 1_000_000,
                "end_us": 1_000_000,
                "segment_index": 0,
            },
            {
                "text": segment_texts[1],
                "start_us": 1_000_000,
                "duration_us": 1_000_000,
                "end_us": 2_000_000,
                "segment_index": 1,
            },
        ),
        segment_durations_seconds=(1.0, 1.0),
    )


def test_h3_project_contract_reuses_existing_audio_and_original_project(
    tmp_path: Path,
) -> None:
    store = ProjectStore(tmp_path / "control.db")
    project = store.create_project(
        owner_user_id="user-1",
        owner_username="tester",
        name="H3 正式项目",
        items=[{"row_key": "1", "script_text": "第一条台词。"}],
    )
    project_id = project["project_id"]
    item_id = project["items"][0]["item_id"]
    image_path = tmp_path / "identity.png"
    image_path.write_bytes(b"identity")
    project = store.register_input_image(
        owner_user_id="user-1",
        project_id=project_id,
        filename="identity.png",
        content_type="image/png",
        size_bytes=8,
        sha256="a" * 64,
        managed_path=str(image_path),
    )
    image_id = project["image_id"]
    audio_path = tmp_path / "voice.mp3"
    audio_path.write_bytes(b"audio")
    audio_asset = store.add_asset(
        owner_user_id="user-1",
        project_id=project_id,
        item_id=item_id,
        asset_type="audio",
        source_type="minimax",
        status="READY",
        filename="voice.mp3",
        managed_path=str(audio_path),
        external_ref={
            "batch_id": "audio-batch",
            "remote_item_id": "audio-item",
            "generation_version": 3,
        },
        metadata={"provider_status": "AWAITING_REVIEW"},
        make_current=True,
    )
    reference_path = tmp_path / "reference.mp4"
    reference_path.write_bytes(b"video")
    store.add_h3_reference_video(
        owner_user_id="user-1",
        project_id=project_id,
        item_id=item_id,
        filename="reference.mp4",
        managed_path=str(reference_path),
        metadata={"sha256": "b" * 64},
    )
    store.set_h3_configuration(
        "user-1",
        project_id,
        identity_image_ids=[image_id],
        defaults={
            "continuity_mode": "loop_anchor",
            "aspect_ratio": "9:16 (Portrait Widescreen)",
            "megapixels": 1,
            "generation_tail_seconds": 0.1,
        },
    )
    store.set_h3_item_overrides(
        "user-1",
        project_id,
        item_id,
        {
            "user_direction": "人物动作以参考视频为主体，镜头保持稳定。",
            "continuity_mode": "soft_chain",
            "aspect_ratio": "16:9 (Widescreen)",
            "megapixels": 0.8,
        },
    )
    client = FakeH3Client()
    coordinator = ProjectH3Coordinator(
        store,
        client,  # type: ignore[arg-type]
        storage_root=tmp_path / "storage",
        caption_aligner=FakeCaptionAligner(),
        require_precise_alignment=True,
        media_preparer=fake_media_preparer,
    )

    reviewed = coordinator.approve_audio(
        "user-1", project_id, "token", item_ids=[item_id]
    )
    assert reviewed["reviewed_item_ids"] == [item_id]
    assert (
        reviewed["project"]["items"][0]["outputs"]["audio"]["asset_id"]
        == audio_asset["asset_id"]
    )

    prepared = coordinator.prepare(
        "user-1",
        project_id,
        "token",
        idempotency_key="quote-1",
        selected_account_ids=[7],
        item_ids=[item_id],
    )
    assert prepared["project"]["project_id"] == project_id
    assert prepared["project"]["items"][0]["status"] == "H3_COST_PENDING"
    assert client.prepared is not None
    assert client.prepared["rows"][0]["audio_generation_version"] == 3
    assert client.prepared["rows"][0]["script_text"] == "第一条台词。"
    assert client.prepared["defaults"]["continuity_mode"] == "loop_anchor"
    assert client.prepared["defaults"]["generation_tail_seconds"] == pytest.approx(0.1)
    assert client.prepared["rows"][0]["overrides"] == {
        "user_direction": "人物动作以参考视频为主体，镜头保持稳定。",
        "continuity_mode": "soft_chain",
        "aspect_ratio": "16:9 (Widescreen)",
        "megapixels": 0.8,
    }
    assert client.uploads == [
        ("image", "identity.png"),
        ("video", "reference.mp4"),
    ]
    with pytest.raises(ValueError, match="尚未结束"):
        coordinator.prepare(
            "user-1",
            project_id,
            "token",
            idempotency_key="quote-duplicate",
            selected_account_ids=[7],
            item_ids=[item_id],
        )

    confirmed = coordinator.confirm("user-1", project_id, "token")
    assert confirmed["project"]["project_id"] == project_id
    assert confirmed["project"]["settings"]["h3"]["remote_batch_id"] == "h3-batch-1"
    assert confirmed["project"]["items"][0]["status"] == "H3_RUNNING"
    assert confirmed["project"]["items"][0]["outputs"]["audio"]["asset_id"]
    with pytest.raises(ValueError, match="正在生成"):
        store.set_h3_item_overrides(
            "user-1", project_id, item_id, {"megapixels": 1.2}
        )

    client.snapshot = {
        **client.snapshot,
        "status": "SUCCESS",
        "items": [
            {
                "batch_id": "h3-batch-1",
                "item_id": "remote-row-1",
                "row_id": "1",
                "status": "SUCCESS",
                "segments": [
                    {
                        "segment_id": "h3-segment-1",
                        "index": 0,
                        "script_text": "第一条",
                        "status": "SUCCESS",
                        "normalized_video_download_url": "/segment-1/video",
                    },
                    {
                        "segment_id": "h3-segment-2",
                        "index": 1,
                        "script_text": "台词。",
                        "status": "SUCCESS",
                        "normalized_video_download_url": "/segment-2/video",
                    },
                ],
            }
        ],
    }
    synced = coordinator.sync("user-1", project_id, "token")
    final_item = synced["project"]["items"][0]
    assert final_item["status"] == "BASE_VIDEO_READY"
    assert final_item["outputs"]["audio"]["source_type"] == "h3"
    assert final_item["outputs"]["base_video"]["source_type"] == "h3"
    assert final_item["subtitles"]["source"] == "h3_generated_audio"
    assert final_item["subtitles"]["asr_alignment"]["status"] == "SUCCESS"
    assert [
        asset["source_type"] for asset in final_item["asset_history"]["audio"]
    ] == ["minimax", "h3"]

    # Re-sync is idempotent: it must not create duplicate current H3 assets.
    synced_again = coordinator.sync("user-1", project_id, "token")
    history = synced_again["project"]["items"][0]["asset_history"]
    assert len(history["audio"]) == 2
    assert len(history["base_video"]) == 1

    # A later H3 quote must still use the reviewed MiniMax input audio, not the
    # H3-generated authoritative output that is now current in JYD.
    coordinator.prepare(
        "user-1",
        project_id,
        "token",
        idempotency_key="quote-2",
        selected_account_ids=[7],
    )
    assert client.prepared is not None
    assert client.prepared["rows"][0]["audio_batch_id"] == "audio-batch"
    assert client.prepared["rows"][0]["audio_item_id"] == "audio-item"
    assert client.prepared["rows"][0]["audio_generation_version"] == 3
