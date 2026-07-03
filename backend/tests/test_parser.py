from datetime import datetime, timedelta

import pytest

from app.ai import lookup, parser
from app.ai.schema import ParsedExercise, ParsedFood, ParsedWeight, ParseOutput

PROFILE = parser.Profile(weight_kg=70, height_cm=178, sex="male", birth_year=1997)
NOW = datetime(2026, 7, 2, 19, 30)
# BMR=1672.5,每分钟基础消耗 ≈1.16146


def _build(items, **kwargs):
    return parser.build_records(
        ParseOutput(items=items), profile=PROFILE, now=NOW, **kwargs
    )


def test_优先级1_用户自报热量直接采用并算出净耗():
    [r] = _build([ParsedExercise(name="跑步", duration_min=30, reported_kcal=300)])
    assert r.source == "user_reported"
    assert r.kcal == 300
    assert r.kcal_net == pytest.approx(265.2, abs=0.1)  # 300 - 基础代谢份额


def test_优先级2_自定义食物按份计算():
    uf = {"老三样": parser.UserFoodDef(name="老三样", unit="份", kcal=520, protein=45)}
    [r] = _build([ParsedFood(name="老三样", units=2)], user_foods=uf)
    assert r.source == "user_food"
    assert r.kcal == 1040
    assert r.protein == 90


def test_优先级3_静态表按克重计算():
    [r] = _build([ParsedFood(name="鸡胸脯肉", grams=200)])
    assert r.source == "food_table"
    assert r.kcal == pytest.approx(236.0)
    assert r.protein == pytest.approx(49.2)


def test_优先级4_表外食物用估算兜底():
    [r] = _build([ParsedFood(name="楼下的猪脚饭", grams=400, est_kcal=850)])
    assert r.source == "llm_estimated"
    assert r.kcal == 850


def test_补油条目_油量查表计值但强制标估算():
    oil_item = lookup.find_food("菜籽油")
    [r] = _build([ParsedFood(name="菜籽油", is_cooking_oil=True)])
    assert r.source == "llm_estimated"
    assert r.grams == 10
    assert r.kcal == pytest.approx(round(oil_item.kcal * 0.1, 1))


def test_力量首组_按动作时间计():
    [r] = _build([ParsedExercise(name="卧推", reps=10, load_kg=60)])
    assert r.source == "met_table"
    assert r.met == 6.0
    assert r.duration_min == pytest.approx(0.67)  # 10次×4秒
    assert r.kcal == pytest.approx(4.7, abs=0.1)
    assert r.kcal_net == pytest.approx(3.9, abs=0.1)


def test_组间隔20分钟内_时长取实际间隔():
    [r] = _build(
        [ParsedExercise(name="卧推", reps=10, load_kg=60)],
        last_exercise_at=NOW - timedelta(minutes=6),
    )
    assert r.duration_min == pytest.approx(6.0)
    assert r.kcal == pytest.approx(41.8, abs=0.1)
    assert r.kcal_net == pytest.approx(34.8, abs=0.1)


def test_组间隔超20分钟_视为新场只算动作时间():
    [r] = _build(
        [ParsedExercise(name="卧推", reps=10)],
        last_exercise_at=NOW - timedelta(minutes=30),
    )
    assert r.duration_min == pytest.approx(0.67)


def test_表外力量动作_归强度档且动作名照存():
    [r] = _build(
        [ParsedExercise(name="龙门架斜下拉", reps=12, fallback_tier="vigorous")]
    )
    assert r.exercise_name == "龙门架斜下拉"
    assert r.met == 6.0
    assert r.source == "met_table"


def test_体重记录透传():
    [r] = _build([ParsedWeight(weight_kg=75)])
    assert r.weight_kg == 75


def test_校验器_不可解的输出被列为问题():
    problems = parser.output_problems(
        ParseOutput(
            items=[
                ParsedExercise(name="卧推"),  # 缺时长/次数
                ParsedExercise(name="划龙舟", reps=10),  # 表外且无档位
                ParsedFood(name="鸡胸脯肉"),  # 缺份量
                ParsedFood(name="外星料理", grams=100),  # 表外且无估算
            ]
        ),
        frozenset(),
    )
    assert len(problems) == 4


def test_校验器_合格输出零问题():
    problems = parser.output_problems(
        ParseOutput(
            items=[
                ParsedExercise(name="卧推", reps=10),
                ParsedFood(name="鸡胸脯肉", grams=200),
                ParsedFood(name="自家蛋白粉", units=1),
            ]
        ),
        frozenset({"自家蛋白粉"}),
    )
    assert problems == []


def test_候选搜索_口语名能召回标准名():
    assert "鸡胸脯肉" in lookup.candidate_foods("鸡胸肉")
