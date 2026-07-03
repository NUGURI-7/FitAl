"""LLM 输出 schema:structured output 强约束(决策 3)。

LLM 只输出"结构"(名称/数量/档位);除用户自报数与末路估算外不含热量数
(决策 2:AI 定结构,表定数值)。
"""

from typing import Annotated, Literal

from pydantic import BaseModel, Field


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


class ParsedWeight(BaseModel):
    type: Literal["weight"] = "weight"
    weight_kg: float


ParsedItem = Annotated[
    ParsedExercise | ParsedFood | ParsedWeight, Field(discriminator="type")
]


class ParseOutput(BaseModel):
    items: list[ParsedItem]


class NameRemap(BaseModel):
    """微循环第二轮:未命中的名字 → 从候选里挑标准名,挑不出给 null。"""

    mapping: dict[str, str | None]
