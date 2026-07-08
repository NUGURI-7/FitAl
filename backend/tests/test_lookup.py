from datetime import datetime

import pytest

from app.ai import lookup


def test_精确查食物_鸡胸脯肉命中且数值来自成分表():
    item = lookup.find_food("鸡胸脯肉")
    assert item is not None
    assert item.kcal == 118.0
    assert item.protein == 24.6


def test_歧义别名不精确匹配_西红柿交给LLM裁决():
    # "西红柿"在表里同时是番茄和奶柿子的别名 → 精确映射不猜,返回 None
    assert lookup.find_food("西红柿") is None


def test_无歧义别名可精确匹配():
    # 从数据中任取一个只有唯一归属的别名验证别名通道本身工作
    assert lookup._FOOD_ALIAS, "别名表不应为空"
    alias, name = next(iter(lookup._FOOD_ALIAS.items()))
    assert lookup.find_food(alias).name == name


def test_查不到的食物返回None_交给LLM估算兜底():
    assert lookup.find_food("楼下的猪脚饭") is None


def test_食物按克重折算_米饭200克热量翻倍():
    item = lookup.find_food("米饭(蒸)(代表值)") or lookup.find_food("稻米(代表值)")
    n = lookup.food_nutrition(item, 200)
    assert n["kcal"] == pytest.approx(item.kcal * 2)


def test_基础代谢_MifflinStJeor男性已知值():
    # 10×70 + 6.25×178 − 5×29 + 5 = 1672.5
    bmr = lookup.bmr_kcal_per_day(70, 178, "male", 1997, now=datetime(2026, 7, 2))
    assert bmr == pytest.approx(1672.5)


def test_基础代谢_女性常数不同():
    bmr = lookup.bmr_kcal_per_day(55, 165, "female", 2000, now=datetime(2026, 7, 2))
    # 10×55 + 6.25×165 − 5×26 − 161 = 1290.25
    assert bmr == pytest.approx(1290.25)


def test_运动消耗_修正MET按个体基础代谢计():
    # MET8.3 × (1672.5/1440) × 30min ≈ 289.2
    kcal = lookup.exercise_kcal(met=8.3, bmr=1672.5, duration_min=30)
    assert kcal == pytest.approx(289.2, abs=0.1)


def test_按次数换算时长_俯卧撑20次约1分钟():
    item = lookup.find_exercise("俯卧撑")
    assert lookup.count_to_duration_min(item, 20) == pytest.approx(1.0)


def test_别名查运动_撸铁映射到力量训练():
    assert lookup.find_exercise("撸铁").name == "力量训练(中等)"


def test_无换算规则的运动按次数返回None():
    assert lookup.count_to_duration_min(lookup.find_exercise("跑步"), 10) is None


# ── 形态歧义簇(2026-07-08 缩水版:人工圈定高频簇,簇内标形态) ──────────


def test_歧义簇_每个成员都能在官方表命中():
    for cluster in lookup._FORM_CLUSTERS.values():
        for m in cluster:
            assert lookup.find_food(m.name) is not None, f"簇成员不在官方表: {m.name}"


def test_歧义簇_同簇形态互不重复且在封闭词表内():
    allowed = {"生", "熟", "干", "水发", "即食"}
    seen_clusters = {id(c): c for c in lookup._FORM_CLUSTERS.values()}
    for cluster in seen_clusters.values():
        forms = [m.form for m in cluster]
        assert len(forms) == len(set(forms)), f"同簇形态重复: {forms}"
        assert set(forms) <= allowed, f"形态超出封闭词表: {forms}"


def test_歧义簇_同簇成员热量差异至少两倍_否则不配当陷阱():
    seen_clusters = {id(c): c for c in lookup._FORM_CLUSTERS.values()}
    for cluster in seen_clusters.values():
        kcals = [lookup.find_food(m.name).kcal for m in cluster]
        assert max(kcals) >= 2 * min(kcals), (
            f"热量差不足两倍: {[m.name for m in cluster]}"
        )


def test_歧义簇_簇成员查得到全簇_非簇食物返回空():
    cluster = lookup.form_cluster("米饭(蒸，代表值)")
    assert cluster is not None
    assert {m.name for m in cluster} == {"稻米(代表值)", "米饭(蒸，代表值)"}
    assert lookup.form_cluster("鸡胸脯肉") is None


def test_歧义簇_成员自身形态标签可查():
    assert lookup.cluster_member_form("稻米(代表值)") == "生"
    assert lookup.cluster_member_form("木耳(水发)") == "水发"
    assert lookup.cluster_member_form("鸡胸脯肉") is None
