from __future__ import annotations

from dataclasses import replace
import hashlib
import json

import pytest

from jyd_probe.semantic_food_matching import food_match_ranks, normalized_food_text
from jyd_probe.semantic_visuals import (
    CATALOG_SCHEMA_V3,
    SemanticVisualCatalog,
    _choose_unused_asset,
    build_visual_recipe,
    frozen_visual_overlays,
)

LABELS = {
    "food.cucumber": "黄瓜",
    "food.chicken_breast": "鸡胸肉",
    "food.egg": "鸡蛋",
    "food.tomato": "西红柿",
    "food.wood_ear": "木耳",
    "food.apple": "苹果",
    "food.carrot": "胡萝卜",
    "food.radish": "白萝卜",
    "food.pumpkin_seed": "南瓜子",
    "food.pumpkin": "南瓜",
    "food.tofu": "豆腐",
    "food.mushroom": "菌菇",
    "body_shape.apple": "苹果型身材",
    "activity.running": "跑步",
}


@pytest.fixture
def make_catalog(tmp_path):
    def make(specs, *, mode="folders"):
        assets = []
        for i, spec in enumerate(specs):
            aid = spec.get("asset_id", f"review.asset.{i}")
            media = spec.get("media_type", "image")
            path = tmp_path / aid
            if media == "image":
                path.mkdir(exist_ok=True)
                (path / "sticker.json").write_text("{}")
                resource = {"bundle": aid, "preview": aid + "/preview.png"}
            else:
                path.write_bytes(b"video")
                resource = {
                    "video": aid,
                    "preview": "preview.png",
                    "duration_us": 12_000_000,
                }
            cid = spec.get("concept_ids", ["food.cucumber"])
            defaults = {
                "corner": "bottom_center",
                "scale": 0.56,
                "opacity": 1,
                "duration_us": 2_000_000,
            }
            if media == "video":
                defaults.update(
                    source_start_us=4_000_000, mute=True, loop=False, fit="contain"
                )
            assets.append(
                {
                    "asset_id": aid,
                    "name": spec["name"],
                    "media_type": media,
                    "concept_ids": cid,
                    "auto_eligible": spec.get("auto_eligible", True),
                    "usage_modes": spec.get(
                        "usage_modes", ["semantic_overlay", "list_quick_cut"]
                    ),
                    "resource_path": str(path),
                    "resource": resource,
                    "defaults": defaults,
                    "renderer": (
                        "jyd_sticker_bundle" if media == "image" else "video_overlay"
                    ),
                    "preview_url": "/preview",
                    "rights_status": "attributed",
                    "content_sha256": spec.get(
                        "hash", hashlib.sha256(aid.encode()).hexdigest()
                    ),
                    "semantic_roles": {
                        "depicts": cid,
                        "expresses": [],
                        "related": spec.get("related", []),
                    },
                }
            )
        concepts = tuple(
            {
                "concept_id": cid,
                "label": label,
                "description": label,
                "aliases": [label],
            }
            for cid, label in LABELS.items()
        )
        return SemanticVisualCatalog(
            tmp_path,
            CATALOG_SCHEMA_V3,
            "food.test",
            "v1",
            concepts,
            tuple(assets),
            source_mode=mode,
        )

    return make


def candidate(phrase="今天吃黄瓜炒鸡胸", keyword="黄瓜", *, occurrence=0, seed="row1"):
    start = -1
    for _ in range(occurrence + 1):
        start = phrase.index(keyword, start + 1)
    return {
        "candidate_id": "test",
        "text": keyword,
        "phrase_text": phrase,
        "char_start": start,
        "char_end": start + len(keyword),
        "phrase_char_start": 0,
        "phrase_char_end": len(phrase),
        "start_us": 0,
        "duration_us": 3_000_000,
        "_selection_seed": seed,
    }


def choose(
    cat, c=None, *, cid="food.cucumber", usage="explicit", used=(), policy="mixed"
):
    c = c or candidate()
    return _choose_unused_asset(
        catalog=cat,
        mapped={"test": c},
        candidate=c,
        concept_id=cid,
        media_policy=policy,
        usage=usage,
        used_asset_ids=set(used),
    )


