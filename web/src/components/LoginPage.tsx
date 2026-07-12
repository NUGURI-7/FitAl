import { useState } from "react";
import { KeyRound, Ticket, UserRound } from "lucide-react";
import { login, register } from "@/api";

function Field({
  label,
  value,
  onChange,
  type = "text",
  mode,
  unit,
  placeholder,
  autoComplete,
  delay,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
  mode?: "decimal" | "numeric";
  unit?: string;
  placeholder?: string;
  autoComplete?: string;
  delay: number;
}) {
  return (
    <label
      className="rise flex items-center justify-between gap-3 rounded-xl bg-card px-4 py-3 ring-1 ring-black/[0.04]"
      style={{ animationDelay: `${delay}ms` }}
    >
      <span className="shrink-0 text-[13px] text-ink-soft">{label}</span>
      <span className="flex min-w-0 flex-1 items-baseline justify-end gap-1">
        <input
          type={type}
          inputMode={mode}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          autoComplete={autoComplete}
          className={`min-w-0 flex-1 bg-transparent text-right text-[16px] font-semibold outline-none placeholder:font-normal placeholder:text-ink-soft/40 ${
            mode ? "num" : ""
          }`}
        />
        {unit && (
          <span className="shrink-0 text-[11px] text-ink-soft">{unit}</span>
        )}
      </span>
    </label>
  );
}

/** 登录页:本地无令牌/被踢下线时的全屏门面。
 * 登录=昵称+密码;注册=邀请码+昵称+密码+身体档案(注册页一并填,2026-07-12 用户定);
 * 注册成功当场发令牌,免二次登录 */
export function LoginPage({ onAuthed }: { onAuthed: () => void }) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [nickname, setNickname] = useState("");
  const [password, setPassword] = useState("");
  const [inviteCode, setInviteCode] = useState("");
  const [height, setHeight] = useState("");
  const [sex, setSex] = useState<"male" | "female">("male");
  const [birthYear, setBirthYear] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isRegister = mode === "register";
  const nick = nickname.trim();
  const hNum = Number(height);
  const yNum = Number(birthYear);
  const baseValid = nick.length > 0 && nick.length <= 50 && password.length >= 6;
  const valid = isRegister
    ? baseValid &&
      inviteCode.trim().length > 0 &&
      height.trim() !== "" &&
      Number.isFinite(hNum) &&
      hNum > 0 &&
      birthYear.trim() !== "" &&
      Number.isInteger(yNum) &&
      yNum >= 1900 &&
      yNum <= new Date().getFullYear()
    : baseValid;

  const submit = async () => {
    if (!valid || busy) return;
    setBusy(true);
    setError(null);
    try {
      if (isRegister) {
        await register({
          inviteCode: inviteCode.trim(),
          nickname: nick,
          password,
          heightCm: hNum,
          sex,
          birthYear: yNum,
        });
      } else {
        await login(nick, password);
      }
      onAuthed();
    } catch (e) {
      setError(e instanceof Error ? e.message : "出错了,再试一次");
    } finally {
      setBusy(false);
    }
  };

  const switchMode = (m: "login" | "register") => {
    if (m === mode) return;
    setMode(m);
    setError(null);
  };

  return (
    <div className="relative min-h-dvh overflow-hidden">
      {/* 顶部品牌光晕:纸感体系内的柔和径向渐变,无常驻动画 */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -top-28 left-1/2 h-72 w-[26rem] -translate-x-1/2 rounded-full bg-[radial-gradient(closest-side,rgba(47,107,83,0.14),rgba(47,107,83,0))]"
      />
      <main className="mx-auto flex min-h-dvh w-full max-w-md flex-col justify-center px-6 pt-[max(2rem,env(safe-area-inset-top))] pb-[max(2.5rem,env(safe-area-inset-bottom))]">
        <div className="rise" style={{ animationDelay: "0ms" }}>
          <h1 className="text-center text-[34px] font-bold tracking-tight">
            Fit<span className="text-intake">Al</span>
            <span className="ml-1 align-super text-[13px] font-bold text-burn">
              .
            </span>
          </h1>
          <p className="pt-1 pb-8 text-center text-[13px] text-ink-soft">
            一句话,记下吃和练
          </p>
        </div>

        {/* 登录/注册切换:与设置页性别滑块同款胶囊 */}
        <div
          className="rise mx-auto mb-5 flex w-fit gap-1 rounded-full bg-hairline/60 p-1"
          style={{ animationDelay: "40ms" }}
        >
          {(["login", "register"] as const).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => switchMode(m)}
              className={`rounded-full px-5 py-1.5 text-[13px] font-semibold transition-colors ${
                mode === m ? "bg-paper shadow-sm" : "text-ink-soft"
              }`}
            >
              {m === "login" ? "登录" : "注册"}
            </button>
          ))}
        </div>

        <form
          className="space-y-2"
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
        >
          {isRegister && (
            <>
              <Field
                label="邀请码"
                value={inviteCode}
                onChange={(v) => setInviteCode(v.toUpperCase())}
                placeholder="问管理员要"
                autoComplete="off"
                delay={60}
              />
              <p className="flex items-center gap-1.5 px-1 pt-1 pb-2 text-[11px] text-ink-soft/80">
                <Ticket size={12} className="shrink-0" />
                一码注册一人,用过即作废
              </p>
            </>
          )}

          <Field
            label="昵称"
            value={nickname}
            onChange={setNickname}
            autoComplete="username"
            delay={80}
          />
          <Field
            label="密码"
            value={password}
            onChange={setPassword}
            type="password"
            autoComplete={isRegister ? "new-password" : "current-password"}
            delay={100}
          />
          {isRegister && password.length > 0 && password.length < 6 && (
            <p className="px-1 text-[11px] text-burn">密码最短 6 位</p>
          )}

          {isRegister && (
            <>
              <p className="px-1 pt-3 pb-1 text-[12px] font-semibold text-ink-soft">
                身体档案
                <span className="ml-1.5 font-normal text-ink-soft/70">
                  用于基础代谢与消耗计算,之后可在设置里改
                </span>
              </p>
              <Field
                label="身高"
                value={height}
                onChange={setHeight}
                mode="decimal"
                unit="cm"
                delay={0}
              />
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
                value={birthYear}
                onChange={setBirthYear}
                mode="numeric"
                unit="年"
                delay={0}
              />
            </>
          )}

          {error && <p className="px-1 pt-1 text-[12px] text-burn">{error}</p>}

          <div className="pt-4">
            <button
              type="submit"
              disabled={!valid || busy}
              className="rise flex w-full items-center justify-center gap-2 rounded-xl bg-ink py-3 text-[15px] font-semibold text-paper transition-transform active:scale-[0.98] disabled:opacity-25"
              style={{ animationDelay: "120ms" }}
            >
              {isRegister ? (
                <UserRound size={16} strokeWidth={2.5} />
              ) : (
                <KeyRound size={16} strokeWidth={2.5} />
              )}
              {busy ? (isRegister ? "注册中…" : "登录中…") : isRegister ? "注册并进入" : "登录"}
            </button>
          </div>
        </form>

        <p
          className="rise px-1 pt-4 text-center text-[11px] leading-relaxed text-ink-soft/70"
          style={{ animationDelay: "160ms" }}
        >
          {isRegister
            ? "注册即登录,不用再输一遍"
            : "没有账号?切到注册,拿邀请码进来 · 忘了密码找管理员重置"}
        </p>
      </main>
    </div>
  );
}
