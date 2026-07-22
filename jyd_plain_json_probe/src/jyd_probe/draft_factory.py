from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

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
