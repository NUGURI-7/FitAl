import { ChevronLeft, ChevronRight, TrendingUp } from "lucide-react";
import type { DaySummary } from "@/types";

/** 顶部常驻区:日期切换 + 当日汇总条(切日期/曲线面板接后端时启用) */
export function TopBar({ day }: { day: DaySummary }) {
  return (
    <header className="sticky top-0 z-20 border-b border-hairline bg-paper/85 backdrop-blur-md">
      <div className="mx-auto max-w-md px-4 pt-[env(safe-area-inset-top)]">
        {/* 日期切换 */}
        <div className="flex items-center justify-between py-2">
          <button
            type="button"
            className="flex size-8 items-center justify-center rounded-full text-ink-soft active:bg-hairline"
            aria-label="前一天"
          >
            <ChevronLeft size={20} />
          </button>
          <div className="text-center leading-tight">
            <div className="text-[17px] font-semibold">今天</div>
            <div className="text-[11px] text-ink-soft">
              {day.dateLabel} {day.weekdayLabel}
            </div>
          </div>
          <button
            type="button"
            className="flex size-8 items-center justify-center rounded-full text-ink-soft/40"
            aria-label="后一天"
            disabled
          >
            <ChevronRight size={20} />
          </button>
        </div>

        {/* 汇总条:摄入 / 消耗 / 体重(点体重出曲线,第三步接) */}
        <div className="rise mt-2 mb-3.5 grid grid-cols-3 divide-x divide-hairline rounded-2xl bg-card shadow-[0_1px_2px_rgba(38,35,29,0.06)] ring-1 ring-black/[0.04]">
          <div className="px-4 py-3">
            <div className="text-[11px] font-medium text-intake">摄入</div>
            <div className="num text-[24px] font-bold leading-8">
              {day.intakeKcal}
              <span className="ml-0.5 text-[11px] font-normal text-ink-soft">
                千卡
              </span>
            </div>
          </div>
          <div className="px-4 py-3">
            <div className="text-[11px] font-medium text-burn">消耗</div>
            <div className="num text-[24px] font-bold leading-8">
              {day.burnKcal}
              <span className="ml-0.5 text-[11px] font-normal text-ink-soft">
                千卡
              </span>
            </div>
          </div>
          <button type="button" className="px-4 py-3 text-left active:bg-paper/60">
            <div className="flex items-center gap-1 text-[11px] font-medium text-steel">
              体重 <TrendingUp size={11} strokeWidth={2.5} />
            </div>
            <div className="num text-[24px] font-bold leading-8">
              {day.weightKg ?? "–"}
              <span className="ml-0.5 text-[11px] font-normal text-ink-soft">
                kg
              </span>
            </div>
          </button>
        </div>
      </div>
    </header>
  );
}
