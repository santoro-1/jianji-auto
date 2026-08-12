from __future__ import annotations

from jyd_probe.project_export_naming import (
    audio_export_filename,
    composition_export_filename,
    project_item_export_stem,
    segment_export_filename,
    variant_export_filename,
)


def _four_column_item() -> dict:
    return {
        "row_key": "2",
        "settings": {
            "source_metadata": {
                "article_type": "鸡汤文",
                "assigned_account": "5",
            }
        },
    }


def test_four_column_exports_use_account_type_task_order() -> None:
    item = _four_column_item()
    assert project_item_export_stem(item) == "账号5-鸡汤文-2"
    assert audio_export_filename(
        item, {"filename": "2_0.9倍速.mp3", "metadata": {"speed": 0.9}}
    ) == "账号5-鸡汤文-2_0.9倍速.mp3"
    assert composition_export_filename(
        item, {"filename": "2-composition.mp4"}
    ) == "账号5-鸡汤文-2-composition.mp4"
    assert variant_export_filename(
        item, {"filename": "任务-2-变体-007.mp4"}
    ) == "账号5-鸡汤文-2-变体-007.mp4"
    assert segment_export_filename(
        item, {"filename": "2-segment-001.mp4"}, index=1
    ) == "账号5-鸡汤文-2-segment-001.mp4"


def test_legacy_two_column_item_keeps_existing_asset_filename() -> None:
    item = {"row_key": "2", "settings": {}}
    assert audio_export_filename(item, {"filename": "2_0.9倍速.mp3"}) == "2_0.9倍速.mp3"
    assert composition_export_filename(
        item, {"filename": "2-composition.mp4"}
    ) == "2-composition.mp4"
    assert variant_export_filename(
        item, {"filename": "任务-2-变体-001.mp4"}
    ) == "任务-2-变体-001.mp4"
