"""静态表查询与热量计算:进程启动加载内存 dict,精确匹配+别名匹配。

模糊的口语对齐(鸡胸肉→鸡胸脯肉)是 LLM 的职责,不在这里做字符串相似度。
所有数值计算(食物按克重、运动修正 MET)collected 在此,LLM 绝不做算术。
"""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def _norm(s: str) -> str:
    """查表键归一化:去空白,全角括号/逗号转半角——两侧(建表与查询)同用。"""
    return (
        s.strip()
        .replace(" ", "")
        .replace("（", "(")
        .replace("）", ")")
        .replace("，", ",")
    )


@dataclass(frozen=True)
class FoodItem:
    name: str
    category: str
    kcal: float  # 每100g
    protein: float | None
    fat: float | None
    cho: float | None
    fiber: float | None


@dataclass(frozen=True)
class MetItem:
    name: str
    met: float
    count_seconds: float | None  # 按次数报告的运动:每次折算秒数
    note: str


def _load_food() -> tuple[dict[str, FoodItem], dict[str, str]]:
    raw = json.loads((_DATA_DIR / "food.json").read_text(encoding="utf-8"))
    by_name: dict[str, FoodItem] = {}
    alias_owners: dict[str, set[str]] = {}
    for item in raw["items"]:
        food = FoodItem(
            name=item["name"],
            category=item["category"],
            kcal=item["kcal"],
            protein=item["protein"],
            fat=item["fat"],
            cho=item["cho"],
            fiber=item["fiber"],
        )
        by_name.setdefault(_norm(food.name), food)
        for alias in item["aliases"]:
            alias_owners.setdefault(_norm(alias), set()).add(_norm(food.name))
    # 歧义别名(指向多个不同条目,如"西红柿"→番茄/奶柿子)不进精确映射,
    # 留给 LLM 映射阶段用常识裁决——确定性归代码,歧义归 AI
    alias_to_name = {
        alias: next(iter(names))
        for alias, names in alias_owners.items()
        if len(names) == 1 and alias not in by_name
    }
    return by_name, alias_to_name


def _load_met() -> tuple[dict[str, MetItem], dict[str, str]]:
    raw = json.loads((_DATA_DIR / "met.json").read_text(encoding="utf-8"))
    by_name: dict[str, MetItem] = {}
    alias_to_name: dict[str, str] = {}
    for item in raw["items"]:
        met = MetItem(
            name=item["name"],
            met=item["met"],
            count_seconds=item["count_seconds"],
            note=item["note"],
        )
        by_name.setdefault(_norm(met.name), met)
        for alias in item["aliases"]:
            alias_to_name.setdefault(_norm(alias), _norm(met.name))
    return by_name, alias_to_name


_FOOD_BY_NAME, _FOOD_ALIAS = _load_food()
_MET_BY_NAME, _MET_ALIAS = _load_met()


def find_food(name: str) -> FoodItem | None:
    key = _norm(name)
    return _FOOD_BY_NAME.get(key) or _FOOD_BY_NAME.get(_FOOD_ALIAS.get(key, ""))


def find_exercise(name: str) -> MetItem | None:
    key = _norm(name)
    return _MET_BY_NAME.get(key) or _MET_BY_NAME.get(_MET_ALIAS.get(key, ""))


def food_nutrition(item: FoodItem, grams: float) -> dict[str, float | None]:
    """按克重折算营养(表值为每100g可食部)。"""
    factor = grams / 100
    scale = lambda v: None if v is None else round(v * factor, 1)  # noqa: E731
    return {
        "kcal": round(item.kcal * factor, 1),
        "protein": scale(item.protein),
        "fat": scale(item.fat),
        "cho": scale(item.cho),
        "fiber": scale(item.fiber),
    }


def bmr_kcal_per_day(
    weight_kg: float, height_cm: float, sex: str, birth_year: int, now: datetime
) -> float:
    """Mifflin-St Jeor 基础代谢(kcal/天)。sex: male | female。"""
    age = now.year - birth_year
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age
    if sex == "male":
        return base + 5
    if sex == "female":
        return base - 161
    raise ValueError(f"未知性别: {sex}")


def exercise_kcal(met: float, bmr: float, duration_min: float) -> float:
    """修正 MET 消耗:MET 是基础代谢的倍数,用个体 BMR 替代标准参考人。

    kcal = MET × (BMR/1440 每分钟基础消耗) × 分钟
    """
    return round(met * (bmr / 1440) * duration_min, 1)


def count_to_duration_min(item: MetItem, reps: int) -> float | None:
    """按次数报告的运动 → 动作时长(分钟);无换算规则的运动返回 None。"""
    if item.count_seconds is None:
        return None
    return round(reps * item.count_seconds / 60, 2)
