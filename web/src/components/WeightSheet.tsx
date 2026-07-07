import { useEffect, useRef, useState } from "react";
import { LineChart } from "echarts/charts";
import { GridComponent, TooltipComponent } from "echarts/components";
import * as echarts from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { fetchWeights, type WeightPoint } from "@/api";
import { Sheet } from "@/components/Sheet";

echarts.use([LineChart, GridComponent, TooltipComponent, CanvasRenderer]);

const STEEL = "#40679b";
const INK_SOFT = "#8d877b";
const HAIRLINE = "#e8e4da";

/** 体重曲线抽屉:近30天,单序列折线(文字用墨色,序列色只给线) */
export function WeightSheet({ onClose }: { onClose: () => void }) {
  const [points, setPoints] = useState<WeightPoint[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const chartRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchWeights()
      .then(setPoints)
      .catch((e) => setError(e instanceof Error ? e.message : "加载失败"));
  }, []);

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
        valueFormatter: (v: number) => `${v} kg`,
      },
      xAxis: {
        type: "category",
        data: points.map((p) => `${p.at.getMonth() + 1}/${p.at.getDate()}`),
        boundaryGap: false,
        axisLine: { lineStyle: { color: HAIRLINE } },
        axisTick: { show: false },
        axisLabel: { color: INK_SOFT, fontSize: 10 },
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
          data: points.map((p) => p.kg),
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
    </Sheet>
  );
}
