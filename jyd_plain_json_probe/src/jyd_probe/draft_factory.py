from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .cli import append_track_compat, import_pyjianyingdraft, log


@dataclass(frozen=True)
class CreatedVideoDraft:
    draft_dir: Path
    draft_name: str
    media_path: Path
    duration_us: int
    width: int
    height: int
    fps: int


@dataclass(frozen=True)
class VideoSequenceItem:
    media_path: Path
    target_duration_us: int = 0
    source_start_us: int = 0


def _safe_draft_name(stem: str) -> str:
    keep = []
    for char in stem.strip():
        if char in '<>:"/\\|?*':
            keep.append("_")
        else:
            keep.append(char)
    name = "".join(keep).strip(" ._")
    return name or "uploaded_video"


def create_plain_draft_from_video(
    media_path: str | Path,
    output_root: str | Path,
    *,
    draft_name: str = "",
    width: int = 0,
    height: int = 0,
    fps: int = 30,
    source_start_us: int = 0,
    source_duration_us: int = 0,
) -> CreatedVideoDraft:
    """Create a plain Jianying draft containing one top-level video segment."""

    draft = import_pyjianyingdraft()
    media = Path(media_path).expanduser().resolve()
    root = Path(output_root).expanduser().resolve()
    if not media.exists():
        raise FileNotFoundError(f"输入视频不存在: {media}")
    if not root.exists():
        root.mkdir(parents=True, exist_ok=True)

    material = draft.VideoMaterial(str(media))
    canvas_width = int(width) if width and width > 0 else int(material.width)
    canvas_height = int(height) if height and height > 0 else int(material.height)
    canvas_fps = int(fps) if fps and fps > 0 else 30

    source_start = max(0, int(source_start_us))
    available_duration = max(0, int(material.duration) - source_start)
    segment_duration = int(source_duration_us) if source_duration_us and source_duration_us > 0 else available_duration
    if segment_duration <= 0:
        raise RuntimeError(
            f"输入视频可用时长无效: material_duration={material.duration}, source_start_us={source_start}"
        )
    if source_start + segment_duration > int(material.duration):
        raise RuntimeError(
            "输入视频截取范围超过素材时长: "
            f"source_start_us={source_start}, source_duration_us={segment_duration}, "
            f"material_duration={material.duration}"
        )

    if not draft_name:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        draft_name = f"{_safe_draft_name(media.stem)}_base_{stamp}"

    folder = draft.DraftFolder(str(root))
    script = folder.create_draft(
        draft_name,
        canvas_width,
        canvas_height,
        canvas_fps,
        maintrack_adsorb=True,
        allow_replace=False,
    )
    append_track_compat(draft, script, draft.TrackType.video)
    script.add_segment(
        draft.VideoSegment(
            material,
            draft.Timerange(0, segment_duration),
            source_timerange=draft.Timerange(source_start, segment_duration),
        )
    )
    script.save()

    draft_dir = root / draft_name
    log(
        "已从输入视频创建基础草稿: "
        f"draft_dir={draft_dir}, duration={segment_duration}, canvas={canvas_width}x{canvas_height}, fps={canvas_fps}"
    )
    return CreatedVideoDraft(
        draft_dir=draft_dir,
        draft_name=draft_name,
        media_path=media,
        duration_us=segment_duration,
        width=canvas_width,
        height=canvas_height,
        fps=canvas_fps,
    )


def _extract_tail_frame(media: Path, output: Path, duration_us: int) -> None:
    import cv2

    capture = cv2.VideoCapture(str(media))
    if not capture.isOpened():
        raise RuntimeError(f"无法读取分段视频尾帧: {media}")
    try:
        capture.set(cv2.CAP_PROP_POS_MSEC, max(0, duration_us - 40_000) / 1000.0)
        ok, frame = capture.read()
        if not ok or frame is None:
            capture.set(cv2.CAP_PROP_POS_AVI_RATIO, 1.0)
            ok, frame = capture.read()
        if not ok or frame is None:
            raise RuntimeError(f"无法提取分段视频尾帧: {media}")
        output.parent.mkdir(parents=True, exist_ok=True)
        encoded, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
        if not encoded:
            raise RuntimeError(f"无法编码分段视频尾帧: {media}")
        buffer.tofile(str(output))
    finally:
        capture.release()


def create_plain_draft_from_videos(
    items: Iterable[VideoSequenceItem],
    output_root: str | Path,
    *,
    draft_name: str = "",
    width: int = 0,
    height: int = 0,
    fps: int = 30,
) -> CreatedVideoDraft:
    """Create one main track whose source videos remain separate, ordered clips."""

    draft = import_pyjianyingdraft()
    sequence = [
        VideoSequenceItem(
            Path(item.media_path).expanduser().resolve(),
            max(0, int(item.target_duration_us)),
            max(0, int(item.source_start_us)),
        )
        for item in items
    ]
    if not sequence:
        raise ValueError("多段主轨道至少需要一个视频素材")
    for item in sequence:
        if not item.media_path.is_file():
            raise FileNotFoundError(f"分段视频不存在: {item.media_path}")

    root = Path(output_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    materials = [draft.VideoMaterial(str(item.media_path)) for item in sequence]
    first = materials[0]
    canvas_width = int(width) if width and width > 0 else int(first.width)
    canvas_height = int(height) if height and height > 0 else int(first.height)
    canvas_fps = int(fps) if fps and fps > 0 else 30
    if not draft_name:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        draft_name = f"{_safe_draft_name(sequence[0].media_path.stem)}_sequence_{stamp}"

    folder = draft.DraftFolder(str(root))
    script = folder.create_draft(
        draft_name,
        canvas_width,
        canvas_height,
        canvas_fps,
        maintrack_adsorb=True,
        allow_replace=False,
    )
    append_track_compat(draft, script, draft.TrackType.video)
    cursor = 0
    for index, (item, material) in enumerate(zip(sequence, materials), start=1):
        available = max(0, int(material.duration) - item.source_start_us)
        if available <= 0:
            raise RuntimeError(f"分段视频可用时长无效: {item.media_path}")
        requested = item.target_duration_us or available
        clip_duration = min(requested, available)
        script.add_segment(
            draft.VideoSegment(
                material,
                draft.Timerange(cursor, clip_duration),
                source_timerange=draft.Timerange(item.source_start_us, clip_duration),
            )
        )
        cursor += clip_duration
        hold_duration = requested - clip_duration
        if hold_duration > 0:
            hold_path = root / draft_name / "_segment_holds" / f"segment-{index:03d}-tail.jpg"
            _extract_tail_frame(item.media_path, hold_path, int(material.duration))
            hold_material = draft.VideoMaterial(str(hold_path))
            script.add_segment(
                draft.VideoSegment(
                    hold_material,
                    draft.Timerange(cursor, hold_duration),
                    source_timerange=draft.Timerange(0, hold_duration),
                    volume=0.0,
                )
            )
            cursor += hold_duration
    script.save()

    draft_dir = root / draft_name
    log(
        "已从原始分段创建独立主轨道: "
        f"draft_dir={draft_dir}, clips={len(sequence)}, duration={cursor}, "
        f"canvas={canvas_width}x{canvas_height}, fps={canvas_fps}"
    )
    return CreatedVideoDraft(
        draft_dir=draft_dir,
        draft_name=draft_name,
        media_path=sequence[0].media_path,
        duration_us=cursor,
        width=canvas_width,
        height=canvas_height,
        fps=canvas_fps,
    )
