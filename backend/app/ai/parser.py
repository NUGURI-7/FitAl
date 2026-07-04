"""洗数据:LLM 调用(structured output)+ 确定性后处理。

harness(微循环):schema 不合格由 PydanticAI 带错自动重试;输出校验器强制
"每条记录必须可解"(缺份量/缺时长/表外无档位 → 打回重出);查表未命中 →
带候选名再问一轮(NameRemap);仍不中 → 按 est 降级为 llm_estimated。
所有数值计算在 build_records(纯函数,离线可测),LLM 一个数都不算。
"""

import json
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from zoneinfo import ZoneInfo

from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings

from app.ai import lookup
from app.ai.schema import (
    ConsolidatedMemories,
    MemoryItem,
    NameRemap,
    ParsedExercise,
    ParsedFood,
    ParsedMemory,
    ParsedUserFoodDef,
    ParsedWeight,
    ParseOutput,
)
from app.config import settings

SESSION_GAP_MIN = 20  # 距上一条运动记录超过此间隔视为新一场
DEFAULT_REP_SECONDS = 4  # 表外力量动作按次换算的兜底秒数
TIER_MET = {"moderate": 3.5, "vigorous": 6.0}
OIL_DEFAULT_GRAMS = 10.0


@dataclass(frozen=True)
class Profile:
    """计算消耗所需的身体档案;体重取该用户最新一条体重记录。"""

    weight_kg: float
    height_cm: float
    sex: str
    birth_year: int


@dataclass(frozen=True)
class UserFoodDef:
    """用户自定义食物(user_foods 表的一行,按"份"计)。"""

    name: str
    unit: str
    kcal: float
    protein: float | None = None
    fat: float | None = None
    cho: float | None = None
    fiber: float | None = None


@dataclass
class ResolvedExercise:
    exercise_name: str
    source: str
    kcal: float
    kcal_net: float | None
    met: float | None
    duration_min: float | None
    load_kg: float | None
    reps: int | None
    starts_new_group: bool = False  # AI 的归组判断:新开一场还是延续当前
    group_name: str = ""  # AI 给所在场次起的展示名,空则聚合时走时段兜底


@dataclass
class ResolvedFood:
    food_name: str
    source: str
    kcal: float
    grams: float | None
    protein: float | None
    fat: float | None
    cho: float | None
    fiber: float | None
    starts_new_group: bool = False  # AI 的归组判断:新开一顿还是延续当前
    group_name: str = ""  # AI 给所在餐次起的展示名,空则聚合时走时段兜底


@dataclass
class ResolvedWeight:
    weight_kg: float


# 记忆类条目无任何计算,解析后原样进入落库环节
ResolvedRecord = (
    ResolvedExercise | ResolvedFood | ResolvedWeight | ParsedUserFoodDef | ParsedMemory
)


# ── 确定性后处理:解析结果 → 可入库记录(纯函数) ─────────────────────────


def build_records(
    parsed: ParseOutput,
    *,
    profile: Profile,
    now: datetime,
    last_exercise_at: datetime | None = None,
    user_foods: dict[str, UserFoodDef] | None = None,
) -> list[ResolvedRecord]:
    bmr = lookup.bmr_kcal_per_day(
        profile.weight_kg, profile.height_cm, profile.sex, profile.birth_year, now
    )
    records: list[ResolvedRecord] = []
    for item in parsed.items:
        if isinstance(item, ParsedWeight):
            records.append(ResolvedWeight(weight_kg=item.weight_kg))
        elif isinstance(item, ParsedExercise):
            records.append(_resolve_exercise(item, bmr, now, last_exercise_at))
            last_exercise_at = now  # 同一句里的多组按顺序衔接
        elif isinstance(item, ParsedUserFoodDef | ParsedMemory):
            records.append(item)  # 无计算,原样落库
        else:
            records.append(_resolve_food(item, user_foods or {}))
    return records


