from __future__ import annotations

from pathlib import Path
from typing import Any


WORKBENCH_DISSOLVE_DURATION_US = 250_000


def _segment_index(asset: dict[str, Any]) -> int:
    try:
        return int(asset.get("external_ref", {}).get("video_index") or 0)
    except (TypeError, ValueError):
        return 0


def _base_video_source(item: dict[str, Any]) -> dict[str, Any]:
    outputs = item.get("outputs", {})
    base = outputs.get("base_video")
    if not isinstance(base, dict) or not base.get("managed_path"):
        raise ValueError(f"任务 {item.get('row_key') or item.get('item_id')} 缺少基础视频")
    return {
        "type": "video",
        "media_path": str(Path(str(base["managed_path"])).resolve()),
    }


def build_normalized_project_video_source(item: dict[str, Any]) -> dict[str, Any]:
    """Return the normalized base video used by preview, captions, and export."""

    return _base_video_source(item)


def build_project_speech_audio(item: dict[str, Any]) -> dict[str, Any]:
    """Return the approved MiniMax audio as an independent Jianying track."""

    audio = item.get("outputs", {}).get("audio")
    if not isinstance(audio, dict) or not audio.get("managed_path"):
        raise ValueError(
            f"任务 {item.get('row_key') or item.get('item_id')} 缺少已确认音频"
        )
    return {
        "type": "add",
        "media_path": str(Path(str(audio["managed_path"])).resolve()),
        "target_start_us": 0,
        # Keep the provider audio at its native duration. The video segments
        # are independently aligned to the same approved cue boundaries.
        "target_duration_us": 0,
        "volume": 1.0,
    }


def build_project_video_source(item: dict[str, Any]) -> dict[str, Any]:
    """Return the Jianying source while keeping RunningHub clips independent."""

    outputs = item.get("outputs", {})
    base = outputs.get("base_video")
    normalized_source = _base_video_source(item)
    assert isinstance(base, dict)

    try:
        expected = int(base.get("metadata", {}).get("segment_count") or 0)
    except (TypeError, ValueError):
        expected = 0
    segments = sorted(
        (
            asset
            for asset in outputs.get("original_video_segments", [])
            if isinstance(asset, dict)
            and asset.get("status") == "READY"
            and asset.get("managed_path")
        ),
        key=_segment_index,
    )
    if expected <= 1:
        return normalized_source
    if len(segments) != expected or [_segment_index(asset) for asset in segments] != list(
        range(1, expected + 1)
    ):
        raise ValueError(
            f"任务 {item.get('row_key') or item.get('item_id')} 的原始分段不完整："
            f"应有 {expected} 段，当前可用 {len(segments)} 段"
        )

    source_items: list[dict[str, Any]] = []
    for asset in segments:
        metadata = asset.get("metadata", {})
        try:
            start_seconds = float(metadata.get("start_seconds"))
            end_seconds = float(metadata.get("end_seconds"))
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"原始分段 {_segment_index(asset)} 缺少有效的音频时间范围"
            ) from exc
        duration_us = round((end_seconds - start_seconds) * 1_000_000)
        if duration_us <= 0:
            raise ValueError(f"原始分段 {_segment_index(asset)} 的目标时长无效")
        source_item = {
            "media_path": str(Path(str(asset["managed_path"])).resolve()),
            "target_duration_us": duration_us,
            "video_index": _segment_index(asset),
            # The authoritative speech track is the complete approved
            # MiniMax audio, not the re-encoded audio embedded in each
            # RunningHub segment.
            "volume": 0.0,
        }
        source_items.append(source_item)
    for position in range(len(source_items) - 1):
        transition_duration = min(
            WORKBENCH_DISSOLVE_DURATION_US,
            int(source_items[position]["target_duration_us"]) // 2,
            int(source_items[position + 1]["target_duration_us"]) // 2,
        )
        if transition_duration > 0:
            source_items[position]["transition_after_us"] = transition_duration
    return {"type": "video_sequence", "items": source_items}
