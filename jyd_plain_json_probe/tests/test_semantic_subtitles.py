from __future__ import annotations

import hashlib
from pathlib import Path
import sys

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from jyd_probe.project_postprocess import derive_project_render_cues  # noqa: E402
from jyd_probe.semantic_subtitles import (  # noqa: E402
    SemanticSubtitleMappingError,
    map_subtitle_units_to_raw_cues,
    semantic_break_groups,
)


FONT_PATH = (
    PROJECT_ROOT
    / "data"
    / "libraries"
    / "font_library"
    / "files"
    / "DouyinSansBold_7244518590332801592.otf"
)


def _units(parts: list[tuple[str, str, str, str]]) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    cursor = 0
    for text, kind, bind, break_after in parts:
        result.append(
            {
                "start": cursor,
                "end": cursor + len(text),
                "text": text,
                "kind": kind,
                "bind": bind,
                "break_after": break_after,
            }
        )
        cursor += len(text)
    return result


def _item(
    script: str,
    units: list[dict[str, object]],
    raw_cues: list[dict[str, object]],
    *,
    audio_script_hash: str | None = None,
) -> dict[str, object]:
    script_hash = hashlib.sha256(script.encode("utf-8")).hexdigest()
    return {
        "script_text": script,
        "content_analysis": {
            "subtitle_analysis_status": "SUCCESS",
            "subtitle_units": units,
            "script_sha256": script_hash,
            "schema_version": "jyd.content-analysis.v1",
            "prompt_version": "jyd.content-analysis.prompt.v1",
        },
        "outputs": {
            "audio": {
                "asset_id": "audio-current",
                "version": 2,
                "metadata": {
                    "script_sha256": audio_script_hash or script_hash,
                    "script_length": len(script),
                },
            }
        },
        "subtitles": {
            "bound_audio_asset_id": "audio-current",
            "raw_cues": raw_cues,
        },
    }


def test_semantic_layout_keeps_connectors_numbers_words_and_tilde_intact() -> None:
    script = "那么通过八十四天糖原呼吸MiniMax~模型说明"
    units = _units(
        [
            ("那么", "connector", "right", "avoid"),
            ("通过", "word", "none", "prefer"),
            ("八十四", "number", "right", "avoid"),
            ("天", "word", "none", "prefer"),
            ("糖原", "word", "none", "prefer"),
            ("呼吸", "word", "none", "prefer"),
            ("MiniMax~", "proper_noun", "none", "prefer"),
            ("模型说明", "phrase", "none", "prefer"),
        ]
    )
    raw_cues = [
        {"start_us": 0, "end_us": 2_400_000, "text": "那么通过八十四天糖原"},
        {"start_us": 2_500_000, "end_us": 4_800_000, "text": "呼吸MiniMax~模型说明"},
    ]

    render_cues, mapping = derive_project_render_cues(
        _item(script, units, raw_cues),
        font_path=FONT_PATH,
    )

    assert mapping["status"] == "SUCCESS"
    assert mapping["mapped_unit_count"] == len(units)
    assert render_cues
    texts = [str(cue["text"]) for cue in render_cues]
    assert any("那么通过" in text for text in texts)
    assert any("八十四天" in text for text in texts)
    assert any("糖原" in text for text in texts)
    assert any("呼吸" in text for text in texts)
    assert any("MiniMax~" in text for text in texts)
    assert all(int(cue["end_us"]) > int(cue["start_us"]) for cue in render_cues)


def test_spaces_and_newlines_may_be_absent_from_provider_cues_without_losing_version_safety() -> None:
    script = "那么 通过八十四天\n糖原~呼吸"
    units = _units(
        [
            ("那么", "connector", "right", "avoid"),
            (" ", "whitespace", "none", "allow"),
            ("通过", "word", "none", "prefer"),
            ("八十四", "number", "right", "avoid"),
            ("天", "word", "none", "prefer"),
            ("\n", "whitespace", "none", "allow"),
            ("糖原", "word", "none", "prefer"),
            ("~", "punctuation", "none", "allow"),
            ("呼吸", "word", "none", "prefer"),
        ]
    )
    raw_cues = [
        {"start_us": 0, "end_us": 2_000_000, "text": "那么通过八十四天"},
        {"start_us": 2_100_000, "end_us": 3_600_000, "text": "糖原~呼吸"},
    ]

    timed = map_subtitle_units_to_raw_cues(script, units, raw_cues)
    groups = semantic_break_groups(timed)
    render_cues, mapping = derive_project_render_cues(
        _item(script, units, raw_cues),
        font_path=FONT_PATH,
    )

    assert mapping["status"] == "SUCCESS"
    assert len(timed) == len(units)
    assert "".join(str(group["text"]) for group in groups) == script.replace("\n", "")
    assert all("\n" not in str(group["text"]) for group in groups)
    assert "~" in "".join(str(cue["text"]) for cue in render_cues)
    assert all("\n" not in str(cue["text"]) for cue in render_cues)
    assert not any(
        "八十四天" in str(cue["text"]) and "糖原" in str(cue["text"])
        for cue in render_cues
    )


