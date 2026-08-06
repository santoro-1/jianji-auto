from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .subtitles import CaptionCue, caption_cues_from_payload


SEMANTIC_MAPPING_SCHEMA = "jyd.semantic-caption-mapping.v1"
_KINDS = {"word", "phrase", "number", "proper_noun", "connector", "punctuation", "whitespace"}
_BINDS = {"none", "left", "right", "both"}
_BREAKS = {"prefer", "allow", "avoid"}
_FORBIDDEN_TIME_FIELDS = {"start_us", "end_us", "duration_us", "timestamp", "time"}


class SemanticSubtitleMappingError(ValueError):
    """Semantic units cannot be safely anchored to the current MiniMax cues."""

    def __init__(self, code: str, summary: str) -> None:
        super().__init__(summary)
        self.code = str(code or "SEMANTIC_MAPPING_FAILED")[:100]
        self.summary = str(summary or "字幕语义时间映射失败")[:500]


@dataclass(frozen=True)
class TimedSemanticUnit:
    start: int
    end: int
    text: str
    kind: str
    bind: str
    break_after: str
    start_us: int
    end_us: int

    def as_dict(self) -> dict[str, int | str]:
        return {
            "start": self.start,
            "end": self.end,
            "text": self.text,
            "kind": self.kind,
            "bind": self.bind,
            "break_after": self.break_after,
            "start_us": self.start_us,
            "end_us": self.end_us,
            "duration_us": self.end_us - self.start_us,
        }


def _validated_units(
    original_script: str,
    subtitle_units: Iterable[object],
) -> list[dict[str, Any]]:
    if not isinstance(original_script, str) or not original_script:
        raise SemanticSubtitleMappingError("SCRIPT_EMPTY", "当前脚本文本为空")
    if not isinstance(subtitle_units, list) or not subtitle_units:
        raise SemanticSubtitleMappingError(
            "SUBTITLE_UNITS_MISSING", "当前分析没有可用的 subtitle_units"
        )
    result: list[dict[str, Any]] = []
    cursor = 0
    for index, raw in enumerate(subtitle_units, start=1):
        if not isinstance(raw, Mapping):
            raise SemanticSubtitleMappingError(
                "SUBTITLE_UNIT_INVALID", f"第 {index} 个字幕语义单元不是对象"
            )
        if _FORBIDDEN_TIME_FIELDS.intersection(raw):
            raise SemanticSubtitleMappingError(
                "MODEL_TIMESTAMP_FORBIDDEN", "字幕语义单元不得包含大模型生成的时间字段"
            )
        start = raw.get("start")
        end = raw.get("end")
        text = raw.get("text")
        if (
            isinstance(start, bool)
            or isinstance(end, bool)
            or not isinstance(start, int)
            or not isinstance(end, int)
            or not isinstance(text, str)
        ):
            raise SemanticSubtitleMappingError(
                "SUBTITLE_UNIT_INVALID", f"第 {index} 个字幕语义单元字段无效"
            )
        if start != cursor or end <= start or end > len(original_script):
            raise SemanticSubtitleMappingError(
                "SUBTITLE_UNIT_RANGE_INVALID", "subtitle_units 没有按原文位置连续覆盖"
            )
        if original_script[start:end] != text:
            raise SemanticSubtitleMappingError(
                "SUBTITLE_TEXT_MISMATCH", "subtitle_units 没有逐字符重建当前脚本"
            )
        kind = str(raw.get("kind") or "")
        bind = str(raw.get("bind") or "none")
        break_after = str(raw.get("break_after") or "allow")
        if kind not in _KINDS or bind not in _BINDS or break_after not in _BREAKS:
            raise SemanticSubtitleMappingError(
                "SUBTITLE_SEMANTICS_INVALID", "subtitle_units 的语义属性不符合 v1 契约"
            )
        if (kind == "whitespace" and not text.isspace()) or (
            kind != "whitespace" and text.isspace()
        ):
            raise SemanticSubtitleMappingError(
                "SUBTITLE_SEMANTICS_INVALID", "空白文本与 whitespace 类型不一致"
            )
        if bind in {"right", "both"} and break_after != "avoid":
            raise SemanticSubtitleMappingError(
                "SUBTITLE_BINDING_CONFLICT", "右绑定单元后方必须避免断句"
            )
        result.append(
            {
                "start": start,
                "end": end,
                "text": text,
                "kind": kind,
                "bind": bind,
                "break_after": break_after,
            }
        )
        cursor = end
    if cursor != len(original_script) or "".join(unit["text"] for unit in result) != original_script:
        raise SemanticSubtitleMappingError(
            "SUBTITLE_COVERAGE_INCOMPLETE", "subtitle_units 没有完整覆盖当前脚本"
        )
    for index in range(1, len(result)):
        if result[index]["bind"] in {"left", "both"} and result[index - 1]["break_after"] != "avoid":
            raise SemanticSubtitleMappingError(
                "SUBTITLE_BINDING_CONFLICT", "左绑定单元前方必须避免断句"
            )
    return result


def _spoken_characters(value: str) -> list[str]:
    return [character for character in value if not character.isspace()]


