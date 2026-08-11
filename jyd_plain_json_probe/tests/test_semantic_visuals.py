from __future__ import annotations

from pathlib import Path
import json
import shutil

import pytest

from jyd_probe.semantic_subtitles import SemanticSubtitleMappingError
from jyd_probe.semantic_visuals import (
    _assets_for_media_policy,
    CATALOG_SCHEMA_V1,
    CATALOG_SCHEMA_V2,
    RECIPE_SCHEMA_V2,
    build_visual_recipe,
    frozen_visual_overlays,
    load_semantic_visual_catalog,
    map_visual_candidates_to_raw_cues,
    recall_semantic_visual_candidates,
    SemanticVisualCatalog,
    SemanticVisualCatalogError,
    validate_visual_occupancy,
    visual_overlay_conflicts,
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


def test_catalog_contains_images_and_registered_activity_videos() -> None:
    catalog = _catalog()

    assert catalog.schema == CATALOG_SCHEMA_V2
    assert catalog.library_id == "jyd.semantic-visual-library.default"
    assert len(catalog.concepts) == 37
    assert len(catalog.assets) == 40
    assert len([item for item in catalog.assets if item["media_type"] == "image"]) == 38
    assert len([item for item in catalog.assets if item["media_type"] == "video"]) == 2
    assert len([item for item in catalog.assets if item["concept_id"] == "food.egg"]) == 2
    assert all(Path(item["image_path"]).is_file() for item in catalog.assets)


def test_generic_staple_food_does_not_recall_quality_carbohydrate() -> None:
    catalog = _catalog()
    payload = recall_semantic_visual_candidates(
        "平时吃的精米白面替换三分之一成粗粮，比如喝杂粮粥。",
        catalog,
    )

    assert [item["text"] for item in payload["candidates"]] == ["粗粮", "杂粮粥"]
    assert {
        concept["concept_id"]
        for item in payload["candidates"]
        for concept in item["allowed_concepts"]
    } == {"food.whole_grain"}
    assert recall_semantic_visual_candidates("不要完全不吃主食", catalog)["candidates"] == []
    assert all(
        item["renderer"]
        == ("jyd_sticker_bundle" if item["media_type"] == "image" else "video_overlay")
        for item in catalog.assets
    )
    assert all(item["concept_ids"] == [item["concept_id"]] for item in catalog.assets)
    assert catalog.asset("protein.food_guide.01") is not None
    assert catalog.asset("fruit.platter.01") is not None
    assert catalog.asset("water.warm_glass.01") is not None
    assert catalog.asset("activity.walking.01") is not None
    assert catalog.asset("activity.aerobic.crotch_clap.video.01") is not None
    assert catalog.asset("activity.aerobic.core_broll.video.01") is not None


def test_extended_food_and_activity_aliases_recall_specific_concepts() -> None:
    catalog = load_semantic_visual_catalog(CATALOG_ROOT)
    payload = recall_semantic_visual_candidates(
        "早餐吃全麦面包和酸奶，午餐有米饭、西红柿和三文鱼，晚上快走，雨天用跑步机。",
        catalog,
    )

    concept_by_text = {
        item["text"]: item["allowed_concepts"][0]["concept_id"]
        for item in payload["candidates"]
    }
    assert concept_by_text["全麦面包"] == "food.whole_wheat_bread"
    assert concept_by_text["酸奶"] == "food.yogurt"
    assert concept_by_text["米饭"] == "food.rice"
    assert concept_by_text["西红柿"] == "food.tomato"
    assert concept_by_text["三文鱼"] == "food.salmon"
    assert concept_by_text["快走"] == "activity.walking"
    assert concept_by_text["跑步机"] == "activity.treadmill"


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
    assert image["defaults"]["corner"] == "bottom_center"
    assert image["defaults"]["scale"] == 0.78
    assert video is not None and video["media_type"] == "video"
    assert video["renderer"] == "video_overlay"
    assert video["defaults"]["corner"] == "bottom_center"
    assert video["defaults"]["scale"] == 0.615
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


def test_mixed_media_prefers_images_for_objects_and_video_for_actions(tmp_path: Path) -> None:
    root = tmp_path / "library"
    _write_v2_catalog(root)
    catalog = load_semantic_visual_catalog(root)

    assert _assets_for_media_policy(catalog, "food.beef", "mixed")[0]["media_type"] == "image"
    action_catalog = SemanticVisualCatalog(
        root=catalog.root,
        schema=catalog.schema,
        library_id=catalog.library_id,
        catalog_version=catalog.catalog_version,
        concepts=catalog.concepts,
        assets=tuple(
            {**asset, "concept_ids": ["activity.running"]}
            for asset in catalog.assets
        ),
    )
    assert _assets_for_media_policy(action_catalog, "activity.running", "mixed")[0]["media_type"] == "video"


def test_explicit_activity_uses_action_asset_and_enrichment_uses_only_tagged_broll() -> None:
    catalog = _catalog()

    explicit = _assets_for_media_policy(
        catalog, "activity.aerobic", "mixed", usage="explicit"
    )
    enrichment = _assets_for_media_policy(
        catalog, "activity.aerobic", "mixed", usage="enrichment"
    )

    assert explicit[0]["asset_id"] == "activity.aerobic.crotch_clap.video.01"
    assert all("broll" not in item["asset_id"] for item in explicit)
    assert [item["asset_id"] for item in enrichment] == [
        "activity.aerobic.core_broll.video.01"
    ]
    assert explicit[0]["defaults"]["corner"] == "bottom_center"
    assert explicit[0]["defaults"]["scale"] == 0.615
    assert enrichment[0]["defaults"]["corner"] == "center"
    assert enrichment[0]["defaults"]["scale"] == 1.0


def test_shared_occupancy_rejects_overlap_and_applies_locked_spacing() -> None:
    locked = {
        "overlay_id": "locked-video",
        "concept_id": "activity.running",
        "asset_id": "running.video.01",
        "media_type": "video",
        "enabled": True,
        "locked": True,
        "start_us": 10_000_000,
        "duration_us": 3_000_000,
    }
    image = {
        "overlay_id": "automatic-image",
        "concept_id": "food.egg",
        "asset_id": "egg.boiled.01",
        "media_type": "image",
        "enabled": True,
        "start_us": 12_000_000,
        "duration_us": 1_800_000,
    }

    assert visual_overlay_conflicts(image, [locked]) is True
    with pytest.raises(ValueError, match="同一时间只能显示一个语义视觉素材"):
        validate_visual_occupancy([locked, image])


def test_recall_adds_compact_enrichment_anchors_only_for_tagged_assets() -> None:
    catalog = _catalog()
    tagged_assets = tuple(
        {**asset, "tags": ["空镜"] if index == 0 else []}
        for index, asset in enumerate(catalog.assets)
    )
    tagged_catalog = SemanticVisualCatalog(
        root=catalog.root,
        schema=catalog.schema,
        library_id=catalog.library_id,
        catalog_version=catalog.catalog_version,
        concepts=catalog.concepts,
        assets=tagged_assets,
    )
    script = "这是健康知识讲解，需要结合实际生活理解。" * 8

    recalled = recall_semantic_visual_candidates(script, tagged_catalog)
    enrichment = [
        item
        for item in recalled["candidates"]
        if str(item.get("candidate_id") or "").startswith("ve_")
    ]

    assert enrichment
    assert len(enrichment) <= 6
    assert all(len(item["allowed_concepts"]) <= 8 for item in enrichment)
    assert all(item["allowed_concepts"][0]["concept_id"] == "food.egg" for item in enrichment)


def test_enrichment_requires_twenty_second_drought_and_is_capped_per_minute() -> None:
    catalog = _catalog()
    candidates = recall_semantic_visual_candidates(
        "燃脂操核心燃脂胯下击掌", catalog
    )["candidates"]
    mapped = [
        {
            **candidate,
            "start_us": start_us,
            "duration_us": 1_800_000,
            "usage": "enrichment",
        }
        for candidate, start_us in zip(
            candidates,
            (20_000_000, 45_000_000, 70_000_000),
        )
    ]
    decisions = [
        {
            "candidate_id": candidate["candidate_id"],
            "decision": "SHOW",
            "concept_id": candidate["allowed_concepts"][0]["concept_id"],
            "usage": "enrichment",
            "confidence": 1.0,
            "importance": 0.75,
        }
        for candidate in mapped
    ]

    recipe = build_visual_recipe(
        catalog=catalog,
        mapped_candidates=mapped,
        decisions=decisions,
        media_policy="mixed",
    )

    assert [item["start_us"] for item in recipe["overlays"]] == [20_000_000, 45_000_000]
    assert all(item["usage"] == "enrichment" for item in recipe["overlays"])
    assert all(
        item["asset_id"] == "activity.aerobic.core_broll.video.01"
        for item in recipe["overlays"]
    )

    too_early = build_visual_recipe(
        catalog=catalog,
        mapped_candidates=[{**mapped[0], "start_us": 19_999_999}],
        decisions=[decisions[0]],
        media_policy="mixed",
    )
    assert too_early["overlays"] == []


def test_untouched_auto_recipe_refreshes_current_asset_layout_and_resource() -> None:
    overlay = {
        "overlay_id": "vo-cucumber",
        "asset_id": "cucumber.salad.01",
        "enabled": True,
        "selection_mode": "auto",
        "manual": False,
        "locked": False,
        "media_type": "image",
        "renderer": "jyd_sticker_bundle",
        "resource_path": "bundles/cucumber_salad_01",
        "corner": "top_right",
        "scale": 0.25,
        "opacity": 1.0,
    }
    item = {
        "visual_analysis": {
            "recipe": {
                "schema": RECIPE_SCHEMA_V2,
                "catalog_version": "sha256:legacy",
                "overlays": [overlay],
            }
        }
    }

    refreshed = frozen_visual_overlays(item, library_root=CATALOG_ROOT)[0]

    assert refreshed["corner"] == "bottom_center"
    assert refreshed["scale"] == 0.78
    assert Path(refreshed["bundle_path"]).name == "cucumber_salad_lower_fade_02"

    overlay.update({"manual": True, "locked": True})
    manual = frozen_visual_overlays(item, library_root=CATALOG_ROOT)[0]
    assert manual["corner"] == "top_right"
    assert manual["scale"] == 0.25
    assert Path(manual["bundle_path"]).name == "cucumber_salad_01"


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


def test_recall_rejects_known_compounds_that_have_no_matching_asset() -> None:
    payload = recall_semantic_visual_candidates(
        "不要吃油脂很多的鸡蛋糕，也不要吃放久的蔬菜沙拉。",
        _catalog(),
    )

    assert all(item["text"] not in {"鸡蛋", "蔬菜"} for item in payload["candidates"])


def test_recall_does_not_decide_idiom_negation_or_meta_context_locally() -> None:
    script = "每天吃一个鸡蛋。鸡蛋里挑骨头。这不是鸡蛋。讨论鸡蛋这个词。"
    payload = recall_semantic_visual_candidates(script, _catalog())

    assert [item["text"] for item in payload["candidates"]] == ["鸡蛋"] * 4


def test_minimax_mapping_uses_phrase_span_and_clamps_to_video_duration() -> None:
    script = "每天吃一个鸡蛋"
    candidates = recall_semantic_visual_candidates(script, _catalog())["candidates"]
    mapped = map_visual_candidates_to_raw_cues(
        script,
        candidates,
        [{"start_us": 1_000_000, "end_us": 3_000_000, "text": script}],
        video_duration_us=3_100_000,
        cover_offset_us=200_000,
    )

    assert mapped[0]["start_us"] == 1_200_000
    assert mapped[0]["duration_us"] == 1_900_000
    assert mapped[0]["start_us"] + mapped[0]["duration_us"] == 3_100_000


def test_mapping_covers_the_punctuation_phrase_containing_the_keyword() -> None:
    script = "早餐可以灵活安排，比如早上喝碗杂粮粥。"
    candidate = next(
        item
        for item in recall_semantic_visual_candidates(script, _catalog())["candidates"]
        if item["text"] == "杂粮粥"
    )

    mapped = map_visual_candidates_to_raw_cues(
        script,
        [candidate],
        [{"start_us": 0, "end_us": 8_000_000, "text": script}],
        video_duration_us=8_000_000,
    )[0]

    assert mapped["phrase_text"] == "比如早上喝碗杂粮粥"
    assert mapped["phrase_char_start"] == script.index("比如")
    assert mapped["phrase_char_end"] == script.index("。")
    keyword_time_us = candidate["char_start"] / len(script) * 8_000_000
    assert mapped["start_us"] < keyword_time_us
    assert mapped["start_us"] + mapped["duration_us"] > keyword_time_us
    assert mapped["timing_source"] == "minimax_raw_cue_phrase_span"


def test_mapping_prefers_funasr_phrase_timestamps_when_available() -> None:
    script = "每天吃一个鸡蛋"
    candidate = recall_semantic_visual_candidates(script, _catalog())["candidates"][0]
    raw_cues = [{"start_us": 0, "end_us": 4_000_000, "text": script}]
    alignment = {
        "status": "SUCCESS",
        "ranges": [
            {
                "token_index": index,
                "start_us": 500_000 + index * 300_000,
                "end_us": 760_000 + index * 300_000,
            }
            for index in range(7)
        ],
    }

    mapped = map_visual_candidates_to_raw_cues(
        script,
        [candidate],
        raw_cues,
        asr_alignment=alignment,
    )[0]

    assert mapped["start_us"] == 500_000
    assert mapped["duration_us"] == 2_060_000
    assert mapped["matched_end_us"] == 2_560_000
    assert mapped["phrase_text"] == script
    assert mapped["timing_source"] == "funasr_phrase_timestamps"


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

    assert [item["concept_id"] for item in recipe["overlays"]] == [
        "food.egg",
        "food.corn",
    ]


def test_distinct_food_images_can_form_a_short_rapid_sequence() -> None:
    catalog = _catalog()
    script = "牛肉鸡蛋豆腐苹果西红柿黄瓜杏仁"
    candidates = recall_semantic_visual_candidates(script, catalog)["candidates"]
    mapped = [
        {
            **candidate,
            "start_us": 1_200_000 + index * 2_000_000,
            "duration_us": 1_500_000,
        }
        for index, candidate in enumerate(candidates)
    ]
    decisions = [
        {
            "candidate_id": candidate["candidate_id"],
            "decision": "SHOW",
            "concept_id": candidate["allowed_concepts"][0]["concept_id"],
            "importance": 0.9,
            "confidence": 0.95,
        }
        for candidate in candidates
    ]

    recipe = build_visual_recipe(
        catalog=catalog,
        mapped_candidates=mapped,
        decisions=decisions,
    )

    assert len(candidates) >= 6
    assert len(recipe["overlays"]) == len(candidates)
    assert all(item["duration_us"] == 1_500_000 for item in recipe["overlays"])
    assert all(
        current["start_us"] - previous["start_us"] == 2_000_000
        for previous, current in zip(recipe["overlays"], recipe["overlays"][1:])
    )


def test_recipe_allows_first_phrase_visual_to_start_at_zero() -> None:
    catalog = _catalog()
    candidate = recall_semantic_visual_candidates("早餐吃鸡蛋", catalog)["candidates"][0]
    recipe = build_visual_recipe(
        catalog=catalog,
        mapped_candidates=[
            {
                **candidate,
                "start_us": 0,
                "duration_us": 2_000_000,
                "matched_end_us": 1_500_000,
            }
        ],
        decisions=[
            {
                "candidate_id": candidate["candidate_id"],
                "decision": "SHOW",
                "concept_id": "food.egg",
                "confidence": 0.95,
            }
        ],
    )

    assert recipe["overlays"][0]["start_us"] == 0
    assert recipe["overlays"][0]["duration_us"] == 2_000_000


def test_recipe_keeps_a_short_first_phrase_without_opening_delay() -> None:
    catalog = _catalog()
    candidate = recall_semantic_visual_candidates("早餐吃鸡蛋", catalog)["candidates"][0]
    recipe = build_visual_recipe(
        catalog=catalog,
        mapped_candidates=[
            {
                **candidate,
                "start_us": 0,
                "duration_us": 1_800_000,
                "matched_end_us": 900_000,
            }
        ],
        decisions=[
            {
                "candidate_id": candidate["candidate_id"],
                "decision": "SHOW",
                "concept_id": "food.egg",
                "confidence": 0.95,
            }
        ],
    )

    assert len(recipe["overlays"]) == 1
    assert recipe["overlays"][0]["start_us"] == 0
    assert recipe["overlays"][0]["duration_us"] == 1_800_000


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
