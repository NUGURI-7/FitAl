import { useCallback, useEffect, useRef, useState } from "react";
import { ChevronLeft, Trash2 } from "lucide-react";
import {
  deleteMemory,
  deleteUserFood,
  fetchMemories,
  fetchUserFoods,
  patchUser,
  type MemoryItem,
  type UserFoodItem,
  type UserProfile,
} from "@/api";

function Field({
  label,
  unit,
  value,
  onChange,
  mode = "decimal",
}: {
  label: string;
  unit?: string;
  value: string;
  onChange: (v: string) => void;
  mode?: "text" | "decimal" | "numeric";
}) {
  return (
    <label className="flex items-center justify-between rounded-xl bg-card px-4 py-3 ring-1 ring-black/[0.04]">
      <span className="text-[13px] text-ink-soft">{label}</span>
      <span className="flex items-baseline gap-1">
        <input
          inputMode={mode === "text" ? undefined : mode}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className={`bg-transparent text-right text-[16px] font-semibold outline-none ${
            mode === "text" ? "w-36" : "num w-24"
          }`}
        />
        {unit && <span className="w-8 text-[11px] text-ink-soft">{unit}</span>}
      </span>
    </label>
  );
}

const KIND_LABEL: Record<MemoryItem["kind"], string> = {
  alias: "叫法",
  habit: "习惯",
  correction: "纠正",
};
const KIND_STYLE: Record<MemoryItem["kind"], string> = {
  alias: "bg-steel-soft text-steel",
  habit: "bg-intake-soft text-intake",
  correction: "bg-note-soft text-note",
};

/** 独立设置页(从右滑入,主页原地保留):身体档案读改 + 自定义食物查删 + AI 记忆查删。
 * 改档案不回算已存记录,读时现算的基础代谢自动采用新档案 */
