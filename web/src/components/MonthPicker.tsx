import { useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { isToday, toISODate } from "@/lib/date";

interface Props {
  /** 当前正在看的日子(打开时定位到它所在的月) */
  selected: Date;
  onPick: (d: Date) => void;
  onClose: () => void;
}

const WEEKDAYS = ["日", "一", "二", "三", "四", "五", "六"];

/** 轻量月历浮层:点日期直达,未来日不可选,翻月不越过当前月 */
export function MonthPicker({ selected, onPick, onClose }: Props) {
  // 展示的月份:该月1号
  const [month, setMonth] = useState(
    () => new Date(selected.getFullYear(), selected.getMonth(), 1),
  );

  const today = new Date();
  const curMonth = new Date(today.getFullYear(), today.getMonth(), 1);
  const atCurrentMonth = month.getTime() >= curMonth.getTime();
  const todayISO = toISODate(today);
  const selectedISO = toISODate(selected);

  const daysInMonth = new Date(
    month.getFullYear(),
    month.getMonth() + 1,
    0,
  ).getDate();
  const leadingBlanks = month.getDay(); // 1号是周几,前面垫空格

  const cells: (Date | null)[] = [
    ...Array.from({ length: leadingBlanks }, () => null),
    ...Array.from(
      { length: daysInMonth },
      (_, i) => new Date(month.getFullYear(), month.getMonth(), i + 1),
    ),
  ];

  return (
    <>
      {/* 点空白处收起 */}
      <button
        type="button"
        aria-label="收起日历"
        onClick={onClose}
        className="fixed inset-0 z-20 cursor-default"
      />
      <div className="rise absolute top-full left-1/2 z-30 mt-2 w-[19.5rem] -translate-x-1/2 rounded-2xl bg-card p-3 shadow-[0_12px_40px_rgba(38,35,29,0.18)] ring-1 ring-black/[0.06]">
        {/* 月份导航 */}
        <div className="flex items-center justify-between px-1 pb-2">
          <button
            type="button"
            onClick={() =>
              setMonth(new Date(month.getFullYear(), month.getMonth() - 1, 1))
            }
            className="flex size-7 items-center justify-center rounded-full text-ink-soft active:bg-hairline"
            aria-label="上一月"
          >
            <ChevronLeft size={16} />
          </button>
          <span className="text-[14px] font-semibold">
            {month.getFullYear()}年{month.getMonth() + 1}月
          </span>
          <button
            type="button"
            onClick={() =>
              setMonth(new Date(month.getFullYear(), month.getMonth() + 1, 1))
            }
            disabled={atCurrentMonth}
            className={`flex size-7 items-center justify-center rounded-full ${
              atCurrentMonth
                ? "text-ink-soft/25"
                : "text-ink-soft active:bg-hairline"
            }`}
            aria-label="下一月"
          >
            <ChevronRight size={16} />
          </button>
        </div>

        {/* 星期表头 */}
        <div className="grid grid-cols-7 pb-1">
          {WEEKDAYS.map((w) => (
            <span
              key={w}
              className="text-center text-[10px] text-ink-soft/70"
            >
              {w}
            </span>
          ))}
        </div>

        {/* 日格 */}
        <div className="grid grid-cols-7 gap-y-0.5">
          {cells.map((d, i) => {
            if (!d) return <span key={`b${i}`} />;
            const iso = toISODate(d);
            const future = iso > todayISO;
            const isSel = iso === selectedISO;
            const isTod = iso === todayISO;
            return (
              <button
                key={iso}
                type="button"
                disabled={future}
                onClick={() => onPick(d)}
                className={`mx-auto flex size-9 items-center justify-center rounded-full text-[13px] ${
                  isSel
                    ? "num bg-intake font-bold text-white"
                    : future
                      ? "text-ink-soft/25"
                      : isTod
                        ? "num font-bold text-intake active:bg-intake-soft"
                        : "num text-ink active:bg-hairline"
                }`}
              >
                {d.getDate()}
              </button>
            );
          })}
        </div>

        {/* 快捷回今天:看历史时一步跳回 */}
        {!isToday(selected) && (
          <button
            type="button"
            onClick={() => onPick(today)}
            className="mt-1.5 w-full rounded-xl py-1.5 text-center text-[12px] font-medium text-intake active:bg-intake-soft"
          >
            回到今天
          </button>
        )}
      </div>
    </>
  );
}
