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

const TINT = {
  green: "#3a735026",
  orange: "#d4551f22",
  steel: "#40679b26",
} as const;

function StatCard({
  label,
  labelCls,
  tint,
  value,
  unit,
  caption,
  onClick,
  icon,
  delay,
}: {
  label: string;
  labelCls: string;
  tint: keyof typeof TINT;
  value: string;
  unit: string;
  caption?: string;
  onClick?: () => void;
  icon?: boolean;
  delay: number;
}) {
  const Tag = onClick ? "button" : "div";
  return (
    <Tag
      {...(onClick ? { type: "button" as const, onClick } : {})}
      className={`rise relative flex-1 overflow-hidden rounded-2xl bg-card px-3 py-2.5 text-left shadow-[0_1px_2px_rgba(38,35,29,0.06)] ring-1 ring-black/[0.04] ${
        onClick ? "active:bg-paper/60" : ""
      }`}
      style={{ animationDelay: `${delay}ms` }}
    >
      <div
        className="absolute -top-5 -right-5 size-14 rounded-full blur-xl transition-colors duration-700"
        style={{ background: TINT[tint] }}
      />
      <div className="relative">
        <div
          className={`flex items-center gap-1 text-[11px] font-medium transition-colors duration-700 ${labelCls}`}
        >
          {label}
          {icon && <TrendingUp size={11} strokeWidth={2.5} />}
        </div>
        <div className="num text-[21px] leading-8 font-bold">
          {value}
          <span className="ml-0.5 text-[10px] font-normal text-ink-soft">
            {unit}
          </span>
        </div>
        <div className="h-3.5 text-[9px] leading-3.5 text-ink-soft/80">
          {caption ?? ""}
        </div>
      </div>
    </Tag>
  );
}

interface Props {
  day: DaySummary | null;
  atToday: boolean;
  prevWeight: { kg: number; at: Date } | null;
  onWeightClick: () => void;
}

/** 汇总行:净摄入 / 消耗 / 体重 三张独立小卡,与记录卡同风格。
 * 净摄入 = 摄入 − 基础代谢 − 运动净耗;今天的基础代谢按已过时间折算,
 * 纯本地乘法每分钟自刷,不轮询服务器。 */
export function Hero({ day, atToday, prevWeight, onWeightClick }: Props) {
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
    burnTotal = day.bmrKcal * frac + day.burnNetKcal;
    net = day.intakeKcal - burnTotal;
  }
  const deficit = (net ?? 0) < 0;
  const netAnim = useCountUp(net == null ? 0 : Math.abs(net));
  const burnAnim = useCountUp(burnTotal ?? 0);

  const todayKg = day?.weightKg ?? null;
  const shownKg = todayKg ?? prevWeight?.kg ?? null;
  const delta =
    todayKg != null && prevWeight != null ? todayKg - prevWeight.kg : null;

  return (
    <div className="flex gap-2 pt-2">
      <StatCard
        label={deficit ? "净消耗" : "净摄入"}
        labelCls={deficit ? "text-burn" : "text-intake"}
        tint={deficit ? "orange" : "green"}
        value={net == null ? "–" : String(Math.round(netAnim))}
        unit="千卡"
        delay={40}
      />
      <StatCard
        label="消耗"
        labelCls="text-burn"
        tint="orange"
        value={burnTotal == null ? "–" : String(Math.round(burnAnim))}
        unit="千卡"
        caption="基础代谢+运动"
        delay={110}
      />
      <StatCard
        label="体重"
        labelCls="text-steel"
        tint="steel"
        value={shownKg == null ? "–" : shownKg.toFixed(1)}
        unit="kg"
        caption={
          delta != null
            ? `${delta > 0 ? "+" : ""}${delta.toFixed(1)} 较上次`
            : prevWeight && todayKg == null
              ? `上次 ${prevWeight.at.getMonth() + 1}/${prevWeight.at.getDate()}`
              : "看曲线"
        }
        onClick={onWeightClick}
        icon
        delay={180}
      />
    </div>
  );
}
