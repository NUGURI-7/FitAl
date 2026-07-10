"""回归对比运行器:28句考题灌新管线(分诊+专科并发),与旧管线基线同口径。

上下文与基线运行器完全一致(档案/自定义键/记忆只读取自库,不带开放场次,
组间隔按首组),唯一区别是解析走 parse_via_triage;记忆按种类分流
(叫法给分诊,全量给专科)。只读库不写库。
输出 tests/regression_pipeline.json;跑完顺带打印与基线的三数对比。
运行:backend 目录下 PYTHONPATH=. uv run python scripts/run_regression_pipeline.py
"""

import asyncio
import json
import time
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from tortoise import Tortoise, timezone

from app.ai import lookup, parser, pipeline
from app.config import settings
from app.db import TORTOISE_ORM
from app.models import AiMemory, User, UserFood, WeightRecord

USER_ID = 1
TESTS = Path(__file__).parent.parent / "tests"
CASES_PATH = TESTS / "regression_cases.json"
BASELINE_PATH = TESTS / "regression_baseline.json"
OUT_PATH = TESTS / "regression_pipeline.json"


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
        lookup.norm_key(uf.name): parser.UserFoodDef(
            name=uf.name,
            kcal=uf.kcal,
            protein=uf.protein,
            fat=uf.fat,
            cho=uf.cho,
            fiber=uf.fiber,
        )
        for uf in await UserFood.filter(user=user)
    }
    memory_rows = await AiMemory.filter(user=user).order_by("updated_at")
    alias_memories = (
        ";".join(r.content for r in memory_rows if r.kind == "alias") or None
    )
    all_memories = ";".join(r.content for r in memory_rows) or None

    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))["cases"]
    results = []
    ok = partial = failed = 0
    for i, case in enumerate(cases, 1):
        text = case["text"]
        now = timezone.now()
        rounds: dict = {}
        t0 = time.perf_counter()
        try:
            pr = await pipeline.parse_via_triage(
                text,
                now=now,
                user_food_keys=frozenset(user_foods),
                open_session=None,
                alias_memories=alias_memories,
                all_memories=all_memories,
                rounds_sink=rounds,
            )
            resolved = parser.build_records(
                pr.output,
                profile=profile,
                now=now,
                last_exercise_at=None,
                user_foods=user_foods,
            )
            elapsed = round(time.perf_counter() - t0, 2)
            results.append(
                {
                    "text": text,
                    "ok": pr.status == "ok",
                    "status": pr.status,
                    "seconds": elapsed,
                    "failed_tracks": pr.failed_tracks or None,
                    "records": [_dump_record(r) for r in resolved],
                    "rounds": rounds,
                }
            )
            if pr.status == "ok":
                ok += 1
            else:
                partial += 1
            print(
                f"[{i}/{len(cases)}] {pr.status} {elapsed}s "
                f"{len(resolved)}条  {text[:30]}"
            )
        except Exception as e:  # noqa: BLE001 如实记录一切失败,不中断整批
            elapsed = round(time.perf_counter() - t0, 2)
            failed += 1
            results.append(
                {
                    "text": text,
                    "ok": False,
                    "status": "failed",
                    "seconds": elapsed,
                    "error": f"{type(e).__name__}: {e}",
                    "rounds": rounds,
                }
            )
            print(f"[{i}/{len(cases)}] FAIL {elapsed}s  {text[:30]}")

    seconds = [r["seconds"] for r in results]
    summary = {
        "pipeline": "v2-triage-concurrent",
        "model": settings.LLM_MODEL,
        "run_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
        "context": {
            "profile": asdict(profile),
            "user_food_keys": sorted(user_foods),
            "alias_memories": alias_memories,
            "all_memories": all_memories,
            "open_session": None,
            "last_exercise_at": None,
        },
        "total": len(results),
        "ok": ok,
        "partial": partial,
        "failed": failed,
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

    base = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))["summary"]
    print(
        f"\n新管线: {ok}全成 {partial}部分 {failed}失败 / {len(results)}句,"
        f"平均 {summary['seconds_avg']}s,最慢 {summary['seconds_max']}s"
    )
    print(
        f"旧基线: {base['ok']}成 {base['failed']}败 / {base['total']}句,"
        f"平均 {base['seconds_avg']}s,最慢 {base['seconds_max']}s"
    )
    print(f"已写入 {OUT_PATH}")

    await Tortoise.close_connections()


asyncio.run(main())