def test_overwide_semantic_group_is_repaired_without_discarding_other_ai_breaks() -> None:
    script = "百分之八十四另外一部分就叫到肌肉和肝脏成为肌糖原和肝糖原呼吸排出"
    units = _units(
        [
            ("百分之八十四", "phrase", "none", "prefer"),
            (
                "另外一部分就叫到肌肉和肝脏成为肌糖原和肝糖原",
                "phrase",
                "none",
                "prefer",
            ),
            ("呼吸排出", "phrase", "none", "prefer"),
        ]
    )
    raw_cues = [{"start_us": 0, "end_us": 6_000_000, "text": script}]

    render_cues, mapping = derive_project_render_cues(
        _item(script, units, raw_cues),
        font_path=FONT_PATH,
    )

    texts = [str(cue["text"]) for cue in render_cues]
    assert mapping["status"] == "SUCCESS"
    assert mapping["mapped_unit_count"] == len(units)
    assert len(render_cues) >= 3
    assert any("百分之八十四" in text for text in texts)
    assert any("呼吸排出" in text for text in texts)


def test_bad_model_fragments_are_repaired_and_hard_sentence_breaks_are_preserved() -> None:
    script = (
        "脂肪是怎么离开我们身体的呢？有人说是出汗，"
        "出汗只是身体调节体温的表现。如果你真的这么想"
    )
    units = _units(
        [
            ("脂肪是怎么离开我们身体的", "phrase", "none", "prefer"),
            ("呢？", "phrase", "none", "prefer"),
            ("有人说是出汗，", "phrase", "none", "prefer"),
            ("出汗只是身体调节体温的表", "phrase", "none", "prefer"),
            ("现。", "phrase", "none", "prefer"),
            ("如果你真的这么想", "phrase", "none", "prefer"),
        ]
    )
    raw_cues = [{"start_us": 0, "end_us": 8_000_000, "text": script}]

    render_cues, mapping = derive_project_render_cues(
        _item(script, units, raw_cues),
        font_path=FONT_PATH,
    )

    texts = [str(cue["text"]) for cue in render_cues]
    assert mapping["status"] == "SUCCESS"
    assert "呢有人" not in "|".join(texts)
    assert "现如果" not in "|".join(texts)
    assert any(text.endswith("呢") for text in texts)
    assert any(text.endswith("表现") for text in texts)
    assert any(text.startswith("如果") for text in texts)


def test_soft_comma_does_not_force_an_orphan_short_caption() -> None:
    script = "第一，脂肪是怎么储存在我们身体的。"
    units = _units(
        [
            ("第一，", "phrase", "none", "prefer"),
            ("脂肪是怎么储存在我们身体的。", "phrase", "none", "prefer"),
        ]
    )
    raw_cues = [{"start_us": 0, "end_us": 4_000_000, "text": script}]

    render_cues, mapping = derive_project_render_cues(
        _item(script, units, raw_cues),
        font_path=FONT_PATH,
    )

    texts = [str(cue["text"]) for cue in render_cues]
    assert mapping["status"] == "SUCCESS"
    assert texts[0] != "第一"
    assert texts[0].startswith("第一脂肪")
    assert not any(
        left.endswith("储") and right.startswith("存")
        for left, right in zip(texts, texts[1:])
    )


