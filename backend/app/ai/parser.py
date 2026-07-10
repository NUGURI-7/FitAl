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
    ParsedDish,
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
GRAMS_TOLERANCE = 0.05  # 克重守恒容差:成分和与总克重偏差 ≤5%
MAX_PARSE_RETRIES = 2  # 校验打回的重试上限;守恒重试用尽 → 整菜降级估算


@dataclass(frozen=True)
class Profile:
    """计算消耗所需的身体档案;体重取该用户最新一条体重记录。"""

    weight_kg: float
    height_cm: float
    sex: str
    birth_year: int


@dataclass(frozen=True)
class UserFoodDef:
    """用户自定义食物(user_foods 表的一行,每100克口径,与官方表同构)。"""

    name: str
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
    meal_slot: str | None = None  # 用户明说的餐次;空则聚合时按时钟落槽
    dish: str | None = None  # 所属菜名:拆解出的成分带同名标签;单品为空


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
        elif isinstance(item, ParsedDish):
            # 菜=展示标签,不是实体:成分逐条入 raw,带同名菜标签,菜合计现算
            for ing in item.ingredients:
                rf = _resolve_food(
                    ParsedFood(
                        spoken_name=ing.spoken_name,
                        name=ing.name,
                        grams=ing.grams,
                        form=ing.form,
                        est_kcal=ing.est_kcal,
                        meal_slot=item.meal_slot,
                    ),
                    user_foods or {},
                )
                rf.dish = item.dish_name
                records.append(rf)
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


def _form_resolved_name(name: str, form: str | None) -> str:
    """用户明说了形态且名字落在歧义簇 → 代码在簇内换成对应形态的条目(零 AI)。"""
    if not form:
        return name
    cluster = lookup.form_cluster(name)
    if not cluster:
        return name
    for m in cluster:
        if m.form == form:
            return m.name
    return name


def _resolve_food(p: ParsedFood, user_foods: dict[str, UserFoodDef]) -> ResolvedFood:
    name = _form_resolved_name(p.name, p.form)
    food_item = lookup.find_food(name)
    # 数量格:报了数量时 grams 是单份克数,总克数=数量×单份(乘法归代码)
    grams = None if p.grams is None else p.grams * (p.count or 1)
    nutrition = lookup.food_nutrition(food_item, grams) if food_item and grams else None

    if p.is_condiment:  # 补油/补调味显式原则:独立成条,永远标估算,可删可改
        grams = grams or OIL_DEFAULT_GRAMS
        kcal = (
            round(food_item.kcal * grams / 100, 1)
            if food_item
            else (p.est_kcal or round(9 * grams, 1))
        )
        return ResolvedFood(
            food_name=name,
            source="llm_estimated",
            kcal=kcal,
            grams=grams,
            meal_slot=p.meal_slot,
            protein=nutrition["protein"] if nutrition else None,
            fat=nutrition["fat"] if nutrition else None,
            cho=nutrition["cho"] if nutrition else None,
            fiber=nutrition["fiber"] if nutrition else None,
        )

    if p.reported_kcal is not None:  # 优先级1:用户自报
        return _food_record(
            name, "user_reported", p.reported_kcal, grams, nutrition, p.meal_slot
        )

    # 优先级2:自定义食物——原话叫法精确命中(键归一化与官方表同规则),
    # 每100克口径,与官方表同一算法
    uf = user_foods.get(lookup.norm_key(p.spoken_name))
    if uf and grams:
        factor = grams / 100
        scale = lambda v: None if v is None else round(v * factor, 1)  # noqa: E731
        return ResolvedFood(
            food_name=uf.name,
            source="user_food",
            kcal=round(uf.kcal * factor, 1),
            grams=grams,
            meal_slot=p.meal_slot,
            protein=scale(uf.protein),
            fat=scale(uf.fat),
            cho=scale(uf.cho),
            fiber=scale(uf.fiber),
        )

    if food_item and grams:  # 优先级3:静态表
        return _food_record(
            food_item.name,
            "food_table",
            nutrition["kcal"],
            grams,
            nutrition,
            p.meal_slot,
        )

    if p.est_kcal is not None:  # 优先级4:估算兜底
        return _food_record(name, "llm_estimated", p.est_kcal, grams, None, p.meal_slot)

    raise ValueError(f"{name}: 查表未命中且无估算值")


