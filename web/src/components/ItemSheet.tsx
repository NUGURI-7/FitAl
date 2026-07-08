import { useState } from "react";
import { Trash2 } from "lucide-react";
import { deleteRecord, patchRecord } from "@/api";
import { Sheet } from "@/components/Sheet";
import { SourceBadge } from "@/components/SourceBadge";
import type { RecordItem } from "@/types";

function Field({
  label,
  unit,
  value,
  onChange,
  integer = false,
}: {
  label: string;
  unit: string;
  value: string;
  onChange: (v: string) => void;
  integer?: boolean;
}) {
  return (
    <label className="flex items-center justify-between rounded-xl bg-card px-4 py-3 ring-1 ring-black/[0.04]">
      <span className="text-[13px] text-ink-soft">{label}</span>
      <span className="flex items-baseline gap-1">
        <input
          inputMode={integer ? "numeric" : "decimal"}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="num w-24 bg-transparent text-right text-[16px] font-semibold outline-none"
        />
        <span className="w-8 text-[11px] text-ink-soft">{unit}</span>
      </span>
    </label>
  );
}

const str = (n: number | null) => (n == null ? "" : String(+n.toFixed(1)));

/** 明细改删抽屉:改份量→后端重算;直接改热量→记为自报;删除需二次确认 */
export function ItemSheet({
  item,
  onClose,
  onDone,
}: {
  item: RecordItem;
  onClose: () => void;
  onDone: (msg: string) => void;
}) {
  const isFood = item.kind === "food";
  const [grams, setGrams] = useState(str(item.grams));
  const [duration, setDuration] = useState(str(item.durationMin));
  const [load, setLoad] = useState(str(item.loadKg));
  const [reps, setReps] = useState(item.reps == null ? "" : String(item.reps));
  const [kcalStr, setKcalStr] = useState(String(item.kcal));
  const [armed, setArmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 只把"改过且有效"的字段收进请求体
  const body: Record<string, number> = {};
  const collect = (
    key: string,
    input: string,
    original: number | null,
    integer = false,
  ) => {
    if (input.trim() === "") return true; // 留空=不改
    const n = Number(input);
    if (!Number.isFinite(n) || n <= 0 || (integer && !Number.isInteger(n))) {
      return false;
    }
    if (original == null || Math.abs(n - original) > 1e-9) body[key] = n;
    return true;
  };
  const valid = isFood
    ? collect("grams", grams, item.grams) &&
      collect("kcal", kcalStr, item.kcal)
    : collect("duration_min", duration, item.durationMin) &&
      collect("load_kg", load, item.loadKg) &&
      collect("reps", reps, item.reps, true) &&
      collect("kcal", kcalStr, item.kcal);
  const changed = valid && Object.keys(body).length > 0;

  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      await patchRecord(item.kind, item.id, body);
      onDone("已更新,已重算所在分组");
    } catch (e) {
      setError(e instanceof Error ? e.message : "保存失败");
      setBusy(false);
    }
  };

  const remove = async () => {
    if (!armed) {
      setArmed(true);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await deleteRecord(item.kind, item.id);
      onDone("已删除");
    } catch (e) {
      setError(e instanceof Error ? e.message : "删除失败");
      setBusy(false);
    }
  };

  const nutrition = [
    ["蛋白质", item.protein],
    ["脂肪", item.fat],
    ["碳水", item.cho],
    ["纤维", item.fiber],
  ].filter(([, v]) => v != null) as [string, number][];

  return (
    <Sheet title={item.name} onClose={onClose}>
      <div className="flex items-center gap-2 pb-1">
        <SourceBadge source={item.source} />
        <span className="text-[12px] text-ink-soft">{item.detail}</span>
        {item.kcalNet != null && (
          <span className="text-[12px] text-ink-soft">
            · 净耗 {item.kcalNet} 千卡
          </span>
        )}
      </div>
      {item.rawName && (
        <p className="pb-2 text-[11px] text-ink-soft/70">
          成分表名:{item.rawName}
        </p>
      )}

      {nutrition.length > 0 && (
        <div className="mb-3 grid grid-cols-4 divide-x divide-hairline rounded-xl bg-card py-2.5 ring-1 ring-black/[0.04]">
          {nutrition.map(([label, v]) => (
            <div key={label} className="px-3 text-center">
              <div className="text-[10px] text-ink-soft">{label}</div>
              <div className="num text-[14px] font-semibold">
                {+v.toFixed(1)}
                <span className="text-[9px] font-normal text-ink-soft">g</span>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="space-y-2">
        {isFood && item.grams != null && (
          <Field label="克数" unit="g" value={grams} onChange={setGrams} />
        )}
        {!isFood && (
          <>
            <Field
              label="时长"
              unit="分钟"
              value={duration}
              onChange={setDuration}
            />
            {item.loadKg != null && (
              <Field label="负重" unit="kg" value={load} onChange={setLoad} />
            )}
            {item.reps != null && (
              <Field
                label="次数"
                unit="次"
                value={reps}
                onChange={setReps}
                integer
              />
            )}
          </>
        )}
        <Field label="热量" unit="千卡" value={kcalStr} onChange={setKcalStr} />
      </div>

      <p className="px-1 pt-2 text-[11px] leading-relaxed text-ink-soft/80">
        {isFood
          ? "改克数会按成分表重算热量和营养;直接改热量则采用你的数,来源改为「你报的」。"
          : "改时长会按公式重算消耗;直接改热量则采用你的数,来源改为「你报的」。"}
      </p>

      {error && <p className="px-1 pt-1 text-[12px] text-burn">{error}</p>}

      <div className="flex gap-2 pt-4">
        <button
          type="button"
          onClick={remove}
          disabled={busy}
          className={`flex items-center justify-center gap-1.5 rounded-xl px-4 py-3 text-[15px] font-semibold transition-colors disabled:opacity-40 ${
            armed ? "bg-burn text-white" : "bg-burn-soft text-burn"
          }`}
        >
          <Trash2 size={15} />
          {armed ? "确认删除" : "删除"}
        </button>
        <button
          type="button"
          onClick={save}
          disabled={!changed || busy}
          className="flex-1 rounded-xl bg-ink py-3 text-[15px] font-semibold text-paper disabled:opacity-25"
        >
          {busy ? "处理中…" : "保存修改"}
        </button>
      </div>
    </Sheet>
  );
}
