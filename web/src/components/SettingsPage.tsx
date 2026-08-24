import { useCallback, useEffect, useRef, useState } from "react";
import { ChevronLeft, KeyRound, LogOut, Smartphone, Trash2 } from "lucide-react";
import {
  changePassword,
  deleteMemory,
  deleteUserFood,
  fetchMemories,
  fetchUserFoods,
  logout,
  logoutOthers,
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
  onLogout,
}: {
  profile: UserProfile;
  onClose: () => void;
  onSaved: (msg: string) => void;
  onLogout: () => void;
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

  // 改密码:旧密码即身份证明;改完服务器把其他设备踢下线,当前这台留着
  const [pwOpen, setPwOpen] = useState(false);
  const [pwOld, setPwOld] = useState("");
  const [pwNew, setPwNew] = useState("");
  const [pwAgain, setPwAgain] = useState("");
  const [pwBusy, setPwBusy] = useState(false);
  const [pwError, setPwError] = useState<string | null>(null);
  const [pwDone, setPwDone] = useState<string | null>(null);
  const pwValid =
    pwOld.length > 0 && pwNew.length >= 6 && pwNew === pwAgain;

  const closePw = () => {
    setPwOpen(false);
    setPwOld("");
    setPwNew("");
    setPwAgain("");
    setPwError(null);
  };

  const doChangePassword = async () => {
    setPwBusy(true);
    setPwError(null);
    setPwDone(null);
    try {
      const revoked = await changePassword(pwOld, pwNew);
      closePw();
      setPwDone(
        revoked > 0
          ? `密码已改,顺带把另外 ${revoked} 台设备退了`
          : "密码已改",
      );
    } catch (e) {
      setPwError(e instanceof Error ? e.message : "改密码失败");
    } finally {
      setPwBusy(false);
    }
  };

  // 退出其他设备:令牌存库天生可吊销,删掉别处的行即可;当前这台不受影响
  const [othersBusy, setOthersBusy] = useState(false);
  const [othersMsg, setOthersMsg] = useState<string | null>(null);
  const doLogoutOthers = async () => {
    setOthersBusy(true);
    try {
      const n = await logoutOthers();
      setOthersMsg(n > 0 ? `已退出 ${n} 台` : "没有别的设备登录着");
    } catch (e) {
      setOthersMsg(e instanceof Error ? e.message : "操作失败");
    } finally {
      setOthersBusy(false);
    }
  };

  // 退出登录:删服务器上本枚令牌+清本地,整界面切回登录页;数据都在云端不受影响
  const [loggingOut, setLoggingOut] = useState(false);
  const doLogout = async () => {
    setLoggingOut(true);
    try {
      await logout();
    } finally {
      onLogout();
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
          <div className="flex items-center justify-between rounded-xl bg-card px-4 py-3 ring-1 ring-black/[0.04]">
            <span className="text-[13px] text-ink-soft">用户名</span>
            <span className="text-[16px] font-semibold text-ink-soft">
              {profile.username}
            </span>
          </div>
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
        </div>

        <p className="px-1 pt-2 text-[11px] leading-relaxed text-ink-soft/80">
          用户名是登录标识,不可改;昵称随便改、可重名。身高、性别、出生年份用于
          基础代谢与消耗计算;改档案不影响已存的记录,汇总里现算的数字会自动按新档案计。
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
            <br />
            改过 AI 估算的热量后,也会自动记在这里
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
                  {+(f.unit ? (f.kcalPerUnit ?? 0) : (f.kcal ?? 0)).toFixed(1)}
                  <span className="ml-0.5 text-[10px] font-normal text-ink-soft">
                    {f.unit ? `千卡/${f.unit}` : "千卡/100g"}
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

        <p className="px-1 pt-6 pb-2 text-[12px] font-semibold text-ink-soft">
          账号
        </p>
        {!pwOpen ? (
          <button
            type="button"
            onClick={() => {
              setPwOpen(true);
              setPwDone(null);
            }}
            className="mb-2 flex w-full items-center justify-between rounded-xl bg-card px-4 py-3 text-[15px] font-semibold ring-1 ring-black/[0.04] transition-transform active:scale-[0.98]"
          >
            <span className="flex items-center gap-2">
              <KeyRound size={16} strokeWidth={2.5} className="text-ink-soft" />
              修改密码
            </span>
            <span className="text-[12px] font-normal text-ink-soft">
              {pwDone ?? ""}
            </span>
          </button>
        ) : (
          <div className="mb-2 space-y-2 rounded-xl bg-card p-4 ring-1 ring-black/[0.04]">
            {(
              [
                ["当前密码", pwOld, setPwOld],
                ["新密码", pwNew, setPwNew],
                ["再输一遍", pwAgain, setPwAgain],
              ] as const
            ).map(([label, value, set]) => (
              <label key={label} className="flex items-center justify-between">
                <span className="text-[13px] text-ink-soft">{label}</span>
                <input
                  type="password"
                  autoComplete={
                    label === "当前密码" ? "current-password" : "new-password"
                  }
                  value={value}
                  onChange={(e) => set(e.target.value)}
                  className="w-40 bg-transparent text-right text-[16px] font-semibold outline-none"
                />
              </label>
            ))}
            <p className="pt-1 text-[11px] leading-relaxed text-ink-soft/80">
              新密码至少 6 位。改完其他设备会被退出登录,这台不用重新登录。
            </p>
            {pwError && <p className="text-[12px] text-burn">{pwError}</p>}
            <div className="flex gap-2 pt-1">
              <button
                type="button"
                onClick={closePw}
                disabled={pwBusy}
                className="flex-1 rounded-xl bg-paper py-2.5 text-[14px] font-semibold text-ink-soft disabled:opacity-40"
              >
                取消
              </button>
              <button
                type="button"
                onClick={doChangePassword}
                disabled={!pwValid || pwBusy}
                className="flex-1 rounded-xl bg-ink py-2.5 text-[14px] font-semibold text-paper disabled:opacity-25"
              >
                {pwBusy ? "提交中…" : "确认修改"}
              </button>
            </div>
          </div>
        )}
        <button
          type="button"
          onClick={doLogoutOthers}
          disabled={othersBusy}
          className="mb-2 flex w-full items-center justify-between rounded-xl bg-card px-4 py-3 text-[15px] font-semibold ring-1 ring-black/[0.04] transition-transform active:scale-[0.98] disabled:opacity-40"
        >
          <span className="flex items-center gap-2">
            <Smartphone size={16} strokeWidth={2.5} className="text-ink-soft" />
            退出其他设备
          </span>
          <span className="text-[12px] font-normal text-ink-soft">
            {othersBusy ? "处理中…" : (othersMsg ?? "")}
          </span>
        </button>
        <button
          type="button"
          onClick={doLogout}
          disabled={loggingOut}
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-card py-3 text-[15px] font-semibold text-burn ring-1 ring-black/[0.04] transition-transform active:scale-[0.98] disabled:opacity-40"
        >
          <LogOut size={16} strokeWidth={2.5} />
          {loggingOut ? "退出中…" : "退出登录"}
        </button>
        <p className="px-1 pt-2 text-[11px] leading-relaxed text-ink-soft/80">
          只下线这台设备,数据都在云端;重新登录即可回来。
        </p>
      </main>
    </div>
  );
}
