"""从 Sanotsu/china-food-composition-data 生成 app/data/food.json。

用法:
    git clone --depth 1 https://github.com/Sanotsu/china-food-composition-data.git <源目录>
    cd backend && uv run python scripts/build_food_json.py --source <源目录>

数据主库取视觉模型最新修正版(json_data_vision_251206_*),三道校验:
1. 数值清洗:"Tr"(微量)→0,"—"等缺失→None,无法解析→None
2. 能量粗校验:kcal ≈ 4×蛋白 + 9×脂肪 + 4×(碳水-纤维) + 2×纤维,偏差过大标记
   (专抓 OCR 把 energyKJ 错认进 energyKCal 这类数量级错误)
3. 双版本交叉比对:与 OCR 版(json_data)按 foodCode 逐条对核心数值

缺名称、缺 kcal、能量校验不过、或两版本 kcal 严重不一致的条目不进 food.json,
写入 scripts/food_needs_review.json 供人工核对;其余字段的不一致仅记为 advisory。

补充工序:视觉版提取时丢失的条目(馒头/花卷/煮面条等,仅存在于 OCR 旧版),
过同一套质检后并入;婴幼儿食品类目维持排除(品牌商品数据,非通用食物)。
"""

import argparse
import json
import re
from pathlib import Path

VISION_DIR = "json_data_vision_251206_Qwen2-5-VL-72B-Instruct"
OCR_DIR = "json_data"
CHECK_FIELDS = ["energyKCal", "protein", "fat", "CHO", "dietaryFiber"]


def parse_num(raw) -> float | None:
    """'Tr'→0(微量),'—'/'…'/空/非数字→None,去掉 '*' 星号与括号注记。"""
    if raw is None:
        return None
    s = str(raw).strip().replace("＊", "").replace("*", "")
    s = s.replace("（", "(").replace("）", ")")
    if s.lower() == "tr":
        return 0.0
    s = re.sub(r"\(.*?\)", "", s).replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def split_name(raw: str) -> tuple[str, list[str]]:
    """'番茄[西红柿]' → ('番茄', ['西红柿']);全角括号统一为半角。"""
    s = re.sub(r"\s+", "", str(raw))
    s = s.replace("［", "[").replace("］", "]")
    s = s.replace("（", "(").replace("）", ")")
    aliases: list[str] = []
    for m in re.findall(r"\[(.+?)\]", s):
        aliases += [a for a in re.split(r"[、,，/]", m) if a]
    name = re.sub(r"\[.+?\]", "", s)
    return name, aliases


def atwater_reason(kcal, protein, fat, cho, fiber) -> str | None:
    p, f, c, fib = (x or 0.0 for x in (protein, fat, cho, fiber))
    est = 4 * p + 9 * f + 4 * max(c - fib, 0) + 2 * fib
    if abs(kcal - est) > max(30, 0.35 * max(est, 20)):
        return f"能量校验不过:标注{kcal},按宏量估算≈{est:.0f}"
    return None


