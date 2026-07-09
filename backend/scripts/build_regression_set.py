"""构建回归测试集:从 raw 层两张记录表捞全部真实原话,去重后写 JSON。

原话来源:food_records / exercise_records 的 raw_text 列(现状:原句整句复制到每条记录)。
库里捞不到的考题手工补:炸500未入库的错例原句、纯体重句(体重表无原话列)、
"记住"指令句(只落自定义表/记忆表,均无原话列)。

只读库,不写库;输出 tests/regression_cases.json(进仓库,考题固定可重复)。
运行:backend 目录下 uv run python scripts/build_regression_set.py
"""

import asyncio
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from tortoise import Tortoise

from app.db import TORTOISE_ORM
from app.models import ExerciseRecord, FoodRecord

CST = ZoneInfo("Asia/Shanghai")
OUT_PATH = Path(__file__).parent.parent / "tests" / "regression_cases.json"

# 库里捞不到的考题(text, note)
MANUAL_CASES = [
    ("140克生米煮成的米饭", "错例②原句:整句炸500未入库,拆两条+缺克数死循环"),
    (
        "90分钟胸训,5组40kg卧推,3组50kg卧推,3组二头弯举,3组12次悬垂举腿",
        "错例④原句(按看板描述还原):缺次数打回重试耗尽炸500",
    ),
    ("今天75公斤", "纯体重句:体重表无原话列,库里捞不到"),
    ("记住一勺蛋白粉是30克120千卡", "记住指令句:只落自定义表,无原话列"),
]


async def main() -> None:
    await Tortoise.init(config=TORTOISE_ORM)

    # text -> 首次出现时间(两表合并取最早)
    first_seen: dict[str, object] = {}
    for model in (FoodRecord, ExerciseRecord):
        rows = await model.all().values("raw_text", "created_at")
        for row in rows:
            text = row["raw_text"].strip()
            if not text:
                continue
            at = row["created_at"]
            if text not in first_seen or at < first_seen[text]:
                first_seen[text] = at

    cases = [
        {
            "text": text,
            "origin": "db",
            "first_seen": at.astimezone(CST).isoformat(timespec="seconds"),
            "note": None,
        }
        for text, at in sorted(first_seen.items(), key=lambda kv: kv[1])
    ]
    db_count = len(cases)

    added = 0
    for text, note in MANUAL_CASES:
        if text not in first_seen:
            cases.append(
                {"text": text, "origin": "manual", "first_seen": None, "note": note}
            )
            added += 1

    OUT_PATH.write_text(
        json.dumps({"cases": cases}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"库里捞到去重原话 {db_count} 句,手工补 {added} 句,共 {len(cases)} 句")
    print(f"已写入 {OUT_PATH}")
    print("前5句预览:")
    for case in cases[:5]:
        print(f"  [{case['first_seen']}] {case['text']}")

    await Tortoise.close_connections()


asyncio.run(main())
