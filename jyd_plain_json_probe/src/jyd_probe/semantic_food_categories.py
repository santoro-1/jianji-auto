"""Food-entity grouping, not recipe inference or nutrition inference."""

from __future__ import annotations

import hashlib
import re
import copy

# Longest noun wins: 南瓜子 is not 南瓜, 胡萝卜 is not 白萝卜, and
# 菠萝蜜 is not 菠萝. Only named subjects are split out of mixed dishes.
_FOODS = """
苹果 香蕉 牛油果 芦笋 娃娃菜 牛肉 牛肉丸 甜菜根 苦瓜 小白菜 西兰花
胡萝卜 胡萝卜叶 鸡胸肉 鸡肉 鸡爪 鸡腿 鸡翅 鸡肠 辣椒 茼蒿 猪肝 玉米
黄瓜 巧克力 甜甜圈 火龙果 百合 榴莲 毛豆 鸡蛋 金针菇 鱼 鱼丸 龙利鱼
巴沙鱼 鲈鱼 巴旦木 海参 三文鱼 亚麻籽油 水果 大蒜 生姜 枸杞 芡实 葡萄
青萝卜 火腿 汉堡 哈密瓜 山楂 蜂蜜 冬枣 南瓜 海带 猕猴桃 瘦肉 柠檬 青柠
生菜 龙眼 丝瓜 莲藕 螺蛳粉 荔枝 橘子 芒果 山竹 肉类 包子 小米 杂粮饭
坚果 桑葚 绿豆 菌菇 面条 燕麦 橄榄油 洋葱 橙子 木瓜 豌豆苗 桃子 梨 豌豆
柿子 披萨 柚子 猪肉 猪肥肉 五花肉 土豆 蛋白棒 紫薯 藜麦 白萝卜 油菜 红枣
米饭 糍粑 米粉 凉皮 冰糖 根茎类主食 香肠 大葱 小葱 紫菜 麻团 香油 香菇 虾
虾仁 虾皮 虾滑 烧麦 黄豆 豆类 菠菜 白糖 红薯 芋头 豆腐 豆腐皮 豆腐脑 西红柿
蔬菜 食醋 白醋 核桃 西瓜 蓝莓 粗粮杂粮 全麦面包 冬瓜 木耳 山药 粽子 豆芽
蛋糕 水果罐头 巧乐兹 饺子 饼 油条 油饼 小不丁 酸辣粉 泡面 煎饼果子 烤冷面
馄饨 臭豆腐 面包 欧包 甜玉米 食盐 秋葵 糙米 腐竹 茄子 红糖 红芸豆 莲子 红豆
羊肉 腊肉 芝士 芥菜 花椒 花生 芹菜 玫瑰 陈皮 黄芪 茯苓 草莓 荞麦面 荠菜
荷兰豆 莴笋 菠萝 菠萝蜜 菱角 蒜苔 薯条 藕粉 蚕豆 西葫芦 车厘子 辣条 米线
排骨 里脊 鹅肉 银耳 韭菜 韭黄 饭团 饼干 香菜 马蹄 马齿苋 魔芋 鸭掌 鸭肉
鹅掌 麻花 麻薯球 芝麻酱 南瓜子 黑芝麻 黑豆 樱桃 甘蔗 莓果 果干 鹰嘴豆 黑米
奶油 火腿肠 黄油 猪油 羊油 吐司 板栗 腰果 鸭脖 鸭血 牛角包 薏米 荷叶 菊花
乌龙茶 珍珠 粉丝 年糕 河粉 空心菜 油麦菜 南瓜藤 平菇 口蘑 樱桃萝卜 蛋黄
动物内脏 锅巴 砂糖橘 西柚 煎饺 手抓饼 寿司 灌饼 汤 粥 火锅 麻辣香锅
四神汤 五黑粥 地三鲜 夫妻肺片 鸡蛋豆腐 蚂蚁上树 裙带菜 馒头 肉串 海鲜 酱油 三明治 猪蹄 豆角 花菜
""".split()
_DRINKS = "牛奶 酸奶 豆浆 咖啡 黑咖啡 美式咖啡 意式咖啡 奶咖 茶 红茶 绿茶 养生茶 奶茶 椰奶 橙汁 水 果汁 乳酸菌饮料 含糖饮料".split()
_MEALS = "早餐 午餐 晚餐 下午茶 减脂餐 清淡餐食 餐食拼盘 餐桌 备餐".split()
ALIASES = {
    "西红柿": "番茄",
    "黄瓜": "青瓜",
    "西兰花": "西蓝花",
    "芹菜": "西芹",
    "鸡胸肉": "鸡胸,鸡i胸肉",
    "鸡蛋": "水煮蛋,荷包蛋,煎蛋,炸蛋,溏心蛋,滑蛋,蛋花,蛋羹,蒸蛋,蛋汤",
    "木耳": "黑木耳",
    "大蒜": "蒜蓉,蒜瓣",
    "生姜": "姜片,姜丝,姜汁,姜饮,姜茶",
    "小葱": "香葱,葱花",
    "大葱": "青葱",
    "莲藕": "藕片,藕丁",
    "白萝卜": "萝卜",
    "樱桃萝卜": "樱桃小萝卜,樱桃萝卜",
    "彩椒": "甜椒,红黄彩椒,灯笼椒,青椒",
    "包菜": "甘蓝,卷心菜,圆白菜",
    "白菜": "大白菜",
    "芋头": "芋艿",
    "山药": "淮山药",
    "蓝莓": "蓝梅",
    "龙眼": "桂圆",
    "猕猴桃": "奇异果",
    "砂糖橘": "沙糖桔,沙糖橘",
    "西柚": "葡萄柚",
    "食盐": "盐",
    "白糖": "白砂糖,方糖",
    "食醋": "醋",
    "米饭": "白米饭,大米饭,炒饭",
    "杂粮饭": "杂粮米饭",
    "小米": "小米粥",
    "粥": "白粥,稀饭,大米粥",
    "豆腐皮": "豆皮,千张",
    "菌菇": "蘑菇",
    "口蘑": "口菇",
    "豆芽": "绿豆芽,黄豆芽",
    "面条": "炒面,炸酱面,热干面,肉酱面",
    "豌豆": "青豆",
    "羊肉": "手撕全羊",
    "花菜": "菜花",
    "饺子": "水饺",
    "馄饨": "混沌,云吞",
    "烧麦": "烧卖",
    "泡面": "方便面,火鸡面,速食面",
    "螺蛳粉": "螺狮粉",
    "肉类": "肉类菜品,各种各样的肉,炒肉,拌肉,酿肉,肉丝",
    "猪肥肉": "肥猪肉",
    "猪肉": "红烧肉",
    "鸭肉": "烤鸭",
    "鹅肉": "炖鹅",
    "饼": "饼类主食",
    "包子": "大包子",
    "蛋糕": "蛋糕甜点",
    "果干": "蜜饯果干",
    "水": "饮用水,白水,开水,温水,冰水,饮水",
    "黑咖啡": "手冲黑咖啡,冰黑咖啡",
    "美式咖啡": "美式,冰美式",
    "奶咖": "奶咖制作",
    "茶": "茶叶,冰泡茶,茶水",
    "鸡肉": "鸡丝,走地鸡,炸鸡",
    "蔬菜": "水煮菜,水煮蔬菜,水煮杂蔬",
    "豆类": "混合豆浆豆",
    "红茶": "祁门红茶,冰红茶",
    "奶茶": "珍珠奶茶",
    "果汁": "榨汁",
    "早餐": "早餐餐盘,一人食早餐,混合早餐盘,减脂早餐餐盘",
    "午餐": "减脂午餐餐盘",
    "减脂餐": "均衡减脂餐盘",
    "餐桌": "丰盛餐桌,川菜餐桌",
    "餐食拼盘": "家常两人餐,南京家常菜,混合餐盘",
    "备餐": "备餐餐盒",
    "营养餐": "水煮营养餐",
    "外出用餐": "外出用餐",
}
_MEALS += ["营养餐", "外出用餐"]
FOOD_GROUPS = {word: "食物" for word in [*_FOODS, *ALIASES]}
FOOD_GROUPS.update({word: "饮品" for word in _DRINKS})
FOOD_GROUPS.update({word: "餐食" for word in _MEALS})
FOOD_GROUPS["乌龙茶"] = "饮品"

