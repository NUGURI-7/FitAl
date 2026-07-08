import { useState } from "react";
import {
  ChevronDown,
  Dumbbell,
  Soup,
  Trash2,
  UtensilsCrossed,
} from "lucide-react";
import { SourceBadge } from "@/components/SourceBadge";
import type { DishEntry, Group, GroupEntry, RecordItem } from "@/types";

/** 一顿饭 / 一场训练的卡片:点卡片展开明细;菜可再展开成分;点记录弹改删抽屉 */
export function GroupCard({
  group,
  index,
  onItemClick,
  onDeleteDish,
}: {
  group: Group;
  index: number;
  onItemClick: (item: RecordItem) => void;
  onDeleteDish: (dish: DishEntry) => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const isMeal = group.kind === "meal";
  // "条"数按 raw 记录计:菜按其成分数计,不把菜自身算一条
  const recordCount = group.items.reduce(
    (n, e) => n + (e.kind === "dish" ? e.items.length : 1),
    0,
  );

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
            {group.timeRange} · {recordCount} 条
          </span>
        </span>
        <span className="num text-[17px] font-bold">
          {Math.round(group.kcalTotal)}
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
          {group.items.map((entry: GroupEntry) =>
            entry.kind === "dish" ? (
              <DishRow
                key={entry.name}
                dish={entry}
                onItemClick={onItemClick}
                onDeleteDish={onDeleteDish}
              />
            ) : (
              <ItemRow key={entry.id} item={entry} onItemClick={onItemClick} />
            ),
          )}
        </ul>
      )}
    </div>
  );
}

/** 单条记录行(单品/成分/运动);indent=作为菜的成分缩进展示 */
function ItemRow({
  item,
  onItemClick,
  indent = false,
}: {
  item: RecordItem;
  onItemClick: (item: RecordItem) => void;
  indent?: boolean;
}) {
  return (
    <li>
      <button
        type="button"
        onClick={() => onItemClick(item)}
        className={`flex w-full items-center gap-2 py-2.5 pr-4 text-left active:bg-paper/60 ${
          indent ? "pl-10" : "pl-4"
        }`}
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
  );
}

/** 菜行:菜名+总克重+合计热量(后端现算),点开看成分,成分照旧可改可删;
 * 整菜删除=删掉全部成分(两击确认,与抽屉删除同款交互) */
function DishRow({
  dish,
  onItemClick,
  onDeleteDish,
}: {
  dish: DishEntry;
  onItemClick: (item: RecordItem) => void;
  onDeleteDish: (dish: DishEntry) => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const [armed, setArmed] = useState(false);
  const [busy, setBusy] = useState(false);

  const remove = async () => {
    if (!armed) {
      setArmed(true);
      setTimeout(() => setArmed(false), 3000); // 3秒不点第二下自动收回
      return;
    }
    setBusy(true);
    await onDeleteDish(dish);
  };

  return (
    <li>
      <div className="flex w-full items-center gap-2 pr-4">
        <button
          type="button"
          onClick={() => setOpen(!open)}
          className="flex min-w-0 flex-1 items-center gap-2 py-2.5 pl-4 text-left active:bg-paper/60"
        >
          <span className="min-w-0 flex-1">
            <span className="flex items-center gap-1.5">
              <Soup size={13} className="shrink-0 text-intake" />
              <span className="truncate text-[13px] font-medium">
                {dish.name}
              </span>
            </span>
            <span className="block text-[11px] text-ink-soft">
              {+dish.totalGrams} g · {dish.items.length} 种成分
            </span>
          </span>
          <span className="num text-[13px] font-semibold text-ink-soft">
            {Math.round(dish.kcalTotal)}
          </span>
          <ChevronDown
            size={13}
            className={`shrink-0 text-ink-soft/50 transition-transform duration-200 ${
              open ? "rotate-180" : ""
            }`}
          />
        </button>
        <button
          type="button"
          onClick={remove}
          disabled={busy}
          aria-label={armed ? "确认删除整菜" : "删除整菜"}
          className={`flex shrink-0 items-center gap-1 rounded-lg px-1.5 py-1 text-[10px] font-medium transition-colors disabled:opacity-40 ${
            armed ? "bg-burn text-white" : "text-ink-soft/50 active:text-burn"
          }`}
        >
          <Trash2 size={13} />
          {armed && "确认"}
        </button>
      </div>
      {open && (
        <ul className="unfold">
          {dish.items.map((item) => (
            <ItemRow
              key={item.id}
              item={item}
              onItemClick={onItemClick}
              indent
            />
          ))}
        </ul>
      )}
    </li>
  );
}
