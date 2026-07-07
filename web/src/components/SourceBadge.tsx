import { Sparkles } from "lucide-react";
import type { Source } from "@/types";

const STYLE: Record<Source, { label: string; cls: string }> = {
  user_reported: { label: "你报的", cls: "bg-intake-soft text-intake" },
  user_food: { label: "自定义", cls: "bg-steel-soft text-steel" },
  food_table: { label: "查表", cls: "bg-paper text-ink-soft" },
  met_table: { label: "查表", cls: "bg-paper text-ink-soft" },
  llm_estimated: { label: "AI估算", cls: "bg-note-soft text-note" },
};

export function SourceBadge({ source }: { source: Source }) {
  const s = STYLE[source];
  return (
    <span
      className={`inline-flex items-center gap-0.5 rounded-full px-1.5 py-0.5 text-[10px] font-medium ${s.cls}`}
    >
      {source === "llm_estimated" && <Sparkles size={9} strokeWidth={2.5} />}
      {s.label}
    </span>
  );
}
