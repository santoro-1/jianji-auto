from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Iterable

from .cli import import_pyjianyingdraft, log
from .content_replace import apply_text_track_style


@dataclass(frozen=True)
class CaptionCue:
    start_us: int
    duration_us: int
    text: str

    @property
    def end_us(self) -> int:
        return self.start_us + self.duration_us

    def as_dict(self) -> dict[str, int | str]:
        return {
            "start_us": self.start_us,
            "duration_us": self.duration_us,
            "end_us": self.end_us,
            "text": self.text,
        }


def _display_units(text: str) -> float:
    units = 0.0
    for char in text:
        code = ord(char)
        if char.isspace():
            units += 0.35
        elif char.isascii() and char.isalnum():
            units += 0.55
        elif char in "，。！？；：、,.!?;:()（）《》<>\"'“”‘’":
            units += 0.5
        elif 0x2E80 <= code <= 0x9FFF or 0xFF00 <= code <= 0xFFEF:
            units += 1.0
        else:
            units += 0.8
    return units


def _split_paragraph(paragraph: str, max_units: float) -> list[str]:
    chunks: list[str] = []
    break_chars = set("，,、：:。！？!?；;")
    cursor = 0
    while cursor < len(paragraph):
        width = 0.0
        end = cursor
        while end < len(paragraph):
            next_width = width + _display_units(paragraph[end])
            if end > cursor and next_width > max_units:
                break
            width = next_width
            end += 1

        if end >= len(paragraph):
            tail = paragraph[cursor:].strip()
            if tail:
                chunks.append(tail)
            break

        window = paragraph[cursor:end]
        preferred_breaks = [
            index + 1
            for index, char in enumerate(window)
            if char in break_chars and _display_units(window[: index + 1]) >= max_units * 0.45
        ]
        cut = cursor + (preferred_breaks[-1] if preferred_breaks else len(window))
        chunk = paragraph[cursor:cut].strip()
        if chunk:
            chunks.append(chunk)
        cursor = cut
        while cursor < len(paragraph) and paragraph[cursor].isspace():
            cursor += 1
    return chunks


def split_caption_text(text: str, max_chars: int = 16) -> list[str]:
    """Split long copy into readable caption chunks using punctuation and visual width."""

    if not text or not text.strip():
        return []
    if not 4 <= int(max_chars) <= 60:
        raise ValueError(f"每条字幕最大字数必须在 4 到 60 之间: {max_chars}")

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    paragraphs = [re.sub(r"[ \t]+", " ", item).strip() for item in normalized.split("\n")]
    result: list[str] = []

    for paragraph in paragraphs:
        if not paragraph:
            continue
        result.extend(_split_paragraph(paragraph, float(max_chars)))

    return result


def build_caption_cues(
    text: str,
    *,
    start_us: int = 0,
    duration_us: int,
    max_chars: int = 16,
    min_duration_us: int = 650_000,
) -> list[CaptionCue]:
    chunks = split_caption_text(text, max_chars=max_chars)
    if not chunks:
        return []
    if start_us < 0:
        raise ValueError(f"字幕开始时间不能小于 0: {start_us}")
    if duration_us <= 0:
        raise ValueError(f"字幕总时长必须大于 0: {duration_us}")
    if duration_us < len(chunks):
        raise ValueError("字幕总时长过短，无法为每条字幕分配有效时间")

    base_duration = min(max(0, int(min_duration_us)), duration_us // len(chunks))
    remaining = duration_us - base_duration * len(chunks)
    weights = [max(1.0, _display_units(chunk)) for chunk in chunks]
    total_weight = sum(weights)

    cues: list[CaptionCue] = []
    cursor = start_us
    allocated_extra = 0
    for index, (chunk, weight) in enumerate(zip(chunks, weights)):
        if index == len(chunks) - 1:
            extra = remaining - allocated_extra
            cue_duration = start_us + duration_us - cursor
        else:
            next_allocated_extra = round(remaining * sum(weights[: index + 1]) / total_weight)
            extra = next_allocated_extra - allocated_extra
            allocated_extra = next_allocated_extra
            cue_duration = base_duration + extra
        cues.append(CaptionCue(start_us=cursor, duration_us=cue_duration, text=chunk))
        cursor += cue_duration
    return cues


def _srt_timestamp(value_us: int) -> str:
    milliseconds = max(0, value_us // 1000)
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    seconds, milliseconds = divmod(milliseconds, 1_000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def cues_to_srt(cues: Iterable[CaptionCue]) -> str:
    blocks = []
    for index, cue in enumerate(cues, start=1):
        blocks.append(
            f"{index}\n{_srt_timestamp(cue.start_us)} --> {_srt_timestamp(cue.end_us)}\n{cue.text}"
        )
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def add_captions_to_draft(
    draft_dir: str | Path,
    cues: list[CaptionCue],
    *,
    style_json_path: str | Path = "",
    size: float | None = None,
    color: str = "",
    transform_x: float | None = None,
    transform_y: float | None = None,
    line_max_width: float | None = None,
    font_id: str = "",
    font_path: str = "",
    font_title: str = "",
    track_name: str = "自动字幕",
) -> Path:
    if not cues:
        raise ValueError("没有可导入的字幕")

    draft_path = Path(draft_dir).resolve()
    srt_path = draft_path / "auto_captions.srt"
    srt_path.write_text(cues_to_srt(cues), encoding="utf-8-sig")

    draft = import_pyjianyingdraft()
    folder = draft.DraftFolder(str(draft_path.parent))
    script = folder.load_template(draft_path.name)
    actual_track_name = track_name or "自动字幕"
    suffix = 2
    while actual_track_name in script.tracks:
        actual_track_name = f"{track_name or '自动字幕'}_{suffix}"
        suffix += 1
    default_size = float(size) if size is not None and size > 0 else 8.0
    default_width = float(line_max_width) if line_max_width is not None else 0.82
    script.import_srt(
        str(srt_path),
        actual_track_name,
        text_style=draft.TextStyle(
            size=default_size,
            align=1,
            auto_wrapping=True,
            max_line_width=default_width,
        ),
        clip_settings=draft.ClipSettings(
            transform_x=float(transform_x or 0.0),
            transform_y=float(transform_y if transform_y is not None else -0.8),
        ),
    )
    script.save()

    apply_text_track_style(
        draft_path,
        track_name=actual_track_name,
        style_json_path=style_json_path,
        size=size,
        color=color,
        transform_x=transform_x,
        transform_y=transform_y,
        line_max_width=line_max_width,
        font_id=font_id,
        font_path=font_path,
        font_title=font_title,
    )
    log(f"已导入自动字幕: track={actual_track_name!r}, cues={len(cues)}, srt={srt_path}")
    return srt_path
