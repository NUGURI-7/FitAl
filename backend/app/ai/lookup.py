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


def norm_key(s: str) -> str:
    """对外的键归一化:自定义食物"原话叫法"精确命中用,与官方表同一套规则。"""
    return _norm(s)


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
class ClusterMember:
    """形态歧义簇成员:官方表条目名 + 形态(生/熟/干/水发/即食)。"""

    name: str
    form: str


@dataclass(frozen=True)
class MetItem:
    name: str
    met: float
    count_seconds: float | None  # 按次数报告的运动:每次折算秒数
    note: str
    aliases: tuple[str, ...] = ()


def _load_food() -> tuple[
    dict[str, FoodItem], dict[str, str], dict[str, tuple[str, ...]]
]:
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
    # 但保留在歧义表里供候选召回——精确归代码,裁决归 AI
    alias_to_name = {
        alias: next(iter(names))
        for alias, names in alias_owners.items()
        if len(names) == 1 and alias not in by_name
    }
    ambiguous = {
        alias: tuple(sorted(names))
        for alias, names in alias_owners.items()
        if len(names) > 1
    }
    return by_name, alias_to_name, ambiguous


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
            aliases=tuple(item["aliases"]),
        )
        by_name.setdefault(_norm(met.name), met)
        for alias in item["aliases"]:
            alias_to_name.setdefault(_norm(alias), _norm(met.name))
    return by_name, alias_to_name


def _load_clusters() -> dict[str, tuple[ClusterMember, ...]]:
    """高频形态歧义簇(人工圈定小清单):簇成员名 → 全簇。"""
    raw = json.loads((_DATA_DIR / "form_clusters.json").read_text(encoding="utf-8"))
    by_member: dict[str, tuple[ClusterMember, ...]] = {}
    for cluster in raw["clusters"]:
        members = tuple(
            ClusterMember(name=m["name"], form=m["form"]) for m in cluster["members"]
        )
        for m in members:
            by_member[_norm(m.name)] = members
    return by_member


_FOOD_BY_NAME, _FOOD_ALIAS, _FOOD_AMBIGUOUS = _load_food()
_MET_BY_NAME, _MET_ALIAS = _load_met()
_FORM_CLUSTERS = _load_clusters()


def find_food(name: str) -> FoodItem | None:
    key = _norm(name)
    hit = _FOOD_BY_NAME.get(key) or _FOOD_BY_NAME.get(_FOOD_ALIAS.get(key, ""))
    if hit:
        return hit
    # 模型爱给名字乱加"(代表值)"后缀(表里未必有该条目,错例④补充线索):
    # 精确未命中时剥掉该后缀再试一次——确定性归一化,免去一轮估算打回
    stripped = key.removesuffix("(代表值)")
    if stripped != key:
        return _FOOD_BY_NAME.get(stripped) or _FOOD_BY_NAME.get(
            _FOOD_ALIAS.get(stripped, "")
        )
    return None


def find_exercise(name: str) -> MetItem | None:
    key = _norm(name)
    return _MET_BY_NAME.get(key) or _MET_BY_NAME.get(_MET_ALIAS.get(key, ""))


def form_cluster(name: str) -> tuple[ClusterMember, ...] | None:
    """名字落在歧义簇内则返回全簇(形态裁决的封闭候选);否则返回 None。"""
    key = _norm(name)
    return _FORM_CLUSTERS.get(key) or _FORM_CLUSTERS.get(_FOOD_ALIAS.get(key, ""))


def cluster_member_form(name: str) -> str | None:
    """簇内条目自身的形态标签;非簇条目返回 None。"""
    key = _norm(name)
    if key not in _FORM_CLUSTERS:  # 别名先落到标准名,再进簇查
        key = _FOOD_ALIAS.get(key, "")
    cluster = _FORM_CLUSTERS.get(key)
    if cluster is None:
        return None
    for m in cluster:
        if _norm(m.name) == key:
            return m.form
    return None


def met_items() -> list[MetItem]:
    """全部运动条目(注入解析 prompt 用)。"""
    return list(_MET_BY_NAME.values())


def candidate_foods(query: str, limit: int = 8) -> list[str]:
    """微循环第二轮的候选:按字符重合度粗召回,精挑交 LLM。

    纯子串匹配抓不住"鸡胸肉→鸡胸脯肉"这类插字变体,故用字符集重合度;
    子串命中额外加权置顶。
    """
    # 用括号前主名召回:模型常给"辣椒(代表值)"这类名字,而表里该类并无代表值条目,
    # 若带"代表值"等后缀算字符重合度会被同后缀的别的食物("桃(代表值)"…)淹没,
    # 反而召回不到辣椒本身。剥到主名再召回,长尾食物才能进候选裁决。
    q_full = _norm(query)
    q = q_full.split("(")[0] or q_full
    if not q:
        return []
    q_chars = set(q)
    scored: list[tuple[int, int, str]] = []

    def consider(text: str, target_name: str) -> None:
        overlap = len(q_chars & set(text))
        if q in text or text in q:
            overlap += len(q)
        if overlap >= 2 and overlap * 2 >= len(q_chars):
            scored.append((-overlap, len(text), target_name))

    for name in _FOOD_BY_NAME:
        consider(name, name)
    for alias, name in _FOOD_ALIAS.items():
        consider(alias, name)
    for alias, names in _FOOD_AMBIGUOUS.items():
        for name in names:
            consider(alias, name)

    out: list[str] = []
    for _, _, name in sorted(scored):
        if name not in out:
            out.append(name)
    return out[:limit]


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
