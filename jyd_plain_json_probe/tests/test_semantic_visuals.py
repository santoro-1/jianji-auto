from __future__ import annotations

from pathlib import Path
import json
import shutil

import pytest

from jyd_probe.semantic_subtitles import SemanticSubtitleMappingError
from jyd_probe.semantic_visuals import (
    build_visual_recipe,
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


def test_catalog_contains_six_concepts_and_two_egg_assets() -> None:
    catalog = _catalog()

    assert len(catalog.concepts) == 6
    assert len([item for item in catalog.assets if item["concept_id"] == "food.egg"]) == 2
    assert all(Path(item["image_path"]).is_file() for item in catalog.assets)


def test_catalog_rejects_path_escape_and_duplicate_asset_id(tmp_path: Path) -> None:
    root = tmp_path / "catalog"
    shutil.copytree(CATALOG_ROOT, root)
    manifest_path = root / "catalog.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["assets"][0]["bundle"] = "../outside"
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

    assert [item["text"] for item in payload["candidates"]] == ["水煮蛋", "玉米", "豆浆"]
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
