import { useState } from "react";
import { ChevronDown, Dumbbell, UtensilsCrossed } from "lucide-react";
import { SourceBadge } from "@/components/SourceBadge";
import type { Group } from "@/types";

/** 一顿饭 / 一场训练的卡片:点卡片展开明细;点明细弹改删抽屉(第三步接) */
export function GroupCard({ group, index }: { group: Group; index: number }) {
  const [open, setOpen] = useState(false);
  const isMeal = group.kind === "meal";

  return (
    <div
      className="rise overflow-hidden rounded-2xl bg-card shadow-[0_1px_2px_rgba(38,35,29,0.06)] ring-1 ring-black/[0.04]"
      style={{ animationDelay: `${80 + index * 70}ms` }}
    >
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-3 px-4 py-3.5 text-left active:bg-paper/60"
      >
        <span
          className={`flex size-9 shrink-0 items-center justify-center rounded-xl ${
            isMeal ? "bg-intake-soft text-intake" : "bg-burn-soft text-burn"
          }`}
        >
          {isMeal ? <UtensilsCrossed size={17} /> : <Dumbbell size={17} />}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-[15px] font-semibold">
            {group.name}
          </span>
          <span className="block text-[11px] text-ink-soft">
            {group.timeRange} · {group.items.length} 条
          </span>
        </span>
        <span className="num text-[17px] font-bold">
          {group.kcalTotal}
          <span className="ml-0.5 text-[11px] font-normal text-ink-soft">
            千卡
          </span>
        </span>
        <ChevronDown
          size={16}
          className={`shrink-0 text-ink-soft/60 transition-transform duration-200 ${
            open ? "rotate-180" : ""
          }`}
        />
      </button>

      {open && (
        <ul className="unfold border-t border-hairline">
          {group.items.map((item) => (
            <li key={item.id}>
              <button
                type="button"
                className="flex w-full items-center gap-2 px-4 py-2.5 text-left active:bg-paper/60"
              >
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-1.5">
                    <span className="truncate text-[13px] font-medium">
                      {item.name}
                    </span>
                    <SourceBadge source={item.source} />
                  </span>
                  <span className="block text-[11px] text-ink-soft">
                    {item.detail}
                    {item.kcalNet != null && ` · 净耗 ${item.kcalNet}`}
                  </span>
                </span>
                <span className="num text-[13px] font-semibold text-ink-soft">
                  {item.kcal}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
