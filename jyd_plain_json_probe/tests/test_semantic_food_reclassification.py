from __future__ import annotations

import copy
import json
import sqlite3
from pathlib import Path

from PIL import Image
import pytest

from jyd_probe.semantic_food_categories import classification_plan, entities
import jyd_probe.semantic_food_reclassification as regroup
import jyd_probe.semantic_visual_folders as folders
from jyd_probe.semantic_visuals import (
    CATALOG_SCHEMA_V3,
    SemanticVisualCatalogError,
    build_visual_recipe,
    frozen_visual_overlays,
    recall_semantic_visual_candidates,
)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("吃鸡蛋", ["鸡蛋"]),
        ("50克白米饭", ["米饭"]),
        ("切芹菜", ["芹菜"]),
        ("黄瓜炒鸡胸", ["黄瓜", "鸡胸肉"]),
        ("黄瓜拌木耳", ["黄瓜", "木耳"]),
        ("黄瓜鸡蛋三明治", ["黄瓜", "鸡蛋", "三明治"]),
        ("胡萝卜苹果汁", ["胡萝卜", "苹果"]),
        ("裙带菜豆腐汤", ["裙带菜", "豆腐", "汤"]),
        ("水煮鸡蛋", ["鸡蛋"]),
        ("水煮菜", ["蔬菜"]),
        ("倒牛奶", ["牛奶"]),
        ("茶水", ["茶"]),
        ("蛋炒饭", ["鸡蛋", "米饭"]),
        ("菠萝蜜", ["菠萝蜜"]),
        ("南瓜子", ["南瓜子"]),
        ("樱桃萝卜", ["樱桃萝卜"]),
        ("鸡蛋豆腐", ["鸡蛋豆腐"]),
        ("蚂蚁上树", ["蚂蚁上树"]),
        ("鱼香茄子", ["茄子"]),
        ("馒头", ["馒头"]),
    ],
)
def test_core_entities(text, expected):
    assert entities(text) == expected


def concept(cid, label):
    return {"concept_id": cid, "label": label, "description": label, "aliases": [label]}


@pytest.fixture
def library(tmp_path):
    original = tmp_path / "original"
    original.mkdir()
    assets = []
    concepts = [
        concept("action.eat_egg", "吃鸡蛋"),
        concept("portion.rice_50g", "50克白米饭"),
        concept("review.dish", "黄瓜炒鸡胸"),
        concept("food.cucumber", "黄瓜"),
    ]
    for i, (cid, name, color) in enumerate(
        [
            ("action.eat_egg", "吃鸡蛋", "yellow"),
            ("portion.rice_50g", "50克白米饭", "white"),
            ("review.dish", "黄瓜炒鸡胸", "green"),
        ]
    ):
        source = original / f"image{i}.png"
        Image.new("RGB", (40, 30), color).save(source)
        asset = folders._new_asset(original, source, folders._digest(source), cid)
        asset.update(
            asset_id=f"test.{i}",
            name=name,
            description=name,
            rights_status="attributed",
        )
        assets.append(asset)
    # There are already two physical copies, which must merge without loss.
    assets[2]["concept_ids"].append("food.cucumber")
    assets[2]["auto_trigger_concept_ids"] = list(assets[2]["concept_ids"])
    assets[2]["semantic_roles"]["depicts"] = list(assets[2]["concept_ids"])
    assets[2]["trigger_basis"]["food.cucumber"] = "co_dominant_subject"
    video = copy.deepcopy(assets[2])
    (original / "video.mp4").write_bytes(b"reviewed-video-data")
    video.update(
        asset_id="test.video",
        media_type="video",
        renderer="video_overlay",
        auto_eligible=False,
        resource={
            "video": "video.mp4",
            "preview": assets[2]["resource"]["preview"],
            "duration_us": 12_000_000,
            "width": 120,
            "height": 90,
            "has_audio": True,
        },
        defaults={
            "corner": "center",
            "scale": 1,
            "opacity": 1,
            "duration_us": 2_000_000,
            "source_start_us": 4_000_000,
            "mute": True,
            "loop": False,
            "fit": "cover",
        },
        usage_modes=["semantic_overlay"],
    )
    # Force additional copies for the video while the image reuses both originals.
    video["concept_ids"] = video["auto_trigger_concept_ids"] = ["review.dish"]
    video["trigger_basis"] = {"review.dish": "exact_subject"}
    assets.append(video)
    payload = {
        "schema": CATALOG_SCHEMA_V3,
        "library_id": "regroup.test",
        "concepts": concepts,
        "assets": assets,
    }
    (original / "catalog.json").write_text(json.dumps(payload), encoding="utf-8")
    target = tmp_path / "library"
    folders.migrate_catalog(original, target)
    return original, target