def load_dir(root: Path, dirname: str) -> dict[str, tuple[str, dict]]:
    """返回 foodCode → (category, 原始条目)。category 取自文件名。"""
    out: dict[str, tuple[str, dict]] = {}
    for fp in sorted((root / dirname).glob("merged*.json")):
        category = re.sub(r"^merged[_-]", "", fp.stem)
        for entry in json.loads(fp.read_text(encoding="utf-8")):
            code = str(entry.get("foodCode", "")).strip()
            if code:
                out[code] = (category, entry)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--source", required=True, help="china-food-composition-data 克隆目录"
    )
    args = ap.parse_args()
    root = Path(args.source)
    backend = Path(__file__).resolve().parents[1]

    vision = load_dir(root, VISION_DIR)
    ocr = load_dir(root, OCR_DIR)

    items, excluded, advisory, merged_from_old = [], [], [], []
    for code, (category, entry) in sorted(vision.items()):
        name, aliases = split_name(entry.get("foodName", ""))
        kcal = parse_num(entry.get("energyKCal"))
        protein = parse_num(entry.get("protein"))
        fat = parse_num(entry.get("fat"))
        cho = parse_num(entry.get("CHO"))
        fiber = parse_num(entry.get("dietaryFiber"))

        reasons = []
        if not name:
            reasons.append("缺名称")
        if kcal is None:
            reasons.append("缺 kcal")
        else:
            atwater = atwater_reason(kcal, protein, fat, cho, fiber)
            if atwater:
                reasons.append(atwater)

        # 与 OCR 版交叉比对(仅两边都有数的字段;kcal 不一致才排除)
        cross_notes = []
        if code in ocr:
            for field in CHECK_FIELDS:
                a = parse_num(entry.get(field))
                b = parse_num(ocr[code][1].get(field))
                if a is None or b is None:
                    continue
                if abs(a - b) > 2 and abs(a - b) > 0.15 * max(abs(a), abs(b)):
                    cross_notes.append(f"{field}: 视觉版{a} ≠ OCR版{b}")
        # kcal 两版不一致时以能量校验仲裁:视觉版能通过校验则采信,否则排除
        if not reasons and any(n.startswith("energyKCal") for n in cross_notes):
            cross_notes.insert(0, "kcal 两版不一致,视觉版通过能量校验,已采视觉版")

        record = {
            "code": code,
            "name": name,
            "aliases": aliases,
            "category": category,
            "kcal": kcal,
            "protein": protein,
            "fat": fat,
            "cho": cho,
            "fiber": fiber,
        }
        if reasons:
            excluded.append({**record, "reasons": reasons})
        else:
            if cross_notes:
                advisory.append({"code": code, "name": name, "notes": cross_notes})
            items.append(record)

    # 补充工序:仅旧版存在的条目(视觉版丢失),同一套质检后并入
    for code, (category, entry) in sorted(ocr.items()):
        if code in vision or "婴" in category:
            continue
        name, aliases = split_name(entry.get("foodName", ""))
        kcal = parse_num(entry.get("energyKCal"))
        protein = parse_num(entry.get("protein"))
        fat = parse_num(entry.get("fat"))
        cho = parse_num(entry.get("CHO"))
        fiber = parse_num(entry.get("dietaryFiber"))

        reasons = []
        if not name:
            reasons.append("缺名称")
        if kcal is None:
            reasons.append("缺 kcal")
        else:
            atwater = atwater_reason(kcal, protein, fat, cho, fiber)
            if atwater:
                reasons.append(atwater)

        record = {
            "code": code,
            "name": name,
            "aliases": aliases,
            "category": category,
            "kcal": kcal,
            "protein": protein,
            "fat": fat,
            "cho": cho,
            "fiber": fiber,
        }
        if reasons:
            excluded.append({**record, "reasons": ["仅旧版(OCR)存在"] + reasons})
        else:
            merged_from_old.append({"code": code, "name": name})
            items.append(record)

    items.sort(key=lambda r: r["code"])

    food_json = {
        "meta": {
            "source": "《中国食物成分表标准版(第6版)》,经 Sanotsu/china-food-composition-data "
            f"({VISION_DIR}) 提取,本脚本清洗校验",
            "per": "每100g可食部",
            "count": len(items),
        },
        "items": items,
    }
    out_path = backend / "app" / "data" / "food.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(food_json, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )

    review_path = backend / "scripts" / "food_needs_review.json"
    review_path.write_text(
        json.dumps(
            {
                "excluded": excluded,
                "advisory_kept_vision_value": advisory,
                "merged_from_old_version": merged_from_old,
            },
            ensure_ascii=False,
            indent=1,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        f"视觉版共 {len(vision)} 条;入库 {len(items)} 条 → {out_path.relative_to(backend)}"
    )
    print(f"排除 {len(excluded)} 条(人工核对清单:{review_path.relative_to(backend)}):")
    for e in excluded:
        print(f"  - [{e['code']}] {e['name']}: {'; '.join(e['reasons'])}")
    print(f"advisory(非 kcal 字段两版不一致,已采视觉版值){len(advisory)} 条")
    print(f"自旧版补入 {len(merged_from_old)} 条:")
    for m in merged_from_old:
        print(f"  + [{m['code']}] {m['name']}")


if __name__ == "__main__":
    main()