def _resolve_exercise(
    p: ParsedExercise, bmr: float, now: datetime, last_exercise_at: datetime | None
) -> ResolvedExercise:
    met_item = lookup.find_exercise(p.name)
    if met_item:
        name, met, source = met_item.name, met_item.met, "met_table"
        rep_seconds = met_item.count_seconds or DEFAULT_REP_SECONDS
    elif p.fallback_tier:  # 表外力量动作归强度档:数值出自表的档位,动作名照存原话
        name, met, source = p.name, TIER_MET[p.fallback_tier], "met_table"
        rep_seconds = DEFAULT_REP_SECONDS
    elif p.est_met:
        name, met, source = p.name, p.est_met, "llm_estimated"
        rep_seconds = DEFAULT_REP_SECONDS
    else:
        name, met, source = p.name, None, "user_reported"
        rep_seconds = DEFAULT_REP_SECONDS

    # 时长:自报 > 组间隔推断(≤20min 取实际间隔,已含动作) > 次数换算(首组/新场)
    if p.duration_min:
        duration = p.duration_min
    elif p.reps:
        action_min = round(p.reps * rep_seconds / 60, 2)
        gap_min = (
            (now - last_exercise_at).total_seconds() / 60 if last_exercise_at else None
        )
        duration = (
            round(gap_min, 2)
            if gap_min is not None and 0 < gap_min <= SESSION_GAP_MIN
            else action_min
        )
    else:
        duration = None

    per_min = bmr / 1440
    if p.reported_kcal is not None:
        kcal, source = p.reported_kcal, "user_reported"
        kcal_net = round(kcal - per_min * duration, 1) if duration else None
    else:
        if met is None or duration is None:
            raise ValueError(f"{p.name}: 无法计算消耗(缺 MET 或时长)")
        kcal = round(met * per_min * duration, 1)
        kcal_net = round((met - 1) * per_min * duration, 1)

    return ResolvedExercise(
        exercise_name=name,
        source=source,
        kcal=kcal,
        kcal_net=kcal_net,
        met=met,
        duration_min=duration,
        load_kg=p.load_kg,
        reps=p.reps,
        starts_new_group=p.starts_new_group,
        group_name=p.group_name,
    )


def _resolve_food(p: ParsedFood, user_foods: dict[str, UserFoodDef]) -> ResolvedFood:
    food_item = lookup.find_food(p.name)
    nutrition = (
        lookup.food_nutrition(food_item, p.grams) if food_item and p.grams else None
    )

    if p.is_cooking_oil:  # 补油显式原则:独立成条,永远标估算,可删可改
        grams = p.grams or OIL_DEFAULT_GRAMS
        kcal = (
            round(food_item.kcal * grams / 100, 1)
            if food_item
            else (p.est_kcal or round(9 * grams, 1))
        )
        return ResolvedFood(
            food_name=p.name,
            source="llm_estimated",
            kcal=kcal,
            grams=grams,
            group_name=p.group_name,
            protein=nutrition["protein"] if nutrition else None,
            fat=nutrition["fat"] if nutrition else None,
            cho=nutrition["cho"] if nutrition else None,
            fiber=nutrition["fiber"] if nutrition else None,
        )

    if p.reported_kcal is not None:  # 优先级1:用户自报
        return _food_record(
            p.name,
            "user_reported",
            p.reported_kcal,
            p.grams,
            nutrition,
            p.starts_new_group,
            p.group_name,
        )

    uf = user_foods.get(p.name)
    if uf:  # 优先级2:自定义食物,按份
        units = p.units or 1
        scale = lambda v: None if v is None else round(v * units, 1)  # noqa: E731
        return ResolvedFood(
            food_name=uf.name,
            source="user_food",
            kcal=round(uf.kcal * units, 1),
            grams=p.grams,
            starts_new_group=p.starts_new_group,
            group_name=p.group_name,
            protein=scale(uf.protein),
            fat=scale(uf.fat),
            cho=scale(uf.cho),
            fiber=scale(uf.fiber),
        )

    if food_item and p.grams:  # 优先级3:静态表
        return _food_record(
            food_item.name,
            "food_table",
            nutrition["kcal"],
            p.grams,
            nutrition,
            p.starts_new_group,
            p.group_name,
        )

    if p.est_kcal is not None:  # 优先级4:估算兜底
        return _food_record(
            p.name,
            "llm_estimated",
            p.est_kcal,
            p.grams,
            None,
            p.starts_new_group,
            p.group_name,
        )

    raise ValueError(f"{p.name}: 查表未命中且无估算值")


def _food_record(
    name, source, kcal, grams, nutrition, starts_new=False, group_name=""
) -> ResolvedFood:
    return ResolvedFood(
        food_name=name,
        source=source,
        kcal=kcal,
        grams=grams,
        starts_new_group=starts_new,
        group_name=group_name,
        protein=nutrition["protein"] if nutrition else None,
        fat=nutrition["fat"] if nutrition else None,
        cho=nutrition["cho"] if nutrition else None,
        fiber=nutrition["fiber"] if nutrition else None,
    )


