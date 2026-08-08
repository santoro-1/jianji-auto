from __future__ import annotations

from pathlib import Path
import json
import shutil

import pytest

from jyd_probe.semantic_subtitles import SemanticSubtitleMappingError
from jyd_probe.semantic_visuals import (
    CATALOG_SCHEMA_V1,
    CATALOG_SCHEMA_V2,
    RECIPE_SCHEMA_V2,
    build_visual_recipe,
    frozen_visual_overlays,
    load_semantic_visual_catalog,
    map_visual_candidates_to_raw_cues,
    recall_semantic_visual_candidates,
    SemanticVisualCatalogError,
)


CATALOG_ROOT = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "libraries"
    / "semantic_visual_library"
)


def _catalog():
    return load_semantic_visual_catalog(CATALOG_ROOT)


def _write_v2_catalog(root: Path) -> Path:
    bundle = root / "bundles" / "beef_image_01"
    shutil.copytree(CATALOG_ROOT / "bundles" / "egg_boiled", bundle)
    videos = root / "videos" / "beef_cooking_01"
    videos.mkdir(parents=True)
    (videos / "video.mp4").write_bytes(b"fake-mp4-for-catalog-loader")
    shutil.copy2(
        bundle / "resources" / "sticker" / "singleImage.png",
        videos / "poster.png",
    )
    (videos / "metadata.json").write_text(
        json.dumps({"source": "test"}), encoding="utf-8"
    )
    payload = {
        "schema": CATALOG_SCHEMA_V2,
        "library_id": "jyd.semantic-visual-library.test",
        "concepts": [
            {
                "concept_id": "food.beef",
                "label": "牛肉",
                "description": "作为食物或食材出现的牛肉",
                "aliases": ["瘦牛肉", "牛肉"],
            },
            {
                "concept_id": "meal.breakfast",
                "label": "早餐",
                "description": "明确作为早餐出现的餐食",
                "aliases": ["早餐"],
            },
        ],
        "assets": [
            {
                "asset_id": "beef.image.01",
                "concept_ids": ["food.beef", "meal.breakfast"],
                "name": "牛肉图片",
                "description": "一盘熟牛肉",
                "media_type": "image",
                "renderer": "jyd_sticker_bundle",
                "tags": ["熟食", "照片"],
                "resource": {
                    "bundle": "bundles/beef_image_01",
                    "preview": "bundles/beef_image_01/resources/sticker/singleImage.png",
                },
                "defaults": {
                    "corner": "top_left",
                    "scale": 0.26,
                    "opacity": 1.0,
                    "duration_us": 1_800_000,
                },
            },
            {
                "asset_id": "beef.video.01",
                "concept_ids": ["food.beef"],
                "name": "牛肉烹饪视频",
                "description": "牛肉烹饪过程近景",
                "media_type": "video",
                "renderer": "video_overlay",
                "tags": ["烹饪过程", "动态"],
                "resource": {
                    "video": "videos/beef_cooking_01/video.mp4",
                    "preview": "videos/beef_cooking_01/poster.png",
                    "metadata": "videos/beef_cooking_01/metadata.json",
                    "duration_us": 6_200_000,
                    "width": 1920,
                    "height": 1080,
                    "has_audio": True,
                },
                "defaults": {
                    "corner": "top_right",
                    "scale": 0.32,
                    "opacity": 1.0,
                    "duration_us": 3_000_000,
                    "source_start_us": 0,
                    "mute": True,
                    "loop": False,
                    "fit": "cover",
                },
            },
        ],
    }
    manifest = root / "catalog.json"
    manifest.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return manifest


def test_catalog_contains_eighteen_concepts_and_nineteen_image_assets() -> None:
    catalog = _catalog()

    assert catalog.schema == CATALOG_SCHEMA_V2
    assert catalog.library_id == "jyd.semantic-visual-library.default"
    assert len(catalog.concepts) == 18
    assert len(catalog.assets) == 19
    assert len([item for item in catalog.assets if item["concept_id"] == "food.egg"]) == 2
    assert all(Path(item["image_path"]).is_file() for item in catalog.assets)
    assert all(item["media_type"] == "image" for item in catalog.assets)
    assert all(item["renderer"] == "jyd_sticker_bundle" for item in catalog.assets)
    assert all(item["concept_ids"] == [item["concept_id"]] for item in catalog.assets)
    assert catalog.asset("protein.food_guide.01") is not None
    assert catalog.asset("fruit.platter.01") is not None


