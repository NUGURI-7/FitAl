import { lazy, Suspense, useCallback, useEffect, useRef, useState } from "react";
import { Dumbbell, NotebookPen, UtensilsCrossed } from "lucide-react";
import { fetchDay, fetchWeights, sendChat, type WeightPoint } from "@/api";
import { GroupCard } from "@/components/GroupCard";
import { Hero } from "@/components/Hero";
import { InputBar } from "@/components/InputBar";
import { ItemSheet } from "@/components/ItemSheet";
import { TopBar } from "@/components/TopBar";
import { addDays, dateLabel, isToday, subLabel, toISODate } from "@/lib/date";
import type { DaySummary, Group, RecordItem } from "@/types";

// 图表库较重,点开体重曲线时才加载
const WeightSheet = lazy(() =>
  import("@/components/WeightSheet").then((m) => ({ default: m.WeightSheet })),
);

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
        className={`num inline-flex items-baseline gap-0.5 rounded-full px-2.5 py-1 text-[13px] font-bold ${
          isMeal ? "bg-intake-soft text-intake" : "bg-burn-soft text-burn"
        }`}
      >
        {totalKcal}
        <span className="text-[10px] font-normal opacity-70">千卡</span>
      </span>
    </div>
  );
}

function Section({
  kind,
  groups,
  delay,
  onItemClick,
}: {
  kind: "meal" | "session";
  groups: Group[];
  delay: number;
  onItemClick: (item: RecordItem) => void;
}) {
  if (groups.length === 0) return null;
  const total = Math.round(groups.reduce((acc, g) => acc + g.kcalTotal, 0));
  return (
    <>
      <SectionHeader kind={kind} totalKcal={total} delay={delay} />
      <div className="space-y-2.5">
        {groups.map((g, i) => (
          <GroupCard
            key={g.id}
            group={g}
            index={i + 1}
            onItemClick={onItemClick}
          />
        ))}
      </div>
    </>
  );
}

function App() {
  const [date, setDate] = useState(() => new Date());
  const [day, setDay] = useState<DaySummary | null>(null);
  const [weights, setWeights] = useState<WeightPoint[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [editing, setEditing] = useState<RecordItem | null>(null);
  const [showWeights, setShowWeights] = useState(false);
  const [toast, setToast] = useState<{ text: string; error: boolean } | null>(
    null,
  );
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const showToast = (text: string, isError = false) => {
    if (toastTimer.current) clearTimeout(toastTimer.current);
    setToast({ text, error: isError });
    toastTimer.current = setTimeout(() => setToast(null), 5000);
  };

  const load = useCallback(async (d: Date) => {
    setLoading(true);
    setError(null);
    try {
      setDay(await fetchDay(toISODate(d)));
    } catch (e) {
      setDay(null);
      setError(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(date);
  }, [date, load]);

  const loadWeights = useCallback(() => {
    fetchWeights().then(setWeights).catch(() => setWeights(null));
  }, []);
  useEffect(loadWeights, [loadWeights]);

  const handleSend = async (text: string): Promise<boolean> => {
    setSending(true);
    try {
      const reply = await sendChat(text);
      showToast(reply);
      // 记录永远落在"现在":不在今天就跳回今天,否则原地刷新
      if (isToday(date)) await load(date);
      else setDate(new Date());
      loadWeights(); // 可能记了体重,顺带刷新曲线数据
      return true;
    } catch (e) {
      showToast(e instanceof Error ? e.message : "发送失败", true);
      return false;
    } finally {
      setSending(false);
    }
  };

  const handleEdited = async (msg: string) => {
    setEditing(null);
    showToast(msg);
    await load(date);
  };

  const meals = day?.groups.filter((g) => g.kind === "meal") ?? [];
  const sessions = day?.groups.filter((g) => g.kind === "session") ?? [];
  const empty = !loading && !error && day && day.groups.length === 0;

  // 所选日期零点之前的最后一次称重 =「上次体重」
  const dayStartMs = new Date(
    date.getFullYear(),
    date.getMonth(),
    date.getDate(),
  ).getTime();
  const prior = (weights ?? []).filter((w) => w.at.getTime() < dayStartMs);
  const prevWeight = prior.length > 0 ? prior[prior.length - 1] : null;

  return (
    <div className="min-h-dvh">
      <TopBar
        dateLabel={dateLabel(date)}
        subLabel={subLabel(date)}
        atToday={isToday(date)}
        onPrev={() => setDate(addDays(date, -1))}
        onNext={() => setDate(addDays(date, 1))}
      />

      <main className="mx-auto max-w-md px-4 pb-32">
        <Hero
          day={day}
          atToday={isToday(date)}
          prevWeight={prevWeight}
          spark={(weights ?? []).map((w) => w.kg)}
          onWeightClick={() => setShowWeights(true)}
        />
        {loading && (
          <p className="pt-16 text-center text-[13px] text-ink-soft/70">
            加载中…
          </p>
        )}
        {error && (
          <div className="pt-16 text-center">
            <p className="text-[13px] text-burn">{error}</p>
            <button
              type="button"
              onClick={() => load(date)}
              className="mt-2 rounded-full bg-card px-4 py-1.5 text-[13px] font-medium ring-1 ring-black/[0.06] active:bg-paper"
            >
              重试
            </button>
          </div>
        )}
        {empty && (
          <div className="rise pt-16 text-center">
            <NotebookPen size={28} className="mx-auto text-ink-soft/40" />
            <p className="mt-3 text-[14px] font-medium text-ink-soft">
              {isToday(date) ? "今天还没有记录" : "这天没有记录"}
            </p>
            {isToday(date) && (
              <p className="mt-1 text-[12px] text-ink-soft/70">
                在下面说一句试试,比如"吃了200克鸡胸肉"
              </p>
            )}
          </div>
        )}

        {!loading && !error && (
          <>
            <Section
              kind="meal"
              groups={meals}
              delay={60}
              onItemClick={setEditing}
            />
            <Section
              kind="session"
              groups={sessions}
              delay={60 + (meals.length + 1) * 70}
              onItemClick={setEditing}
            />
            {day && day.groups.length > 0 && (
              <p className="pt-4 pb-1 text-center text-[11px] text-ink-soft/70">
                点卡片看明细 · 点明细可改可删
              </p>
            )}
          </>
        )}
      </main>

      {/* 回执气泡 */}
      {toast && (
        <div className="pointer-events-none fixed inset-x-0 bottom-20 z-30 flex justify-center px-6">
          <div
            className={`rise max-w-md rounded-2xl px-4 py-2.5 text-[13px] leading-relaxed shadow-lg ring-1 ring-black/[0.06] ${
              toast.error ? "bg-burn text-white" : "bg-ink text-paper"
            }`}
          >
            {toast.text}
          </div>
        </div>
      )}

      <InputBar sending={sending} onSend={handleSend} />

      {editing && (
        <ItemSheet
          item={editing}
          onClose={() => setEditing(null)}
          onDone={handleEdited}
        />
      )}
      {showWeights && (
        <Suspense fallback={null}>
          <WeightSheet onClose={() => setShowWeights(false)} />
        </Suspense>
      )}
    </div>
  );
}

export default App;
