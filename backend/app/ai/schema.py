"""LLM 输出 schema:structured output 强约束(决策 3)。

LLM 只输出"结构"(名称/数量/档位);除用户自报数与末路估算外不含热量数
(决策 2:AI 定结构,表定数值)。
"""

from typing import Annotated, Literal

from pydantic import BaseModel, Field

# 餐次时段制(2026-07-07 用户定):餐次=固定五槽,组名=时段名
MealSlot = Literal["早餐", "午餐", "下午茶", "晚餐", "其余"]

# 形态封闭词表(2026-07-08 菜层工程包):仅用户明说才填,绝不猜
FoodForm = Literal["生", "熟", "干", "水发", "即食"]


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
    """单独报的一种食物(不是拆解出的菜);拆解类用 ParsedDish。"""

    type: Literal["food"] = "food"
    spoken_name: str = Field(description="用户嘴里对这个食物的叫法,一字不改照抄")
    name: str = Field(
        description="标准名映射:往成分表标准名靠(同类多条目优先带'(代表值)'的);映射不了保留原话"
    )
    grams: float | None = Field(None, description="克数;个/碗/勺等按常识换算成克")
    form: FoodForm | None = Field(
        None,
        description="形态:仅当用户明说了生/熟/干/水发/即食(或同义词)才填;没明说必须不填,绝不猜",
    )
    reported_kcal: float | None = Field(None, description="用户自己报的热量,原样照抄")
    est_kcal: float | None = Field(
        None, description="该份食物总热量估算,仅当名称可能不在表里时作兜底"
    )
    is_condiment: bool = Field(
        False, description="是否为自动补的烹调油/高热量调味条目(非用户明说)"
    )
    meal_slot: MealSlot | None = Field(
        None,
        description="仅当用户明说了这是哪一顿(早餐/午餐/下午茶/晚餐;夜宵、宵夜填其余)才填;没明说必须不填,由系统按时间归入",
    )


class ParsedIngredient(BaseModel):
    """菜的一个成分。"""

    spoken_name: str = Field(
        description="用户提到该成分的叫法;用户没逐一点名则填你拆出的通俗名"
    )
    name: str = Field(description="标准名映射:往成分表标准名靠;映射不了保留通俗名")
    grams: float = Field(description="该成分的克数(估克重可以,估热量不行)")
    form: FoodForm | None = Field(
        None, description="形态:仅当用户明说才填;没明说必须不填,绝不猜"
    )
    est_kcal: float | None = Field(
        None, description="该成分总热量估算,仅当名称可能不在表里时作兜底"
    )


class ParsedDish(BaseModel):
    """拆解类输出:一道菜=菜名+总克重+成分清单。单独报的食物不用这个结构。

    硬校验(代码当裁判):成分克数之和必须等于总克重(±5%),超差打回重拆。
    """

    type: Literal["dish"] = "dish"
    dish_name: str = Field(description="菜名,按用户的叫法(如'番茄炒蛋''毛毛虫面包')")
    total_grams: float = Field(
        description="整道菜总克重:用户报了必须原样用用户的数;没报则为各成分克数之和"
    )
    ingredients: list[ParsedIngredient] = Field(
        description="成分清单;各成分克数之和必须等于总克重,成分间不得重叠计量"
    )
    est_total_kcal: float | None = Field(
        None,
        description="整道菜总热量的兜底估算(仅在无法按成分查表时使用,平时不用);"
        "漏填由代码从成分求和补出,不作硬校验",
    )
    meal_slot: MealSlot | None = Field(
        None,
        description="仅当用户明说了这是哪一顿才填;没明说必须不填",
    )


class ParsedWeight(BaseModel):
    type: Literal["weight"] = "weight"
    weight_kg: float


class ParsedUserFoodDef(BaseModel):
    """用户说"记住……"定义自己的食物 → user_foods 表(每100克口径,换算归代码)。

    用户必须给"克数+热量";缺克数不入库,回执提示补克数(硬校验,代码当裁判)。
    """

    type: Literal["user_food_def"] = "user_food_def"
    name: str = Field(description="用户对这个食物的叫法,原样保留")
    grams: float | None = Field(
        None, description="基准克数(用户报的热量对应多少克);用户没给克数必须不填,绝不猜"
    )
    kcal: float = Field(description="该克数对应的热量,用户报的数原样填")
    protein: float | None = Field(None, description="该克数对应的蛋白质克数,没报不填")
    fat: float | None = Field(None, description="该克数对应的脂肪克数,没报不填")
    cho: float | None = Field(None, description="该克数对应的碳水克数,没报不填")
    fiber: float | None = Field(None, description="该克数对应的纤维克数,没报不填")


class ParsedMemory(BaseModel):
    """用户要求记住的叫法/习惯 → ai_memories 表,解析时注入 prompt。"""

    type: Literal["memory"] = "memory"
    kind: Literal["alias", "habit"] = Field(
        description="alias=叫法对应(我说X指的是Y);habit=习惯或长期事实"
    )
    content: str = Field(description="一句话陈述要记住的内容,自包含、无上下文也能懂")


ParsedItem = Annotated[
    ParsedExercise
    | ParsedFood
    | ParsedDish
    | ParsedWeight
    | ParsedUserFoodDef
    | ParsedMemory,
    Field(discriminator="type"),
]


class ParseOutput(BaseModel):
    items: list[ParsedItem]


class NameRemap(BaseModel):
    """微循环第二轮:未命中的名字 → 从候选里挑标准名,挑不出给 null。"""

    mapping: dict[str, str | None]


class TriageSegment(BaseModel):
    """分诊切出的一段:类型+原文片段(照抄原句子串,代码机器校验)。"""

    type: Literal["eat", "exercise", "weight", "remember"]
    text: str = Field(description="对应原话的片段,一字不改照抄")
    meal_slot: MealSlot | None = Field(
        None, description="仅 eat 段且用户明说哪一顿才填;没明说必须 null"
    )
    weight_kg: float | None = Field(
        None, description="仅 weight 段:公斤数,分诊直接出结果不发子任务"
    )


class TriageOutput(BaseModel):
    """分诊输出(提示词JSON通道:开思考的端点不支持强制结构化输出)。"""

    segments: list[TriageSegment]


class MemoryItem(BaseModel):
    kind: Literal["alias", "habit", "correction"]
    content: str


class ConsolidatedMemories(BaseModel):
    """每日巩固:输入现有记忆全量,输出合并去重后的新全量(整层替换)。"""

    memories: list[MemoryItem]
