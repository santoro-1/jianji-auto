from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
from typing import Any, Iterable
import uuid

from fontTools.ttLib import TTFont

from .music_matching import MusicProfileMatcher
from .project_music import ProjectMusicSelector, manual_music_selection
from .project_store import ProjectStore
from .project_video_source import build_project_video_source
from .semantic_subtitles import (
    SEMANTIC_MAPPING_SCHEMA,
    SemanticSubtitleMappingError,
    map_subtitle_units_to_raw_cues,
    semantic_break_groups,
)
from .subtitles import CaptionCue, caption_cues_from_payload


CAPTION_MAX_WIDTH_RATIO = 0.8
CAPTION_MAX_LINES = 1
CAPTION_BOTTOM_OFFSET_RATIO = 0.2
CAPTION_TRANSFORM_Y = -0.6
CAPTION_REFERENCE_FONT_SIZE = 11.0
CAPTION_REFERENCE_MAX_EM = 13.0
CAPTION_STROKE_COLOR = "#000000"
CAPTION_STROKE_WIDTH = 0.06
CAPTION_MIN_SLICE_US = 80_000
_BREAK_CHARS = set("，,、：:。.！？!?；;")
_HIDDEN_CAPTION_PUNCTUATION = _BREAK_CHARS | set("…")
_HARD_SENTENCE_BREAKS = set("。.！？!?；;…\r\n")
_SOFT_SENTENCE_BREAKS = set("，,、：:")
_ORPHAN_PARTICLES = tuple("的地得呢啊了吧吗")
_PROTECTED_TERMS = (
    "表现",
    "问题",
    "世界冠军",
    "核心逻辑",
    "储存",
    "储存机制",
    "小时",
    "新中年女性",
    "女性",
    "健康体重管理",
    "胖肚子",
    "以及",
    "内脏脂肪",
    "呼吸",
    "形式",
    "脂肪",
    "糖原",
    "二氧化碳",
    "葡萄糖",
)
_PREFERRED_PHRASE_END_TERMS = (
    "世界冠军",
    "新中年女性",
    "健康体重管理",
    "核心逻辑",
    "胖肚子",
    "内脏脂肪",
    "形式",
)
_LEADING_CONNECTORS = (
    "那么",
    "但是",
    "所以",
    "然后",
    "不过",
    "因此",
    "同时",
    "另外",
    "而且",
    "其实",
    "如果",
    "因为",
    "虽然",
    "否则",
    "比如",
    "例如",
)
_HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")


class CaptionLayoutReviewRequired(ValueError):
    """The selected font cannot safely produce the requested one-line cues."""


@dataclass(frozen=True)
class FontMetrics:
    path: Path
    units_per_em: int
    cmap: dict[int, str]
    advances: dict[str, tuple[int, int]]

    @classmethod
    def load(cls, path: str | Path) -> "FontMetrics":
        resolved = Path(path).resolve()
        if not resolved.is_file():
            raise CaptionLayoutReviewRequired("所选字幕字体文件不存在")
        try:
            font = TTFont(str(resolved), lazy=True)
            cmap = font.getBestCmap() or {}
            advances = dict(font["hmtx"].metrics)
            units_per_em = int(font["head"].unitsPerEm)
            font.close()
        except Exception as exc:
            raise CaptionLayoutReviewRequired("无法读取所选字幕字体的真实字宽") from exc
        if not cmap or not advances or units_per_em <= 0:
            raise CaptionLayoutReviewRequired("所选字幕字体缺少可用字宽数据")
        return cls(resolved, units_per_em, cmap, advances)

    def text_width_em(self, text: str) -> float:
        width = 0.0
        missing: list[str] = []
        for character in text:
            glyph = self.cmap.get(ord(character))
            metric = self.advances.get(glyph or "")
            if metric is None:
                missing.append(character)
                continue
            width += float(metric[0]) / self.units_per_em
        if missing:
            preview = "".join(dict.fromkeys(missing))[:8]
            raise CaptionLayoutReviewRequired(
                f"所选字体缺少字幕字符：{preview}"
            )
        return width


def _normalized_caption_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _is_numeric_separator(text: str, index: int) -> bool:
    return (
        text[index] in {".", ",", ":"}
        and index > 0
        and index + 1 < len(text)
        and text[index - 1].isdigit()
        and text[index + 1].isdigit()
    )


def _caption_display_text(value: str) -> tuple[str, set[int]]:
    """Remove display punctuation while retaining its preferred break positions."""

    normalized = _normalized_caption_text(value)
    display: list[str] = []
    preferred_breaks: set[int] = set()
    for index, character in enumerate(normalized):
        if (
            character in _HIDDEN_CAPTION_PUNCTUATION
            and not _is_numeric_separator(normalized, index)
        ):
            if display:
                preferred_breaks.add(len(display))
            continue
        display.append(character)
    cleaned = "".join(display).strip()
    if not cleaned:
        raise CaptionLayoutReviewRequired("字幕去除标点后内容为空")
    return cleaned, {position for position in preferred_breaks if 0 < position < len(cleaned)}


def _trailing_sentence_break(text: str) -> str:
    normalized = str(text or "").rstrip()
    if not normalized:
        return ""
    if normalized[-1] in _HARD_SENTENCE_BREAKS:
        return "hard"
    if normalized[-1] in _SOFT_SENTENCE_BREAKS:
        return "soft"
    return ""