def _food_record(name, source, kcal, grams, nutrition, meal_slot=None) -> ResolvedFood:
    return ResolvedFood(
        food_name=name,
        source=source,
        kcal=kcal,
        grams=grams,
        meal_slot=meal_slot,
        protein=nutrition["protein"] if nutrition else None,
        fat=nutrition["fat"] if nutrition else None,
        cho=nutrition["cho"] if nutrition else None,
        fiber=nutrition["fiber"] if nutrition else None,
    )


# ── 输出校验(harness 的硬反馈):不可解的输出打回模型重出 ─────────────────


def _off_table_without_est(
    spoken: str, name: str, user_food_keys: frozenset[str]
) -> bool:
    return (
        lookup.norm_key(spoken) not in user_food_keys and lookup.find_food(name) is None
    )


def output_problems(output: ParseOutput, user_food_keys: frozenset[str]) -> list[str]:
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
        elif isinstance(item, ParsedFood) and item.is_condiment:
            # 官方表没有糖/麻酱/沙拉酱类条目;表外调味必须带估算,
            # 否则会错用"油≈每克9千卡"的兜底去算糖
            if lookup.find_food(item.name) is None and item.est_kcal is None:
                problems.append(f"{item.name}: 调味不在成分表,必须补 est_kcal")
        elif isinstance(item, ParsedFood):
            if item.reported_kcal is None and item.grams is None:
                problems.append(f"{item.name}: 缺克数(grams)")
            if (
                item.reported_kcal is None
                and item.est_kcal is None
                and _off_table_without_est(item.spoken_name, item.name, user_food_keys)
            ):
                problems.append(f"{item.name}: 可能不在成分表,必须补 est_kcal 兜底")
        elif isinstance(item, ParsedDish):
            for ing in item.ingredients:
                if ing.est_kcal is None and _off_table_without_est(
                    ing.spoken_name, ing.name, user_food_keys
                ):
                    problems.append(
                        f"{item.dish_name}/{ing.name}: 可能不在成分表,必须补 est_kcal 兜底"
                    )
    return problems


# ── 克重守恒(硬校验,代码当裁判):成分和=总克重±5%,超差打回,重试不过降级 ──


def dish_violation(item: ParsedDish) -> str | None:
    if item.total_grams <= 0:
        return f"{item.dish_name}: 总克重必须大于0"
    if not item.ingredients:
        return f"{item.dish_name}: 成分清单为空,无法核对克重"
    total = sum(i.grams for i in item.ingredients)
    diff = total - item.total_grams
    if abs(diff) > GRAMS_TOLERANCE * item.total_grams:
        return (
            f"{item.dish_name}: 成分克数之和{total:g}g 与总克重{item.total_grams:g}g "
            f"相差{diff:+g}g(超±5%容差);成分是总量的组成部分,不得额外叠加,"
            f"请调整各成分克数使其和等于总克重"
        )
    return None


def conservation_violations(output: ParseOutput) -> list[str]:
    return [
        v
        for item in output.items
        if isinstance(item, ParsedDish) and (v := dish_violation(item))
    ]


def degrade_dish(dish: ParsedDish) -> ParsedFood:
    """守恒重试不过 → 整菜降级为估算一条(走 est 路径,必标 llm_estimated)。

    整菜估算值模型没给时,代码从成分自己求和(表内按每100克算,表外用成分估算;
    算术归代码)——该字段因此无需硬校验,漏填不烧重试。
    """
    est = dish.est_total_kcal
    if est is None:
        parts = []
        for ing in dish.ingredients:
            item = lookup.find_food(_form_resolved_name(ing.name, ing.form))
            if item is not None:
                parts.append(item.kcal * ing.grams / 100)
            elif ing.est_kcal is not None:
                parts.append(ing.est_kcal)
        est = round(sum(parts), 1) if parts else None
    return ParsedFood(
        spoken_name=dish.dish_name,
        name=dish.dish_name,
        grams=dish.total_grams if dish.total_grams > 0 else None,
        est_kcal=est,
        meal_slot=dish.meal_slot,
    )


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
3. 每条食物给两个名字:spoken_name=用户嘴里的叫法,一字不改照抄;
   name=映射到《中国食物成分表》标准名(同类多条目优先带"(代表值)"的);
   映射不了则 name 保留原话并填 est_kcal 兜底。
