"""分诊管线:分诊(开思考)→ 专科并发抽取 → 合并 → 第二轮裁决。

取代"一次大调用包揽十职"的旧解析(错例温床;实验证明瓶颈是任务形态不是模型智力):
- 分诊只切片段+定类型+提共享槽,不带任何解析规则和 MET 表;开思考,
  走提示词 JSON 通道(端点拒"思考+强制工具调用"),代码解析校验打回;
- 专科按类型合并调用(吃的/运动/记住),各拿各的瘦身说明书,校验微循环
  下沉到各科;asyncio 并发,总耗时=分诊+最慢一科;
- 单科失败只降级该段(爆炸半径隔离),其他段照常返回;
- 合并后的查表/算数/入库/归组全部复用现有代码,对外契约不变。
"""

import asyncio
import json
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache
from zoneinfo import ZoneInfo

from pydantic import ValidationError
from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.settings import ModelSettings

from app.ai import lookup, parser
from app.ai.schema import (
    ParsedDish,
    ParsedExercise,
    ParsedFood,
    ParsedMemory,
    ParsedUserFoodDef,
    ParsedWeight,
    ParseOutput,
    TriageOutput,
    TriageSegment,
)
from app.config import settings

TRIAGE_MAX_RETRIES = 2
# 每路专科允许输出的条目类型;越界条目直接丢弃(那是别科的活,别科自有自己的段)
TRACK_TYPES = {
    "eat": (ParsedFood, ParsedDish),
    "exercise": (ParsedExercise,),
    "remember": (ParsedUserFoodDef, ParsedMemory),
}

StatusEmit = Callable[[dict], Awaitable[None]]


@dataclass
class PipelineResult:
    output: ParseOutput  # 合并后的解析结果(已完成第二轮裁决),直接喂 build_records
    failed_tracks: dict[str, str] = field(default_factory=dict)  # 科 -> 错误
    failed_texts: list[str] = field(default_factory=list)  # 失败段原话(回执用)

    @property
    def status(self) -> str:
        """输入行状态:全成 ok / 部分降级 partial(全败也算 partial:原话已留底)。"""
        return "ok" if not self.failed_tracks else "partial"


# ── 分诊:提示词 JSON 通道(开思考),代码解析校验打回 ─────────────────────


def _triage_instructions() -> str:
    return """你是分诊器:把用户的一句话切成若干段,每段标类型。你不解析细节、不做任何换算。

类型只有四种:
- eat:吃了/喝了什么(含复合菜)
- exercise:运动/训练
- weight:陈述当前体重
- remember:"记住……"类指令(定义自己的食物/叫法/习惯)

规则:
1. text 一字不改照抄原句中的对应片段,绝不改写、绝不补词;
2. 与记录无关的内容不出段;整句都无关则 segments 为空数组;
3. 同一件事只出一段:针对同一对象的补充说明、改口纠正,连同原文一起并进那一段;
4. meal_slot 仅当用户明说这是哪一顿才填(早餐/午餐/下午茶/晚餐;夜宵、宵夜填"其余"),
   没明说必须 null;只有 eat 段可填;
5. weight 段把公斤数直接填进 weight_kg;
6. 消息可能附带[用户记忆](用户的私人叫法),用它理解某段说的是哪类东西。

只输出一个 JSON 对象,不要任何其他文字。格式:
{"segments": [{"type": "eat|exercise|weight|remember", "text": "原文片段",
  "meal_slot": null, "weight_kg": null}]}"""


def _triage_model_settings() -> ModelSettings:
    """分诊开思考:端点拒'思考+强制工具调用',故走纯文本通道;
    .env 里显式关思考的端点,分诊单独翻回 enabled,其余私有参数照传。"""
    ms = ModelSettings(temperature=0.0)
    extra = json.loads(settings.LLM_EXTRA_BODY) if settings.LLM_EXTRA_BODY else {}
    if "thinking" in extra:
        extra["thinking"] = {"type": "enabled"}
    if extra:
        ms["extra_body"] = extra
    return ms