def dish(name="黄瓜炒鸡胸", **extra):
    return {
        "name": name,
        "concept_ids": ["food.cucumber", "food.chicken_breast"],
        **extra,
    }


@pytest.mark.parametrize(
    "a,b",
    [
        ("青瓜炒鸡胸肉", "黄瓜炒鸡胸"),
        ("番茄炒蛋", "西红柿炒鸡蛋"),
        ("黑木耳拌青瓜", "木耳拌黄瓜"),
        ("蛋炒饭", "鸡蛋炒饭"),
        ("煎蛋", "煎鸡蛋"),
        ("水煮蛋", "水煮鸡蛋"),
    ],
)
def test_equivalent_dish_names(a, b):
    assert normalized_food_text(a) == normalized_food_text(b)


@pytest.mark.parametrize(
    "a,b",
    [
        ("煎蛋", "水煮蛋"),
        ("黄瓜拌鸡胸", "黄瓜炒鸡胸"),
        ("胡萝卜", "白萝卜"),
        ("南瓜子", "南瓜"),
    ],
)
def test_different_dishes_are_not_normalized_together(a, b):
    assert normalized_food_text(a) != normalized_food_text(b)


@pytest.mark.parametrize(
    "name",
    ["黄瓜炒鸡胸", "青瓜炒鸡胸肉", "🔥黄瓜炒鸡胸2", "青瓜炒鸡胸肉__123456789a.png"],
)
def test_exact_dish_beats_other_ingredients_and_cooking(make_catalog, name):
    cat = make_catalog([{"name": "黄瓜"}, dish("黄瓜拌鸡胸"), dish(name)])
    for seed in range(20):
        assert choose(cat, candidate(seed=str(seed)))["name"] == name


def test_exact_video_beats_generic_image_and_retains_reviewed_window(make_catalog):
    cat = make_catalog([{"name": "黄瓜"}, dish(media_type="video")])
    asset = choose(cat)
    assert asset["media_type"] == "video"
    assert asset["defaults"]["source_start_us"] == 4_000_000
    assert asset["defaults"]["duration_us"] == 2_000_000
    assert asset["rights_status"] == "attributed"
    assert choose(cat, policy="image_only")["name"] == "黄瓜"


def test_combination_then_single_subject_then_skip(make_catalog):
    cat = make_catalog([{"name": "黄瓜"}, dish("鸡胸肉拌黄瓜"), dish()])
    exact = choose(cat)
    assert exact["name"] == "黄瓜炒鸡胸"
    combination = choose(cat, used={exact["asset_id"]})
    assert combination["name"] == "鸡胸肉拌黄瓜"
    single = choose(cat, used={exact["asset_id"], combination["asset_id"]})
    assert single["name"] == "黄瓜"
    assert choose(cat, used={a["asset_id"] for a in cat.assets}) is None


def test_unavailable_disabled_or_wrong_usage_exact_dish_is_not_selected(make_catalog):
    cat = make_catalog(
        [
            {"name": "黄瓜"},
            dish(auto_eligible=False),
            dish(usage_modes=["manual_only"]),
            dish(),
        ]
    )
    (cat.root / cat.assets[-1]["asset_id"] / "sticker.json").unlink()
    assert choose(cat)["name"] == "黄瓜"


def test_related_tags_cannot_promote_a_combination(make_catalog):
    cat = make_catalog(
        [{"name": "黄瓜沙拉", "related": ["food.chicken_breast"]}, dish("鸡胸肉拌黄瓜")]
    )
    for seed in range(10):
        assert choose(cat, candidate(seed=str(seed)))["name"] == "鸡胸肉拌黄瓜"