4. 份量:克数直接用;个/碗/勺/把等按常识换算成克填 grams;
   [用户记忆]里有个人单位换算(如"一勺=30克")时必须优先按记忆换算。
5. 形态 form:仅当用户明说了生/熟/干/水发/即食(含"晒干""泡发""没煮"等同义说法)才填;
   没明说必须留空,绝不猜。
6. 补油补调味:做法按常识需要油(炒/煎/炸/红烧/油焖/干煸/爆等)而用户没提到油
   → 追加一条独立 food(name:"菜籽油", grams:10, is_condiment:true);
   做法按常识含糖/芝麻酱/沙拉酱/蚝油/蜂蜜等高热量调味(如红烧/糖醋必有糖)
   而用户没报 → 同样各追加一条独立 food,克数按常识估,is_condiment:true,
   并填 est_kcal(这份调味的总热量,成分表没有调味条目);
   盐/醋/生抽/胡椒等低热量调味忽略不出条。纯水煮/清蒸且没提油就不补。
   用户自己报了油/调味则正常解析,不打标。
7. 运动动作名先对下方 MET 表(含别名);表里没有的力量动作(有负重/组次特征)填 fallback_tier:器械或单关节孤立动作=moderate,大重量自由复合=vigorous;表外有氧才填 est_met。
8. 报次数填 reps,报时长填 duration_min;绝不自行换算。
9. 陈述当前体重(如"今天75公斤")→ weight 记录。
10. 复合菜/带馅带夹心面点等多成分食物 → 输出 dish 条目:dish_name=用户的叫法;
    用户报了总克重则 total_grams 必须原样用用户的数,没报则 total_grams=各成分克数之和;
    成分拆为表内食材逐条估克数(估克重可以,估热量不行),各成分克数之和必须等于
    总克重——成分(馅、夹心、配料)是总量的组成部分,绝不能在总克重之外额外叠加;
    规则6的补油补调味对 dish 同样生效:做法需要而用户没提的油/高热量调味,
    作为成分列入 ingredients(占总克重的份额),不得漏;
    est_total_kcal 必填。单独报的一种食物用 food,不用 dish。
11. 补充说明不是新记录,同一对象整句只输出一条:
    动作:"硬拉100公斤5个又一组" → 仅一条(name=硬拉, load_kg=100, reps=5);
    食物:同一句里对刚提过的食物追加做法/状态/品牌描述("100克虾仁,水煮的虾仁"
    "刚才那杯奶是脱脂的")→ 仅一条,把描述并进该条理解;
    只有用户明确说"又吃了/再来一份"才算新记录。
12. 餐次归属(仅 food/dish):仅当用户明说了这是哪一顿——早餐/早饭→早餐,午餐/午饭/中饭→午餐,
    下午茶/下午加餐→下午茶,晚餐/晚饭→晚餐,夜宵/宵夜→其余——才填 meal_slot;
    没明说必须不填(留空),系统会按时间自动归,绝不要猜。
13. 场次归组(仅 exercise):消息可能附带[当前训练场次](当天最近一场的时间与内容)。
    结合当前时间和内容常识判断:延续它 → starts_new_group=false;新一场 → true。
    每条 exercise 填 group_name——所在场次的展示名(2~8字,按内容与时段起,
    如"晚间胸部训练");延续已有场次时结合已含内容给更贴切的名字。
14. "记住……"类指令:定义自己的食物 → 输出 user_food_def 条目,name=用户的叫法,
    用户给的克数填 grams、对应热量填 kcal;用户没给克数则 grams 不填,绝不猜数;
    叫法对应("我说X指的是Y")→ memory 条目(kind=alias);习惯/长期事实 → memory
    条目(kind=habit)。这类话本身不产生 food/exercise 记录,除非用户同时说这次吃了/练了。
