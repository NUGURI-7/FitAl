import { useCallback, useEffect, useRef, useState } from "react";
import { LineChart } from "echarts/charts";
import { GridComponent, TooltipComponent } from "echarts/components";
import * as echarts from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { Trash2 } from "lucide-react";
import { deleteRecord, fetchWeights, patchRecord, type WeightPoint } from "@/api";
import { Sheet } from "@/components/Sheet";

echarts.use([LineChart, GridComponent, TooltipComponent, CanvasRenderer]);

const STEEL = "#40679b";
const INK_SOFT = "#8d877b";
const HAIRLINE = "#e8e4da";

const hm = (d: Date) =>
  d.toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });

/** 体重曲线抽屉:近30天,单序列折线(文字用墨色,序列色只给线);
 * 曲线下挂全部记录,点数值改公斤数(时间不动),垃圾桶两击删除 */
export function WeightSheet({
  onClose,
  onChanged,
}: {
  onClose: () => void;
  onChanged: () => void;
}) {
  const [points, setPoints] = useState<WeightPoint[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [opError, setOpError] = useState<string | null>(null);
  const [editId, setEditId] = useState<number | null>(null);
  const [editVal, setEditVal] = useState("");
  const [armedId, setArmedId] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const chartRef = useRef<HTMLDivElement>(null);
  const armTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const load = useCallback(
    () =>
      fetchWeights()
        .then(setPoints)
        .catch((e) => setError(e instanceof Error ? e.message : "加载失败")),
    [],
  );
  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!points || points.length === 0 || !chartRef.current) return;
    const chart = echarts.init(chartRef.current);
    chart.setOption({
      grid: { left: 8, right: 16, top: 20, bottom: 4, containLabel: true },
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "line", lineStyle: { color: INK_SOFT } },
        backgroundColor: "#ffffff",
        borderColor: HAIRLINE,
        textStyle: { color: "#26231d", fontSize: 12 },
        formatter: (params: { value: [number, number] }[]) => {
          const [ts, kg] = params[0].value;
          const d = new Date(ts);
          return `${d.getMonth() + 1}月${d.getDate()}日 ${hm(d)} · ${kg} kg`;
        },
      },
      // 时间轴:点按真实称重时刻落位(下午称的偏向下一天),而非一条一格等距
      xAxis: {
        type: "time",
        axisLine: { lineStyle: { color: HAIRLINE } },
        axisTick: { show: false },
        axisLabel: {
          color: INK_SOFT,
          fontSize: 10,
          formatter: "{M}/{d}",
          hideOverlap: true,
        },
        splitLine: { show: false },
      },
      yAxis: {
        type: "value",
        min: (v: { min: number }) => Math.floor(v.min - 0.5),
        max: (v: { max: number }) => Math.ceil(v.max + 0.5),
        splitLine: { lineStyle: { color: HAIRLINE } },
        axisLabel: { color: INK_SOFT, fontSize: 10 },
      },
      series: [
        {
          name: "体重",
          type: "line",
          data: points.map((p) => [p.at.getTime(), p.kg]),
          color: STEEL,
          lineStyle: { width: 2 },
          symbol: "circle",
          symbolSize: 7,
          smooth: 0.2,
          areaStyle: {
            color: {
              type: "linear",
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: "rgba(64,103,155,0.14)" },
                { offset: 1, color: "rgba(64,103,155,0)" },
              ],
            },
          },
        },
      ],
    });
    return () => chart.dispose();
  }, [points]);

  const editing = editId != null ? points?.find((p) => p.id === editId) : null;
  const editNum = Number(editVal);
  const editOk =
    editVal.trim() !== "" && Number.isFinite(editNum) && editNum > 0;
  const changed = editOk && editing != null && editNum !== editing.kg;

  const startEdit = (p: WeightPoint) => {
    setEditId(p.id);
    setEditVal(String(p.kg));
    setArmedId(null);
    setOpError(null);
  };

  const save = async () => {
    if (editId == null) return;
    setBusy(true);
    setOpError(null);
    try {
      await patchRecord("weight", editId, { weight_kg: editNum });
      await load();
      onChanged();
      setEditId(null);
    } catch (e) {
      setOpError(e instanceof Error ? e.message : "保存失败");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id: number) => {
    if (armedId !== id) {
      setArmedId(id);
      if (armTimer.current) clearTimeout(armTimer.current);
      armTimer.current = setTimeout(() => setArmedId(null), 3000);
      return;
    }
    if (armTimer.current) clearTimeout(armTimer.current);
    setArmedId(null);
    setBusy(true);
    setOpError(null);
    try {
      await deleteRecord("weight", id);
      if (editId === id) setEditId(null);
      await load();
      onChanged();
    } catch (e) {
      setOpError(e instanceof Error ? e.message : "删除失败");
    } finally {
      setBusy(false);
    }
  };

  const latest = points?.at(-1);

  return (
    <Sheet title="体重 · 近30天" onClose={onClose}>
      {error && <p className="py-10 text-center text-[13px] text-burn">{error}</p>}
      {points && points.length === 0 && (
        <p className="py-10 text-center text-[13px] text-ink-soft">
          还没有体重记录,说一句「今天70公斤」试试
        </p>
      )}
      {latest && (
        <div className="flex items-baseline gap-2 pb-1">
          <span className="num text-[28px] font-bold">
            {latest.kg}
            <span className="ml-0.5 text-[12px] font-normal text-ink-soft">
              kg
            </span>
          </span>
          <span className="text-[11px] text-ink-soft">
            最近 · {latest.at.getMonth() + 1}月{latest.at.getDate()}日 · 共{" "}
            {points!.length} 次称重
          </span>
        </div>
      )}
      {points && points.length > 0 && (
        <div ref={chartRef} className="h-60 w-full" />
      )}

      {points && points.length > 0 && (
        <>
          <p className="px-1 pt-4 pb-2 text-[12px] font-semibold text-ink-soft">
            全部记录 · 点数值可改
          </p>
          <div className="space-y-2">
            {[...points].reverse().map((p) => (
              <div
                key={p.id}
                className="flex items-center gap-2 rounded-xl bg-card px-4 py-2.5 ring-1 ring-black/[0.04]"
              >
                <span className="text-[12px] text-ink-soft">
                  {p.at.getMonth() + 1}月{p.at.getDate()}日 {hm(p.at)}
                </span>
                {editId === p.id ? (
                  <>
                    <span className="flex flex-1 items-baseline justify-end gap-1">
                      <input
                        autoFocus
                        inputMode="decimal"
                        value={editVal}
                        onChange={(e) => setEditVal(e.target.value)}
                        className="num w-20 bg-transparent text-right text-[15px] font-semibold outline-none"
                      />
                      <span className="text-[11px] text-ink-soft">kg</span>
                    </span>
                    <button
                      type="button"
                      onClick={save}
                      disabled={!changed || busy}
                      className="rounded-lg bg-ink px-3 py-1.5 text-[12px] font-semibold text-paper disabled:opacity-25"
                    >
                      保存
                    </button>
                  </>
                ) : (
                  <button
                    type="button"
                    onClick={() => startEdit(p)}
                    className="num flex-1 text-right text-[15px] font-semibold"
                  >
                    {p.kg}
                    <span className="ml-0.5 text-[11px] font-normal text-ink-soft">
                      kg
                    </span>
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => remove(p.id)}
                  disabled={busy}
                  aria-label="删除这条体重"
                  className={`flex items-center justify-center transition-colors disabled:opacity-40 ${
                    armedId === p.id
                      ? "rounded-lg bg-burn px-2.5 py-1.5 text-[12px] font-semibold text-white"
                      : "size-7 rounded-lg text-ink-soft/50 active:bg-hairline/60"
                  }`}
                >
                  {armedId === p.id ? "确认" : <Trash2 size={14} />}
                </button>
              </div>
            ))}
          </div>
          {opError && (
            <p className="px-1 pt-2 text-[12px] text-burn">{opError}</p>
          )}
        </>
      )}
    </Sheet>
  );
}
