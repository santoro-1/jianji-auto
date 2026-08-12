from __future__ import annotations

from dataclasses import dataclass
import hashlib
import logging
from pathlib import Path
import re
from typing import Any, Iterable
import uuid

import jieba
import jieba.posseg as pseg
from fontTools.ttLib import TTFont

from .caption_alignment import (
    CaptionAlignmentError,
    alignment_matches,
    retime_render_cues,
)
from .music_matching import MusicProfileMatcher
from .project_music import (
    ProjectMusicSelector,
    automatic_music_identity_counts,
    manual_music_selection,
)
from .project_export_naming import composition_export_filename
from .project_store import ProjectStore
from .project_video_source import build_project_speech_audio, build_project_video_source
from .semantic_subtitles import (
    SEMANTIC_MAPPING_SCHEMA,
    SemanticSubtitleMappingError,
    map_subtitle_units_to_raw_cues,
    semantic_break_groups,
)
from .semantic_visuals import (
    SemanticVisualCatalogError,
    fixed_nameplate_overlay,
    frozen_visual_overlays,
    load_semantic_visual_catalog,
)
from .subtitles import CaptionCue, caption_cues_from_payload
from .unified_visual_plan import remap_saved_visual_plan


CAPTION_MAX_WIDTH_RATIO = 0.8
CAPTION_MAX_LINES = 1
CAPTION_TRANSFORM_Y = -850 / 1920
CAPTION_BOTTOM_OFFSET_RATIO = 0.5 + CAPTION_TRANSFORM_Y / 2
CAPTION_REFERENCE_FONT_SIZE = 14.0
CAPTION_REFERENCE_MAX_EM = 13.0 * 11.0 / CAPTION_REFERENCE_FONT_SIZE
CAPTION_STROKE_COLOR = "#000000"
CAPTION_STROKE_WIDTH = 0.06
FIXED_VIDEO_TITLE_TEXT = "世界冠军带你自律"
FIXED_VIDEO_TITLE_TRANSFORM_Y = 1535 / 1920
FIXED_VIDEO_TITLE_FONT_SIZE = 19.0
FIXED_VIDEO_TITLE_COLOR = "#E53935"
FIXED_VIDEO_TITLE_STROKE_COLOR = "#FFFFFF"
FIXED_VIDEO_TITLE_STROKE_WIDTH = 0.06
TOP_TITLE_MAX_LABEL_CHARS = 5
TOP_TITLE_MAX_HEADLINE_CHARS = 14
COVER_TITLE_MAX_LINE_1_CHARS = 5
COVER_TITLE_MAX_LINE_2_CHARS = 14
GENERATED_TITLE_MAX_LINE_2_CHARS = 8
COVER_FONT_IDENTITY = "resource_id:6807742980271641102"
COVER_LINE_1_TRANSFORM_Y = -160 / 1920
COVER_LINE_2_TRANSFORM_Y = -655 / 1920
COVER_OVERLAY_TRANSFORM_Y = -420 / 1920
COVER_OVERLAY_CENTER_RATIO = 0.5 - COVER_OVERLAY_TRANSFORM_Y / 2
COVER_OVERLAY_HEIGHT_RATIO = 0.36
COVER_LINE_1_FONT_SIZE = 30.0
COVER_LINE_2_FONT_SIZE = 22.0
COVER_LINE_1_COLOR = "#FADF4A"
COVER_LINE_2_COLOR = "#F5F6F0"
CAPTION_MIN_SLICE_US = 80_000
_BREAK_CHARS = set("，,、：:。.！？!?；;")
_HIDDEN_CAPTION_PUNCTUATION = _BREAK_CHARS | set("…")
_HARD_SENTENCE_BREAKS = set("。.！？!?；;…\r\n")
_SOFT_SENTENCE_BREAKS = set("，,、：:")
_CLAUSE_BREAKS = set("，,：:。.！？!?；;…")
_ORPHAN_PARTICLES = tuple("的地得呢啊了吧吗")
_STRUCTURAL_PARTICLES = frozenset("的地得")
_RIGHT_BINDING_CLAUSES = frozenset(
    {
        "第一",
        "第二",
        "第三",
        "第四",
        "第五",
        "首先",
        "其次",
        "再次",
        "最后",
    }
)
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