def test_v2_catalog_loads_unified_image_and_reserved_video_assets(tmp_path: Path) -> None:
    root = tmp_path / "catalog-v2"
    _write_v2_catalog(root)

    catalog = load_semantic_visual_catalog(root)

    assert catalog.schema == CATALOG_SCHEMA_V2
    assert catalog.library_id == "jyd.semantic-visual-library.test"
    assert len(catalog.concepts) == 2
    image = catalog.asset("beef.image.01")
    video = catalog.asset("beef.video.01")
    assert image is not None and image["concept_ids"] == ["food.beef", "meal.breakfast"]
    assert image["media_type"] == "image"
    assert video is not None and video["media_type"] == "video"
    assert video["renderer"] == "video_overlay"
    assert video["defaults"]["mute"] is True
    public = catalog.public_payload()
    assert public["schema"] == CATALOG_SCHEMA_V2
    assert public["library_id"] == catalog.library_id
    assert all("resource_path" not in item for item in public["assets"])
    assert all("preview_path" not in item for item in public["assets"])
    assert all("bundle_path" not in item for item in public["assets"])
    assert all("image_path" not in item for item in public["assets"])


def test_v2_catalog_rejects_path_escape_and_renderer_mismatch(tmp_path: Path) -> None:
    root = tmp_path / "catalog-v2"
    manifest = _write_v2_catalog(root)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["assets"][1]["resource"]["video"] = "../outside.mp4"
    (tmp_path / "outside.mp4").write_bytes(b"outside")
    manifest.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(SemanticVisualCatalogError):
        load_semantic_visual_catalog(root)

    shutil.rmtree(root)
    manifest = _write_v2_catalog(root)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["assets"][0]["renderer"] = "video_overlay"
    manifest.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(SemanticVisualCatalogError):
        load_semantic_visual_catalog(root)


def test_v2_catalog_version_changes_with_video_bytes(tmp_path: Path) -> None:
    root = tmp_path / "catalog-v2"
    _write_v2_catalog(root)
    before = load_semantic_visual_catalog(root).catalog_version
    video_path = root / "videos" / "beef_cooking_01" / "video.mp4"
    video_path.write_bytes(video_path.read_bytes() + b"changed")

    assert load_semantic_visual_catalog(root).catalog_version != before


def test_recipe_v2_can_freeze_and_resolve_one_video_overlay(tmp_path: Path) -> None:
    root = tmp_path / "catalog-v2"
    _write_v2_catalog(root)
    catalog = load_semantic_visual_catalog(root)
    candidate = recall_semantic_visual_candidates("早餐吃牛肉", catalog)["candidates"][1]

    recipe = build_visual_recipe(
        catalog=catalog,
        mapped_candidates=[
            {**candidate, "start_us": 1_000_000, "duration_us": 3_000_000}
        ],
        decisions=[
            {
                "candidate_id": candidate["candidate_id"],
                "decision": "SHOW",
                "concept_id": "food.beef",
                "importance": 0.9,
                "confidence": 0.95,
                "reason_code": "LITERAL_CONCRETE_OBJECT",
            }
        ],
        media_policy="video_only",
    )

    assert recipe["schema"] == RECIPE_SCHEMA_V2
    assert recipe["media_policy"] == "video_only"
    assert recipe["library_id"] == catalog.library_id
    overlay = recipe["overlays"][0]
    assert overlay["asset_id"] == "beef.video.01"
    assert overlay["media_type"] == "video"
    assert overlay["renderer"] == "video_overlay"
    assert overlay["resource_path"] == "videos/beef_cooking_01/video.mp4"
    assert "video_path" not in overlay
    resolved = frozen_visual_overlays(
        {"visual_analysis": {"recipe": recipe}}, library_root=root
    )
    assert Path(resolved[0]["video_path"]).resolve() == (
        root / "videos" / "beef_cooking_01" / "video.mp4"
    ).resolve()


def test_catalog_rejects_path_escape_and_duplicate_asset_id(tmp_path: Path) -> None:
    root = tmp_path / "catalog"
    shutil.copytree(CATALOG_ROOT, root)
    manifest_path = root / "catalog.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["assets"][0]["resource"]["bundle"] = "../outside"
    (tmp_path / "outside").mkdir()
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(SemanticVisualCatalogError):
        load_semantic_visual_catalog(root)

    shutil.rmtree(root)
    shutil.copytree(CATALOG_ROOT, root)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["assets"][1]["asset_id"] = payload["assets"][0]["asset_id"]
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(SemanticVisualCatalogError):
        load_semantic_visual_catalog(root)


def test_catalog_version_changes_when_image_bytes_change(tmp_path: Path) -> None:
    root = tmp_path / "catalog"
    shutil.copytree(CATALOG_ROOT, root)
    before = load_semantic_visual_catalog(root).catalog_version
    image_path = Path(load_semantic_visual_catalog(root).assets[0]["image_path"])
    image_path.write_bytes(image_path.read_bytes() + b"catalog-version-test")

    assert load_semantic_visual_catalog(root).catalog_version != before


