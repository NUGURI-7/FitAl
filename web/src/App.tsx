import { lazy, Suspense, useCallback, useEffect, useRef, useState } from "react";
import { Dumbbell, NotebookPen, Settings, UtensilsCrossed } from "lucide-react";
import {
  type ChatStatus,
  deleteRecord,
  fetchDay,
  fetchUser,
  fetchWeights,
  sendChat,
  type UserProfile,
  type WeightPoint,
} from "@/api";
import { GroupCard } from "@/components/GroupCard";
import { Hero } from "@/components/Hero";
import { InputBar } from "@/components/InputBar";
import { ItemSheet } from "@/components/ItemSheet";
import { ProcessPanel } from "@/components/ProcessPanel";
import { SettingsPage } from "@/components/SettingsPage";
import { TopBar } from "@/components/TopBar";
import { addDays, dateLabel, isToday, subLabel, toISODate } from "@/lib/date";
import type { DaySummary, DishEntry, Group, RecordItem } from "@/types";

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
  onDeleteDish,
}: {
  kind: "meal" | "session";
  groups: Group[];
  delay: number;
  onItemClick: (item: RecordItem) => void;
  onDeleteDish: (dish: DishEntry) => Promise<void>;
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
            onDeleteDish={onDeleteDish}
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
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [showSettings, setShowSettings] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [toast, setToast] = useState<{ text: string; error: boolean } | null>(
    null,
  );
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  // 过程面板:一次发送一份状态事件流;seq 换值强制重挂,连发不串台
  const [proc, setProc] = useState<{
    seq: number;
    events: ChatStatus[];
    done: boolean;
  } | null>(null);
  const procSeq = useRef(0);
  // 回执压到面板收场后再弹,两者同位不打架
  const pendingToast = useRef<{ text: string; error: boolean } | null>(null);

  const showToast = (text: string, isError = false) => {
    if (toastTimer.current) clearTimeout(toastTimer.current);
    setToast({ text, error: isError });
    toastTimer.current = setTimeout(() => setToast(null), 5000);
  };

  // silent=静默刷新(改/删/记录后的重拉):旧数据挂着原地换数值,
  // 不清空列表、不闪加载态、展开状态与动画都不受影响;
  // 仅首次进入与切换日期走带加载态的完整加载
  const load = useCallback(async (d: Date, silent = false) => {
    if (!silent) setLoading(true);
    setError(null);
    try {
      setDay(await fetchDay(toISODate(d)));
    } catch (e) {
      setDay(null);
      setError(e instanceof Error ? e.message : "加载失败");
    } finally {
      if (!silent) setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(date);
  }, [date, load]);

  const loadWeights = useCallback(() => {
    fetchWeights().then(setWeights).catch(() => setWeights(null));
  }, []);
  useEffect(loadWeights, [loadWeights]);

  const loadProfile = useCallback(() => {
    fetchUser().then(setProfile).catch(() => setProfile(null));
  }, []);
  useEffect(loadProfile, [loadProfile]);

  // 保存档案后设置页留在原地(独立页面,用户自己返回);球上首字与主页数字静默跟新
  const handleProfileSaved = async (msg: string) => {
    showToast(msg);
    loadProfile();
    await load(date, true); // 档案影响基础代谢等现算数字,静默刷新
  };

  const handleSend = async (text: string): Promise<boolean> => {
    setSending(true);
    setToast(null); // 旧气泡先退场,发送期间舞台交给过程面板
    // 上一条回执还压着没弹(面板收场中就连发)则先弹出来
    if (pendingToast.current) {
      showToast(pendingToast.current.text, pendingToast.current.error);
      pendingToast.current = null;
    }
    procSeq.current += 1;
    setProc({ seq: procSeq.current, events: [], done: false });
    try {
      const reply = await sendChat(text, (s) =>
        setProc((p) => (p ? { ...p, events: [...p.events, s] } : p)),
      );
      pendingToast.current = { text: reply, error: false };
      // 记录永远落在"现在":不在今天就跳回今天,否则原地静默刷新
      if (isToday(date)) await load(date, true);
      else setDate(new Date());
      loadWeights(); // 可能记了体重,顺带刷新曲线数据
      return true;
    } catch (e) {
      pendingToast.current = {
        text: e instanceof Error ? e.message : "发送失败",
        error: true,
      };
      return false;
    } finally {
      setProc((p) => (p ? { ...p, done: true } : p));
      setSending(false);
    }
  };

  // 面板收场完毕:卸掉面板,弹出压着的回执
  const handleProcGone = () => {
    setProc(null);
    if (pendingToast.current) {
      showToast(pendingToast.current.text, pendingToast.current.error);
      pendingToast.current = null;
    }
  };

  const handleEdited = async (msg: string) => {
    setEditing(null);
    showToast(msg);
    await load(date, true);
  };

  // 整菜删除=逐条删成分(raw 是唯一事实源,菜无实体),所在顿由后端增量重算
  const handleDeleteDish = async (dish: DishEntry) => {
    try {
      for (const item of dish.items) {
        await deleteRecord("food", item.id);
      }
      showToast(`已删除整道「${dish.name}」`);
    } catch (e) {
      showToast(e instanceof Error ? e.message : "删除失败", true);
    }
    await load(date, true);
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
              onDeleteDish={handleDeleteDish}
            />
            <Section
              kind="session"
              groups={sessions}
              delay={60 + (meals.length + 1) * 70}
              onItemClick={setEditing}
              onDeleteDish={handleDeleteDish}
            />
            {day && day.groups.length > 0 && (
              <p className="pt-4 pb-1 text-center text-[11px] text-ink-soft/70">
                点卡片看明细 · 点明细可改可删
              </p>
            )}
          </>
        )}
      </main>

      {/* 发送后的过程面板:节点逐个点亮,走完收起让位回执 */}
      {proc && (
        <ProcessPanel
          key={proc.seq}
          events={proc.events}
          done={proc.done}
          onGone={handleProcGone}
        />
      )}

      {/* 回执气泡 */}
      {toast && (
        <div className="pointer-events-none fixed inset-x-0 bottom-20 z-50 flex justify-center px-6">
          <div
            className={`rise max-w-md rounded-2xl px-4 py-2.5 text-[13px] leading-relaxed shadow-lg ring-1 ring-black/[0.06] ${
              toast.error ? "bg-burn text-white" : "bg-ink text-paper"
            }`}
          >
            {toast.text}
          </div>
        </div>
      )}

      {/* 头像球=悬浮菜单开关:点开浮出小球(现仅"设置",后续可加),点小球进对应界面 */}
      {profile && (
        <>
          {menuOpen && (
            <button
              type="button"
              aria-label="收起菜单"
              onClick={() => setMenuOpen(false)}
              className="fixed inset-0 z-20 cursor-default"
            />
          )}
          <div className="pointer-events-none fixed inset-x-0 bottom-[calc(env(safe-area-inset-bottom)+4.25rem)] z-30">
            <div className="mx-auto flex max-w-md flex-col items-start gap-2.5 px-4">
              <button
                type="button"
                onClick={() => {
                  setMenuOpen(false);
                  setShowSettings(true);
                }}
                aria-label="设置"
                className={`relative flex size-10 items-center justify-center overflow-hidden rounded-full bg-paper/55 text-ink shadow-[0_6px_20px_rgba(38,35,29,0.16)] ring-1 ring-black/[0.08] backdrop-blur-xl transition-all duration-200 ease-out ${
                  menuOpen
                    ? "pointer-events-auto translate-y-0 scale-100 opacity-100"
                    : "pointer-events-none translate-y-4 scale-50 opacity-0"
                }`}
              >
                <span className="pointer-events-none absolute inset-0 rounded-full bg-[radial-gradient(circle_at_30%_25%,rgba(255,255,255,0.9),rgba(255,255,255,0)_60%)]" />
                <Settings size={17} className="relative" />
              </button>
              <button
                type="button"
                onClick={() => setMenuOpen((o) => !o)}
                aria-label="菜单"
                className={`rise pointer-events-auto relative flex size-11 items-center justify-center overflow-hidden rounded-full bg-paper/55 text-[16px] font-bold shadow-[0_6px_20px_rgba(38,35,29,0.16)] ring-1 ring-black/[0.08] backdrop-blur-xl transition-transform duration-200 active:scale-90 ${
                  menuOpen ? "scale-95" : ""
                }`}
              >
                <span className="pointer-events-none absolute inset-0 rounded-full bg-[radial-gradient(circle_at_30%_25%,rgba(255,255,255,0.9),rgba(255,255,255,0)_60%)]" />
                <span className="relative">
                  {profile.nickname.trim().charAt(0) || "我"}
                </span>
              </button>
            </div>
          </div>
        </>
      )}

      <InputBar sending={sending} onSend={handleSend} />

      {editing && (
        <ItemSheet
          item={editing}
          onClose={() => setEditing(null)}
          onDone={handleEdited}
        />
      )}
      {showSettings && profile && (
        <SettingsPage
          profile={profile}
          onClose={() => setShowSettings(false)}
          onSaved={handleProfileSaved}
        />
      )}
      {showWeights && (
        <Suspense fallback={null}>
          <WeightSheet
            onClose={() => setShowWeights(false)}
            onChanged={() => {
              loadWeights();
              load(date, true); // 英雄区体重/基础代谢可能受影响,静默刷新
            }}
          />
        </Suspense>
      )}
    </div>
  );
}

export default App;
