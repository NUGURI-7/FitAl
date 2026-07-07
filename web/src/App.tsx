import { GroupCard } from "@/components/GroupCard";
import { InputBar } from "@/components/InputBar";
import { TopBar } from "@/components/TopBar";
import { mockDay } from "@/data/mock";
import type { Group } from "@/types";

function SectionHeader({
  label,
  colorCls,
  totalKcal,
  delay,
}: {
  label: string;
  colorCls: string;
  totalKcal: number;
  delay: number;
}) {
  return (
    <div
      className="rise flex items-baseline justify-between px-1.5 pt-3 pb-1"
      style={{ animationDelay: `${delay}ms` }}
    >
      <span className={`text-[13px] font-semibold ${colorCls}`}>{label}</span>
      <span className="num text-[11px] text-ink-soft">共 {totalKcal} 千卡</span>
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
        <SectionHeader
          label="饮食"
          colorCls="text-intake"
          totalKcal={sum(meals)}
          delay={60}
        />
        <div className="space-y-2.5">
          {meals.map((g, i) => (
            <GroupCard key={g.id} group={g} index={i + 1} />
          ))}
        </div>

        <SectionHeader
          label="运动"
          colorCls="text-burn"
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
