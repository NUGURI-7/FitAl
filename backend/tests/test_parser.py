from datetime import datetime, timedelta

import pytest

from app.ai import lookup, parser
from app.ai.schema import (
    ParsedDish,
    ParsedExercise,
    ParsedFood,
    ParsedIngredient,
    ParsedWeight,
    ParseOutput,
)

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


def test_优先级2_自定义食物按每100克乘以克数计算():
    uf = {"老三样": parser.UserFoodDef(name="老三样", kcal=520, protein=45)}
    [r] = _build(
        [ParsedFood(spoken_name="老三样", name="老三样", grams=50)], user_foods=uf
    )
    assert r.source == "user_food"
    assert r.kcal == 260
    assert r.protein == 22.5


def test_优先级3_静态表按克重计算():
    [r] = _build([ParsedFood(spoken_name="鸡胸肉", name="鸡胸脯肉", grams=200)])
    assert r.source == "food_table"
    assert r.kcal == pytest.approx(236.0)
    assert r.protein == pytest.approx(49.2)


def test_明说餐次与场次归组判断穿透到解析结果():
    [f, e] = _build(
        [
            ParsedFood(
                spoken_name="鸡胸肉", name="鸡胸脯肉", grams=200, meal_slot="早餐"
            ),
            ParsedExercise(
                name="卧推", reps=10, starts_new_group=True, group_name="晚间胸部训练"
            ),
        ]
    )
    assert f.meal_slot == "早餐"  # 用户明说的餐次原样穿透,归组由聚合层执行
    assert e.starts_new_group is True
    assert e.group_name == "晚间胸部训练"


def test_优先级4_表外食物用估算兜底():
    [r] = _build(
        [
            ParsedFood(
                spoken_name="楼下的猪脚饭", name="楼下的猪脚饭", grams=400, est_kcal=850
            )
        ]
    )
    assert r.source == "llm_estimated"
    assert r.kcal == 850


def test_补油条目_油量查表计值但强制标估算():
    oil_item = lookup.find_food("菜籽油")
    [r] = _build([ParsedFood(spoken_name="菜籽油", name="菜籽油", is_condiment=True)])
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
                ParsedFood(spoken_name="鸡胸肉", name="鸡胸脯肉"),  # 缺份量
                ParsedFood(
                    spoken_name="外星料理", name="外星料理", grams=100
                ),  # 表外且无估算
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
                ParsedFood(spoken_name="鸡胸肉", name="鸡胸脯肉", grams=200),
                ParsedFood(spoken_name="自家蛋白粉", name="自家蛋白粉", grams=30),
            ]
        ),
        frozenset({"自家蛋白粉"}),
    )
    assert problems == []


def test_候选搜索_口语名能召回标准名():
    assert "鸡胸脯肉" in lookup.candidate_foods("鸡胸肉")


# ── 菜层 + 克重守恒 + 形态(2026-07-08 工程包第三步) ──────────────────────


def _dish(total=120.0, bread=90.0, cream=30.0):
    return ParsedDish(
        dish_name="毛毛虫面包",
        total_grams=total,
        ingredients=[
            ParsedIngredient(
                spoken_name="面包", name="面包", grams=bread, est_kcal=280
            ),
            ParsedIngredient(spoken_name="奶油", name="奶油", grams=cream),
        ],
        est_total_kcal=420,
        meal_slot="早餐",
    )


def test_菜拆解_成分逐条计算并带同名菜标签_餐次随菜():
    [bread, cream] = _build([_dish()])
    assert bread.dish == cream.dish == "毛毛虫面包"
    assert bread.meal_slot == cream.meal_slot == "早餐"
    assert bread.source == "llm_estimated"  # 面包不在表,走成分自身的估算兜底
    assert bread.kcal == 280
    assert cream.source == "food_table"  # 奶油在表,查表计算
    assert cream.kcal == pytest.approx(879 * 0.3, abs=0.1)


