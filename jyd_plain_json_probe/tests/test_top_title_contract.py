from __future__ import annotations

import pytest

from jyd_probe.project_postprocess import (
    CAPTION_REFERENCE_MAX_EM,
    build_project_cover,
    build_top_title_texts,
    normalize_cover_title,
    normalize_top_title,
)
from jyd_probe.render_job import _build_text_replacements


def test_top_title_is_optional_and_normalizes_whitespace() -> None:
    assert normalize_top_title(None) == {"label": "", "headline": ""}
    assert normalize_top_title(
        {"label": "  \u51cf\u8102  \u771f\u76f8 ", "headline": "\u575a\u6301\n\u624d\u662f\u5173\u952e"}
    ) == {
        "label": "\u51cf\u8102 \u771f\u76f8",
        "headline": "\u575a\u6301 \u624d\u662f\u5173\u952e",
    }
    assert CAPTION_REFERENCE_MAX_EM == pytest.approx(10.214285714285714)


def test_top_title_builds_two_full_duration_styled_text_additions() -> None:
    texts = build_top_title_texts(
        {"line_1": "\u51cf\u8102\u771f\u76f8", "line_2": "\u575a\u6301\u624d\u662f\u5173\u952e"},
        font={"resource_id": "font-id", "path": "D:/font.ttf", "name": "Fixed"},
    )
    assert [item["transform_y"] for item in texts] == [1535 / 1920, 1350 / 1920]
    assert [item["size"] for item in texts] == [11.0, 13.0]
    assert [item["color"] for item in texts] == ["#FFD600", "#FFFFFF"]
    assert all(item["duration_us"] == 0 for item in texts)

    _replacements, additions, _styles, _nested_styles = _build_text_replacements(
        {"texts": texts}, timeline_duration_us=5_000_000
    )
    assert [item.duration_us for item in additions] == [5_000_000, 5_000_000]
    assert [item.line_max_width for item in additions] == [0.92, 0.92]
    assert [item.font_id for item in additions] == ["font-id", "font-id"]
    assert [item.stroke_width for item in additions] == [0.04, 0.04]


def test_top_title_rejects_multiline_overflow() -> None:
    with pytest.raises(ValueError, match="\u9ec4\u8272\u5c0f\u6807\u9898"):
        normalize_top_title({"label": "123456", "headline": ""})


def test_cover_title_requires_two_compact_lines() -> None:
    assert normalize_cover_title(None) == {"line_1": "", "line_2": ""}
    assert normalize_cover_title({"topic": "健康真相", "hook": "别再踩坑"}) == {
        "line_1": "健康真相",
        "line_2": "别再踩坑",
    }
    with pytest.raises(ValueError, match="同时提供两行"):
        normalize_cover_title({"line_1": "健康真相", "line_2": ""})
    with pytest.raises(ValueError, match="不能包含空格"):
        normalize_cover_title({"line_1": "健康 真相", "line_2": "别再踩坑"})
    with pytest.raises(ValueError, match="最多 5 个字符"):
        normalize_cover_title({"line_1": "一二三四五六", "line_2": "别再踩坑"})
    with pytest.raises(ValueError, match="最多 14 个字符"):
        normalize_cover_title({"line_1": "健康真相", "line_2": "一二三四五六七八九十一二三四五"})
    assert normalize_cover_title(
        {"line_1": "健康真相", "line_2": "一二三四五六七八九十一二三四"}
    )["line_2"] == "一二三四五六七八九十一二三四"


def test_project_cover_uses_input_image_and_fixed_visual_recipe(tmp_path) -> None:
    image = tmp_path / "person.png"
    image.write_bytes(b"image")
    font = tmp_path / "SourceHanSerifCN-Heavy.otf"
    font.write_bytes(b"font")
    cover = build_project_cover(
        {
            "row_key": "1",
            "inputs": {"image": {"managed_path": str(image)}},
            "settings": {
                "postprocess": {
                    "cover_title": {"line_1": "健康真相", "line_2": "别再踩坑"}
                }
            },
        },
        fonts={
            "resource_id:6807742980271641102": {
                "resource_id": "6807742980271641102",
                "name": "SourceHanSerifCN-Heavy",
                "path": str(font),
            }
        },
    )
    assert cover is not None
    assert cover["frame_source"] == "input_image"
    assert cover["image_path"] == str(image.resolve())
    assert cover["frame_count"] == 3
    assert cover["line_1_size"] == 30.0
    assert cover["line_2_size"] == 22.0
    assert cover["line_1_color"] == "#FADF4A"
    assert cover["line_2_color"] == "#F5F6F0"
    assert cover["line_1_y"] == pytest.approx(-160 / 1920)
    assert cover["line_2_y"] == pytest.approx(-655 / 1920)
    assert cover["overlay_y_ratio"] == pytest.approx(0.609375)
    assert cover["line_1_shadow_alpha"] == 0.9
    assert cover["line_2_shadow_alpha"] == 0.5