def test_other_dish_in_same_sentence_does_not_supply_ingredients(make_catalog):
    cat = make_catalog(
        [
            dish(),
            {
                "name": "黄瓜鸡胸苹果餐盘",
                "concept_ids": ["food.cucumber", "food.chicken_breast", "food.apple"],
            },
        ]
    )
    for phrase in [
        "黄瓜炒鸡胸和苹果",
        "黄瓜炒鸡胸，苹果留到下午",
        "黄瓜炒鸡胸或者苹果",
        "黄瓜炒鸡胸和番茄炒鸡蛋",
    ]:
        assert choose(cat, candidate(phrase))["name"] == "黄瓜炒鸡胸"


def test_exact_dish_must_cover_current_keyword_occurrence(make_catalog):
    cat = make_catalog(
        [dish(), {"name": "黄瓜炒鸡蛋", "concept_ids": ["food.cucumber", "food.egg"]}]
    )
    phrase = "吃黄瓜炒鸡胸而不是黄瓜炒鸡蛋"
    assert choose(cat, candidate(phrase))["name"] == "黄瓜炒鸡胸"
    # The semantic model still decides whether a negated candidate may SHOW;
    # the ranking must never borrow an earlier occurrence's exact dish name.
    assert choose(cat, candidate(phrase, occurrence=1))["name"] == "黄瓜炒鸡蛋"


def test_secondary_ingredient_anchor_has_same_exact_dish_priority(make_catalog):
    cat = make_catalog([dish("鸡胸肉拌黄瓜"), dish("青瓜炒鸡胸肉")])
    c = candidate(keyword="鸡胸")
    assert choose(cat, c, cid="food.chicken_breast")["name"] == "青瓜炒鸡胸肉"


def test_rapid_list_keeps_each_item_independent(make_catalog):
    cat = make_catalog([{"name": "黄瓜"}, dish("黄瓜鸡胸肉餐盘")])
    assert choose(cat, candidate("黄瓜、鸡胸肉"), usage="rapid_list")["name"] == "黄瓜"


def test_joined_preparation_recognizes_ingredient_combination(make_catalog):
    cat = make_catalog([{"name": "黄瓜"}, dish("鸡胸肉拌黄瓜")])
    assert choose(cat, candidate("黄瓜和鸡胸肉一起炒"))["name"] == "鸡胸肉拌黄瓜"


def test_mushroom_is_required_in_a_combination(make_catalog):
    cat = make_catalog(
        [
            {"name": "西红柿豆腐", "concept_ids": ["food.tomato", "food.tofu"]},
            {
                "name": "菌菇西红柿豆腐煲",
                "concept_ids": ["food.tomato", "food.tofu", "food.mushroom"],
            },
        ]
    )
    c = candidate("西红柿豆腐菌菇汤", "西红柿")
    assert choose(cat, c, cid="food.tomato")["name"] == "菌菇西红柿豆腐煲"


def test_new_folder_filenames_support_dish_and_combination(make_catalog):
    cat = make_catalog(
        [{"name": "黄瓜"}, {"name": "黄瓜鸡胸肉沙拉", "asset_id": "folder.new"}]
    )
    assert choose(cat)["asset_id"] == "folder.new"


def test_same_grade_is_seeded_random_and_stable(make_catalog):
    cat = make_catalog([dish("黄瓜炒鸡胸1"), dish("青瓜炒鸡胸肉2"), {"name": "黄瓜"}])
    selected = [
        choose(cat, candidate(seed=str(seed)))["asset_id"] for seed in range(40)
    ]
    assert set(selected) == {cat.assets[0]["asset_id"], cat.assets[1]["asset_id"]}
    assert selected == [
        choose(cat, candidate(seed=str(seed)))["asset_id"] for seed in range(40)
    ]


def test_same_grade_keeps_default_image_preference(make_catalog):
    cat = make_catalog([dish(media_type="video"), dish()])
    assert choose(cat)["media_type"] == "image"


def test_identical_content_in_other_folder_cannot_repeat(make_catalog):
    cat = make_catalog(
        [dish(hash="same-bytes"), dish(hash="same-bytes"), {"name": "黄瓜"}]
    )
    assert choose(cat, used={cat.assets[0]["asset_id"]})["name"] == "黄瓜"