def _unbreakable_terms() -> tuple[str, ...]:
    return (*_PROTECTED_TERMS, *_LEADING_CONNECTORS)


def _merge_unbreakable_term_boundaries(
    groups: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Discard model boundaries that split a known lexical unit."""

    source_text = "".join(str(group.get("text") or "") for group in groups)
    unsafe_offsets: set[int] = set()
    for term in _unbreakable_terms():
        cursor = 0
        while True:
            position = source_text.find(term, cursor)
            if position < 0:
                break
            unsafe_offsets.update(range(position + 1, position + len(term)))
            cursor = position + 1

    merged: list[dict[str, Any]] = []
    source_offset = 0
    for source in groups:
        group = dict(source)
        if merged and source_offset in unsafe_offsets:
            previous = merged.pop()
            group = {
                "text": str(previous.get("text") or "") + str(group.get("text") or ""),
                "start_us": int(previous.get("start_us") or 0),
                "end_us": int(group.get("end_us") or 0),
                "break_after": str(group.get("break_after") or "allow"),
                "hard_break_after": bool(group.get("hard_break_after")),
                "unit_count": int(previous.get("unit_count") or 1)
                + int(group.get("unit_count") or 1),
            }
        merged.append(group)
        source_offset += len(str(source.get("text") or ""))
    return merged


def _merge_orphan_sentence_tails(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Repair one-character tails and very short comma-led prefixes."""

    merged: list[dict[str, Any]] = []
    for source in groups:
        group = dict(source)
        display, _preferred = _caption_display_text(str(group.get("text") or ""))
        if (
            merged
            and len(display) == 1
            and _trailing_sentence_break(str(group.get("text") or ""))
        ):
            previous = merged.pop()
            group = {
                "text": str(previous.get("text") or "") + str(group.get("text") or ""),
                "start_us": int(previous.get("start_us") or 0),
                "end_us": int(group.get("end_us") or 0),
                "break_after": str(group.get("break_after") or "allow"),
                "hard_break_after": bool(group.get("hard_break_after")),
                "unit_count": int(previous.get("unit_count") or 1)
                + int(group.get("unit_count") or 1),
            }
        merged.append(group)

    rebalanced: list[dict[str, Any]] = []
    index = 0
    while index < len(merged):
        group = merged[index]
        display, _preferred = _caption_display_text(str(group.get("text") or ""))
        if (
            index + 1 < len(merged)
            and len(display) < 4
            and _trailing_sentence_break(str(group.get("text") or "")) == "soft"
        ):
            following = merged[index + 1]
            rebalanced.append(
                {
                    "text": str(group.get("text") or "")
                    + str(following.get("text") or ""),
                    "start_us": int(group.get("start_us") or 0),
                    "end_us": int(following.get("end_us") or 0),
                    "break_after": str(following.get("break_after") or "allow"),
                    "hard_break_after": bool(following.get("hard_break_after")),
                    "unit_count": int(group.get("unit_count") or 1)
                    + int(following.get("unit_count") or 1),
                }
            )
            index += 2
            continue
        rebalanced.append(group)
        index += 1

    attached: list[dict[str, Any]] = []
    for group in rebalanced:
        display, _preferred = _caption_display_text(str(group.get("text") or ""))
        if (
            attached
            and display.startswith(_ORPHAN_PARTICLES)
            and _trailing_sentence_break(str(attached[-1].get("text") or ""))
            != "hard"
        ):
            previous = attached.pop()
            group = {
                "text": str(previous.get("text") or "") + str(group.get("text") or ""),
                "start_us": int(previous.get("start_us") or 0),
                "end_us": int(group.get("end_us") or 0),
                "break_after": str(group.get("break_after") or "allow"),
                "hard_break_after": bool(group.get("hard_break_after")),
                "unit_count": int(previous.get("unit_count") or 1)
                + int(group.get("unit_count") or 1),
            }
        attached.append(group)
    return attached


def _split_one_line(
    text: str, metrics: FontMetrics, *, maximum_width_em: float
) -> list[str]:
    normalized, preferred_breaks = _caption_display_text(text)
    if not normalized:
        raise CaptionLayoutReviewRequired("字幕内容为空")
    if metrics.text_width_em(normalized) <= maximum_width_em:
        return [normalized]

    connector_starts: set[int] = set()
    connector_ends: set[int] = set()
    for connector in _LEADING_CONNECTORS:
        cursor = 0
        while True:
            position = normalized.find(connector, cursor)
            if position < 0:
                break
            if position > 0:
                connector_starts.add(position)
                connector_ends.add(position + len(connector))
            cursor = position + len(connector)

    protected_breaks: set[int] = set()
    for term in _unbreakable_terms():
        cursor = 0
        while True:
            position = normalized.find(term, cursor)
            if position < 0:
                break
            protected_breaks.update(range(position + 1, position + len(term)))
            cursor = position + 1

    preferred_term_ends: set[int] = set()
    for term in _PREFERRED_PHRASE_END_TERMS:
        cursor = 0
        while True:
            position = normalized.find(term, cursor)
            if position < 0:
                break
            term_end = position + len(term)
            if term_end < len(normalized):
                preferred_term_ends.add(term_end)
            cursor = position + 1

    # Use a whole-sentence optimum instead of greedily preferring the first
    # punctuation seen in each window.  The greedy version could turn the
    # beginning of the next window into an orphan such as ``糖，``.
    length = len(normalized)
    widths = [0.0]
    for character in normalized:
        widths.append(widths[-1] + metrics.text_width_em(character))

    scores = [float("inf")] * (length + 1)
    previous: list[int | None] = [None] * (length + 1)
    scores[0] = 0.0
    for end in range(1, length + 1):
        for start in range(end - 1, -1, -1):
            width = widths[end] - widths[start]
            if width > maximum_width_em:
                break
            if scores[start] == float("inf"):
                continue
            chunk = normalized[start:end].strip()
            if not chunk:
                continue
            if end < length and end in protected_breaks:
                continue
            core_length = len(chunk)
            fill_ratio = width / maximum_width_em
            score = scores[start] + (1.0 - fill_ratio) ** 2
            if core_length < 4:
                score += (4 - core_length) * 8.0
            if end < length:
                score += 0.25
                if end in preferred_breaks:
                    score -= 0.35
                if end in connector_starts:
                    score -= 0.55
                if end in preferred_term_ends:
                    score -= 1.25
                if end in connector_ends or chunk.endswith(_LEADING_CONNECTORS):
                    score += 4.0
                if chunk.endswith(_ORPHAN_PARTICLES):
                    score += 10.0
            if start > 0 and chunk.startswith(_ORPHAN_PARTICLES):
                score += 10.0
            if score < scores[end]:
                scores[end] = score
                previous[end] = start

    if previous[length] is None:
        raise CaptionLayoutReviewRequired("字幕无法可靠拆成单行")
    chunks: list[str] = []
    cursor = length
    while cursor > 0:
        start = previous[cursor]
        if start is None:
            raise CaptionLayoutReviewRequired("字幕无法可靠拆成单行")
        chunks.append(normalized[start:cursor].strip())
        cursor = start
    chunks.reverse()
    return chunks


def _allocate_cue_chunks(
    cue: CaptionCue,
    chunks: list[str],
    metrics: FontMetrics,
) -> list[CaptionCue]:
    if len(chunks) == 1:
        return [CaptionCue(cue.start_us, cue.duration_us, chunks[0])]
    if cue.duration_us < len(chunks) * CAPTION_MIN_SLICE_US:
        raise CaptionLayoutReviewRequired("字幕时间过短，无法安全拆成多条单行字幕")
    weights = [max(metrics.text_width_em(chunk), 0.01) for chunk in chunks]
    total = sum(weights)
    result: list[CaptionCue] = []
    cursor = cue.start_us
    allocated = 0
    for index, (chunk, weight) in enumerate(zip(chunks, weights)):
        if index == len(chunks) - 1:
            duration = cue.end_us - cursor
        else:
            next_allocated = round(cue.duration_us * sum(weights[: index + 1]) / total)
            duration = next_allocated - allocated
            allocated = next_allocated
        if duration < CAPTION_MIN_SLICE_US:
            raise CaptionLayoutReviewRequired("字幕拆分后的显示时间过短")
        result.append(CaptionCue(cursor, duration, chunk))
        cursor += duration
    return result


def layout_one_line_captions(
    raw_cues: Iterable[object],
    *,
    font_path: str | Path,
    font_size: float = CAPTION_REFERENCE_FONT_SIZE,
    max_width_ratio: float = CAPTION_MAX_WIDTH_RATIO,
) -> list[dict[str, int | str]]:
    """Derive one-line render cues while preserving every provider cue range."""

    safe_size = float(font_size)
    safe_ratio = float(max_width_ratio)
    if safe_size <= 0:
        raise CaptionLayoutReviewRequired("字幕字号必须大于 0")
    if not 0.2 <= safe_ratio <= CAPTION_MAX_WIDTH_RATIO:
        raise CaptionLayoutReviewRequired("字幕宽度必须在画面宽度 20%–80% 之间")
    metrics = FontMetrics.load(font_path)
    maximum_width_em = (
        CAPTION_REFERENCE_MAX_EM
        * (safe_ratio / CAPTION_MAX_WIDTH_RATIO)
        * (CAPTION_REFERENCE_FONT_SIZE / safe_size)
    )
    result: list[CaptionCue] = []
    for cue in caption_cues_from_payload(raw_cues):
        chunks = _split_one_line(
            cue.text,
            metrics,
            maximum_width_em=maximum_width_em,
        )
        result.extend(_allocate_cue_chunks(cue, chunks, metrics))
    if not result:
        raise CaptionLayoutReviewRequired("当前音频没有可用的 MiniMax 字幕时间轴")
    return [cue.as_dict() for cue in result]


def _layout_semantic_groups(
    groups: list[dict[str, Any]],
    metrics: FontMetrics,
    *,
    maximum_width_em: float,
) -> list[dict[str, int | str]]:
    groups = _merge_unbreakable_term_boundaries(groups)
    groups = _merge_orphan_sentence_tails(groups)
    repaired_groups: list[dict[str, Any]] = []
    for group in groups:
        group_text = str(group.get("text") or "")
        sentence_break = (
            "hard"
            if group.get("hard_break_after")
            else _trailing_sentence_break(group_text)
        )
        display, _preferred = _caption_display_text(group_text)
        if metrics.text_width_em(display) <= maximum_width_em:
            retained = dict(group)
            retained["sentence_break"] = sentence_break
            repaired_groups.append(retained)
            continue

        start_us = int(group.get("start_us") or 0)
        end_us = int(group.get("end_us") or 0)
        if end_us <= start_us:
            raise SemanticSubtitleMappingError(
                "SEMANTIC_TIME_INVALID", "超宽语义单元的派生时间范围无效"
            )
        try:
            chunks = _split_one_line(
                group_text,
                metrics,
                maximum_width_em=maximum_width_em,
            )
            repaired = _allocate_cue_chunks(
                CaptionCue(start_us, end_us - start_us, display),
                chunks,
                metrics,
            )
        except CaptionLayoutReviewRequired as exc:
            raise SemanticSubtitleMappingError(
                "SEMANTIC_GROUP_REPAIR_FAILED",
                "超宽语义单元无法在保留其余语义断点的情况下局部修复",
            ) from exc
        for index, cue in enumerate(repaired):
            repaired_groups.append(
                {
                    "text": cue.text,
                    "start_us": cue.start_us,
                    "end_us": cue.end_us,
                    "break_after": (
                        str(group.get("break_after") or "allow")
                        if index == len(repaired) - 1
                        else "allow"
                    ),
                    "sentence_break": (
                        sentence_break if index == len(repaired) - 1 else ""
                    ),
                    "unit_count": int(group.get("unit_count") or 1),
                }
            )

    groups = repaired_groups
    displays: list[str] = []
    for group in groups:
        display, _preferred = _caption_display_text(str(group.get("text") or ""))
        if metrics.text_width_em(display) > maximum_width_em:
            raise SemanticSubtitleMappingError(
                "SEMANTIC_GROUP_TOO_WIDE",
                "不可拆语义组超过当前字体和画面宽度限制",
            )
        displays.append(display)

    length = len(groups)
    scores = [float("inf")] * (length + 1)
    previous: list[int | None] = [None] * (length + 1)
    rendered_texts: dict[tuple[int, int], str] = {}
    scores[0] = 0.0
    for end in range(1, length + 1):
        for start in range(end - 1, -1, -1):
            if any(
                groups[index].get("sentence_break") == "hard"
                for index in range(start, end - 1)
            ):
                continue
            text, _preferred = _caption_display_text(
                "".join(str(group.get("text") or "") for group in groups[start:end])
            )
            width = metrics.text_width_em(text)
            if width > maximum_width_em:
                continue
            if scores[start] == float("inf"):
                continue
            fill_ratio = width / maximum_width_em
            score = scores[start] + (1.0 - fill_ratio) ** 2
            if len(text) < 4:
                score += (4 - len(text)) * 8.0
            if start > 0 and text.startswith(_ORPHAN_PARTICLES):
                score += 10.0
            if end < length:
                score += 0.25
                sentence_break = str(groups[end - 1].get("sentence_break") or "")
                break_after = str(groups[end - 1].get("break_after") or "allow")
                if sentence_break == "soft":
                    score -= 2.0
                elif break_after == "prefer":
                    score -= 0.45
                elif break_after == "avoid":
                    score += 8.0
                if text.endswith(_ORPHAN_PARTICLES):
                    score += 10.0
            if score < scores[end]:
                scores[end] = score
                previous[end] = start
                rendered_texts[(start, end)] = text
    if previous[length] is None:
        raise SemanticSubtitleMappingError(
            "SEMANTIC_LAYOUT_FAILED", "语义字幕无法在当前真实字宽内排成单行"
        )

    slices: list[tuple[int, int]] = []
    cursor = length
    while cursor > 0:
        start = previous[cursor]
        if start is None:
            raise SemanticSubtitleMappingError(
                "SEMANTIC_LAYOUT_FAILED", "语义字幕断点回溯失败"
            )
        slices.append((start, cursor))
        cursor = start
    slices.reverse()

    result: list[CaptionCue] = []
    for start, end in slices:
        start_us = int(groups[start]["start_us"])
        end_us = int(groups[end - 1]["end_us"])
        if end_us <= start_us:
            raise SemanticSubtitleMappingError(
                "SEMANTIC_TIME_INVALID", "语义字幕的派生时间范围无效"
            )
        result.append(
            CaptionCue(
                start_us=start_us,
                duration_us=end_us - start_us,
                text=rendered_texts[(start, end)],
            )
        )
    return [cue.as_dict() for cue in result]


def _fallback_mapping(
    item: dict[str, Any],
    *,
    code: str,
    summary: str,
) -> dict[str, Any]:
    analysis = dict(item.get("content_analysis") or {})
    audio = item.get("outputs", {}).get("audio")
    return {
        "schema": SEMANTIC_MAPPING_SCHEMA,
        "status": "FALLBACK",
        "reason_code": str(code or "SEMANTIC_MAPPING_UNAVAILABLE")[:100],
        "reason_summary": str(summary or "使用 MiniMax 原始字幕排版")[:500],
        "script_sha256": hashlib.sha256(str(item.get("script_text") or "").encode("utf-8")).hexdigest(),
        "analysis_script_sha256": analysis.get("script_sha256"),
        "audio_asset_id": audio.get("asset_id") if isinstance(audio, dict) else None,
        "audio_version": audio.get("version") if isinstance(audio, dict) else None,
        "mapped_unit_count": 0,
    }


def derive_project_render_cues(
    item: dict[str, Any],
    *,
    font_path: str | Path,
    font_size: float = CAPTION_REFERENCE_FONT_SIZE,
    max_width_ratio: float = CAPTION_MAX_WIDTH_RATIO,
) -> tuple[list[dict[str, int | str]], dict[str, Any]]:
    """Use semantic units only when script, analysis and current audio versions agree."""

    raw_cues = item.get("subtitles", {}).get("raw_cues", [])
    script = str(item.get("script_text") or "")
    script_hash = hashlib.sha256(script.encode("utf-8")).hexdigest()
    analysis = dict(item.get("content_analysis") or {})
    audio = item.get("outputs", {}).get("audio")
    subtitles = dict(item.get("subtitles") or {})

    fallback = _fallback_mapping(
        item,
        code="SUBTITLE_ANALYSIS_UNAVAILABLE",
        summary="字幕分析未成功，使用 MiniMax raw_cues 和现有排版",
    )
    semantic_units: list[object] | None = None
    if analysis.get("subtitle_analysis_status") == "SUCCESS":
        if analysis.get("script_sha256") != script_hash:
            fallback = _fallback_mapping(
                item,
                code="ANALYSIS_SCRIPT_VERSION_MISMATCH",
                summary="字幕分析结果不属于当前脚本版本",
            )
        elif not isinstance(audio, dict):
            fallback = _fallback_mapping(
                item,
                code="CURRENT_AUDIO_MISSING",
                summary="当前脚本没有可验证的音频版本",
            )
        elif subtitles.get("bound_audio_asset_id") != audio.get("asset_id"):
            fallback = _fallback_mapping(
                item,
                code="RAW_CUES_AUDIO_VERSION_MISMATCH",
                summary="MiniMax raw_cues 没有绑定当前音频版本",
            )
        elif audio.get("metadata", {}).get("script_sha256") != script_hash:
            fallback = _fallback_mapping(
                item,
                code="AUDIO_SCRIPT_VERSION_MISMATCH",
                summary="当前音频没有绑定当前脚本版本",
            )
        elif not isinstance(analysis.get("subtitle_units"), list):
            fallback = _fallback_mapping(
                item,
                code="SUBTITLE_UNITS_MISSING",
                summary="字幕分析成功状态缺少 subtitle_units",
            )
        else:
            semantic_units = list(analysis["subtitle_units"])

    if semantic_units is not None:
        try:
            metrics = FontMetrics.load(font_path)
            maximum_width_em = (
                CAPTION_REFERENCE_MAX_EM
                * (float(max_width_ratio) / CAPTION_MAX_WIDTH_RATIO)
                * (CAPTION_REFERENCE_FONT_SIZE / float(font_size))
            )
            timed_units = map_subtitle_units_to_raw_cues(
                script,
                semantic_units,
                raw_cues,
            )
            groups = semantic_break_groups(timed_units)
            render_cues = _layout_semantic_groups(
                groups,
                metrics,
                maximum_width_em=maximum_width_em,
            )
            return render_cues, {
                "schema": SEMANTIC_MAPPING_SCHEMA,
                "status": "SUCCESS",
                "reason_code": None,
                "reason_summary": None,
                "script_sha256": script_hash,
                "analysis_script_sha256": analysis.get("script_sha256"),
                "analysis_schema_version": analysis.get("schema_version"),
                "analysis_prompt_version": analysis.get("prompt_version"),
                "audio_asset_id": audio.get("asset_id"),
                "audio_version": audio.get("version"),
                "mapped_unit_count": len(timed_units),
            }
        except (SemanticSubtitleMappingError, CaptionLayoutReviewRequired) as exc:
            fallback = _fallback_mapping(
                item,
                code=getattr(exc, "code", "SEMANTIC_LAYOUT_UNSAFE"),
                summary=str(exc),
            )

    render_cues = layout_one_line_captions(
        raw_cues,
        font_path=font_path,
        font_size=font_size,
        max_width_ratio=max_width_ratio,
    )
    return render_cues, fallback


def _latest_postprocess_operations(
    project: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for operation in project.get("operations", []):
        if (
            operation.get("operation_type")
            in {"POSTPROCESS_GENERATE", "POSTPROCESS_EXPORT"}
            and operation.get("item_id")
        ):
            latest[str(operation["item_id"])] = operation
    return latest


def _postprocess_target_items(
    project: dict[str, Any], requested_item_ids: set[str]
) -> list[dict[str, Any]]:
    return [
        item
        for item in project.get("items", [])
        if item.get("outputs", {}).get("composition_video") is None
        and (
            not requested_item_ids
            or str(item.get("item_id") or "") in requested_item_ids
        )
    ]


class ProjectPostprocessCoordinator:
    """Build browser preview recipes and export them only on explicit request."""

    def __init__(
        self,
        store: ProjectStore,
        render_queue: Any,
        *,
        storage_root: Path,
        draft_root: Path,
        fonts: list[dict[str, Any]],
        bgm_assets: list[dict[str, Any]],
        music_matcher: MusicProfileMatcher,
    ) -> None:
        self.store = store
        self.render_queue = render_queue
        self.storage_root = Path(storage_root).resolve()
        self.draft_root = Path(draft_root).resolve()
        self.fonts = {
            str(item.get("identity") or ""): item
            for item in fonts
            if item.get("identity") and item.get("available") and item.get("path")
        }
        self.bgm_assets = {
            str(item.get("identity") or ""): item
            for item in bgm_assets
            if item.get("identity") and item.get("available", True)
        }
        self.music_selector = ProjectMusicSelector(music_matcher, self.bgm_assets)

    def start(
        self,
        owner_user_id: str,
        project_id: str,
        *,
        idempotency_key: str,
        item_settings: list[dict[str, Any]],
    ) -> dict[str, Any]:
        project = self.store.get_project(owner_user_id, project_id)
        clean_key = str(idempotency_key or "").strip()
        if not clean_key:
            raise ValueError("字幕与背景音乐预览请求缺少幂等键")
        repeated_operations = [
            operation
            for operation in project.get("operations", [])
            if operation.get("operation_type") == "POSTPROCESS_GENERATE"
            and operation.get("idempotency_key") == clean_key
        ]
        if repeated_operations and all(
            operation.get("status") == "SUCCEEDED"
            or operation.get("result", {}).get("job_id")
            for operation in repeated_operations
        ):
            return self.sync(owner_user_id, project_id)
        if any(item["status"] == "POSTPROCESS_RUNNING" for item in project["items"]):
            raise ValueError("当前视频正在按需导出，请勿重复提交")
        if not (
            project["allowed_actions"].get("start_postprocess")
            or project["allowed_actions"].get("retry_postprocess")
        ):
            raise ValueError("当前项目尚未准备好生成字幕与 BGM 成片")
        supplied = {
            str(item.get("item_id") or ""): item
            for item in item_settings
            if isinstance(item, dict) and item.get("item_id")
        }
        subtitle_updates: list[tuple[dict[str, Any], dict[str, Any]]] = []
        resolved_settings: dict[str, dict[str, Any]] = {}

        requested_item_ids = set(supplied)
        target_items = _postprocess_target_items(project, requested_item_ids)
        if not target_items:
            raise ValueError("当前项目没有需要生成的完整预览")

        for item in target_items:
            config = supplied.get(str(item["item_id"]), {})
            base_video = item.get("outputs", {}).get("base_video")
            if not isinstance(base_video, dict) or not base_video.get("managed_path"):
                raise ValueError(f"任务 {item['row_key']} 缺少基础视频")
            font_identity = str(config.get("font_identity") or "").strip()
            font = self.fonts.get(font_identity)
            if font is None:
                raise ValueError(f"任务 {item['row_key']} 选择的字幕字体不可用")
            bgm_mode = str(config.get("bgm_selection_mode") or "manual").strip().lower()
            if bgm_mode not in {"auto", "manual"}:
                raise ValueError(f"任务 {item['row_key']} 的 BGM 选择模式不合法")
            if bgm_mode == "auto":
                bgm_identity, music_selection = self.music_selector.resolve_auto(
                    project, item
                )
            else:
                bgm_identity = str(config.get("bgm_identity") or "").strip()
                music_selection = manual_music_selection(item, bgm_identity)
            if bgm_identity and bgm_identity not in self.bgm_assets:
                raise ValueError(f"任务 {item['row_key']} 选择的 BGM 不可用")
            resolved_settings[str(item["item_id"])] = {
                **config,
                "bgm_identity": bgm_identity,
                "bgm_selection_mode": bgm_mode,
                "music_selection": music_selection,
            }
            color = str(config.get("text_color") or "#FFFFFF").strip().upper()
            if _HEX_COLOR.fullmatch(color) is None:
                raise ValueError(f"任务 {item['row_key']} 的字幕颜色不合法")
            try:
                render_cues, semantic_mapping = derive_project_render_cues(
                    item,
                    font_path=str(font["path"]),
                    font_size=CAPTION_REFERENCE_FONT_SIZE,
                    max_width_ratio=CAPTION_MAX_WIDTH_RATIO,
                )
            except CaptionLayoutReviewRequired as exc:
                subtitles = dict(item.get("subtitles") or {})
                subtitles.update(
                    {
                        "render_cues": [],
                        "status": "REVIEW_REQUIRED",
                        "overflow_risk": True,
                        "review_reason": str(exc),
                        "semantic_mapping": _fallback_mapping(
                            item,
                            code="RAW_CUE_LAYOUT_REVIEW_REQUIRED",
                            summary=str(exc),
                        ),
                    }
                )
                self.store.set_item_subtitles(
                    owner_user_id, project_id, item["item_id"], subtitles
                )
                raise ValueError(f"任务 {item['row_key']} 字幕需要人工检查：{exc}") from exc

            subtitles = dict(item.get("subtitles") or {})
            subtitles.update(
                {
                    "render_cues": render_cues,
                    "status": "PREVIEW_READY",
                    "overflow_risk": False,
                    "review_reason": None,
                    "semantic_mapping": semantic_mapping,
                    "bound_video_asset_id": base_video.get("asset_id"),
                    "style": {
                        "font_id": font_identity,
                        "font_name": str(font.get("name") or ""),
                        "font_size": CAPTION_REFERENCE_FONT_SIZE,
                        "text_color": color,
                        "stroke_color": CAPTION_STROKE_COLOR,
                        "stroke_width": CAPTION_STROKE_WIDTH,
                        "max_width_ratio": CAPTION_MAX_WIDTH_RATIO,
                        "max_lines": CAPTION_MAX_LINES,
                        "bottom_offset_ratio": CAPTION_BOTTOM_OFFSET_RATIO,
                        "transform_y": CAPTION_TRANSFORM_Y,
                    },
                }
            )
            subtitle_updates.append((item, subtitles))
        for item, subtitles in subtitle_updates:
            selected = resolved_settings[str(item["item_id"])]
            self.store.configure_item_postprocess(
                owner_user_id,
                project_id,
                item["item_id"],
                font_identity=str(subtitles["style"]["font_id"]),
                bgm_identity=str(selected.get("bgm_identity") or ""),
                text_color=str(subtitles["style"]["text_color"]),
                bgm_selection_mode=str(
                    selected.get("bgm_selection_mode") or "manual"
                ),
                music_selection=dict(selected.get("music_selection") or {}),
            )
            self.store.set_item_subtitles(
                owner_user_id, project_id, item["item_id"], subtitles
            )
            operation = self.store.create_operation(
                owner_user_id=owner_user_id,
                project_id=project_id,
                item_id=item["item_id"],
                operation_type="POSTPROCESS_GENERATE",
                idempotency_key=clean_key,
                payload={
                    "base_video_asset_id": item.get("outputs", {})
                    .get("base_video", {})
                    .get("asset_id"),
                    "font_identity": subtitles["style"]["font_id"],
                    "bgm_identity": selected.get("bgm_identity") or None,
                    "bgm_selection_mode": selected.get("bgm_selection_mode"),
                    "music_selection": selected.get("music_selection"),
                    "caption_max_width_ratio": CAPTION_MAX_WIDTH_RATIO,
                    "caption_max_lines": CAPTION_MAX_LINES,
                    "caption_bottom_offset_ratio": CAPTION_BOTTOM_OFFSET_RATIO,
                },
            )
            self.store.transition_operation(
                owner_user_id,
                project_id,
                item["item_id"],
                operation_type="POSTPROCESS_GENERATE",
                status="SUCCEEDED",
                item_status="COMPOSITION_READY",
                result={
                    "operation_id": operation["operation_id"],
                    "preview_mode": "browser",
                    "base_video_asset_id": item.get("outputs", {})
                    .get("base_video", {})
                    .get("asset_id"),
                    "caption_cue_count": len(subtitles["render_cues"]),
                    "bgm_identity": selected.get("bgm_identity") or None,
                    "bgm_selection_mode": selected.get("bgm_selection_mode"),
                    "music_selection": selected.get("music_selection"),
                },
            )
        return self.store.get_project(owner_user_id, project_id)

    def export_preview(
        self,
        owner_user_id: str,
        project_id: str,
        item_id: str,
        *,
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Export one browser preview only when the user explicitly requests a file."""

        project = self.store.get_project(owner_user_id, project_id)
        clean_key = str(idempotency_key or "").strip()
        if not clean_key:
            raise ValueError("按需导出请求缺少幂等键")
        item = next(
            (entry for entry in project["items"] if str(entry["item_id"]) == str(item_id)),
            None,
        )
        if item is None:
            raise KeyError("脚本行不存在")
        if item.get("outputs", {}).get("composition_video") is not None:
            return project
        if item.get("status") == "POSTPROCESS_RUNNING":
            return self.sync(owner_user_id, project_id)
        subtitles = dict(item.get("subtitles") or {})
        if subtitles.get("status") != "PREVIEW_READY" or not subtitles.get("render_cues"):
            raise ValueError("请先生成浏览器字幕与 BGM 预览")
        repeated = [
            operation
            for operation in project.get("operations", [])
            if operation.get("operation_type") == "POSTPROCESS_EXPORT"
            and operation.get("item_id") == item["item_id"]
            and operation.get("idempotency_key") == clean_key
        ]
        if repeated and any(operation.get("result", {}).get("job_id") for operation in repeated):
            return self.sync(owner_user_id, project_id)
        base_video = item.get("outputs", {}).get("base_video")
        if not isinstance(base_video, dict) or not base_video.get("managed_path"):
            raise ValueError("当前浏览器预览缺少画面源文件")
        style = dict(subtitles.get("style") or {})
        settings = dict(item.get("settings", {}).get("postprocess") or {})
        font_identity = str(style.get("font_id") or settings.get("font_identity") or "")
        font = self.fonts.get(font_identity)
        if font is None:
            raise ValueError("浏览器预览绑定的字幕字体不可用")
        bgm_identity = str(settings.get("bgm_identity") or "")
        if bgm_identity and bgm_identity not in self.bgm_assets:
            raise ValueError("浏览器预览绑定的 BGM 不可用")
        output = (
            self.storage_root
            / "projects"
            / str(owner_user_id)
            / project_id
            / str(item["item_id"])
            / "composition"
            / f"composition-{uuid.uuid4().hex}.mp4"
        )
        job = {
            "schema": "jyd.render_job.v1",
            "source": build_project_video_source(item),
            "output": {
                "draft_root": str(self.draft_root),
                "mp4_path": str(output),
                "skip_export": False,
            },
            "captions": {
                "cues": subtitles["render_cues"],
                "track_name": "MiniMax 单行字幕",
                "size": CAPTION_REFERENCE_FONT_SIZE,
                "color": str(style.get("text_color") or "#FFFFFF"),
                "stroke_color": CAPTION_STROKE_COLOR,
                "stroke_width": CAPTION_STROKE_WIDTH,
                "transform_x": 0.0,
                "transform_y": CAPTION_TRANSFORM_Y,
                "line_max_width": CAPTION_MAX_WIDTH_RATIO,
                "max_lines": 1,
                "single_line": True,
                "font_id": str(font.get("resource_id") or ""),
                "font_path": str(font["path"]),
                "font_title": str(font.get("name") or ""),
            },
            "audios": (
                [
                    {
                        "type": "bgm",
                        "library_identity": bgm_identity,
                        "target_start_us": 0,
                        "target_duration_us": 0,
                        "fit_to_video": True,
                        "volume": 0.3,
                    }
                ]
                if bgm_identity
                else []
            ),
            "export": {"resolution": "1080P", "framerate": "30fps"},
        }
        operation = self.store.create_operation(
            owner_user_id=owner_user_id,
            project_id=project_id,
            item_id=item["item_id"],
            operation_type="POSTPROCESS_EXPORT",
            idempotency_key=clean_key,
            payload={"reason": "explicit_download", "base_video_asset_id": base_video.get("asset_id")},
        )
        job["observability"] = {
            "project_id": project_id,
            "item_id": item["item_id"],
            "operation_id": operation["operation_id"],
            "correlation_id": operation["correlation_id"],
        }
        try:
            submitted = self.render_queue.submit_batch(
                [job],
                [{"project_id": project_id, "item_id": item["item_id"], "kind": "preview_export"}],
            )
            batch_id = str(submitted.get("batch_id") or "")
            job_ids = [str(value) for value in submitted.get("job_ids", [])]
            if not batch_id or len(job_ids) != 1:
                raise ValueError("剪映任务队列返回了无效的按需导出结果")
            job_id = job_ids[0]
            self.store.add_link(
                owner_user_id=owner_user_id,
                project_id=project_id,
                item_id=item["item_id"],
                system="jianying",
                relation="postprocess_export_job",
                external_id=job_id,
                metadata={"batch_id": batch_id, "reason": "explicit_download"},
            )
            self.store.transition_operation(
                owner_user_id,
                project_id,
                item["item_id"],
                operation_type="POSTPROCESS_EXPORT",
                status="RUNNING",
                item_status="POSTPROCESS_RUNNING",
                result={
                    "batch_id": batch_id,
                    "job_id": job_id,
                    "operation_id": operation["operation_id"],
                },
            )
        except Exception as exc:
            self.store.transition_operation(
                owner_user_id,
                project_id,
                item["item_id"],
                operation_type="POSTPROCESS_EXPORT",
                status="FAILED",
                item_status="COMPOSITION_FAILED",
                error_code=type(exc).__name__,
                error_message=str(exc),
            )
            raise
        return self.sync(owner_user_id, project_id)

    def sync(self, owner_user_id: str, project_id: str) -> dict[str, Any]:
        project = self.store.get_project(owner_user_id, project_id)
        operations = _latest_postprocess_operations(project)
        for item in project["items"]:
            operation = operations.get(str(item["item_id"]))
            if operation is None or operation.get("status") not in {"PENDING", "RUNNING"}:
                continue
            result = operation.get("result") if isinstance(operation.get("result"), dict) else {}
            operation_type = str(operation.get("operation_type") or "POSTPROCESS_GENERATE")
            job_id = str(result.get("job_id") or "")
            if not job_id:
                continue
            try:
                status = self.render_queue.get_status(job_id)
            except Exception as exc:
                self.store.transition_operation(
                    owner_user_id,
                    project_id,
                    item["item_id"],
                    operation_type=operation_type,
                    status="FAILED",
                    item_status="COMPOSITION_FAILED",
                    error_code=type(exc).__name__,
                    error_message=str(exc),
                )
                continue
            remote_status = str(status.get("status") or "")
            if remote_status in {"pending", "running"}:
                continue
            if remote_status != "completed":
                self.store.transition_operation(
                    owner_user_id,
                    project_id,
                    item["item_id"],
                    operation_type=operation_type,
                    status="FAILED",
                    item_status="COMPOSITION_FAILED",
                    result={"job_id": job_id},
                    error_code="JY_RENDER_FAILED",
                    error_message=str(status.get("error") or "剪映后处理失败"),
                )
                continue
            render_result = status.get("result") if isinstance(status.get("result"), dict) else {}
            output = Path(str(render_result.get("output_mp4") or "")).resolve()
            if not output.is_file():
                self.store.transition_operation(
                    owner_user_id,
                    project_id,
                    item["item_id"],
                    operation_type=operation_type,
                    status="FAILED",
                    item_status="COMPOSITION_FAILED",
                    result={"job_id": job_id},
                    error_code="OUTPUT_MISSING",
                    error_message="剪映任务完成但成片文件不存在",
                )
                continue
            current = item.get("outputs", {}).get("composition_video")
            subtitles = dict(item.get("subtitles") or {})
            subtitles["status"] = "RENDERED"
            subtitles["overflow_risk"] = False
            self.store.set_item_subtitles(
                owner_user_id, project_id, item["item_id"], subtitles
            )
            if not (
                isinstance(current, dict)
                and current.get("external_ref", {}).get("render_job_id") == job_id
            ):
                self.store.add_asset(
                    owner_user_id=owner_user_id,
                    project_id=project_id,
                    item_id=item["item_id"],
                    asset_type="composition_video",
                    source_type="jianying_postprocess",
                    status="READY",
                    filename=f"{item['row_key']}-composition.mp4",
                    managed_path=str(output),
                    external_ref={"render_job_id": job_id},
                    metadata={
                        "base_video_asset_id": item.get("outputs", {})
                        .get("base_video", {})
                        .get("asset_id"),
                        "captions": "minimax_one_line",
                        "bgm_volume": 0.3,
                    },
                    make_current=True,
                )
            self.store.transition_operation(
                owner_user_id,
                project_id,
                item["item_id"],
                operation_type=operation_type,
                status="SUCCEEDED",
                item_status="COMPOSITION_READY",
                result={
                    "batch_id": result.get("batch_id"),
                    "job_id": job_id,
                    "output_mp4": str(output),
                },
            )
        return self.store.get_project(owner_user_id, project_id)