def rows(root):
    with folders._connect(root) as connection:
        return regroup._read_index(connection)


def test_plan_is_read_only_and_protects_non_food_and_bad_legacy_names():
    cs = {
        cid: concept(cid, label)
        for cid, label in [
            ("body_shape.apple", "苹果型身材"),
            ("food.cherry_radish", "比黄瓜"),
            ("food.winter_melon", "冬瓜"),
            ("food.steamed_bun", "包子"),
            ("food.rice_noodle", "米粉与凉皮"),
            ("food.fried_dough", "油条油饼"),
        ]
    }
    assets = {}
    for i, (cid, name) in enumerate(
        [
            ("body_shape.apple", "苹果型身材"),
            ("food.cherry_radish", "比黄瓜3"),
            ("food.winter_melon", "比黄瓜1"),
            ("food.steamed_bun", "白馒头"),
            ("food.rice_noodle", "凉皮"),
            ("food.fried_dough", "油条"),
        ]
    ):
        assets[str(i)] = {
            "concept_ids": [cid],
            "name": name,
            "semantic_roles": {"depicts": [cid], "expresses": [], "related": []},
            "trigger_basis": {cid: "exact_subject"},
        }
    before = copy.deepcopy((cs, assets))
    plan = classification_plan(cs, assets, {})
    assert (cs, assets) == before
    labels = [
        [
            plan["concepts"][cid]["label"]
            for cid in plan["assets"][str(i)]["concept_ids"]
        ]
        for i in range(6)
    ]
    assert labels == [
        ["苹果型身材"],
        ["樱桃萝卜"],
        ["冬瓜"],
        ["馒头"],
        ["凉皮"],
        ["油条"],
    ]


def test_apply_preserves_media_metadata_and_deduplicates_folders(library):
    original, root = library
    before = rows(root)
    original_hash = folders._digest(original / "catalog.json")
    index_hash = folders._digest(root / folders.INDEX_NAME)
    preview = regroup.reclassify(root)
    assert preview["changed_assets"] == 4
    assert folders._digest(root / folders.INDEX_NAME) == index_hash
    result = regroup.reclassify(root, apply=True)
    assert result["source_files_after"] == 6
    assert result["extra_copy_bytes"] == len(b"reviewed-video-data")
    assert result["eligible_assets"] == 3
    after = rows(root)
    for aid, old in before["assets"].items():
        new = after["assets"][aid]
        for key in set(old) - {
            "concept_ids",
            "auto_trigger_concept_ids",
            "semantic_roles",
            "trigger_basis",
            "video_taxonomy",
        }:
            assert new[key] == old[key], (aid, key)
    assert before["digests"] == after["digests"]
    assert (root / "素材/食物/鸡蛋/图片").is_dir()
    assert (root / "素材/食物/米饭/图片").is_dir()
    assert (root / "素材/食物/黄瓜/视频").is_dir()
    assert (root / "素材/食物/鸡胸肉/视频").is_dir()
    assert not (root / "素材/份量").exists()
    assert not (root / "素材/待分类/黄瓜炒鸡胸").exists()
    assert folders._digest(original / "catalog.json") == original_hash
    catalog = folders.scan_folders(root)
    for text in ["吃鸡蛋", "白米饭", "黄瓜", "鸡胸肉"]:
        assert recall_semantic_visual_candidates(text, catalog)["candidates"]
    assert regroup.reclassify(root, apply=True) == {"already_applied": True}