def _character_time_ranges(
    original_script: str,
    raw_cues: Iterable[object],
) -> dict[int, tuple[int, int]]:
    try:
        cues = caption_cues_from_payload(raw_cues)
    except (TypeError, ValueError) as exc:
        raise SemanticSubtitleMappingError(
            "RAW_CUES_INVALID", "MiniMax raw_cues 结构或时间范围无效"
        ) from exc
    if not cues:
        raise SemanticSubtitleMappingError(
            "RAW_CUES_MISSING", "当前音频没有 MiniMax raw_cues"
        )
    script_positions = [
        (index, character)
        for index, character in enumerate(original_script)
        if not character.isspace()
    ]
    provider_characters = [
        character
        for cue in cues
        for character in _spoken_characters(cue.text)
    ]
    if provider_characters != [character for _, character in script_positions]:
        raise SemanticSubtitleMappingError(
            "RAW_CUES_TEXT_MISMATCH",
            "MiniMax raw_cues 去除空白后不能逐字符重建当前脚本",
        )

    ranges: dict[int, tuple[int, int]] = {}
    position_cursor = 0
    for cue in cues:
        cue_characters = _spoken_characters(cue.text)
        count = len(cue_characters)
        if count <= 0:
            raise SemanticSubtitleMappingError(
                "RAW_CUE_TEXT_EMPTY", "MiniMax raw_cues 包含纯空白字幕"
            )
        for offset, expected in enumerate(cue_characters):
            script_index, actual = script_positions[position_cursor]
            if actual != expected:
                raise SemanticSubtitleMappingError(
                    "RAW_CUES_TEXT_MISMATCH", "MiniMax raw_cues 字符顺序与当前脚本不一致"
                )
            start_us = cue.start_us + round(cue.duration_us * offset / count)
            end_us = cue.start_us + round(cue.duration_us * (offset + 1) / count)
            if end_us <= start_us:
                raise SemanticSubtitleMappingError(
                    "RAW_CUE_RESOLUTION_TOO_LOW", "MiniMax cue 时间精度不足以映射全部字符"
                )
            ranges[script_index] = (start_us, end_us)
            position_cursor += 1
    return ranges


def map_subtitle_units_to_raw_cues(
    original_script: str,
    subtitle_units: Iterable[object],
    raw_cues: Iterable[object],
) -> list[dict[str, int | str]]:
    """Map model-provided character units onto MiniMax time anchors only."""

    units = _validated_units(original_script, subtitle_units)
    character_ranges = _character_time_ranges(original_script, raw_cues)
    result: list[TimedSemanticUnit] = []
    previous_end_us = -1
    for unit in units:
        spoken_positions = [
            index
            for index in range(unit["start"], unit["end"])
            if index in character_ranges
        ]
        if spoken_positions:
            start_us = character_ranges[spoken_positions[0]][0]
            end_us = character_ranges[spoken_positions[-1]][1]
        else:
            previous_positions = [
                position for position in character_ranges if position < unit["start"]
            ]
            next_positions = [
                position for position in character_ranges if position >= unit["end"]
            ]
            previous_time = (
                character_ranges[max(previous_positions)][1]
                if previous_positions
                else None
            )
            next_time = (
                character_ranges[min(next_positions)][0]
                if next_positions
                else None
            )
            start_us = previous_time if previous_time is not None else int(next_time or 0)
            end_us = next_time if next_time is not None else int(previous_time or 0)
        if start_us < previous_end_us or end_us < start_us or (
            end_us == start_us and unit["kind"] != "whitespace"
        ):
            raise SemanticSubtitleMappingError(
                "SEMANTIC_TIME_NOT_MONOTONIC", "语义单元映射后的时间范围不单调"
            )
        result.append(
            TimedSemanticUnit(
                start=unit["start"],
                end=unit["end"],
                text=unit["text"],
                kind=unit["kind"],
                bind=unit["bind"],
                break_after=unit["break_after"],
                start_us=start_us,
                end_us=end_us,
            )
        )
        previous_end_us = end_us
    return [unit.as_dict() for unit in result]


def semantic_break_groups(
    timed_units: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Merge units across boundaries that the semantic contract forbids breaking."""

    units = [dict(unit) for unit in timed_units]
    if not units:
        raise SemanticSubtitleMappingError("SUBTITLE_UNITS_MISSING", "没有已映射的语义单元")
    groups: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []
    for index, unit in enumerate(units):
        unit_text = str(unit.get("text") or "")
        is_line_break = unit.get("kind") == "whitespace" and any(
            character in unit_text for character in "\r\n"
        )
        if is_line_break:
            # A paragraph break carries no visible text or useful timing of its own.
            # The previous group was already closed before it, and the next unit must
            # start a fresh group so layout can never join text across paragraphs.
            continue
        current.append(unit)
        next_unit = units[index + 1] if index + 1 < len(units) else None
        next_text = str(next_unit.get("text") or "") if next_unit else ""
        next_is_line_break = bool(
            next_unit
            and next_unit.get("kind") == "whitespace"
            and any(character in next_text for character in "\r\n")
        )
        boundary_forbidden = bool(
            next_unit
            and not next_is_line_break
            and (
                unit.get("break_after") == "avoid"
                or unit.get("bind") in {"right", "both"}
                or next_unit.get("bind") in {"left", "both"}
                or unit.get("kind") == "whitespace"
                or (
                    next_unit.get("kind") == "whitespace"
                    and not next_is_line_break
                )
                or next_unit.get("kind") == "punctuation"
                or (index == 0 and unit.get("kind") == "punctuation")
            )
        )
        if boundary_forbidden:
            continue
        groups.append(
            {
                "text": "".join(str(part.get("text") or "") for part in current),
                "start_us": int(current[0]["start_us"]),
                "end_us": int(current[-1]["end_us"]),
                "break_after": str(current[-1].get("break_after") or "allow"),
                "hard_break_after": next_is_line_break,
                "unit_count": len(current),
            }
        )
        current = []
    if current:
        raise SemanticSubtitleMappingError(
            "SUBTITLE_GROUP_INCOMPLETE", "语义绑定关系无法形成完整字幕组"
        )
    return groups