@lru_cache(maxsize=1)
def triage_agent() -> Agent:
    return Agent(
        parser._model(),
        output_type=str,  # 纯文本吐 JSON,解析校验归代码(下方微循环)
        instructions=_triage_instructions(),
        model_settings=_triage_model_settings(),
    )


async def _triage_call(prompt: str) -> str:
    return (await triage_agent().run(prompt)).output


def _extract_json(raw: str) -> dict:
    """剥掉思考模式可能带的围栏/前后缀,取第一个完整 JSON 对象。"""
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-z]*\s*|\s*```$", "", text)
    start = text.find("{")
    if start < 0:
        raise ValueError("输出里没有 JSON 对象")
    return json.loads(text[start : text.rfind("}") + 1])


def _triage_problems(out: TriageOutput, original: str) -> list[str]:
    problems = []
    for seg in out.segments:
        if seg.text.strip() not in original:
            problems.append(f"片段「{seg.text}」不是原句子串,必须一字不改照抄")
        if seg.type == "weight" and seg.weight_kg is None:
            problems.append(f"体重段「{seg.text}」缺 weight_kg")
    return problems


async def run_triage(
    text: str, *, now: datetime, alias_memories: str | None
) -> TriageOutput:
    """分诊微循环:调用→JSON解析→schema校验→照抄校验,不合格带错打回,最多两次。"""
    local_now = now.astimezone(ZoneInfo(settings.TIMEZONE)) if now.tzinfo else now
    prompt = f"[当前时间 {local_now:%Y-%m-%d %H:%M}]"
    if alias_memories:
        prompt += f"[用户记忆:{alias_memories}]"
    prompt += f"\n用户说:{text}"

    last_error = ""
    for _ in range(TRIAGE_MAX_RETRIES + 1):
        ask = (
            prompt
            if not last_error
            else f"{prompt}\n(上次输出不合格:{last_error}。请重新只输出修正后的 JSON)"
        )
        raw = await _triage_call(ask)
        try:
            out = TriageOutput.model_validate(_extract_json(raw))
        except (ValueError, ValidationError) as e:
            last_error = f"JSON 不合法:{e}"
            continue
        problems = _triage_problems(out, text)
        if not problems:
            return out
        last_error = ";".join(problems)
    raise RuntimeError(f"分诊重试耗尽:{last_error}")


# ── 专科:各拿瘦身说明书,structured output + 校验微循环(关思考) ─────────


def _eat_instructions() -> str:
    return """你是饮食记录解析器,输入是用户话里"吃喝相关"的片段,拆成零或多条记录。
你只输出结构,绝不做任何算术、绝不输出建议。只输出 food / dish 两种条目。

规则:
1. 用户自己报了热量数字 → 原样填 reported_kcal,不要改动。
2. 每条食物给两个名字:spoken_name=用户嘴里的叫法,一字不改照抄;
   name=映射到《中国食物成分表》标准名(同类多条目优先带"(代表值)"的);
   映射不了则 name 保留原话并填 est_kcal 兜底。
3. 份量:克数直接用;个/碗/勺/把等按常识换算成克填 grams;
   [用户记忆]里有个人单位换算(如"一勺=30克")时必须优先按记忆换算。
4. 形态 form:仅当用户明说了生/熟/干/水发/即食(含"晒干""泡发""没煮"等同义说法)才填;
   没明说必须留空,绝不猜。
5. 补油补调味:做法按常识需要油(炒/煎/炸/红烧/油焖/干煸/爆等)而用户没提到油
   → 追加一条独立 food(name:"菜籽油", grams:10, is_condiment:true);
   做法按常识含糖/芝麻酱/沙拉酱/蚝油/蜂蜜等高热量调味(如红烧/糖醋必有糖)
   而用户没报 → 同样各追加一条独立 food,克数按常识估,is_condiment:true,
   并填 est_kcal(这份调味的总热量,成分表没有调味条目);
   盐/醋/生抽/胡椒等低热量调味忽略不出条。纯水煮/清蒸且没提油就不补。
   用户自己报了油/调味则正常解析,不打标。
6. 复合菜/带馅带夹心面点等多成分食物 → 输出 dish 条目:dish_name=用户的叫法;
   用户报了总克重则 total_grams 必须原样用用户的数,没报则 total_grams=各成分克数之和;
   成分拆为表内食材逐条估克数(估克重可以,估热量不行),各成分克数之和必须等于
   总克重——成分(馅、夹心、配料)是总量的组成部分,绝不能在总克重之外额外叠加;
   规则5的补油补调味对 dish 同样生效:做法需要而用户没提的油/高热量调味,
   作为成分列入 ingredients(占总克重的份额),不得漏;
   est_total_kcal 必填。单独报的一种食物用 food,不用 dish。
7. 餐次归属:仅当用户明说了这是哪一顿——早餐/早饭→早餐,午餐/午饭/中饭→午餐,
   下午茶/下午加餐→下午茶,晚餐/晚饭→晚餐,夜宵/宵夜→其余——才填 meal_slot;
   没明说必须不填(留空),系统会按时间自动归,绝不要猜。
8. 消息可能附带[用户记忆],解析时优先按记忆理解用户的话。"""


def _exercise_instructions() -> str:
    return f"""你是运动记录解析器,输入是用户话里"运动/训练相关"的片段,拆成零或多条记录。
你只输出结构,绝不做任何算术、绝不输出建议。只输出 exercise 条目。

规则:
1. 用户自己报了消耗热量 → 原样填 reported_kcal,不要改动。
2. 动作名先对下方 MET 表(含别名);表里没有的力量动作(有负重/组次特征)填
   fallback_tier:器械或单关节孤立动作=moderate,大重量自由复合=vigorous;
   表外有氧才填 est_met。
3. 报次数填 reps,报时长填 duration_min;绝不自行换算。
4. 场次归组:消息可能附带[当前训练场次](当天最近一场的时间与内容)。
   结合当前时间和内容常识判断:延续它 → starts_new_group=false;新一场 → true。
   每条 exercise 填 group_name——所在场次的展示名(2~8字,按内容与时段起,
   如"晚间胸部训练");延续已有场次时结合已含内容给更贴切的名字。
5. 消息可能附带[用户记忆],解析时优先按记忆理解用户的话。

MET 表({len(lookup.met_items())}条):
{parser._met_table_block()}"""


def _remember_instructions() -> str:
    return """你是"记住"指令解析器,输入是用户话里"记住……"类的片段。
只输出 user_food_def / memory 两种条目,不产生任何 food/exercise 记录。

规则:
1. 定义自己的食物 → user_food_def 条目:name=用户的叫法,
   用户给的克数填 grams、对应热量填 kcal;用户没给克数则 grams 不填,绝不猜数;
   name 只填食物本身的名字,量词("一勺""一碗")不属于名字。
2. 叫法对应("我说X指的是Y")→ memory 条目(kind=alias);
   习惯/长期事实 → memory 条目(kind=habit)。"""


def _specialist(instructions: str) -> Agent:
    agent = Agent(
        parser._model(),
        output_type=ParseOutput,
        deps_type=frozenset,
        instructions=instructions,
        retries=parser.MAX_PARSE_RETRIES,
        model_settings=parser._model_settings(),
    )

    @agent.output_validator
    async def _validate(ctx: RunContext[frozenset], output: ParseOutput) -> ParseOutput:
        violations = parser.conservation_violations(output)
        if violations and ctx.retry < parser.MAX_PARSE_RETRIES:
            raise ModelRetry("以下菜的克重不守恒,请重拆:" + ";".join(violations))
        if violations:  # 重试用尽仍超差 → 违规的菜整体降级为估算一条
            output.items = [
                parser.degrade_dish(i)
                if isinstance(i, ParsedDish) and parser.dish_violation(i)
                else i
                for i in output.items
            ]
        problems = parser.output_problems(output, ctx.deps or frozenset())
        if problems:
            raise ModelRetry("以下条目不合格,请修正后重新输出:" + ";".join(problems))
        return output

    return agent


@lru_cache(maxsize=1)
def eat_agent() -> Agent:
    return _specialist(_eat_instructions())


@lru_cache(maxsize=1)
def exercise_agent() -> Agent:
    return _specialist(_exercise_instructions())


@lru_cache(maxsize=1)
def remember_agent() -> Agent:
    return _specialist(_remember_instructions())


async def _extract_track(
    track: str,
    texts: list[str],
    *,
    now: datetime,
    user_food_keys: frozenset[str],
    open_session: str | None,
    memories: str | None,
) -> ParseOutput:
    agent = {"eat": eat_agent, "exercise": exercise_agent, "remember": remember_agent}[
        track
    ]()
    local_now = now.astimezone(ZoneInfo(settings.TIMEZONE)) if now.tzinfo else now
    prefix = f"[当前时间 {local_now:%Y-%m-%d %H:%M}]"
    if track == "exercise" and open_session:
        prefix += f"[当前训练场次:{open_session}]"
    if memories and track != "remember":
        prefix += f"[用户记忆:{memories}]"
    joined = "\n".join(texts)
    result = await agent.run(f"{prefix}\n用户说:{joined}", deps=user_food_keys)
    output = result.output
    allowed = TRACK_TYPES[track]
    output.items = [i for i in output.items if isinstance(i, allowed)]  # 越界丢弃
    return output


# ── 编排:分诊 → 按类型并发 → 合并 → 第二轮裁决 ─────────────────────────


async def _emit(on_status: StatusEmit | None, data: dict) -> None:
    if on_status is not None:
        await on_status(data)


async def parse_via_triage(
    text: str,
    *,
    now: datetime,
    user_food_keys: frozenset[str] = frozenset(),
    open_session: str | None = None,
    alias_memories: str | None = None,
    all_memories: str | None = None,
    rounds_sink: dict | None = None,
    on_status: StatusEmit | None = None,
) -> PipelineResult:
    """新管线入口:返回合并解析结果+失败段信息;调用方照旧走 build_records。

    记忆分流:alias_memories(叫法)拼分诊;all_memories(叫法+习惯+纠正)拼专科。
    分诊本身失败会抛异常(整句失败,调用方留底);单科失败不抛,降级进结果。
    """
    await _emit(on_status, {"stage": "triage"})
    triage = await run_triage(text, now=now, alias_memories=alias_memories)
    if rounds_sink is not None:
        rounds_sink["triage"] = triage.model_dump(mode="json")

    by_type: dict[str, list[TriageSegment]] = {}
    for seg in triage.segments:
        by_type.setdefault(seg.type, []).append(seg)

    items: list = [
        ParsedWeight(weight_kg=seg.weight_kg) for seg in by_type.pop("weight", [])
    ]
    tracks = [t for t in TRACK_TYPES if t in by_type]
    await _emit(on_status, {"stage": "extract", "tracks": tracks})

    results = await asyncio.gather(
        *(
            _extract_track(
                t,
                [s.text for s in by_type[t]],
                now=now,
                user_food_keys=user_food_keys,
                open_session=open_session,
                memories=all_memories,
            )
            for t in tracks
        ),
        return_exceptions=True,  # 爆炸半径隔离:一科炸不掀翻别科
    )

    result = PipelineResult(output=ParseOutput(items=items))
    for track, res in zip(tracks, results):
        await _emit(on_status, {"stage": "track_done", "track": track})
        if isinstance(res, BaseException):
            result.failed_tracks[track] = f"{type(res).__name__}: {res}"
            result.failed_texts += [s.text for s in by_type[track]]
            if rounds_sink is not None:
                rounds_sink[track] = {"error": result.failed_tracks[track]}
            continue
        if track == "eat":  # 分诊提的餐次槽:专科没填而段里明说了,单段时回填
            eat_segs = by_type["eat"]
            if len(eat_segs) == 1 and eat_segs[0].meal_slot:
                for item in res.items:
                    if item.meal_slot is None:
                        item.meal_slot = eat_segs[0].meal_slot
        result.output.items.extend(res.items)
        if rounds_sink is not None:
            rounds_sink[track] = res.model_dump(mode="json")

    await parser.adjudicate_names(
        result.output, text, user_food_keys, rounds_sink=rounds_sink
    )
    return result
