"""回归基线运行器:把考题集逐句灌进当前管线,离线解析并记录结果/耗时/成败。

上下文照抄 /chat 的真实组装(档案=最新体重+身体档案、自定义食物键、全量记忆,
均从库只读取来);两处为可重复性刻意固定:不带开放场次摘要、组间隔按首组算
(这两样依赖跑的时刻,带上会让两次运行不可比)。

只读库、不写库、不落任何记录;逐句串行(耗时才是真实单句延迟)。
输出 tests/regression_baseline.json(基线答案,与考题分开存)。
运行:backend 目录下 PYTHONPATH=. uv run python scripts/run_regression_baseline.py
"""

import asyncio
import json
import time
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from tortoise import Tortoise, timezone

from app.ai import lookup, parser
from app.config import settings
from app.db import TORTOISE_ORM
from app.models import AiMemory, User, UserFood, WeightRecord

USER_ID = 1
CASES_PATH = Path(__file__).parent.parent / "tests" / "regression_cases.json"
OUT_PATH = Path(__file__).parent.parent / "tests" / "regression_baseline.json"


def _dump_record(rec) -> dict:
    body = asdict(rec) if is_dataclass(rec) else rec.model_dump()
    return {"record_type": type(rec).__name__, **body}


async def main() -> None:
    await Tortoise.init(config=TORTOISE_ORM)

    user = await User.get(id=USER_ID)
    latest_weight = await WeightRecord.filter(user=user).order_by("-created_at").first()
    profile = parser.Profile(
        weight_kg=latest_weight.weight_kg,
        height_cm=user.height_cm,
        sex=user.sex,
        birth_year=user.birth_year,
    )
    user_foods = {
        (lookup.norm_key(uf.name), uf.unit): parser.UserFoodDef(
            name=uf.name,
            kcal=uf.kcal,
            unit=uf.unit,
            kcal_per_unit=uf.kcal_per_unit,
            protein=uf.protein,
            fat=uf.fat,
            cho=uf.cho,
            fiber=uf.fiber,
        )
        for uf in await UserFood.filter(user=user)
    }
    memory_rows = await AiMemory.filter(user=user).order_by("updated_at")
    memories = ";".join(r.content for r in memory_rows) or None

    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))["cases"]
    results = []
    ok_count = 0
    for i, case in enumerate(cases, 1):
        text = case["text"]
        now = timezone.now()
        t0 = time.perf_counter()
        try:
            parsed = await parser.parse_text(
                text,
                now=now,
                user_food_keys=frozenset(k for k, _ in user_foods),
                open_session=None,
                memories=memories,
            )
            resolved = parser.build_records(
                parsed,
                profile=profile,
                now=now,
                last_exercise_at=None,
                user_foods=user_foods,
            )
            elapsed = round(time.perf_counter() - t0, 2)
            results.append(
                {
                    "text": text,
                    "ok": True,
                    "seconds": elapsed,
                    "records": [_dump_record(r) for r in resolved],
                }
            )
            ok_count += 1
            print(f"[{i}/{len(cases)}] ok {elapsed}s {len(resolved)}条  {text[:30]}")
        except Exception as e:  # noqa: BLE001 基线要如实记录一切失败,不中断整批
            elapsed = round(time.perf_counter() - t0, 2)
            results.append(
                {
                    "text": text,
                    "ok": False,
                    "seconds": elapsed,
                    "error": f"{type(e).__name__}: {e}",
                }
            )
            print(f"[{i}/{len(cases)}] FAIL {elapsed}s  {text[:30]}")

    seconds = [r["seconds"] for r in results]
    summary = {
        "pipeline": "v1-single-call",
        "model": settings.LLM_MODEL,
        "run_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
        "context": {
            "profile": asdict(profile),
            "user_food_keys": sorted(user_foods),
            "memories": memories,
            "open_session": None,
            "last_exercise_at": None,
        },
        "total": len(results),
        "ok": ok_count,
        "failed": len(results) - ok_count,
        "seconds_avg": round(sum(seconds) / len(seconds), 2),
        "seconds_max": max(seconds),
    }
    OUT_PATH.write_text(
        json.dumps(
            {"summary": summary, "results": results}, ensure_ascii=False, indent=2
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        f"\n{summary['ok']}/{summary['total']} 句成功,平均 {summary['seconds_avg']}s,"
        f"最慢 {summary['seconds_max']}s\n已写入 {OUT_PATH}"
    )

    await Tortoise.close_connections()


asyncio.run(main())