export function SettingsPage({
  profile,
  onClose,
  onSaved,
}: {
  profile: UserProfile;
  onClose: () => void;
  onSaved: (msg: string) => void;
}) {
  const [nickname, setNickname] = useState(profile.nickname);
  const [height, setHeight] = useState(String(profile.heightCm));
  const [sex, setSex] = useState(profile.sex);
  const [birthYear, setBirthYear] = useState(String(profile.birthYear));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 自定义食物:列表+两击删;改数值不设表单,对话里重复"记住"即覆盖
  const [foods, setFoods] = useState<UserFoodItem[] | null>(null);
  const [foodsError, setFoodsError] = useState<string | null>(null);
  const [armedId, setArmedId] = useState<number | null>(null);
  const [foodBusy, setFoodBusy] = useState(false);
  const armTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const loadFoods = useCallback(
    () =>
      fetchUserFoods()
        .then(setFoods)
        .catch((e) =>
          setFoodsError(e instanceof Error ? e.message : "加载失败"),
        ),
    [],
  );
  useEffect(() => {
    loadFoods();
  }, [loadFoods]);

  const removeFood = async (id: number) => {
    if (armedId !== id) {
      setArmedId(id);
      if (armTimer.current) clearTimeout(armTimer.current);
      armTimer.current = setTimeout(() => setArmedId(null), 3000);
      return;
    }
    if (armTimer.current) clearTimeout(armTimer.current);
    setArmedId(null);
    setFoodBusy(true);
    setFoodsError(null);
    try {
      await deleteUserFood(id);
      await loadFoods();
    } catch (e) {
      setFoodsError(e instanceof Error ? e.message : "删除失败");
    } finally {
      setFoodBusy(false);
    }
  };

  // AI 记忆:列表+两击删;错的记忆会持续注入解析,删除即止
  const [memories, setMemories] = useState<MemoryItem[] | null>(null);
  const [memError, setMemError] = useState<string | null>(null);
  const [memArmedId, setMemArmedId] = useState<number | null>(null);
  const [memBusy, setMemBusy] = useState(false);
  const memArmTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const loadMemories = useCallback(
    () =>
      fetchMemories()
        .then(setMemories)
        .catch((e) => setMemError(e instanceof Error ? e.message : "加载失败")),
    [],
  );
  useEffect(() => {
    loadMemories();
  }, [loadMemories]);

  const removeMemory = async (id: number) => {
    if (memArmedId !== id) {
      setMemArmedId(id);
      if (memArmTimer.current) clearTimeout(memArmTimer.current);
      memArmTimer.current = setTimeout(() => setMemArmedId(null), 3000);
      return;
    }
    if (memArmTimer.current) clearTimeout(memArmTimer.current);
    setMemArmedId(null);
    setMemBusy(true);
    setMemError(null);
    try {
      await deleteMemory(id);
      await loadMemories();
    } catch (e) {
      setMemError(e instanceof Error ? e.message : "删除失败");
    } finally {
      setMemBusy(false);
    }
  };

  const nick = nickname.trim();
  const hNum = Number(height);
  const yNum = Number(birthYear);
  const valid =
    nick.length > 0 &&
    nick.length <= 50 &&
    height.trim() !== "" &&
    Number.isFinite(hNum) &&
    hNum > 0 &&
    birthYear.trim() !== "" &&
    Number.isInteger(yNum) &&
    yNum >= 1900 &&
    yNum <= new Date().getFullYear();

  const body: Record<string, string | number> = {};
  if (nick !== profile.nickname) body.nickname = nick;
  if (hNum !== profile.heightCm) body.height_cm = hNum;
  if (sex !== profile.sex) body.sex = sex;
  if (yNum !== profile.birthYear) body.birth_year = yNum;
  const changed = valid && Object.keys(body).length > 0;

  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      await patchUser(body);
      onSaved("档案已保存");
    } catch (e) {
      setError(e instanceof Error ? e.message : "保存失败");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page-in fixed inset-0 z-30 overflow-y-auto bg-paper">
      <header className="sticky top-0 z-10 border-b border-hairline bg-paper/85 backdrop-blur-md">
        <div className="mx-auto flex max-w-md items-center justify-between px-4 py-2 pt-[max(0.5rem,env(safe-area-inset-top))]">
          <button
            type="button"
            onClick={onClose}
            aria-label="返回"
            className="flex size-8 items-center justify-center rounded-full text-ink-soft active:bg-hairline"
          >
            <ChevronLeft size={20} />
          </button>
          <div className="text-[17px] font-semibold">设置</div>
          <div className="size-8" aria-hidden="true" />
        </div>
      </header>

      <main className="mx-auto max-w-md px-4 pb-[max(2rem,env(safe-area-inset-bottom))]">
        <p className="px-1 pt-4 pb-2 text-[12px] font-semibold text-ink-soft">
          身体档案
        </p>
        <div className="space-y-2">
          <Field
            label="昵称"
            value={nickname}
            onChange={setNickname}
            mode="text"
          />
          <Field label="身高" unit="cm" value={height} onChange={setHeight} />
          <div className="flex items-center justify-between rounded-xl bg-card px-4 py-3 ring-1 ring-black/[0.04]">
            <span className="text-[13px] text-ink-soft">性别</span>
            <div className="flex gap-1 rounded-lg bg-hairline/50 p-0.5">
              {(["male", "female"] as const).map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => setSex(s)}
                  className={`rounded-md px-4 py-1 text-[13px] font-medium transition-colors ${
                    sex === s ? "bg-paper shadow-sm" : "text-ink-soft"
                  }`}
                >
                  {s === "male" ? "男" : "女"}
                </button>
              ))}
            </div>
          </div>
          <Field
            label="出生年份"
            unit="年"
            value={birthYear}
            onChange={setBirthYear}
            mode="numeric"
          />
          <div className="flex items-center justify-between rounded-xl bg-card px-4 py-3 ring-1 ring-black/[0.04]">
            <span className="text-[13px] text-ink-soft">用户 ID</span>
            <span className="num text-[16px] font-semibold">{profile.id}</span>
          </div>
        </div>

        <p className="px-1 pt-2 text-[11px] leading-relaxed text-ink-soft/80">
          身高、性别、出生年份用于基础代谢与消耗计算;改档案不影响已存的记录,
          汇总里现算的数字会自动按新档案计。
        </p>

        {error && <p className="px-1 pt-1 text-[12px] text-burn">{error}</p>}

        <div className="pt-4">
          <button
            type="button"
            onClick={save}
            disabled={!changed || busy}
            className="w-full rounded-xl bg-ink py-3 text-[15px] font-semibold text-paper disabled:opacity-25"
          >
            {busy ? "保存中…" : "保存档案"}
          </button>
        </div>

        <p className="px-1 pt-6 pb-2 text-[12px] font-semibold text-ink-soft">
          自定义食物
        </p>
        {foods == null && !foodsError && (
          <p className="py-6 text-center text-[13px] text-ink-soft/70">
            加载中…
          </p>
        )}
        {foods && foods.length === 0 && (
          <p className="rounded-xl bg-card px-4 py-6 text-center text-[13px] text-ink-soft ring-1 ring-black/[0.04]">
            还没有自定义食物,对话里说
            <br />
            「记住蛋白粉一勺30克120千卡」就能添加
          </p>
        )}
        {foods && foods.length > 0 && (
          <div className="space-y-2">
            {foods.map((f) => (
              <div
                key={f.id}
                className="flex items-center gap-2 rounded-xl bg-card px-4 py-2.5 ring-1 ring-black/[0.04]"
              >
                <div className="min-w-0 flex-1">
                  <div className="truncate text-[14px] font-medium">
                    {f.name}
                    {f.form && (
                      <span className="ml-1 text-[11px] font-normal text-ink-soft">
                        {f.form}
                      </span>
                    )}
                  </div>
                  <div className="text-[11px] text-ink-soft">
                    {f.updatedAt.getMonth() + 1}月{f.updatedAt.getDate()}日 记
                  </div>
                </div>
                <span className="num text-[14px] font-semibold">
                  {+f.kcal.toFixed(1)}
                  <span className="ml-0.5 text-[10px] font-normal text-ink-soft">
                    千卡/100g
                  </span>
                </span>
                <button
                  type="button"
                  onClick={() => removeFood(f.id)}
                  disabled={foodBusy}
                  aria-label="删除这条自定义食物"
                  className={`flex items-center justify-center transition-colors disabled:opacity-40 ${
                    armedId === f.id
                      ? "rounded-lg bg-burn px-2.5 py-1.5 text-[12px] font-semibold text-white"
                      : "size-7 rounded-lg text-ink-soft/50 active:bg-hairline/60"
                  }`}
                >
                  {armedId === f.id ? "确认" : <Trash2 size={14} />}
                </button>
              </div>
            ))}
          </div>
        )}
        {foodsError && (
          <p className="px-1 pt-2 text-[12px] text-burn">{foodsError}</p>
        )}
        {foods && foods.length > 0 && (
          <p className="px-1 pt-2 text-[11px] leading-relaxed text-ink-soft/80">
            想改数值:对话里再「记住」一遍同名食物即可覆盖。
            删除只影响以后的解析,已记的饭菜数字不变。
          </p>
        )}

        <p className="px-1 pt-6 pb-2 text-[12px] font-semibold text-ink-soft">
          AI 记忆
        </p>
        {memories == null && !memError && (
          <p className="py-6 text-center text-[13px] text-ink-soft/70">
            加载中…
          </p>
        )}
        {memories && memories.length === 0 && (
          <p className="rounded-xl bg-card px-4 py-6 text-center text-[13px] text-ink-soft ring-1 ring-black/[0.04]">
            还没有记忆,对话里说
            <br />
            「记住我一勺是30克」这类话就会长出来
          </p>
        )}
        {memories && memories.length > 0 && (
          <div className="space-y-2">
            {memories.map((m) => (
              <div
                key={m.id}
                className="flex items-start gap-2 rounded-xl bg-card px-4 py-2.5 ring-1 ring-black/[0.04]"
              >
                <div className="min-w-0 flex-1">
                  <p className="text-[13px] leading-relaxed break-words">
                    {m.content}
                  </p>
                  <div className="mt-1 flex items-center gap-1.5 text-[11px] text-ink-soft">
                    <span
                      className={`inline-flex items-center rounded-full px-1.5 py-0.5 text-[10px] font-medium ${KIND_STYLE[m.kind]}`}
                    >
                      {KIND_LABEL[m.kind]}
                    </span>
                    <span>
                      {m.updatedAt.getMonth() + 1}月{m.updatedAt.getDate()}日 更新
                    </span>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => removeMemory(m.id)}
                  disabled={memBusy}
                  aria-label="删除这条记忆"
                  className={`mt-0.5 flex shrink-0 items-center justify-center transition-colors disabled:opacity-40 ${
                    memArmedId === m.id
                      ? "rounded-lg bg-burn px-2.5 py-1.5 text-[12px] font-semibold text-white"
                      : "size-7 rounded-lg text-ink-soft/50 active:bg-hairline/60"
                  }`}
                >
                  {memArmedId === m.id ? "确认" : <Trash2 size={14} />}
                </button>
              </div>
            ))}
          </div>
        )}
        {memError && (
          <p className="px-1 pt-2 text-[12px] text-burn">{memError}</p>
        )}
        {memories && memories.length > 0 && (
          <p className="px-1 pt-2 text-[11px] leading-relaxed text-ink-soft/80">
            记忆会注入每次解析,错的会持续误导,删掉即止。
            「纠正」是你改删 AI 估算记录时系统自动记的。
          </p>
        )}
      </main>
    </div>
  );
}
