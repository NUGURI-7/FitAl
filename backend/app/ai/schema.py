"""LLM 输出 schema:structured output 强约束(决策 3)。

LLM 只输出"结构"(名称/数量/档位);除用户自报数与末路估算外不含热量数
(决策 2:AI 定结构,表定数值)。
"""

from typing import Annotated, Literal

from pydantic import BaseModel, Field

# 餐次时段制(2026-07-07 用户定):餐次=固定五槽,组名=时段名
MealSlot = Literal["早餐", "午餐", "下午茶", "晚餐", "其余"]


class ParsedExercise(BaseModel):
    type: Literal["exercise"] = "exercise"
    name: str = Field(
        description="动作名:优先映射到 MET 表标准名;表里没有则保留用户原话"
    )
    duration_min: float | None = Field(None, description="用户报的时长(分钟),没报不填")
    reps: int | None = Field(None, description="次数,没报不填")
    load_kg: float | None = Field(None, description="负重公斤数,没报不填")
    reported_kcal: float | None = Field(
        None, description="用户自己报的消耗热量,原样照抄"
    )
    fallback_tier: Literal["moderate", "vigorous"] | None = Field(
        None,
        description="仅当动作不在 MET 表时:力量动作归强度档,器械/孤立=moderate,大重量自由复合=vigorous",
    )
    est_met: float | None = Field(
        None, description="仅当动作不在 MET 表且不是力量动作时:估算的 MET 值"
    )
    starts_new_group: bool = Field(
        False,
        description="归组判断:延续消息中给出的[当前训练场次]填 false;是新一场训练填 true",
    )
    group_name: str = Field(
        "",
        description='该记录所在训练场次的展示名(2~8字,按内容与时段起,如"晚间胸部训练");延续已有场次时结合已含内容给更贴切的名字',
    )


class ParsedFood(BaseModel):
    type: Literal["food"] = "food"
    name: str = Field(
        description="食物名:优先映射成分表标准名(熟制/代表值优先);自定义食物用用户叫法;都没有保留原话"
    )
    grams: float | None = Field(None, description="克数;个/碗/勺等按常识换算成克")
    units: float | None = Field(None, description="仅自定义食物:份数,不填克数")
    reported_kcal: float | None = Field(None, description="用户自己报的热量,原样照抄")
    est_kcal: float | None = Field(
        None, description="该份食物总热量估算,仅当名称可能不在表里时作兜底"
    )
    is_cooking_oil: bool = Field(False, description="是否为自动补的烹调油条目")
    meal_slot: MealSlot | None = Field(
        None,
        description="仅当用户明说了这是哪一顿(早餐/午餐/下午茶/晚餐;夜宵、宵夜填其余)才填;没明说必须不填,由系统按时间归入",
    )


class ParsedWeight(BaseModel):
    type: Literal["weight"] = "weight"
    weight_kg: float


class ParsedUserFoodDef(BaseModel):
    """用户说"记住……"定义自己的食物(按份)→ user_foods 表,查表优先级高于标准表。"""

    type: Literal["user_food_def"] = "user_food_def"
    name: str = Field(description="用户对这个食物的叫法,原样保留")
    unit: str = Field("份", description='计量单位:份/勺/碗/个等,用户没说填"份"')
    kcal: float = Field(description="每单位热量,用户报的数原样填")
    protein: float | None = Field(None, description="每单位蛋白质克数,没报不填")
    fat: float | None = Field(None, description="每单位脂肪克数,没报不填")
    cho: float | None = Field(None, description="每单位碳水克数,没报不填")
    fiber: float | None = Field(None, description="每单位纤维克数,没报不填")


class ParsedMemory(BaseModel):
    """用户要求记住的叫法/习惯 → ai_memories 表,解析时注入 prompt。"""

    type: Literal["memory"] = "memory"
    kind: Literal["alias", "habit"] = Field(
        description="alias=叫法对应(我说X指的是Y);habit=习惯或长期事实"
    )
    content: str = Field(description="一句话陈述要记住的内容,自包含、无上下文也能懂")


ParsedItem = Annotated[
    ParsedExercise | ParsedFood | ParsedWeight | ParsedUserFoodDef | ParsedMemory,
    Field(discriminator="type"),
]


class ParseOutput(BaseModel):
    items: list[ParsedItem]


class NameRemap(BaseModel):
    """微循环第二轮:未命中的名字 → 从候选里挑标准名,挑不出给 null。"""

    mapping: dict[str, str | None]


class MemoryItem(BaseModel):
    kind: Literal["alias", "habit", "correction"]
    content: str


class ConsolidatedMemories(BaseModel):
    """每日巩固:输入现有记忆全量,输出合并去重后的新全量(整层替换)。"""

    memories: list[MemoryItem]