def test_saved_selection_wins_over_new_exact_dish(make_catalog):
    cat = make_catalog([{"name": "黄瓜"}, dish()])
    c = candidate()
    c["_preferred_assets"] = {"food.cucumber": cat.assets[0]["asset_id"]}
    assert choose(cat, c)["name"] == "黄瓜"


def test_saved_recipe_remains_identical_and_renderable(make_catalog):
    cat = make_catalog([{"name": "黄瓜"}, dish()])
    c = candidate()
    args = {
        "mapped_candidates": [c],
        "decisions": [
            {
                "candidate_id": "test",
                "decision": "SHOW",
                "confidence": 1,
                "concept_id": "food.cucumber",
                "importance": 1,
            }
        ],
        "media_policy": "mixed",
    }
    first = build_visual_recipe(catalog=replace(cat, assets=(cat.assets[0],)), **args)
    frozen = frozen_visual_overlays({"visual_analysis": {"recipe": first}}, catalog=cat)
    updated = build_visual_recipe(catalog=cat, previous_recipe=first, **args)
    assert updated["overlays"] == first["overlays"]
    assert (
        frozen_visual_overlays({"visual_analysis": {"recipe": updated}}, catalog=cat)
        == frozen
    )


def test_non_food_and_broll_pools_are_unchanged(make_catalog):
    cat = make_catalog([{"name": "苹果型身材", "concept_ids": ["body_shape.apple"]}])
    assert (
        food_match_ranks(
            cat.assets,
            cat.concepts,
            candidate("苹果型身材", "苹果"),
            "body_shape.apple",
            usage="explicit",
        )
        == {}
    )
    for usage in ["enrichment", "seam_broll"]:
        assert (
            food_match_ranks(
                cat.assets, cat.concepts, candidate(), "food.cucumber", usage=usage
            )
            == {}
        )


def test_legacy_json_selection_does_not_use_new_ranker(make_catalog, monkeypatch):
    import jyd_probe.semantic_food_matching as matching

    monkeypatch.setattr(
        matching,
        "food_match_ranks",
        lambda *a, **kw: pytest.fail("legacy selection changed"),
    )
    cat = make_catalog([{"name": "黄瓜"}, dish()], mode="json")
    assert choose(cat)["name"] == "黄瓜"


def test_ranker_does_not_mutate_catalog_or_candidate(make_catalog):
    cat = make_catalog([{"name": "黄瓜"}, dish()])
    c = candidate()
    original = json.dumps([cat.assets, cat.concepts, c], ensure_ascii=False)
    choose(cat, c)
    assert json.dumps([cat.assets, cat.concepts, c], ensure_ascii=False) == original


@pytest.mark.parametrize("decision", ["SKIP", "REVIEW"])
def test_exact_dish_does_not_override_semantic_decision(make_catalog, decision):
    cat = make_catalog([dish()])
    recipe = build_visual_recipe(
        catalog=cat,
        mapped_candidates=[candidate()],
        decisions=[
            {
                "candidate_id": "test",
                "decision": decision,
                "confidence": 1,
                "concept_id": "food.cucumber",
            }
        ],
        media_policy="mixed",
    )
    assert recipe["overlays"] == []


def test_exact_video_recipe_keeps_source_start_and_ends_without_looping(make_catalog):
    cat = make_catalog([{"name": "黄瓜"}, dish(media_type="video")])
    recipe = build_visual_recipe(
        catalog=cat,
        mapped_candidates=[candidate()],
        decisions=[
            {
                "candidate_id": "test",
                "decision": "SHOW",
                "confidence": 1,
                "concept_id": "food.cucumber",
            }
        ],
        media_policy="mixed",
    )
    overlay = recipe["overlays"][0]
    assert overlay["media_type"] == "video"
    assert overlay["source_start_us"] == 4_000_000
    assert overlay["duration_us"] == 2_000_000
    assert overlay["mute"] is True
    assert overlay["loop_to_target"] is False
