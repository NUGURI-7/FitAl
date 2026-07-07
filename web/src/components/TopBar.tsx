import { ChevronLeft, ChevronRight } from "lucide-react";

interface Props {
  dateLabel: string;
  subLabel: string;
  atToday: boolean;
  onPrev: () => void;
  onNext: () => void;
}

/** 顶部常驻:只留日期切换条;汇总数字在英雄区(随内容滚动) */
export function TopBar({ dateLabel, subLabel, atToday, onPrev, onNext }: Props) {
  return (
    <header className="sticky top-0 z-20 border-b border-hairline bg-paper/85 backdrop-blur-md">
      <div className="mx-auto flex max-w-md items-center justify-between px-4 py-2 pt-[max(0.5rem,env(safe-area-inset-top))]">
        <button
          type="button"
          onClick={onPrev}
          className="flex size-8 items-center justify-center rounded-full text-ink-soft active:bg-hairline"
          aria-label="前一天"
        >
          <ChevronLeft size={20} />
        </button>
        <div className="text-center leading-tight">
          <div className="text-[17px] font-semibold">{dateLabel}</div>
          <div className="text-[11px] text-ink-soft">{subLabel}</div>
        </div>
        <button
          type="button"
          onClick={onNext}
          disabled={atToday}
          className={`flex size-8 items-center justify-center rounded-full ${
            atToday ? "text-ink-soft/30" : "text-ink-soft active:bg-hairline"
          }`}
          aria-label="后一天"
        >
          <ChevronRight size={20} />
        </button>
      </div>
    </header>
  );
}
