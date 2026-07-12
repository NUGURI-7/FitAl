import { useState } from "react";
import { ChevronDown, ChevronLeft, ChevronRight } from "lucide-react";
import { MonthPicker } from "@/components/MonthPicker";

interface Props {
  dateLabel: string;
  subLabel: string;
  atToday: boolean;
  date: Date;
  onPrev: () => void;
  onNext: () => void;
  onPick: (d: Date) => void;
}

/** 顶部常驻:日期切换条;点中间日期弹月历直达(2026-07-12 日历跳转) */
export function TopBar({
  dateLabel,
  subLabel,
  atToday,
  date,
  onPrev,
  onNext,
  onPick,
}: Props) {
  const [calOpen, setCalOpen] = useState(false);

  return (
    <header className="sticky top-0 z-20 border-b border-hairline bg-paper/85 backdrop-blur-md">
      <div className="relative mx-auto flex max-w-md items-center justify-between px-4 py-2 pt-[max(0.5rem,env(safe-area-inset-top))]">
        <button
          type="button"
          onClick={onPrev}
          className="flex size-8 items-center justify-center rounded-full text-ink-soft active:bg-hairline"
          aria-label="前一天"
        >
          <ChevronLeft size={20} />
        </button>
        <button
          type="button"
          onClick={() => setCalOpen((o) => !o)}
          className="rounded-xl px-3 py-0.5 text-center leading-tight active:bg-hairline"
          aria-label="选择日期"
        >
          <div className="flex items-center justify-center gap-1 text-[17px] font-semibold">
            {dateLabel}
            <ChevronDown
              size={13}
              className={`text-ink-soft transition-transform duration-200 ${
                calOpen ? "rotate-180" : ""
              }`}
            />
          </div>
          <div className="text-[11px] text-ink-soft">{subLabel}</div>
        </button>
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

        {calOpen && (
          <MonthPicker
            selected={date}
            onPick={(d) => {
              setCalOpen(false);
              onPick(d);
            }}
            onClose={() => setCalOpen(false)}
          />
        )}
      </div>
    </header>
  );
}
