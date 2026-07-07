import { GroupCard } from "@/components/GroupCard";
import { InputBar } from "@/components/InputBar";
import { TopBar } from "@/components/TopBar";
import { mockDay } from "@/data/mock";

function App() {
  const day = mockDay;

  return (
    <div className="min-h-dvh">
      <TopBar day={day} />

      <main className="mx-auto max-w-md space-y-2.5 px-4 pt-3 pb-28">
        {day.groups.map((g, i) => (
          <GroupCard key={`${g.kind}-${g.id}`} group={g} index={i} />
        ))}
        <p className="pt-2 pb-1 text-center text-[11px] text-ink-soft/70">
          点卡片看明细 · 点明细可改可删
        </p>
      </main>

      <InputBar />
    </div>
  );
}

export default App;
