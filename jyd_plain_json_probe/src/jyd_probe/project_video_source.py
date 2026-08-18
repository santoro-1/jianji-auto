from __future__ import annotations

from pathlib import Path
from typing import Any

from .draft_factory import probe_video_duration_us


WORKBENCH_DISSOLVE_DURATION_US = 250_000


def _segment_index(asset: dict[str, Any]) -> int:
    try:
        return int(asset.get("external_ref", {}).get("video_index") or 0)
    except (TypeError, ValueError):
        return 0


def _segment_revision_key(asset: dict[str, Any]) -> tuple[int, str, str]:
    try:
        version = int(asset.get("version") or 0)
    except (TypeError, ValueError):
        version = 0
    return (
        version,
        str(asset.get("created_at") or ""),
        str(asset.get("asset_id") or ""),
    )


def _latest_segments_by_index(
    segments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Keep the newest stored revision for each RunningHub segment index."""

    latest: dict[int, dict[str, Any]] = {}
    invalid: list[dict[str, Any]] = []
    for asset in segments:
        video_index = _segment_index(asset)
        if video_index <= 0:
            invalid.append(asset)
            continue
        current = latest.get(video_index)
        if current is None or _segment_revision_key(asset) > _segment_revision_key(current):
            latest[video_index] = asset
    return [*invalid, *latest.values()]


def _segments_bound_to_base_video(
    base: dict[str, Any], segments: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Discard historical RunningHub segments not used by the current base video."""

    source_task_ids = base.get("external_ref", {}).get("source_task_ids")
    if not isinstance(source_task_ids, list) or not source_task_ids:
        return segments
    bound_task_ids = {str(value) for value in source_task_ids if str(value)}
    return [
        asset
        for asset in segments
        if str(asset.get("external_ref", {}).get("remote_task_id") or "")
        in bound_task_ids
    ]


def _base_video_source(item: dict[str, Any]) -> dict[str, Any]:
    outputs = item.get("outputs", {})
    base = outputs.get("base_video")
    if not isinstance(base, dict) or not base.get("managed_path"):
        raise ValueError(f"任务 {item.get('row_key') or item.get('item_id')} 缺少基础视频")
    return {
        "type": "video",
        "media_path": str(Path(str(base["managed_path"])).resolve()),
    }


def _actual_segment_duration_us(asset: dict[str, Any]) -> int:
    """Return the playable duration of the exact stored segment file."""

    metadata = asset.get("metadata")
    recorded = metadata.get("actual_duration_us") if isinstance(metadata, dict) else None
    if type(recorded) is int and recorded > 0:
        return recorded
    return probe_video_duration_us(str(asset["managed_path"]))


def _segment_timeline(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build one cumulative timeline from the actual segment media files."""

    cursor_us = 0
    timeline: list[dict[str, Any]] = []
    for asset in segments:
        duration_us = _actual_segment_duration_us(asset)
        if duration_us <= 0:
            raise ValueError(f"原始分段 {_segment_index(asset)} 的实际视频时长无效")
        start_us = cursor_us
        cursor_us += duration_us
        timeline.append(
            {
                "asset": asset,
                "start_us": start_us,
                "end_us": cursor_us,
                "duration_us": duration_us,
            }
        )
    return timeline


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
        # MiniMax files can contain a small encoder tail beyond the approved
        # picture. Resolve this against the source draft timeline at render
        # time instead of letting the native audio extend the composition.
        "target_duration_us": 0,
        "fit_to_video": True,
        "volume": 1.0,
    }


def project_segment_boundaries(item: dict[str, Any]) -> list[dict[str, Any]]:
    """Return current multi-segment speech boundaries for local visual planning."""

    outputs = item.get("outputs", {})
    base = outputs.get("base_video")
    if not isinstance(base, dict):
        return []
    try:
        expected = int(base.get("metadata", {}).get("segment_count") or 0)
    except (TypeError, ValueError):
        return []
    if expected <= 1:
        return []
    segments = sorted(
        _latest_segments_by_index(
            _segments_bound_to_base_video(
                base,
                [
                    asset
                    for asset in outputs.get("original_video_segments", [])
                    if isinstance(asset, dict)
                    and asset.get("status") == "READY"
                    and asset.get("managed_path")
                ],
            )
        ),
        key=_segment_index,
    )
    if len(segments) != expected or [_segment_index(asset) for asset in segments] != list(
        range(1, expected + 1)
    ):
        return []
    try:
        timeline = _segment_timeline(segments)
    except (FileNotFoundError, RuntimeError, ValueError):
        # A wrong seam is more harmful than omitting an optional seam overlay.
        return []
    boundaries: list[dict[str, Any]] = []
    for entry in timeline[1:]:
        asset = entry["asset"]
        metadata = asset.get("metadata", {})
        boundaries.append(
            {
                "boundary_us": int(entry["start_us"]),
                "segment_index": _segment_index(asset),
                "segment_start_us": int(entry["start_us"]),
                "segment_end_us": int(entry["end_us"]),
                "script_text": str(metadata.get("script_text") or ""),
            }
        )
    return boundaries


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
        _latest_segments_by_index(
            _segments_bound_to_base_video(
                base,
                [
                    asset
                    for asset in outputs.get("original_video_segments", [])
                    if isinstance(asset, dict)
                    and asset.get("status") == "READY"
                    and asset.get("managed_path")
                ],
            )
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

    timeline = _segment_timeline(segments)
    source_items: list[dict[str, Any]] = []
    for entry in timeline:
        asset = entry["asset"]
        duration_us = int(entry["duration_us"])
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