# ── 输出校验(harness 的硬反馈):不可解的输出打回模型重出 ─────────────────


def output_problems(output: ParseOutput, user_food_names: frozenset[str]) -> list[str]:
    problems = []
    for item in output.items:
        if isinstance(item, ParsedExercise):
            if (
                item.reported_kcal is None
                and item.duration_min is None
                and item.reps is None
            ):
                problems.append(f"{item.name}: 缺时长或次数")
            if (
                lookup.find_exercise(item.name) is None
                and item.fallback_tier is None
                and item.est_met is None
                and item.reported_kcal is None
            ):
                problems.append(
                    f"{item.name}: 不在MET表,需给 fallback_tier(力量)或 est_met(有氧)"
                )
        elif isinstance(item, ParsedFood) and not item.is_cooking_oil:
            if item.reported_kcal is None and item.grams is None and item.units is None:
                problems.append(f"{item.name}: 缺份量(grams 或 units)")
            if (
                item.reported_kcal is None
                and item.name not in user_food_names
                and lookup.find_food(item.name) is None
                and item.est_kcal is None
            ):
                problems.append(f"{item.name}: 可能不在成分表,必须补 est_kcal 兜底")
    return problems


# ── Agent 组装(懒加载,导入不需要 key) ──────────────────────────────────


def _met_table_block() -> str:
    lines = []
    for m in lookup.met_items():
        alias = f"(别名:{'、'.join(m.aliases)})" if m.aliases else ""
        counted = f",按次{m.count_seconds:g}秒" if m.count_seconds else ""
        lines.append(f"{m.name}{alias}{counted}")
    return "\n".join(lines)


def _instructions() -> str:
    return f"""你是健身饮食记录解析器,把用户的一句话拆成零或多条记录(运动/饮食/体重)。
你只输出结构,绝不做任何算术、绝不输出建议。

规则:
1. 一句话可含多条记录;与记录无关的内容忽略,items 可为空。
2. 用户自己报了热量数字 → 原样填 reported_kcal,不要改动。
3. 食物名映射到《中国食物成分表》标准名:用户说熟制主食(米饭/面条)选熟制条目(蒸/煮);同类多条目优先带"(代表值)"的;拿不准时保留用户原话并填 est_kcal 兜底。
4. 份量:克数直接用;个/碗/勺/把等按常识换算成克填 grams。消息里列出的"用户自定义食物"直接用该名称,填 units 份数,不填 grams。
5. 描述含炒/煎/炸且没提到油 → 追加一条 {{name:"菜籽油", grams:10, is_cooking_oil:true}};用户自己报了油则正常解析,不打标。
6. 运动动作名先对下方 MET 表(含别名);表里没有的力量动作(有负重/组次特征)填 fallback_tier:器械或单关节孤立动作=moderate,大重量自由复合=vigorous;表外有氧才填 est_met。
7. 报次数填 reps,报时长填 duration_min;绝不自行换算。
8. 陈述当前体重(如"今天75公斤")→ weight 记录。
9. 复合菜且用户没报食材份量 → 拆解为表内食材,逐条估克重(估克重可以,估热量不行)。
10. "又一组/再来一组/同上"是对同一组动作的补充说明,整句只输出一条记录:
    "硬拉100公斤5个又一组" → 仅一条(name=硬拉, load_kg=100, reps=5)。
11. 归组判断:消息可能附带[当前餐次]/[当前训练场次](当天最近一组的时间与内容)。
    对每条 food/exercise 结合当前时间和内容常识判断:延续它 → starts_new_group=false;
    是新的一顿饭/新一场训练 → starts_new_group=true。没附带当前组信息时此字段无效。
12. 起名:每条 food/exercise 都填 group_name——该记录所归入的一顿/一场的展示名
    (2~8字,按内容与时段起);延续已有组时结合组内已含内容给更贴切的名字。
13. "记住……"类指令:定义自己的食物(名称+每份热量)→ 输出 user_food_def 条目;
    叫法对应("我说X指的是Y")→ memory 条目(kind=alias);习惯/长期事实 → memory
    条目(kind=habit)。这类话本身不产生 food/exercise 记录,除非用户同时说这次吃了/练了。
14. 消息可能附带[用户记忆](该用户积累的叫法与习惯),解析时优先按记忆理解用户的话。

MET 表({len(lookup.met_items())}条):
{_met_table_block()}"""