# Do not derive hidden ingredients from a figurative dish/product name.
SPECIAL_NAMES = {
    "鱼香肉丝": ["肉类"],
    "茶叶蛋": ["鸡蛋"],
    "鱼香茄子": ["茄子"],
    "虎皮青椒": ["彩椒"],
    "蛋炒饭": ["鸡蛋", "米饭"],
}
CONCEPT_LABELS = {
    "food.cherry_radish": "樱桃萝卜",
    "food.mung_bean": "绿豆",
    "action.juice_orange": "橙汁",
    "drink.orange_juice": "橙汁",
    "food.yam_pumpkin": "山药",
    "food.watermelon_blueberry": "水果",
    # Inspected legacy image shows both normal tofu and scrambled egg.
    "review.exact.u1641": "鸡蛋和豆腐",
}
PREFERRED_IDS = {
    "鸡蛋": "food.egg",
    "黄瓜": "food.cucumber",
    "西红柿": "food.tomato",
    "鸡胸肉": "food.chicken_breast",
    "米饭": "food.rice",
    "牛肉": "food.beef",
    "木耳": "food.wood_ear",
    "玉米": "food.corn",
    "枸杞": "food.goji",
    "燕麦": "food.oat",
    "绿豆": "food.mung_bean",
    "豆腐": "food.tofu",
    "生姜": "food.ginger",
    "牛奶": "drink.milk",
    "水": "drink.water",
    "芹菜": "food.celery",
    "樱桃萝卜": "food.cherry_radish",
}
_OTHER_GROUPS = {
    "weather": "天气",
    "season": "生活场景",
    "object": "生活用品",
    "topic": "健康",
    "body_shape": "体型",
}
_FOOD_PREFIXES = {"food", "dish", "drink", "meal", "portion", "action", "review"}
_NONFOOD_LABELS = {"居家客厅": "生活场景"}


