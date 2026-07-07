import { useEffect, useRef, useState } from "react";
import { TrendingUp } from "lucide-react";
import type { DaySummary } from "@/types";

/** 数字滚动:数值变化时从旧值滚到新值 */
function useCountUp(target: number, dur = 700): number {
  const [v, setV] = useState(target);
  const prev = useRef(target);
  useEffect(() => {
    const from = prev.current;
    prev.current = target;
    if (from === target) return;
    const t0 = performance.now();
    let raf: number;
    const tick = (t: number) => {
      const p = Math.min(1, (t - t0) / dur);
      setV(from + (target - from) * (1 - (1 - p) ** 3));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, dur]);
  return v;
}

const ORB_STYLE = {
  green: {
    background:
      "radial-gradient(circle at 32% 26%, #ffffff 0%, #e9f1ea 48%, #cfe2d5 100%)",
    boxShadow: "0 14px 28px rgba(58,115,80,0.22), inset 0 1px 0 #ffffff",
  },
  orange: {
    background:
      "radial-gradient(circle at 32% 26%, #ffffff 0%, #fbece3 48%, #f3d6c2 100%)",
    boxShadow: "0 14px 28px rgba(212,85,31,0.2), inset 0 1px 0 #ffffff",
  },
} as const;

function Orb({
  label,
  caption,
  value,
  tone,
  floatCls,
}: {
  label: string;
  caption?: string;
  value: number | null;
  tone: "green" | "orange";
  floatCls: string;
}) {
  const anim = useCountUp(value ?? 0);
  return (
    <div
      className={`${floatCls} flex size-32 flex-col items-center justify-center rounded-full`}
      style={ORB_STYLE[tone]}
    >
      <div
        className={`text-[11px] font-semibold ${
          tone === "green" ? "text-intake" : "text-burn"
        }`}
      >
        {label}
      </div>
      <div className="num text-[26px] leading-8 font-bold">
        {value == null ? "–" : Math.round(anim)}
        <span className="ml-0.5 text-[10px] font-normal text-ink-soft">
          千卡
        </span>
      </div>
      {caption && (
        <div className="text-[9px] text-ink-soft/80">{caption}</div>
      )}
    </div>
  );
}

interface Props {
  day: DaySummary | null;
  atToday: boolean;
  prevWeight: { kg: number; at: Date } | null;
  spark: number[];
  onWeightClick: () => void;
}

/** 英雄区:左列两颗呼吸圆球(净摄入/总消耗),右侧体重动态卡。
 * 净摄入 = 摄入 − 基础代谢 − 运动净耗;今天的基础代谢按已过时间折算,
 * 纯本地乘法每分钟自刷,不轮询服务器。 */
export function Hero({ day, atToday, prevWeight, spark, onWeightClick }: Props) {
  const [, setTick] = useState(0);
  useEffect(() => {
    if (!atToday) return;
    const t = setInterval(() => setTick((n) => n + 1), 60_000);
    return () => clearInterval(t);
  }, [atToday]);

  let net: number | null = null;
  let burnTotal: number | null = null;
  if (day && day.bmrKcal != null) {
    const now = new Date();
    const midnight = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const frac = atToday
      ? Math.min(1, (now.getTime() - midnight.getTime()) / 86_400_000)
      : 1;
    const bmrUsed = day.bmrKcal * frac;
    burnTotal = bmrUsed + day.burnNetKcal;
    net = day.intakeKcal - burnTotal;
  }
  const deficit = (net ?? 0) < 0;

  const todayKg = day?.weightKg ?? null;
  const shownKg = todayKg ?? prevWeight?.kg ?? null;
  const delta =
    todayKg != null && prevWeight != null ? todayKg - prevWeight.kg : null;
  const kgAnim = useCountUp(shownKg ?? 0);

  return (
    <div className="flex gap-3 pt-2">
      <div className="flex flex-col gap-3">
        <Orb
          label={deficit ? "净消耗" : "净摄入"}
          value={net == null ? null : Math.abs(net)}
          tone={deficit ? "orange" : "green"}
          floatCls="rise float-a"
        />
        <Orb
          label="消耗"
          caption="基础代谢 + 运动"
          value={burnTotal}
          tone="orange"
          floatCls="rise float-b"
        />
      </div>

      <button
        type="button"
        onClick={onWeightClick}
        className="rise float-c relative flex-1 overflow-hidden rounded-3xl bg-card text-left ring-1 ring-black/[0.04] active:bg-paper/60"
        style={{
          boxShadow: "0 14px 28px rgba(64,103,155,0.16), inset 0 1px 0 #ffffff",
          animationDelay: "120ms",
        }}
      >
        <div className="absolute -top-8 -right-6 size-28 rounded-full bg-steel-soft blur-2xl" />
        <div className="relative flex h-full flex-col justify-between px-4 py-4">
          <div className="flex items-center gap-1 text-[11px] font-semibold text-steel">
            体重 <TrendingUp size={11} strokeWidth={2.5} />
            {todayKg == null && shownKg != null && (
              <span className="ml-1 rounded-full bg-steel-soft px-1.5 py-0.5 text-[9px] font-medium">
                上次
              </span>
            )}
          </div>

          <div>
            <div className="num text-[34px] leading-tight font-bold">
              {shownKg == null ? "–" : (Math.round(kgAnim * 10) / 10).toFixed(1)}
              <span className="ml-1 text-[12px] font-normal text-ink-soft">
                kg
              </span>
            </div>
            {delta != null && (
              <div className="num text-[11px] text-ink-soft">
                {delta > 0 ? "+" : ""}
                {delta.toFixed(1)} kg 较上次
              </div>
            )}
          </div>

          <div>
            {spark.length >= 2 && (
              <svg
                viewBox="0 0 100 30"
                preserveAspectRatio="none"
                className="h-8 w-full"
              >
                <polyline
                  points={(() => {
                    const min = Math.min(...spark);
                    const rng = Math.max(...spark) - min || 1;
                    return spark
                      .map(
                        (v, i) =>
                          `${(i / (spark.length - 1)) * 100},${
                            26 - ((v - min) / rng) * 22
                          }`,
                      )
                      .join(" ");
                  })()}
                  fill="none"
                  stroke="#40679b"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  vectorEffect="non-scaling-stroke"
                />
              </svg>
            )}
            <div className="pt-1 text-[10px] text-ink-soft/80">
              {prevWeight
                ? `上次 ${prevWeight.at.getMonth() + 1}月${prevWeight.at.getDate()}日`
                : "点击看曲线"}
            </div>
          </div>
        </div>
      </button>
    </div>
  );
}
