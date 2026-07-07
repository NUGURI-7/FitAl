import { useCallback, useEffect, useRef, useState } from "react";
import { Dumbbell, NotebookPen, UtensilsCrossed } from "lucide-react";
import { fetchDay, sendChat } from "@/api";
import { GroupCard } from "@/components/GroupCard";
import { InputBar } from "@/components/InputBar";
import { TopBar } from "@/components/TopBar";
import { addDays, dateLabel, isToday, subLabel, toISODate } from "@/lib/date";
import type { DaySummary, Group } from "@/types";

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
}: {
  kind: "meal" | "session";
  groups: Group[];
  delay: number;
}) {
  if (groups.length === 0) return null;
  const total = groups.reduce((acc, g) => acc + g.kcalTotal, 0);
  return (
    <>
      <SectionHeader kind={kind} totalKcal={total} delay={delay} />
      <div className="space-y-2.5">
        {groups.map((g, i) => (
          <GroupCard key={g.id} group={g} index={i + 1} />
        ))}
      </div>
    </>
  );
}

function App() {
  const [date, setDate] = useState(() => new Date());
  const [day, setDay] = useState<DaySummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
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

  const handleSend = async (text: string): Promise<boolean> => {
    setSending(true);
    try {
      const reply = await sendChat(text);
      showToast(reply);
      // 记录永远落在"现在":不在今天就跳回今天,否则原地刷新
      if (isToday(date)) await load(date);
      else setDate(new Date());
      return true;
    } catch (e) {
      showToast(e instanceof Error ? e.message : "发送失败", true);
      return false;
    } finally {
      setSending(false);
    }
  };

  const meals = day?.groups.filter((g) => g.kind === "meal") ?? [];
  const sessions = day?.groups.filter((g) => g.kind === "session") ?? [];
  const empty = !loading && !error && day && day.groups.length === 0;

  return (
    <div className="min-h-dvh">
      <TopBar
        day={day}
        dateLabel={dateLabel(date)}
        subLabel={subLabel(date)}
        atToday={isToday(date)}
        onPrev={() => setDate(addDays(date, -1))}
        onNext={() => setDate(addDays(date, 1))}
      />

      <main className="mx-auto max-w-md px-4 pb-32">
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
            <Section kind="meal" groups={meals} delay={60} />
            <Section
              kind="session"
              groups={sessions}
              delay={60 + (meals.length + 1) * 70}
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
    </div>
  );
}

export default App;