def _model() -> OpenAIChatModel:
    """任意 OpenAI 兼容端点;key 可空(本地部署无鉴权,占位符满足 SDK 非空要求)。"""
    return OpenAIChatModel(
        settings.LLM_MODEL,
        provider=OpenAIProvider(
            base_url=settings.LLM_BASE_URL,
            api_key=settings.LLM_API_KEY or "EMPTY",
        ),
    )


def _model_settings() -> ModelSettings:
    ms = ModelSettings(temperature=0.0)
    if settings.LLM_EXTRA_BODY:  # 端点私有参数由 .env 控制,换端点不改代码
        ms["extra_body"] = json.loads(settings.LLM_EXTRA_BODY)
    return ms


@lru_cache(maxsize=1)
def parse_agent() -> Agent:
    agent = Agent(
        _model(),
        output_type=ParseOutput,
        deps_type=frozenset,
        instructions=_instructions(),
        retries=2,
        model_settings=_model_settings(),
    )

    @agent.output_validator
    async def _validate(ctx: RunContext[frozenset], output: ParseOutput) -> ParseOutput:
        problems = output_problems(output, ctx.deps or frozenset())
        if problems:
            raise ModelRetry("以下条目不合格,请修正后重新输出:" + ";".join(problems))
        return output

    return agent


@lru_cache(maxsize=1)
def remap_agent() -> Agent:
    return Agent(
        _model(),
        output_type=NameRemap,
        instructions="为每个未命中的食物名从给出的候选中挑最贴切的标准名;没有合适的填 null。只能从候选里选,不得自造。",
        retries=2,
        model_settings=_model_settings(),
    )


@lru_cache(maxsize=1)
def consolidate_agent() -> Agent:
    return Agent(
        _model(),
        output_type=ConsolidatedMemories,
        instructions=(
            "你负责整理一个用户的记忆清单(叫法对应/习惯/纠正)。"
            "合并重复或矛盾的条目(矛盾时保留较新的,清单按时间先后给出),"
            "每条改写为自包含的一句话;仍然有效的必须保留,不得凭空新增。"
        ),
        retries=2,
        model_settings=_model_settings(),
    )


async def consolidate_memories(rows: list[tuple[str, str]]) -> list[MemoryItem]:
    """每日巩固:传入 (kind, content) 全量,返回合并后的新全量。调用方负责整层替换。"""
    listing = "\n".join(f"[{kind}] {content}" for kind, content in rows)
    result = await consolidate_agent().run(f"现有记忆(从旧到新):\n{listing}")
    return result.output.memories


async def parse_text(
    text: str,
    *,
    now: datetime,
    user_food_names: frozenset[str] = frozenset(),
    open_meal: str | None = None,
    open_session: str | None = None,
    memories: str | None = None,
) -> ParseOutput:
    """LLM 洗数据入口:一次解析 + 未命中名字的候选重映射(微循环)。

    open_meal/open_session:当天最近一顿/一场的摘要,AI 据此判断归组(无阈值常量)。
    memories:该用户全部记忆拼成的一段文本(量小,全量注入,不做检索)。
    """
    # 存储用 UTC;给 LLM 看的时间转本地时区,否则"中午/晚上"这类语境会错 8 小时
    local_now = now.astimezone(ZoneInfo(settings.TIMEZONE)) if now.tzinfo else now
    prefix = f"[当前时间 {local_now:%Y-%m-%d %H:%M}]"
    if open_meal:
        prefix += f"[当前餐次:{open_meal}]"
    if open_session:
        prefix += f"[当前训练场次:{open_session}]"
    if user_food_names:
        prefix += f"[用户自定义食物:{'、'.join(sorted(user_food_names))}]"
    if memories:
        prefix += f"[用户记忆:{memories}]"
    result = await parse_agent().run(f"{prefix}\n用户说:{text}", deps=user_food_names)
    output = result.output

    pending: dict[str, list[str]] = {}
    for item in output.items:
        if (
            isinstance(item, ParsedFood)
            and not item.is_cooking_oil
            and item.reported_kcal is None
            and item.name not in user_food_names
            and lookup.find_food(item.name) is None
        ):
            candidates = lookup.candidate_foods(item.name)
            if candidates:
                pending[item.name] = candidates
    if pending:
        question = "\n".join(
            f"{name} 的候选:{'、'.join(cands)}" for name, cands in pending.items()
        )
        mapping = (await remap_agent().run(question)).output.mapping
        for item in output.items:
            if isinstance(item, ParsedFood) and item.name in mapping:
                target = mapping[item.name]
                if target and lookup.find_food(target):
                    item.name = target
    return output