BOTTOM_DISCLAIMER_TEXT = (
    "非医疗保健科普：仅供参考，个人经验分享，不代表普遍性\n"
    "如有不适请线下就医"
)
BOTTOM_DISCLAIMER_FONT_SIZE = 6.0
BOTTOM_DISCLAIMER_TRANSFORM_Y = -1760 / 1920
BOTTOM_DISCLAIMER_COLOR = "#FFFFFF"
BOTTOM_DISCLAIMER_OPACITY = 0.5

def normalize_top_title(value: Any) -> dict[str, str]:
    """Normalize the optional two-line fixed top title contract."""

    if value is None:
        return {"label": "", "headline": ""}
    if not isinstance(value, dict):
        raise ValueError("顶部固定标题必须是对象")

    def clean(*keys: str) -> str:
        raw = next((value.get(key) for key in keys if value.get(key) is not None), "")
        return re.sub(r"\s+", " ", str(raw or "")).strip()

    label = clean("label", "topic", "line_1")
    headline = clean("headline", "title", "line_2")
    if len(label) > TOP_TITLE_MAX_LABEL_CHARS:
        raise ValueError(f"顶部黄色小标题最多 {TOP_TITLE_MAX_LABEL_CHARS} 个字符")
    if len(headline) > TOP_TITLE_MAX_HEADLINE_CHARS:
        raise ValueError(f"顶部白色主标题最多 {TOP_TITLE_MAX_HEADLINE_CHARS} 个字符")
    return {"label": label, "headline": headline}


def normalize_cover_title(value: Any) -> dict[str, str]:
    """Normalize the model-owned two-line cover title contract."""

    if value is None:
        return {"line_1": "", "line_2": ""}
    if not isinstance(value, dict):
        raise ValueError("封面标题必须是对象")

    def clean(*keys: str) -> str:
        raw = next((value.get(key) for key in keys if value.get(key) is not None), "")
        text = str(raw or "").strip()
        if any(character.isspace() for character in text):
            raise ValueError("封面标题每行不能包含空格或换行")
        return text

    line_1 = clean("line_1", "topic", "label")
    line_2 = clean("line_2", "hook", "headline", "title")
    if bool(line_1) != bool(line_2):
        raise ValueError("封面标题必须同时提供两行")
    for index, (text, limit) in enumerate(
        (
            (line_1, COVER_TITLE_MAX_LINE_1_CHARS),
            (line_2, COVER_TITLE_MAX_LINE_2_CHARS),
        ),
        start=1,
    ):
        if len(text) > limit:
            raise ValueError(
                f"封面第 {index} 行最多 {limit} 个字符"
            )
    return {"line_1": line_1, "line_2": line_2}