def entities(text: str) -> list[str]:
    text = re.sub(r"[\s\d.]+(?:克|千克|公斤|g|kg)?", "", text)
    for name, values in SPECIAL_NAMES.items():
        if name in text:
            text = text.replace(name, "、".join(values))
    matches = []
    for canonical in FOOD_GROUPS:
        for alias in [canonical, *ALIASES.get(canonical, "").split(",")]:
            if not alias:
                continue
            start = text.find(alias)
            while start >= 0:
                matches.append((start, start + len(alias), canonical))
                start = text.find(alias, start + 1)
    selected = []
    for match in sorted(matches, key=lambda x: (-(x[1] - x[0]), x[0], x[2])):
        if not any(match[0] < other[1] and other[0] < match[1] for other in selected):
            selected.append(match)
    names = list(dict.fromkeys(x[2] for x in sorted(selected)))
    # Water is a cooking method/juice suffix here, not a visible ingredient.
    if len(names) > 1 and "水" in names:
        names.remove("水")
    return names


def _core_concept(cid: str, label: str) -> dict:
    return {
        "concept_id": cid,
        "label": label,
        "description": f"画面明确展示{label}本身，或在混合食物中清楚可见的{label}；动作和分量不另设概念，不代表营养或功效。",
        "aliases": list(
            dict.fromkeys([label, *filter(None, ALIASES.get(label, "").split(","))])
        ),
    }