def test_recall_uses_exact_python_ranges_and_longest_alias() -> None:
    script = "早餐吃水煮蛋、玉米和豆浆。"
    payload = recall_semantic_visual_candidates(script, _catalog())

    assert [item["text"] for item in payload["candidates"]] == [
        "早餐",
        "水煮蛋",
        "玉米",
        "豆浆",
    ]
    for item in payload["candidates"]:
        assert script[item["char_start"] : item["char_end"]] == item["text"]
    assert payload == recall_semantic_visual_candidates(script, _catalog())


def test_recall_does_not_decide_idiom_negation_or_meta_context_locally() -> None:
    script = "每天吃一个鸡蛋。鸡蛋里挑骨头。这不是鸡蛋。讨论鸡蛋这个词。"
    payload = recall_semantic_visual_candidates(script, _catalog())

    assert [item["text"] for item in payload["candidates"]] == ["鸡蛋"] * 4


def test_minimax_mapping_leads_and_clamps_to_video_duration() -> None:
    script = "每天吃一个鸡蛋"
    candidates = recall_semantic_visual_candidates(script, _catalog())["candidates"]
    mapped = map_visual_candidates_to_raw_cues(
        script,
        candidates,
        [{"start_us": 1_000_000, "end_us": 3_000_000, "text": script}],
        video_duration_us=3_100_000,
        cover_offset_us=200_000,
    )

    assert mapped[0]["start_us"] >= 200_000
    assert mapped[0]["start_us"] + mapped[0]["duration_us"] <= 3_100_000
    assert mapped[0]["duration_us"] <= 1_800_000


def test_mapping_rejects_raw_cue_text_mismatch() -> None:
    script = "每天吃一个鸡蛋"
    candidates = recall_semantic_visual_candidates(script, _catalog())["candidates"]
    with pytest.raises(SemanticSubtitleMappingError) as error:
        map_visual_candidates_to_raw_cues(
            script,
            candidates,
            [{"start_us": 0, "end_us": 1_000_000, "text": "每天吃一个玉米"}],
        )
    assert error.value.code == "RAW_CUES_TEXT_MISMATCH"


def test_recipe_applies_confidence_and_density_policy() -> None:
    catalog = _catalog()
    script = "鸡蛋鸡蛋鸡蛋"
    candidates = recall_semantic_visual_candidates(script, catalog)["candidates"]
    mapped = [
        {**candidate, "start_us": index * 7_000_000, "duration_us": 1_800_000}
        for index, candidate in enumerate(candidates)
    ]
    decisions = [
        {
            "candidate_id": candidate["candidate_id"],
            "decision": "SHOW",
            "concept_id": "food.egg",
            "confidence": 0.95,
            "reason_code": "LITERAL_CONCRETE_OBJECT",
        }
        for candidate in candidates
    ]

    recipe = build_visual_recipe(
        catalog=catalog, mapped_candidates=mapped, decisions=decisions
    )

    # Same concept/asset has a 20 second cooldown, so only the first survives.
    assert len(recipe["overlays"]) == 1
    assert recipe["overlays"][0]["asset_id"].startswith("egg.")


def test_recipe_conflict_prefers_importance_then_confidence() -> None:
    catalog = _catalog()
    candidates = recall_semantic_visual_candidates("鸡蛋和玉米", catalog)["candidates"]
    mapped = [
        {**candidates[0], "start_us": 0, "duration_us": 1_800_000},
        {**candidates[1], "start_us": 3_000_000, "duration_us": 1_800_000},
    ]
    decisions = [
        {
            "candidate_id": candidates[0]["candidate_id"],
            "decision": "SHOW",
            "concept_id": "food.egg",
            "importance": 0.7,
            "confidence": 0.99,
            "reason_code": "LITERAL_CONCRETE_OBJECT",
        },
        {
            "candidate_id": candidates[1]["candidate_id"],
            "decision": "SHOW",
            "concept_id": "food.corn",
            "importance": 0.95,
            "confidence": 0.9,
            "reason_code": "LITERAL_CONCRETE_OBJECT",
        },
    ]

    recipe = build_visual_recipe(
        catalog=catalog, mapped_candidates=mapped, decisions=decisions
    )

    assert [item["concept_id"] for item in recipe["overlays"]] == ["food.corn"]


def test_low_confidence_show_is_not_auto_enabled() -> None:
    catalog = _catalog()
    candidate = recall_semantic_visual_candidates("鸡蛋", catalog)["candidates"][0]
    recipe = build_visual_recipe(
        catalog=catalog,
        mapped_candidates=[{**candidate, "start_us": 0, "duration_us": 1_800_000}],
        decisions=[
            {
                "candidate_id": candidate["candidate_id"],
                "decision": "SHOW",
                "concept_id": "food.egg",
                "importance": 0.9,
                "confidence": 0.84,
                "reason_code": "LITERAL_CONCRETE_OBJECT",
            }
        ],
    )

    assert recipe["overlays"] == []