def build_project_cover(
    item: dict[str, Any],
    *,
    fonts: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    """Build the fixed project cover recipe from saved titles and the input image."""

    postprocess = dict(item.get("settings", {}).get("postprocess") or {})
    title = normalize_cover_title(
        postprocess.get("title") or postprocess.get("cover_title")
    )
    if not title["line_1"]:
        return None
    image = item.get("inputs", {}).get("image")
    if not isinstance(image, dict) or not image.get("managed_path"):
        raise ValueError(f"任务 {item.get('row_key') or item.get('item_id')} 缺少封面原图")
    image_path = Path(str(image["managed_path"])).expanduser().resolve()
    if not image_path.is_file():
        raise ValueError(f"任务 {item.get('row_key') or item.get('item_id')} 的封面原图不存在")
    font = fonts.get(COVER_FONT_IDENTITY)
    if not isinstance(font, dict) or not font.get("path"):
        raise ValueError("固定封面字体“思源粗宋”不可用")
    overlay_top = COVER_OVERLAY_CENTER_RATIO - COVER_OVERLAY_HEIGHT_RATIO / 2
    overlay_bottom = COVER_OVERLAY_CENTER_RATIO + COVER_OVERLAY_HEIGHT_RATIO / 2
    return {
        "enabled": True,
        "frame_source": "input_image",
        "image_path": str(image_path),
        "frame_time_seconds": 0,
        "frame_count": 3,
        "text_line_1": title["line_1"],
        "text_line_2": title["line_2"],
        "font": {
            "font_id": str(font.get("resource_id") or "6807742980271641102"),
            "font_path": str(Path(str(font["path"])).expanduser().resolve()),
            "font_title": str(font.get("name") or "SourceHanSerifCN-Heavy"),
        },
        "text_scale": 1.0,
        "letter_spacing": 0,
        "line_spacing": 6,
        "line_1_x": 0.0,
        "line_1_y": COVER_LINE_1_TRANSFORM_Y,
        "line_2_x": 0.0,
        "line_2_y": COVER_LINE_2_TRANSFORM_Y,
        "line_1_size": COVER_LINE_1_FONT_SIZE,
        "line_2_size": COVER_LINE_2_FONT_SIZE,
        "line_1_color": COVER_LINE_1_COLOR,
        "line_2_color": COVER_LINE_2_COLOR,
        "line_1_shadow_color": "#000000",
        "line_1_shadow_alpha": 0.9,
        "line_1_shadow_smoothing": 0.15,
        "line_1_shadow_distance": 5.0,
        "line_1_shadow_angle": -45.0,
        "line_2_shadow_color": "#1F1A05",
        "line_2_shadow_alpha": 0.5,
        "line_2_shadow_smoothing": 0.15,
        "line_2_shadow_distance": 5.0,
        "line_2_shadow_angle": -45.0,
        "frame_scale": 1.0,
        "frame_offset_x": 0.0,
        "frame_offset_y": 0.0,
        "overlay_alpha": 0.5,
        "overlay_x_ratio": 0.5,
        "overlay_y_ratio": COVER_OVERLAY_CENTER_RATIO,
        "overlay_width_ratio": 1.0,
        "overlay_height_ratio": COVER_OVERLAY_HEIGHT_RATIO,
        "overlay_top_ratio": overlay_top,
        "overlay_bottom_ratio": overlay_bottom,
    }


def build_top_title_texts(
    top_title: Any,
    *,
    font: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Build the fixed video banner and bottom disclaimer text layers."""

    # The model-owned two-line title is still saved for the project cover, but
    # the body video now uses one product-fixed memory hook.  Keep the argument
    # for render-job/API compatibility with already saved projects.
    _ = top_title
    font_fields = {
        "font_id": str((font or {}).get("resource_id") or ""),
        "font_path": str((font or {}).get("path") or ""),
        "font_title": str((font or {}).get("name") or ""),
    }
    rows = [
        (
            FIXED_VIDEO_TITLE_TEXT,
            "顶部固定标题·世界冠军",
            FIXED_VIDEO_TITLE_TRANSFORM_Y,
            FIXED_VIDEO_TITLE_FONT_SIZE,
            FIXED_VIDEO_TITLE_COLOR,
            FIXED_VIDEO_TITLE_STROKE_COLOR,
            FIXED_VIDEO_TITLE_STROKE_WIDTH,
            1.0,
            950,
        ),
        (
            BOTTOM_DISCLAIMER_TEXT,
            "底部固定免责声明",
            BOTTOM_DISCLAIMER_TRANSFORM_Y,
            BOTTOM_DISCLAIMER_FONT_SIZE,
            BOTTOM_DISCLAIMER_COLOR,
            "#000000",
            0.04,
            BOTTOM_DISCLAIMER_OPACITY,
            952,
        ),
    ]
    return [
        {
            "type": "add",
            "scope": "top",
            "text": text,
            "track_name": track_name,
            "start_us": 0,
            "duration_us": 0,
            "relative_index": relative_index,
            "transform_x": 0.0,
            "transform_y": transform_y,
            "size": size,
            "align": 1,
            "auto_wrapping": False,
            "line_max_width": 0.92,
            "color": color,
            "stroke_color": stroke_color,
            "stroke_width": stroke_width,
            "opacity": opacity,
            **font_fields,
        }
        for (
            text,
            track_name,
            transform_y,
            size,
            color,
            stroke_color,
            stroke_width,
            opacity,
            relative_index,
        ) in rows
        if text
    ]


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
_NUMBER_EXPRESSION = re.compile(
    r"(?:百分之[0-9０-９零〇一二两三四五六七八九十百千万亿几多]+"
    r"|(?:大约|约|近|超过|至少|不到)?"
    r"[0-9０-９零〇一二两三四五六七八九十百千万亿几多]+"
    r"(?:[点.．][0-9０-９零〇一二两三四五六七八九十百千万亿几多]+)?"
    r"(?:(?:到|至|[-~～—–])"
    r"[0-9０-９零〇一二两三四五六七八九十百千万亿几多]+"
    r"(?:[点.．][0-9０-９零〇一二两三四五六七八九十百千万亿几多]+)?)?"
    r"(?:个)?(?:分钟|秒钟|小时|个月|公斤|千克|厘米|毫米|公里|年|月|天|日|周|岁|名|人|斤|元|次|倍|成|餐|%|％)"
    r"|[0-9０-９]+[.:：．][0-9０-９]+)"
)
_HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")
_QUANTITY_TAIL = re.compile(r"[0-9０-９零〇一二两三四五六七八九十百千万亿几多]+个$")
_COUNTING_TAIL = re.compile(
    r"[0-9０-９零〇一二两三四五六七八九十百千万亿几多]+(?:个|名|位|只|条|份|组|家|本|张|件|辆|台)$"
)
_RELATIVE_PREFIXES = ("能", "能够", "可", "可以", "会", "要", "应该")
_BAD_LINE_ENDINGS = (
    "就",
    "都",
    "能",
    "会",
    "要",
    "把",
    "被",
    "从",
    "向",
    "往",
    "给",
    "对",
    "和",
    "与",
    "及",
    "或",
    "并",
)

jieba.setLogLevel(logging.ERROR)
_JIEBA_TOKENIZER = jieba.Tokenizer()
_JIEBA_POS_TOKENIZER = pseg.POSTokenizer(_JIEBA_TOKENIZER)


def _discouraged_break_offsets(text: str) -> dict[int, float]:
    """Score grammatical token boundaries that are legal but usually unnatural."""

    tagged: list[tuple[str, str, int, int]] = []
    cursor = 0
    for token in _JIEBA_POS_TOKENIZER.cut(text, HMM=False):
        word = str(token.word)
        start = cursor
        end = start + len(word)
        tagged.append((word, str(token.flag), start, end))
        cursor = end
    penalties: dict[int, float] = {}
    for left, right in zip(tagged, tagged[1:]):
        _left_word, left_flag, _left_start, boundary = left
        right_word, right_flag, _right_start, _right_end = right
        if (
            (left_flag.startswith("n") or left_flag == "vn")
            and (right_flag.startswith("n") or right_flag == "vn")
        ):
            penalties[boundary] = max(penalties.get(boundary, 0.0), 4.0)
        elif left_flag in {"a", "d"} and (
            right_flag.startswith("v") or right_flag.startswith("a")
        ):
            penalties[boundary] = max(penalties.get(boundary, 0.0), 2.0)
        elif left_flag.startswith("v") and right_flag.startswith("a"):
            penalties[boundary] = max(penalties.get(boundary, 0.0), 2.0)
        elif (
            left_flag.startswith("v")
            and right_word == "点"
            and right_flag.startswith("m")
        ):
            # Verb + quantity constructions such as `做点活动` should not leave
            # the quantifier at the start of the following subtitle.
            penalties[boundary] = max(penalties.get(boundary, 0.0), 12.0)
    return penalties


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


def _unsafe_break_offsets(text: str) -> set[int]:
    """Return character boundaries that would split a lexical or numeric unit."""

    unsafe_offsets: set[int] = set()
    for token, start, end in _JIEBA_TOKENIZER.tokenize(text, mode="default", HMM=False):
        if len(token) <= 1 or token.isspace():
            continue
        unsafe_offsets.update(range(int(start) + 1, int(end)))
    for term in _unbreakable_terms():
        cursor = 0
        while True:
            position = text.find(term, cursor)
            if position < 0:
                break
            unsafe_offsets.update(range(position + 1, position + len(term)))
            cursor = position + 1
    for match in _NUMBER_EXPRESSION.finditer(text):
        unsafe_offsets.update(range(match.start() + 1, match.end()))
    for boundary in range(1, len(text)):
        # Structural particles may neither start nor end a rendered line.  The
        # boundary value means "before text[boundary]"; checking both adjacent
        # characters avoids the former off-by-one that incorrectly protected
        # `，|管得` instead of `管|得`.
        if (
            text[boundary] in _STRUCTURAL_PARTICLES
            or text[boundary - 1] in _STRUCTURAL_PARTICLES
        ):
            unsafe_offsets.add(boundary)
    return unsafe_offsets


def _merge_unbreakable_term_boundaries(
    groups: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Discard model boundaries that split a known lexical unit."""

    source_text = "".join(str(group.get("text") or "") for group in groups)
    unsafe_offsets = _unsafe_break_offsets(source_text)

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


def _merge_orphan_sentence_tails(
    groups: list[dict[str, Any]],
    metrics: FontMetrics,
    *,
    maximum_width_em: float,
) -> list[dict[str, Any]]:
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
            len(display) < 4
            and _trailing_sentence_break(str(group.get("text") or "")) == "soft"
        ):
            previous = rebalanced[-1] if rebalanced else None
            if previous and _trailing_sentence_break(str(previous.get("text") or "")) != "hard":
                combined_display, _combined_preferred = _caption_display_text(
                    str(previous.get("text") or "") + str(group.get("text") or "")
                )
                if metrics.text_width_em(combined_display) <= maximum_width_em:
                    rebalanced.pop()
                    rebalanced.append(
                        {
                            "text": str(previous.get("text") or "")
                            + str(group.get("text") or ""),
                            "start_us": int(previous.get("start_us") or 0),
                            "end_us": int(group.get("end_us") or 0),
                            "break_after": str(group.get("break_after") or "allow"),
                            "hard_break_after": bool(group.get("hard_break_after")),
                            "unit_count": int(previous.get("unit_count") or 1)
                            + int(group.get("unit_count") or 1),
                        }
                    )
                    index += 1
                    continue
            if index + 1 >= len(merged):
                rebalanced.append(group)
                index += 1
                continue
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
    text: str,
    metrics: FontMetrics,
    *,
    maximum_width_em: float,
    preferred_offsets: set[int] | None = None,
) -> list[str]:
    normalized, preferred_breaks = _caption_display_text(text)
    preferred_breaks.update(preferred_offsets or set())
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

    protected_breaks = _unsafe_break_offsets(normalized)
    discouraged_breaks = _discouraged_break_offsets(normalized)

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
            # The tokenizer only sees punctuation-free display text.  It can
            # therefore mistake two words separated by an original comma or
            # enumeration comma for one protected phrase (for example
            # ``嘴馋、减不动`` -> ``嘴馋减不动``).  An original punctuation or
            # model-preferred boundary is stronger evidence and must remain a
            # legal line break.
            if (
                end < length
                and end in protected_breaks
                and end not in preferred_breaks
            ):
                continue
            core_length = len(chunk)
            fill_ratio = width / maximum_width_em
            score = scores[start] + (1.0 - fill_ratio) ** 2
            if core_length < 4:
                score += (4 - core_length) * 8.0
            if end < length:
                score += 0.25
                if end in preferred_breaks:
                    score -= 2.5
                score += discouraged_breaks.get(end, 0.0)
                if end in connector_starts:
                    score -= 0.55
                if end in preferred_term_ends:
                    score -= 1.25
                if end in connector_ends or chunk.endswith(_LEADING_CONNECTORS):
                    score += 4.0
                if chunk.endswith(_ORPHAN_PARTICLES):
                    score += 10.0
                if chunk.endswith(_BAD_LINE_ENDINGS):
                    score += 12.0
                next_text = normalized[end:]
                if (
                    _QUANTITY_TAIL.search(chunk)
                    and next_text.startswith(_RELATIVE_PREFIXES)
                ):
                    score += 8.0
                if _COUNTING_TAIL.search(chunk) and next_text:
                    score += 4.0
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
    # Model boundaries are preferences, not trusted indivisible chunks.  Build
    # punctuation/raw-cue-bounded clauses first, then lay each clause out over
    # tokenizer-approved character boundaries.  This prevents a local repair
    # from crossing `。` or a MiniMax pause and also lets us override a bad model
    # split such as `头晕眼|花`.
    # The model is allowed to suggest boundaries, but it cannot split a lexical
    # or numeric expression.  Repair those boundaries before punctuation is
    # interpreted: otherwise a model result such as `0.|5到1公斤` makes the
    # decimal point look like sentence punctuation and silently removes it.
    groups = _merge_unbreakable_term_boundaries(groups)
    clauses: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for source in groups:
        group = dict(source)
        if current and int(group.get("start_us") or 0) > int(
            current[-1].get("end_us") or 0
        ):
            clauses.append(current)
            current = []
        current.append(group)
        group_text = str(group.get("text") or "").rstrip()
        if group.get("hard_break_after") or (
            group_text and group_text[-1] in _CLAUSE_BREAKS
        ):
            clauses.append(current)
            current = []
    if current:
        clauses.append(current)

    # Ordinal/discourse markers such as `第一，` bind to what follows.  Other
    # punctuation remains a hard layout boundary because punctuation is hidden
    # in rendered captions and merging it would create text such as `花掉的`.
    joined_clauses: list[list[dict[str, Any]]] = []
    index = 0
    while index < len(clauses):
        clause = clauses[index]
        clause_text = "".join(str(group.get("text") or "") for group in clause)
        display, _preferred = _caption_display_text(clause_text)
        if (
            display in _RIGHT_BINDING_CLAUSES
            and index + 1 < len(clauses)
            and int(clauses[index + 1][0].get("start_us") or 0)
            == int(clause[-1].get("end_us") or 0)
        ):
            joined_clauses.append(clause + clauses[index + 1])
            index += 2
            continue
        joined_clauses.append(clause)
        index += 1

    result: list[CaptionCue] = []
    for clause in joined_clauses:
        text = "".join(str(group.get("text") or "") for group in clause)
        display, _punctuation_breaks = _caption_display_text(text)
        preferred_offsets: set[int] = set()
        display_cursor = 0
        for group in clause[:-1]:
            part, _part_breaks = _caption_display_text(str(group.get("text") or ""))
            display_cursor += len(part)
            if str(group.get("break_after") or "allow") == "prefer":
                preferred_offsets.add(display_cursor)
        start_us = int(clause[0].get("start_us") or 0)
        end_us = int(clause[-1].get("end_us") or 0)
        if end_us <= start_us:
            raise SemanticSubtitleMappingError(
                "SEMANTIC_TIME_INVALID", "语义字幕的派生时间范围无效"
            )
        try:
            chunks = _split_one_line(
                text,
                metrics,
                maximum_width_em=maximum_width_em,
                preferred_offsets=preferred_offsets,
            )
            result.extend(
                _allocate_cue_chunks(
                    CaptionCue(start_us, end_us - start_us, display),
                    chunks,
                    metrics,
                )
            )
        except CaptionLayoutReviewRequired as exc:
            raise SemanticSubtitleMappingError(
                "SEMANTIC_LAYOUT_FAILED",
                "语义字幕无法在当前真实字宽内排成单行",
            ) from exc
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
    asr_alignment: dict[str, Any] | None = None,
    require_precise_alignment: bool = False,
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
            if asr_alignment is not None:
                render_cues = retime_render_cues(
                    script, raw_cues, render_cues, asr_alignment
                )
            elif require_precise_alignment:
                raise CaptionAlignmentError(
                    "ASR_ALIGNMENT_REQUIRED", "当前音频尚未完成 ASR 精确字幕校准"
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
                "timing_source": (
                    "funasr_word_timestamps"
                    if asr_alignment is not None
                    else "minimax_raw_cue_interpolation"
                ),
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
    if asr_alignment is not None:
        render_cues = retime_render_cues(script, raw_cues, render_cues, asr_alignment)
        fallback["timing_source"] = "funasr_word_timestamps"
    elif require_precise_alignment:
        raise CaptionAlignmentError(
            "ASR_ALIGNMENT_REQUIRED", "当前音频尚未完成 ASR 精确字幕校准"
        )
    else:
        fallback["timing_source"] = "minimax_raw_cue_interpolation"
    return render_cues, fallback


def _active_postprocess_operations(
    project: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    active: list[dict[str, Any]] = []
    latest_by_item: dict[str, str] = {}
    for operation in project.get("operations", []):
        if (
            operation.get("operation_type")
            in {"POSTPROCESS_GENERATE", "POSTPROCESS_EXPORT"}
            and operation.get("item_id")
        ):
            item_id = str(operation["item_id"])
            latest_by_item[item_id] = str(operation.get("operation_id") or "")
            if operation.get("status") in {"PENDING", "RUNNING"}:
                active.append(operation)
    return active, latest_by_item


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
        caption_aligner: Any | None = None,
        require_precise_alignment: bool = False,
        semantic_visual_library_root: Path | None = None,
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
        self.caption_aligner = caption_aligner
        self.require_precise_alignment = bool(require_precise_alignment)
        self.semantic_visual_library_root = Path(
            semantic_visual_library_root
            or (
                Path(__file__).resolve().parents[2]
                / "data"
                / "libraries"
                / "semantic_visual_library"
            )
        ).resolve()
        try:
            self.semantic_visual_catalog = load_semantic_visual_catalog(
                self.semantic_visual_library_root
            )
        except SemanticVisualCatalogError:
            self.semantic_visual_catalog = None

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
        supplied = {
            str(item.get("item_id") or ""): item
            for item in item_settings
            if isinstance(item, dict) and item.get("item_id")
        }
        if not supplied:
            raise ValueError("字幕与背景音乐预览至少需要指定一条脚本行")
        project_items = {str(item["item_id"]): item for item in project["items"]}
        if not set(supplied).issubset(project_items):
            raise KeyError("项目脚本行不存在")
        blocked = [
            project_items[item_id]
            for item_id in supplied
            if not (
                project_items[item_id].get("allowed_actions", {}).get("start_postprocess")
                or project_items[item_id].get("allowed_actions", {}).get("retry_postprocess")
            )
        ]
        if blocked:
            raise ValueError(f"任务 {blocked[0]['row_key']} 尚未准备好生成字幕与 BGM 成片")
        subtitle_updates: list[tuple[dict[str, Any], dict[str, Any]]] = []
        resolved_settings: dict[str, dict[str, Any]] = {}

        requested_item_ids = set(supplied)
        target_items = _postprocess_target_items(project, requested_item_ids)
        if not target_items:
            raise ValueError("当前项目没有需要生成的完整预览")

        automatic_target_ids = {
            str(item["item_id"])
            for item in target_items
            if str(supplied.get(str(item["item_id"]), {}).get("bgm_selection_mode") or "manual")
            .strip()
            .lower()
            == "auto"
        }
        recent_identity_counts = automatic_music_identity_counts(
            project, excluded_item_ids=automatic_target_ids
        )

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
                    project,
                    item,
                    recent_identity_counts=recent_identity_counts,
                )
                if bgm_identity:
                    recent_identity_counts[bgm_identity] = (
                        recent_identity_counts.get(bgm_identity, 0) + 1
                    )
            else:
                bgm_identity = str(config.get("bgm_identity") or "").strip()
                music_selection = manual_music_selection(item, bgm_identity)
            if bgm_identity and bgm_identity not in self.bgm_assets:
                raise ValueError(f"任务 {item['row_key']} 选择的 BGM 不可用")
            saved_postprocess = dict(item.get("settings", {}).get("postprocess") or {})
            top_title = normalize_top_title(
                config["top_title"]
                if "top_title" in config
                else saved_postprocess.get("top_title")
            )
            cover_title = normalize_cover_title(
                config["cover_title"]
                if "cover_title" in config
                else saved_postprocess.get("cover_title")
            )
            resolved_settings[str(item["item_id"])] = {
                **config,
                "bgm_identity": bgm_identity,
                "bgm_selection_mode": bgm_mode,
                "music_selection": music_selection,
                "top_title": top_title,
                "cover_title": cover_title,
            }
            color = str(config.get("text_color") or "#FFFFFF").strip().upper()
            if _HEX_COLOR.fullmatch(color) is None:
                raise ValueError(f"任务 {item['row_key']} 的字幕颜色不合法")
            subtitles = dict(item.get("subtitles") or {})
            audio = item.get("outputs", {}).get("audio")
            asr_alignment = subtitles.get("asr_alignment")
            alignment_is_current = bool(
                isinstance(audio, dict)
                and alignment_matches(
                    asr_alignment,
                    script=str(item.get("script_text") or ""),
                    audio_asset_id=str(audio.get("asset_id") or ""),
                    audio_version=audio.get("version"),
                )
            )
            if not alignment_is_current and self.caption_aligner is not None:
                if not isinstance(audio, dict) or not audio.get("managed_path"):
                    raise ValueError(f"任务 {item['row_key']} 缺少可供 ASR 校准的音频")
                try:
                    asr_alignment = self.caption_aligner.align(
                        audio["managed_path"],
                        script=str(item.get("script_text") or ""),
                        raw_cues=subtitles.get("raw_cues", []),
                        audio_asset_id=str(audio.get("asset_id") or ""),
                        audio_version=audio.get("version"),
                    )
                    subtitles["asr_alignment"] = asr_alignment
                    alignment_is_current = True
                except CaptionAlignmentError as exc:
                    subtitles.update(
                        {
                            "render_cues": [],
                            "status": "REVIEW_REQUIRED",
                            "overflow_risk": False,
                            "review_reason": str(exc),
                            "asr_alignment": {
                                "status": "FAILED",
                                "reason_code": exc.code,
                                "reason_summary": str(exc)[:500],
                            },
                        }
                    )
                    self.store.set_item_subtitles(
                        owner_user_id, project_id, item["item_id"], subtitles
                    )
                    raise ValueError(
                        f"任务 {item['row_key']} 精确字幕校准失败：{exc}"
                    ) from exc
            if self.require_precise_alignment and not alignment_is_current:
                raise ValueError(
                    f"任务 {item['row_key']} 尚未配置或启动本地 ASR 精确字幕服务"
                )
            render_item = {**item, "subtitles": subtitles}
            try:
                render_cues, semantic_mapping = derive_project_render_cues(
                    render_item,
                    font_path=str(font["path"]),
                    font_size=CAPTION_REFERENCE_FONT_SIZE,
                    max_width_ratio=CAPTION_MAX_WIDTH_RATIO,
                    asr_alignment=(asr_alignment if alignment_is_current else None),
                    require_precise_alignment=self.require_precise_alignment,
                )
            except (CaptionLayoutReviewRequired, CaptionAlignmentError) as exc:
                subtitles.update(
                    {
                        "render_cues": [],
                        "status": "REVIEW_REQUIRED",
                        "overflow_risk": isinstance(exc, CaptionLayoutReviewRequired),
                        "review_reason": str(exc),
                        "semantic_mapping": _fallback_mapping(
                            item,
                            code=(
                                "RAW_CUE_LAYOUT_REVIEW_REQUIRED"
                                if isinstance(exc, CaptionLayoutReviewRequired)
                                else exc.code
                            ),
                            summary=str(exc),
                        ),
                    }
                )
                self.store.set_item_subtitles(
                    owner_user_id, project_id, item["item_id"], subtitles
                )
                raise ValueError(f"任务 {item['row_key']} 字幕需要人工检查：{exc}") from exc

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
                top_title=dict(selected.get("top_title") or {}),
                cover_title=dict(selected.get("cover_title") or {}),
            )
            updated_project = self.store.set_item_subtitles(
                owner_user_id, project_id, item["item_id"], subtitles
            )
            current_audio = item.get("outputs", {}).get("audio") or {}
            visual_alignment_is_current = bool(
                isinstance(current_audio, dict)
                and alignment_matches(
                    subtitles.get("asr_alignment"),
                    script=str(item.get("script_text") or ""),
                    audio_asset_id=str(current_audio.get("asset_id") or ""),
                    audio_version=current_audio.get("version"),
                )
            )
            if self.semantic_visual_catalog is not None and visual_alignment_is_current:
                updated_item = next(
                    (
                        candidate
                        for candidate in updated_project.get("items", [])
                        if candidate.get("item_id") == item["item_id"]
                    ),
                    None,
                )
                if isinstance(updated_item, dict):
                    remap_saved_visual_plan(
                        self.store,
                        owner_user_id=owner_user_id,
                        project_id=project_id,
                        item=updated_item,
                        catalog=self.semantic_visual_catalog,
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
            "original_video_volume": 0.0,
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
            "audios": [
                build_project_speech_audio(item),
                *(
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
            ],
            "export": {"resolution": "1080P", "framerate": "30fps"},
        }
        job["visual_overlays"] = frozen_visual_overlays(
            item, library_root=self.semantic_visual_library_root
        )
        job["fixed_overlays"] = [
            fixed_nameplate_overlay(self.semantic_visual_library_root)
        ]
        title_texts = build_top_title_texts(settings.get("top_title"), font=font)
        if title_texts:
            job["texts"] = title_texts
        cover = build_project_cover(item, fonts=self.fonts)
        if cover is not None:
            job["cover"] = cover
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
                operation_id=operation["operation_id"],
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
                operation_id=operation["operation_id"],
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
        operations, latest_by_item = _active_postprocess_operations(project)
        items = {str(item["item_id"]): item for item in project["items"]}
        for operation in operations:
            item_id = str(operation.get("item_id") or "")
            item = items.get(item_id)
            if item is None:
                continue
            operation_id = str(operation.get("operation_id") or "")
            is_latest = latest_by_item.get(item_id) == operation_id
            preserved_item_status = str(item.get("status") or "DRAFT")
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
                    operation_id=operation_id,
                    operation_type=operation_type,
                    status="FAILED",
                    item_status=("COMPOSITION_FAILED" if is_latest else preserved_item_status),
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
                    operation_id=operation_id,
                    operation_type=operation_type,
                    status="FAILED",
                    item_status=("COMPOSITION_FAILED" if is_latest else preserved_item_status),
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
                    operation_id=operation_id,
                    operation_type=operation_type,
                    status="FAILED",
                    item_status=("COMPOSITION_FAILED" if is_latest else preserved_item_status),
                    result={"job_id": job_id},
                    error_code="OUTPUT_MISSING",
                    error_message="剪映任务完成但成片文件不存在",
                )
                continue
            if not is_latest:
                self.store.transition_operation(
                    owner_user_id,
                    project_id,
                    item["item_id"],
                    operation_id=operation_id,
                    operation_type=operation_type,
                    status="SUCCEEDED",
                    item_status=preserved_item_status,
                    result={
                        "batch_id": result.get("batch_id"),
                        "job_id": job_id,
                        "output_mp4": str(output),
                        "superseded": True,
                    },
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
                    filename=composition_export_filename(item),
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
                operation_id=operation_id,
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
