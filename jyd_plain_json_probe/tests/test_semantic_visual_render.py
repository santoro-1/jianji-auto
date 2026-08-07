from __future__ import annotations

from pathlib import Path

from jyd_probe.content_replace import ContentReplaceJob, StickerAddition, _apply_json_changes
from jyd_probe.render_job import _build_visual_overlay_additions
from jyd_probe.semantic_visuals import frozen_visual_overlays
from jyd_probe.sticker_apply import add_fullscreen_sticker_to_data


def test_visual_overlay_job_uses_independent_optional_track() -> None:
    bundle = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "libraries"
        / "semantic_visual_library"
        / "bundles"
        / "egg_boiled"
    )
    additions = _build_visual_overlay_additions(
        {
            "visual_overlays": [
                {
                    "enabled": True,
                    "bundle_path": str(bundle),
                    "start_us": 500_000,
                    "duration_us": 1_800_000,
                    "corner": "top_right",
                    "scale": 0.28,
                    "opacity": 0.9,
                }
            ]
        }
    )

    assert len(additions) == 1
    assert additions[0].track_name == "语义前景图片"
    assert additions[0].optional is True
    assert additions[0].inside_canvas is True
    assert additions[0].sticker_json_path == bundle / "sticker.json"


def test_missing_optional_visual_does_not_fail_other_json_changes(tmp_path: Path) -> None:
    job = ContentReplaceJob(
        template_draft_dir=tmp_path,
        output_root=tmp_path,
        sticker_additions=[
            StickerAddition(
                sticker_json_path=tmp_path / "missing" / "sticker.json",
                start_us=0,
                duration_us=1_000_000,
                track_name="语义前景图片",
                optional=True,
            )
        ],
    )
    data = {"duration": 3_000_000, "materials": {}, "tracks": []}

    assert _apply_json_changes(object(), data, job) == 0
    assert data["tracks"] == []


def test_semantic_bundle_writes_timed_safe_area_track_without_changing_duration() -> None:
    bundle = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "libraries"
        / "semantic_visual_library"
        / "bundles"
        / "egg_boiled"
    )
    data = {
        "duration": 8_000_000,
        "canvas_config": {"width": 1080, "height": 1920},
        "tracks": [{"id": "video-track", "type": "video", "segments": []}],
        "materials": {"stickers": []},
    }

    changed = add_fullscreen_sticker_to_data(
        data,
        bundle / "sticker.json",
        start_us=500_000,
        duration_us=1_800_000,
        corner="top_right",
        scale=0.28,
        opacity=0.9,
        track_name="语义前景图片",
        inside_canvas=True,
    )

    assert changed == 1
    assert data["duration"] == 8_000_000
    track = data["tracks"][-1]
    assert track["name"] == "语义前景图片"
    segment = track["segments"][0]
    assert segment["target_timerange"] == {
        "start": 500_000,
        "duration": 1_800_000,
    }
    assert segment["global_alpha"] == 0.9
    transform = segment["clip"]["transform"]
    assert -1.0 <= transform["x"] <= 1.0
    assert -1.0 <= transform["y"] <= 1.0


def test_browser_and_render_consumers_read_same_frozen_recipe() -> None:
    overlay = {
        "overlay_id": "vo-1",
        "asset_id": "egg.boiled.01",
        "enabled": True,
        "start_us": 100_000,
        "duration_us": 1_800_000,
        "corner": "top_right",
        "scale": 0.28,
        "opacity": 1.0,
    }
    item = {
        "visual_analysis": {
            "recipe": {
                "schema": "jyd.semantic-visual-recipe.v1",
                "catalog_version": "sha256:test",
                "overlays": [overlay],
            }
        }
    }

    assert frozen_visual_overlays(item) == [overlay]
