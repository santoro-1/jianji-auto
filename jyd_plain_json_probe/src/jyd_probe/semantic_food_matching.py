"""Rank already-approved local food assets: dish, ingredients, then subject.

This is a text/metadata ranking pass, not image recognition. It cannot add a
candidate concept, approve a disabled asset, or widen its media/usage policy.
"""

from __future__ import annotations

from functools import lru_cache
import re
import unicodedata
from typing import Any, Iterable, Mapping

from .semantic_food_categories import FOOD_GROUPS, entities

# Unlike the classification aliases, these preserve cooking methods. Replacing
# 煎蛋 with 鸡蛋 here would incorrectly equate fried eggs and boiled eggs.
_NOUN_ALIASES = {
    "青瓜": "黄瓜",
    "番茄": "西红柿",
    "鸡胸": "鸡胸肉",
    "鸡i胸肉": "鸡胸肉",
    "西蓝花": "西兰花",
    "黑木耳": "木耳",
    "西芹": "芹菜",
    "蒜蓉": "大蒜",
    "卷心菜": "包菜",
    "圆白菜": "包菜",
    "大白菜": "白菜",
    "芋艿": "芋头",
    "淮山药": "山药",
    "蓝梅": "蓝莓",
    "桂圆": "龙眼",
    "奇异果": "猕猴桃",
    "沙糖桔": "砂糖橘",
    "沙糖橘": "砂糖橘",
    "葡萄柚": "西柚",
    "豆皮": "豆腐皮",
    "千张": "豆腐皮",
    "口菇": "口蘑",
    "蘑菇": "菌菇",
    "白米饭": "米饭",
    "大米饭": "米饭",
    "云吞": "馄饨",
    "混沌": "馄饨",
    "烧卖": "烧麦",
    "螺狮粉": "螺蛳粉",
    "白砂糖": "白糖",
    "菜花": "花菜",
}
_NOUN_PATTERN = re.compile(
    "|".join(
        re.escape(s)
        for s in sorted(
            set(FOOD_GROUPS) | set(_NOUN_ALIASES), key=lambda s: (-len(s), s)
        )
    )
)
_GENERIC = {"食物", "水果", "蔬菜", "汤", "粥", "水"}
_CLAUSE_BREAK = re.compile(
    r"[，,。；;！？!?：:\n\r、]|或者|而不是|而非|而是|但是|不如|相比|换成|改成|以及|另外|然后|搭配|配上|但|比"
)
_COOKING = re.compile(r"炒|拌|炖|煮|蒸|烧|焖|烩|煎|炸|烤")


@lru_cache(maxsize=8192)
def normalized_food_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    text = "".join(
        ch for ch in text if not ch.isspace() and unicodedata.category(ch)[0] != "S"
    )
    text = _NOUN_PATTERN.sub(lambda m: _NOUN_ALIASES.get(m.group(), m.group()), text)
    text = re.sub(r"(炒|煎|蒸|煮|拌|炖|炸)蛋(?![糕白黄挞])", r"\1鸡蛋", text)
    text = re.sub(r"(?<!鸡)蛋炒饭", "鸡蛋炒米饭", text)
    text = text.replace("鸡蛋炒饭", "鸡蛋炒米饭")
    return text


@lru_cache(maxsize=8192)
def _asset_name(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    text = re.sub(r"\.(?:png|jpe?g|webp|bmp|mp4|mov|mkv|webm|m4v)$", "", text)
    text = re.sub(r"__[a-f0-9]{8,64}$", "", text)
    text = re.sub(r"[\s_\-]*(?:\(\d+\)|\d+)$", "", text)
    return normalized_food_text(text)


@lru_cache(maxsize=8192)
def _subjects(text: str) -> frozenset[str]:
    names = {name for name in entities(text) if FOOD_GROUPS[name] != "餐食"}
    specific = names - _GENERIC
    return frozenset(specific or names)


def _query_context(candidate: Mapping[str, Any], usage: str) -> tuple[str, int, int]:
    keyword = str(candidate.get("text") or "")
    if usage == "rapid_list":
        text = normalized_food_text(keyword)
        return text, 0, len(text)
    phrase = str(candidate.get("phrase_text") or keyword)
    start = int(candidate.get("char_start", 0)) - int(
        candidate.get("phrase_char_start", 0)
    )
    end = start + len(keyword)
    if start < 0 or phrase[start:end] != keyword:
        start = phrase.find(keyword) if keyword else -1
        if start < 0:
            return "", 0, 0
        end = start + len(keyword)
    cuts = list(_CLAUSE_BREAK.finditer(phrase))
    # "黄瓜和鸡胸肉一起炒" is a combination, but two separately named
    # cooked dishes joined by 和/与 must not borrow each other's ingredients.
    for match in re.finditer(r"和|与|及", phrase):
        joined_preparation = (
            not _COOKING.search(phrase[: match.start()])
            and re.search(r"一起|一同|混合|做成", phrase[match.end() :])
            and _COOKING.search(phrase[match.end() :])
        )
        if not joined_preparation or "分别" in phrase or "单独" in phrase:
            cuts.append(match)
    left = max((m.end() for m in cuts if m.end() <= start), default=0)
    right = min((m.start() for m in cuts if m.start() >= end), default=len(phrase))
    text = normalized_food_text(phrase[left:right])
    local_start = len(normalized_food_text(phrase[left:start]))
    local_end = len(normalized_food_text(phrase[left:end]))
    return text, local_start, local_end


def food_match_ranks(
    assets: Iterable[Mapping[str, Any]],
    concepts: Iterable[Mapping[str, Any]],
    candidate: Mapping[str, Any],
    concept_id: str,
    *,
    usage: str,
) -> dict[str, tuple[int, int]]:
    """Return sort keys; lower is better. No media or filesystem mutation."""
    if usage not in {"explicit", "rapid_list"}:
        return {}
    labels = {str(c["concept_id"]): str(c.get("label") or "") for c in concepts}
    selected_label = labels.get(concept_id, "")
    # Leave non-food scheduling and generic abstract concepts as they were.
    if selected_label not in FOOD_GROUPS or FOOD_GROUPS[selected_label] == "餐食":
        return {}
    text, anchor_start, anchor_end = _query_context(candidate, usage)
    query_subjects = _subjects(text)
    selected_subjects = _subjects(selected_label)
    if not text or not selected_subjects.intersection(query_subjects):
        return {}
    ranks = {}
    for asset in assets:
        aid = str(asset["asset_id"])
        rank = (2, 0)
        name = _asset_name(str(asset.get("name") or ""))
        name_subjects = _subjects(name)
        # Only approved automatic memberships, not related tags, establish the
        # combination. New folder files also have their user-supplied dish name.
        approved_subjects = set()
        for cid in asset.get("concept_ids", ()):
            label = labels.get(str(cid), "")
            if label in FOOD_GROUPS and FOOD_GROUPS[label] != "餐食":
                approved_subjects.update(_subjects(label))
        if aid.startswith("folder.") and not name.startswith("比"):
            approved_subjects.update(name_subjects)
        if len(query_subjects) > 1 and query_subjects.issubset(approved_subjects):
            rank = (1, 0)
        if len(name) >= 2 and query_subjects.issubset(name_subjects):
            cursor = 0
            while True:
                found = text.find(name, cursor)
                if found < 0:
                    break
                if found < anchor_end and found + len(name) > anchor_start:
                    # More complete dish names outrank a bare ingredient name
                    # inside them. Equivalent normalized names remain random.
                    rank = (0, -len(name))
                    break
                cursor = found + 1
        ranks[aid] = rank
    return ranks