def classification_plan(
    concepts: dict[str, dict], assets: dict[str, dict], folders: dict[str, str]
) -> dict:
    """Return revised metadata and folder targets without touching files."""
    canonical_ids = {}
    original_groups = {cid: path.split("/")[1] for path, cid in folders.items()}
    for label in FOOD_GROUPS:
        candidates = sorted(
            cid
            for cid, c in concepts.items()
            if c["label"] == label and cid.split(".")[0] in _FOOD_PREFIXES
        )
        preferred = PREFERRED_IDS.get(label)
        canonical_ids[label] = (
            preferred
            if preferred in concepts
            else (
                candidates[0]
                if candidates
                else "food.entity." + hashlib.sha256(label.encode()).hexdigest()[:16]
            )
        )
    replacements, revised_concepts, target_folders = {}, copy.deepcopy(concepts), {}
    for cid, concept in concepts.items():
        label = CONCEPT_LABELS.get(cid, concept["label"])
        prefix = cid.split(".")[0]
        if prefix in _FOOD_PREFIXES and label not in _NONFOOD_LABELS:
            names = entities(label)
            # Food modifiers don't turn a meal into a separate entity when real
            # ingredients were named; generic breakfast remains breakfast.
            ingredients = [
                n
                for n in names
                if FOOD_GROUPS[n] != "餐食" and n not in {"汤", "粥", "水果", "蔬菜"}
            ]
            if ingredients:
                names = ingredients
            if not names and prefix in {"food", "dish", "drink", "meal"}:
                names = [
                    re.sub(r"^(?:生吃|吃|喝|倒|切|煮|蒸|清炒|水煮|炒|腌|泡)", "", label)
                ]
            if names:
                ids = []
                for name in names:
                    target_id = canonical_ids.setdefault(
                        name,
                        (
                            cid
                            if len(names) == 1
                            else "food.entity."
                            + hashlib.sha256(name.encode()).hexdigest()[:16]
                        ),
                    )
                    ids.append(target_id)
                    revised_concepts[target_id] = _core_concept(target_id, name)
                    group = FOOD_GROUPS.get(
                        name, "饮品" if prefix == "drink" else "食物"
                    )
                    target_folders[target_id] = f"素材/{group}/{name}"
                replacements[cid] = ids
                continue
        replacements[cid] = [cid]
        group = _NONFOOD_LABELS.get(
            label, _OTHER_GROUPS.get(prefix, original_groups.get(cid, "待分类"))
        )
        target_folders[cid] = f"素材/{group}/{label}"

    # Merge aliases only if they denote this one entity. A compound dish alias
    # must not hide the second ingredient from longest-match keyword recall.
    for old_id, ids in replacements.items():
        if len(ids) != 1 or old_id in CONCEPT_LABELS:
            continue
        new_id = ids[0]
        label = revised_concepts[new_id]["label"]
        aliases = revised_concepts[new_id]["aliases"]
        for alias in concepts[old_id]["aliases"]:
            if entities(alias) == [label] and alias not in aliases:
                aliases.append(alias)

    revised_assets, changed = {}, []
    for aid, raw in assets.items():
        asset = copy.deepcopy(raw)

        def remap(ids):
            return list(
                dict.fromkeys(
                    new for old in ids for new in replacements.get(old, [old])
                )
            )

        ids = remap(raw["concept_ids"])
        named = entities(asset["name"])
        # These legacy buckets grouped mutually exclusive foods. The audited
        # asset name, not the old umbrella label, identifies what is present.
        for old_id, options in {
            "food.rice_noodle": {"米粉", "凉皮"},
            "food.fried_dough": {"油条", "油饼"},
            "food.steamed_bun": {"馒头", "包子"},
        }.items():
            if old_id in raw["concept_ids"] and options.intersection(named):
                ids = [cid for cid in ids if cid not in replacements[old_id]]
        # Use the audited per-asset name for extra subjects only for food assets.
        # A bad legacy concept label cannot override its more precise subject ID.
        if (
            any(cid.split(".")[0] in _FOOD_PREFIXES for cid in raw["concept_ids"])
            and "food.cherry_radish" not in raw["concept_ids"]
            and not asset["name"].startswith("比")
        ):
            for name in named:
                if name in {"汤", "粥", "水果", "蔬菜"} or FOOD_GROUPS[name] == "餐食":
                    continue
                if name == "鸡蛋豆腐" and "review.exact.u1641" in raw["concept_ids"]:
                    continue
                new_id = canonical_ids[name]
                if new_id not in ids:
                    ids.append(new_id)
                    revised_concepts.setdefault(new_id, _core_concept(new_id, name))
                    target_folders.setdefault(
                        new_id, f"素材/{FOOD_GROUPS[name]}/{name}"
                    )
        roles = {role: remap(values) for role, values in raw["semantic_roles"].items()}
        roles["depicts"] = list(
            dict.fromkeys(
                [*roles["depicts"], *[x for x in ids if x not in roles["expresses"]]]
            )
        )
        roles["expresses"] = [
            x for x in roles["expresses"] if x not in roles["depicts"]
        ]
        roles["related"] = [
            x
            for x in roles["related"]
            if x not in roles["depicts"] and x not in roles["expresses"]
        ]
        asset["concept_ids"] = asset["auto_trigger_concept_ids"] = ids
        asset["semantic_roles"] = roles
        asset["trigger_basis"] = {
            cid: raw["trigger_basis"].get(
                cid, "co_dominant_subject" if len(ids) > 1 else "exact_subject"
            )
            for cid in ids
        }
        if "video_taxonomy" in asset:
            asset["video_taxonomy"]["l3_exact_concept_ids"] = ids
        revised_assets[aid] = asset
        if ids != raw["concept_ids"]:
            changed.append(
                {
                    "asset_id": aid,
                    "name": raw["name"],
                    "before": [concepts[x]["label"] for x in raw["concept_ids"]],
                    "after": [revised_concepts[x]["label"] for x in ids],
                }
            )
    # Distinct non-food concepts may deliberately share a display label.
    seen = set()
    for cid, path in sorted(target_folders.items()):
        if path.casefold() in seen:
            path += "_" + hashlib.sha256(cid.encode()).hexdigest()[:6]
            target_folders[cid] = path
        seen.add(path.casefold())
    return {
        "concepts": revised_concepts,
        "assets": revised_assets,
        "folders": target_folders,
        "changes": changed,
        "replacements": replacements,
    }