def test_菜拆解_单品记录不带菜标签():
    [r] = _build([ParsedFood(spoken_name="鸡胸肉", name="鸡胸脯肉", grams=200)])
    assert r.dish is None


def test_克重守恒_成分和超容差被判违规且违规话术带差额():
    v = parser.dish_violation(_dish(total=120, bread=120, cream=30))  # 和150,差+30
    assert v is not None
    assert "+30" in v and "毛毛虫面包" in v


def test_克重守恒_容差百分之五以内放行():
    assert parser.dish_violation(_dish(total=120, bread=88, cream=27)) is None  # 差-5<6
    assert parser.dish_violation(_dish()) is None  # 严格相等


def test_克重守恒_成分清单为空或总克重非正也判违规():
    empty = ParsedDish(
        dish_name="谜之菜", total_grams=100, ingredients=[], est_total_kcal=200
    )
    assert parser.dish_violation(empty) is not None


def test_克重守恒_重试不过整菜降级为估算一条并标估算来源():
    degraded = parser.degrade_dish(_dish(total=120, bread=120, cream=30))
    [r] = _build([degraded])
    assert r.source == "llm_estimated"
    assert r.kcal == 420  # 整菜兜底估算值
    assert r.grams == 120  # 总克重保留
    assert r.food_name == "毛毛虫面包"
    assert r.meal_slot == "早餐"  # 明说餐次不因降级丢失


def test_形态_明说形态时代码在歧义簇内换成对应条目():
    [r] = _build(
        [ParsedFood(spoken_name="生米", name="米饭(蒸，代表值)", grams=100, form="生")]
    )
    assert r.food_name == "稻米(代表值)"  # 生熟差3倍,代码裁决零AI
    assert r.kcal == pytest.approx(346.0)


def test_形态_非簇食物明说形态不影响正常查表():
    [r] = _build(
        [ParsedFood(spoken_name="鸡胸肉", name="鸡胸脯肉", grams=100, form="熟")]
    )
    assert r.food_name == "鸡胸脯肉"
    assert r.source == "food_table"


def test_自定义食物_原话叫法命中优先于标准表映射():
    uf = {"老三样": parser.UserFoodDef(name="老三样", kcal=520)}
    [r] = _build(
        [ParsedFood(spoken_name="老三样", name="鸡胸脯肉", grams=100)], user_foods=uf
    )
    assert r.source == "user_food"  # 就算标准名映射命中官方表,原话命中自定义表优先
    assert r.kcal == 520


def test_校验器_菜成分表外无估算被列为问题():
    dish = ParsedDish(
        dish_name="谜之菜",
        total_grams=100,
        ingredients=[ParsedIngredient(spoken_name="外星酱", name="外星酱", grams=100)],
        est_total_kcal=200,
    )
    problems = parser.output_problems(ParseOutput(items=[dish]), frozenset())
    assert len(problems) == 1 and "外星酱" in problems[0]


def test_校验器_表外调味缺估算被列为问题():
    sugar = ParsedFood(spoken_name="糖", name="白砂糖", grams=15, is_condiment=True)
    problems = parser.output_problems(ParseOutput(items=[sugar]), frozenset())
    assert len(problems) == 1 and "est_kcal" in problems[0]


def test_克重守恒_普通单品与合规菜零违规():
    output = ParseOutput(
        items=[ParsedFood(spoken_name="鸡胸肉", name="鸡胸脯肉", grams=200), _dish()]
    )
    assert parser.conservation_violations(output) == []


def test_候选搜索_代表值后缀不淹没主名召回():
    # 模型给"辣椒(代表值)"但表里无此条,应剥主名"辣椒"召回辣椒品种,
    # 不被别的"XX(代表值)"淹没(修复:辣椒曾因此走 llm_estimated)
    cands = lookup.candidate_foods("辣椒(代表值)")
    assert any(c.startswith("辣椒(") for c in cands)
    assert not any("代表值" in c for c in cands)