15. 消息可能附带[用户记忆](该用户积累的叫法与习惯),解析时优先按记忆理解用户的话。

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
        retries=MAX_PARSE_RETRIES,
        model_settings=_model_settings(),
    )

    @agent.output_validator
    async def _validate(ctx: RunContext[frozenset], output: ParseOutput) -> ParseOutput:
        violations = conservation_violations(output)
        if violations and ctx.retry < MAX_PARSE_RETRIES:
            raise ModelRetry("以下菜的克重不守恒,请重拆:" + ";".join(violations))
        if violations:  # 重试用尽仍超差 → 违规的菜整体降级为估算一条
            output.items = [
                degrade_dish(i)
                if isinstance(i, ParsedDish) and dish_violation(i)
                else i
                for i in output.items
            ]
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
        instructions=(
            "结合用户原话,为每个待裁决的食物名从给出的候选中挑最贴切的一条"
            "(注意从原话推断生熟/干湿等形态);没有合适的填 null。"
            "只能从候选里选,不得自造。"
        ),
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


def _iter_foods(output: ParseOutput):
    """全部待查表的食物条目:单品(非补调味)+ 各菜的成分。"""
    for item in output.items:
        if isinstance(item, ParsedFood) and not item.is_condiment:
            yield item
        elif isinstance(item, ParsedDish):
            yield from item.ingredients


async def parse_text(
    text: str,
    *,
    now: datetime,
    user_food_keys: frozenset[str] = frozenset(),
    open_session: str | None = None,
    memories: str | None = None,
    rounds_sink: dict | None = None,
) -> ParseOutput:
    """LLM 洗数据入口:一次解析 + 封闭候选裁决(微循环第二轮,按需)。

    第二轮合并两类待裁决项,一次调用:
    - 未命中重映射:标准名查表不中 → 字符重合度召回候选,连用户原话交模型挑;
    - 形态裁决:命中歧义簇且用户没明说形态 → 全簇为封闭候选,连原话交模型挑。
    user_food_keys:该用户自定义食物的归一化叫法集合,只在代码侧用
    (跳过重映射/免 est 兜底),绝不注入提示词(决策9:禁止 prompt hack)。
    open_session:当天最近一场训练的摘要,AI 据此判断场次归组(无阈值常量)。
    memories:该用户全部记忆拼成的一段文本(量小,全量注入,不做检索)。
    rounds_sink:调用方给的存档口袋,各轮 AI 吐出原样放入(输入表 ai_rounds 用)。
    """
    # 存储用 UTC;给 LLM 看的时间转本地时区,否则"中午/晚上"这类语境会错 8 小时
    local_now = now.astimezone(ZoneInfo(settings.TIMEZONE)) if now.tzinfo else now
    prefix = f"[当前时间 {local_now:%Y-%m-%d %H:%M}]"
    if open_session:
        prefix += f"[当前训练场次:{open_session}]"
    if memories:
        prefix += f"[用户记忆:{memories}]"
    result = await parse_agent().run(f"{prefix}\n用户说:{text}", deps=user_food_keys)
    output = result.output
    if rounds_sink is not None:
        rounds_sink["parse"] = output.model_dump(mode="json")
    await adjudicate_names(output, text, user_food_keys, rounds_sink=rounds_sink)
    return output


async def adjudicate_names(
    output: ParseOutput,
    text: str,
    user_food_keys: frozenset[str] = frozenset(),
    *,
    rounds_sink: dict | None = None,
) -> None:
    """微循环第二轮(按需):未命中重映射 + 形态裁决,合并一次调用,原地改名。

    新旧管线共用:旧入口解析完调用;分诊管线合并各专科结果后调用。
    """
    pending: dict[str, list[str]] = {}
    for item in _iter_foods(output):
        if getattr(item, "reported_kcal", None) is not None:
            continue
        if lookup.norm_key(item.spoken_name) in user_food_keys:
            continue  # 自定义食物按原话精确命中,轮不到裁决
        if lookup.find_food(item.name) is None:
            candidates = lookup.candidate_foods(item.name)
            if candidates:
                pending[item.name] = candidates
        elif item.form is None and (cluster := lookup.form_cluster(item.name)):
            pending[item.name] = [m.name for m in cluster]  # 形态裁决:不猜,交裁决
    if not pending:
        return
    question = f"用户原话:{text}\n" + "\n".join(
        f"{name} 的候选:{'、'.join(cands)}" for name, cands in pending.items()
    )
    mapping = (await remap_agent().run(question)).output.mapping
    if rounds_sink is not None:
        rounds_sink["remap"] = {"pending": pending, "mapping": mapping}
    for item in _iter_foods(output):
        if item.name in mapping:
            target = mapping[item.name]
            if target and lookup.find_food(target):
                item.name = target