def test_frozen_recipe_stays_usable_after_concept_is_merged(library):
    _, root = library
    old = folders.scan_folders(root)
    cid = "action.eat_egg"
    recipe = build_visual_recipe(
        catalog=old,
        mapped_candidates=[
            {
                "candidate_id": "v1",
                "start_us": 0,
                "duration_us": 2_000_000,
                "char_start": 0,
                "char_end": 3,
                "text": "吃鸡蛋",
                "allowed_concepts": [{"concept_id": cid}],
            }
        ],
        decisions=[
            {
                "candidate_id": "v1",
                "decision": "SHOW",
                "confidence": 1,
                "importance": 1,
                "concept_id": cid,
            }
        ],
    )
    frozen = frozen_visual_overlays(recipe, catalog=old)
    regroup.reclassify(root, apply=True)
    assert frozen_visual_overlays(recipe, catalog=folders.scan_folders(root)) == frozen


def test_validation_failure_restores_originals(library, monkeypatch):
    _, root = library
    before = rows(root)
    paths = {p: folders._digest(root / p) for p in before["sources"]}
    monkeypatch.setattr(
        regroup,
        "_load_snapshot",
        lambda *args: (_ for _ in ()).throw(ValueError("reject metadata")),
    )
    with pytest.raises(ValueError, match="reject metadata"):
        regroup.reclassify(root, apply=True)
    assert rows(root) == before
    assert {p: folders._digest(root / p) for p in before["sources"]} == paths
    assert len(folders.scan_folders(root).assets) == 4


@pytest.mark.parametrize("crash_at", [3, 7])
def test_crashed_migration_blocks_scan_and_can_recover(library, monkeypatch, crash_at):
    _, root = library
    before = rows(root)
    original_move = regroup._move
    calls = 0

    def crash(root, source, target):
        nonlocal calls
        calls += 1
        if calls == crash_at:
            raise SystemExit("power loss")
        original_move(root, source, target)

    monkeypatch.setattr(regroup, "_move", crash)
    with pytest.raises(SystemExit):
        regroup.reclassify(root, apply=True)
    with pytest.raises(SemanticVisualCatalogError, match="归类尚未完成"):
        folders.scan_folders(root)
    monkeypatch.setattr(regroup, "_move", original_move)
    backup = next((root / regroup.BACKUPS).iterdir())
    assert regroup.rollback(root, backup)["restored"]
    assert rows(root) == before


def test_completed_migration_can_be_rolled_back(library):
    _, root = library
    before = rows(root)
    result = regroup.reclassify(root, apply=True)
    assert regroup.rollback(root, result["backup"])["restored"]
    assert rows(root) == before
    assert len(folders.scan_folders(root).assets) == 4
    assert regroup.rollback(root, result["backup"]) == {"already_restored": True}


def test_reclassification_never_moves_top_level_directory(library, monkeypatch):
    _, root = library
    original_move = regroup._move

    def files_only(root, source, target):
        assert folders._safe(root, source).is_file()
        return original_move(root, source, target)

    monkeypatch.setattr(regroup, "_move", files_only)
    result = regroup.reclassify(root, apply=True)
    assert regroup.rollback(root, result["backup"])["restored"]


def test_rollback_refuses_to_overwrite_edited_sources(library):
    _, root = library
    result = regroup.reclassify(root, apply=True)
    source = next((root / "素材/食物/鸡蛋/图片").iterdir())
    source.write_bytes(b"user's replacement")
    with pytest.raises(SemanticVisualCatalogError, match="原素材发生变化"):
        regroup.rollback(root, result["backup"])
    assert source.read_bytes() == b"user's replacement"


def test_unregistered_file_prevents_migration(library):
    _, root = library
    source = root / "素材/note.txt"
    source.write_text("user note")
    with pytest.raises(SemanticVisualCatalogError, match="尚未登记"):
        regroup.reclassify(root, apply=True)
    assert source.read_text() == "user note"
    assert not (root / regroup.BACKUPS).exists()
