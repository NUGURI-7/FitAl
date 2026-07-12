import { useState } from "react";
import { CircleHelp, X } from "lucide-react";
import { type ChatClarify, submitClarify } from "@/api";

interface Props {
  clarify: ChatClarify;
  /** 补交成功:带回执文字,父层弹气泡+静默刷新 */
  onDone: (reply: string) => void;
  /** 收起(先不填):数据不丢,待补段躺在服务器上 */
  onDismiss: () => void;
  /** 已补过/不在待补态(409):父层收起并提示 */
  onStale: (msg: string) => void;
}

/** 澄清小表单(契约 event:clarify,2026-07-12):罕见兜底——运动段缺数
 * 连估都估不出时浮出;问题固定=一句问话+数字输入框+单位,不做通用表单 */
export function ClarifyCard({ clarify, onDone, onDismiss, onStale }: Props) {
  const [values, setValues] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 只提交填了正数的格子;后端重跑同套校验,没填够会打回
  const answers: Record<string, number> = {};
  for (const q of clarify.questions) {
    const v = Number.parseFloat(values[q.key] ?? "");
    if (Number.isFinite(v) && v > 0) answers[q.key] = v;
  }
  const filled = Object.keys(answers).length;
  const ready =
    filled >= clarify.minAnswers &&
    clarify.questions.every((q) => !q.required || q.key in answers);
  const eitherOne =
    clarify.minAnswers === 1 && clarify.questions.length > clarify.minAnswers;

  const submit = async () => {
    if (!ready || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      onDone(await submitClarify(clarify.inputId, answers));
    } catch (e) {
      const msg = e instanceof Error ? e.message : "提交失败";
      // 409=这行已经补过/不在待补态,表单没有存在意义,交父层收场
      if (msg.includes("待补")) onStale(msg);
      else {
        setError(msg);
        setSubmitting(false);
      }
    }
  };

  return (
    <div className="fixed inset-x-0 bottom-36 z-40 flex justify-center px-6">
      <div className="rise relative w-full max-w-sm overflow-hidden rounded-2xl bg-paper/80 p-4 shadow-[0_8px_30px_rgba(38,35,29,0.18)] ring-1 ring-black/[0.08] backdrop-blur-xl">
        <span className="pointer-events-none absolute inset-0 rounded-2xl bg-[radial-gradient(circle_at_30%_0%,rgba(255,255,255,0.9),rgba(255,255,255,0)_65%)]" />
        <div className="relative">
          <div className="flex items-start gap-2">
            <span className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-lg bg-intake-soft text-intake">
              <CircleHelp size={13} strokeWidth={2.5} />
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-[13px] leading-tight font-bold">
                还差个数才能记上
              </p>
              <p className="mt-0.5 truncate text-[12px] text-ink-soft">
                「{clarify.text}」
              </p>
            </div>
            <button
              type="button"
              onClick={onDismiss}
              aria-label="先不填"
              className="-mt-1 -mr-1 flex size-7 shrink-0 items-center justify-center rounded-full text-ink-soft/70 active:bg-ink/[0.06]"
            >
              <X size={15} />
            </button>
          </div>

          <div className="mt-3 space-y-2">
            {clarify.questions.map((q) => (
              <label key={q.key} className="flex items-center gap-2">
                <span className="min-w-0 flex-1 truncate text-[13px]">
                  {q.prompt}
                </span>
                <input
                  type="number"
                  inputMode="decimal"
                  min={0}
                  value={values[q.key] ?? ""}
                  onChange={(e) =>
                    setValues((v) => ({ ...v, [q.key]: e.target.value }))
                  }
                  disabled={submitting}
                  className="num h-9 w-20 shrink-0 rounded-xl bg-card px-3 text-right text-[15px] shadow-[0_1px_2px_rgba(38,35,29,0.06)] ring-1 ring-black/[0.04] outline-none focus:ring-intake/40 disabled:opacity-60"
                />
                <span className="w-8 shrink-0 text-[12px] text-ink-soft">
                  {q.unit}
                </span>
              </label>
            ))}
          </div>

          {eitherOne && (
            <p className="mt-2 text-[11px] text-ink-soft/70">填其中一项即可</p>
          )}
          {error && <p className="mt-2 text-[12px] text-burn">{error}</p>}

          <button
            type="button"
            onClick={submit}
            disabled={!ready || submitting}
            className="mt-3 h-10 w-full rounded-full bg-intake text-[14px] font-bold text-white transition-opacity active:opacity-85 disabled:opacity-30"
          >
            {submitting ? "记录中…" : "补交记上"}
          </button>
        </div>
      </div>
    </div>
  );
}
