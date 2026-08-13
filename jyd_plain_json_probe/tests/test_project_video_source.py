from __future__ import annotations

from pathlib import Path

from jyd_probe.project_video_source import project_segment_boundaries


def test_project_segment_boundaries_preserve_next_segment_script_and_time(
    tmp_path: Path,
) -> None:
    first = tmp_path / "segment-1.mp4"
    second = tmp_path / "segment-2.mp4"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    item = {
        "outputs": {
            "base_video": {
                "managed_path": str(tmp_path / "base.mp4"),
                "metadata": {"segment_count": 2},
                "external_ref": {"source_task_ids": ["task-1", "task-2"]},
            },
            "original_video_segments": [
                {
                    "asset_id": "segment-1",
                    "status": "READY",
                    "managed_path": str(first),
                    "external_ref": {"video_index": 1, "remote_task_id": "task-1"},
                    "metadata": {
                        "start_seconds": 0.0,
                        "end_seconds": 2.5,
                        "script_text": "第一句。",
                    },
                },
                {
                    "asset_id": "segment-2",
                    "status": "READY",
                    "managed_path": str(second),
                    "external_ref": {"video_index": 2, "remote_task_id": "task-2"},
                    "metadata": {
                        "start_seconds": 2.5,
                        "end_seconds": 5.0,
                        "script_text": "第二句吃牛肉。",
                    },
                },
            ],
        }
    }

    assert project_segment_boundaries(item) == [
        {
            "boundary_us": 2_500_000,
            "segment_index": 2,
            "segment_start_us": 2_500_000,
            "segment_end_us": 5_000_000,
            "script_text": "第二句吃牛肉。",
        }
    ]
