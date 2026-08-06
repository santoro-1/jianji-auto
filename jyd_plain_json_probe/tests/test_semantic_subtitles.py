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
    assert "".join(str(group["text"]) for group in groups) == script
    assert "~" in "".join(str(cue["text"]) for cue in render_cues)
    assert all("\n" not in str(cue["text"]) for cue in render_cues)


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
