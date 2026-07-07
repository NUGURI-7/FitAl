import { Dumbbell, UtensilsCrossed } from "lucide-react";
import { GroupCard } from "@/components/GroupCard";
import { InputBar } from "@/components/InputBar";
import { TopBar } from "@/components/TopBar";
import { mockDay } from "@/data/mock";
import type { Group } from "@/types";

function SectionHeader({
  kind,
  totalKcal,
  delay,
}: {
  kind: "meal" | "session";
  totalKcal: number;
  delay: number;
}) {
  const isMeal = kind === "meal";
  return (
    <div
      className="rise flex items-center justify-between px-1 pt-4 pb-2"
      style={{ animationDelay: `${delay}ms` }}
    >
      <span className="flex items-center gap-2">
        <span
          className={`flex size-6 items-center justify-center rounded-lg ${
            isMeal ? "bg-intake-soft text-intake" : "bg-burn-soft text-burn"
          }`}
        >
          {isMeal ? (
            <UtensilsCrossed size={13} strokeWidth={2.5} />
          ) : (
            <Dumbbell size={13} strokeWidth={2.5} />
          )}
        </span>
        <span className="text-[15px] font-bold tracking-wide">
          {isMeal ? "饮食" : "运动"}
        </span>
      </span>
      <span
        className={`num text-[15px] font-bold ${isMeal ? "text-intake" : "text-burn"}`}
      >
        {totalKcal}
        <span className="ml-0.5 text-[10px] font-normal text-ink-soft">
          千卡
        </span>
      </span>
    </div>
  );
}

function App() {
  const day = mockDay;
  const meals = day.groups.filter((g) => g.kind === "meal");
  const sessions = day.groups.filter((g) => g.kind === "session");
  const sum = (gs: Group[]) => gs.reduce((acc, g) => acc + g.kcalTotal, 0);

  return (
    <div className="min-h-dvh">
      <TopBar day={day} />

      <main className="mx-auto max-w-md px-4 pb-28">
        <SectionHeader kind="meal" totalKcal={sum(meals)} delay={60} />
        <div className="space-y-2.5">
          {meals.map((g, i) => (
            <GroupCard key={g.id} group={g} index={i + 1} />
          ))}
        </div>

        <SectionHeader
          kind="session"
          totalKcal={sum(sessions)}
          delay={60 + (meals.length + 1) * 70}
        />
        <div className="space-y-2.5">
          {sessions.map((g, i) => (
            <GroupCard key={g.id} group={g} index={meals.length + 1 + i} />
          ))}
        </div>

        <p className="pt-4 pb-1 text-center text-[11px] text-ink-soft/70">
          点卡片看明细 · 点明细可改可删
        </p>
      </main>

      <InputBar />
    </div>
  );
}

export default App;