def test_leading_particle_is_rebalanced_with_its_phrase() -> None:
    script = "答案是让你呼吸急促心跳加速的轻活动。"
    units = _units(
        [
            ("答案是让你呼吸急促心跳加速", "phrase", "none", "prefer"),
            ("的轻活动。", "phrase", "none", "prefer"),
        ]
    )
    raw_cues = [{"start_us": 0, "end_us": 4_000_000, "text": script}]

    render_cues, mapping = derive_project_render_cues(
        _item(script, units, raw_cues),
        font_path=FONT_PATH,
    )

    texts = [str(cue["text"]) for cue in render_cues]
    assert mapping["status"] == "SUCCESS"
    assert not any(text.startswith(tuple("的地得呢啊了吧吗")) for text in texts[1:])
    assert any(text.endswith("呼吸急促") for text in texts)
    assert any(text.endswith("的轻活动") for text in texts)


def test_model_and_local_fallback_cannot_split_protected_phrases() -> None:
    script = (
        "现在专注新中年女性健康体重管理，今天给大家讲清核心逻辑。"
        "而且优先胖肚子以及成为内脏脂肪。"
        "也能够通过呼吸的形式帮助分解脂肪。"
    )
    units = _units(
        [
            ("现在专注新中年女性健康体重管理，", "phrase", "none", "prefer"),
            ("今天给大家讲清核心", "phrase", "none", "prefer"),
            ("逻", "phrase", "none", "prefer"),
            ("辑。", "phrase", "none", "prefer"),
            ("而且优先胖肚子以及成为内脏脂", "phrase", "none", "prefer"),
            ("肪。", "phrase", "none", "prefer"),
            ("也能够通过呼吸的形", "phrase", "none", "prefer"),
            ("式帮助分解脂肪。", "phrase", "none", "prefer"),
        ]
    )
    raw_cues = [{"start_us": 0, "end_us": 9_000_000, "text": script}]

    render_cues, mapping = derive_project_render_cues(
        _item(script, units, raw_cues),
        font_path=FONT_PATH,
    )

    texts = [str(cue["text"]) for cue in render_cues]
    joined = "|".join(texts)
    assert mapping["status"] == "SUCCESS"
    assert "女|性" not in joined
    assert "核心|逻辑" not in joined
    assert "以|及" not in joined
    assert "内脏脂|肪" not in joined
    assert "形|式" not in joined
    assert "现在专注新中年女性" in texts
    assert "而且优先胖肚子" in texts
    assert "以及成为内脏脂肪" in texts
    assert "也能够通过呼吸的形式" in texts


def test_tilde_is_an_exact_character_not_a_wildcard() -> None:
    script = "糖原~呼吸"
    units = _units([("糖原~呼吸", "phrase", "none", "prefer")])
    raw_cues = [{"start_us": 0, "end_us": 1_000_000, "text": "糖原呼吸"}]

    with pytest.raises(SemanticSubtitleMappingError) as error:
        map_subtitle_units_to_raw_cues(script, units, raw_cues)

    assert error.value.code == "RAW_CUES_TEXT_MISMATCH"


def test_model_generated_timestamps_are_rejected() -> None:
    script = "八十四天"
    units = _units([("八十四天", "number", "none", "prefer")])
    units[0]["start_us"] = 123

    with pytest.raises(SemanticSubtitleMappingError) as error:
        map_subtitle_units_to_raw_cues(
            script,
            units,
            [{"start_us": 0, "end_us": 1_000_000, "text": script}],
        )

    assert error.value.code == "MODEL_TIMESTAMP_FORBIDDEN"


def test_audio_script_version_mismatch_falls_back_without_mutating_raw_cues() -> None:
    script = "那么通过八十四天"
    units = _units(
        [
            ("那么", "connector", "right", "avoid"),
            ("通过", "word", "none", "prefer"),
            ("八十四天", "number", "none", "prefer"),
        ]
    )
    raw_cues = [{"start_us": 0, "end_us": 2_000_000, "text": script}]
    original_raw_cues = [dict(cue) for cue in raw_cues]

    render_cues, mapping = derive_project_render_cues(
        _item(
            script,
            units,
            raw_cues,
            audio_script_hash=hashlib.sha256("旧脚本".encode("utf-8")).hexdigest(),
        ),
        font_path=FONT_PATH,
    )

    assert mapping["status"] == "FALLBACK"
    assert mapping["reason_code"] == "AUDIO_SCRIPT_VERSION_MISMATCH"
    assert render_cues
    assert raw_cues == original_raw_cues
