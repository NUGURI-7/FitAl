import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { ArrowUp, LoaderCircle, Mic } from "lucide-react";
import { createVoice, type VoiceController } from "@/lib/voice";

interface Props {
  sending: boolean;
  /** 返回 true 表示发送成功,清空输入框 */
  onSend: (text: string) => Promise<boolean>;
  /** 语音出错时提示(复用主界面的气泡) */
  onNotice?: (msg: string, isError?: boolean) => void;
}

type Rec = "idle" | "connecting" | "recording" | "finishing";

/** 声波条各柱的相对权重,给不齐的自然形态 */
const BARS = [0.45, 0.75, 1, 0.85, 0.6, 0.9, 0.5];

/** 累加拼接:已有内容非空时,去掉尾部空白再空一格接上新文字 */
const join = (base: string, t: string) =>
  !t ? base : base ? base.replace(/\s+$/, "") + " " + t : t;

/** 底部固定输入框:一句话记录 + 语音输入 */
export function InputBar({ sending, onSend, onNotice }: Props) {
  const [text, setText] = useState("");
  const [rec, setRec] = useState<Rec>("idle");
  const [level, setLevel] = useState(0);
  const ctrl = useRef<VoiceController | null>(null);
  const baseRef = useRef(""); // 本次录音开始前框里已有的内容
  const taRef = useRef<HTMLTextAreaElement>(null);

  const active = rec !== "idle";

  // 卸载时静默清理未结束的会话
  useEffect(() => () => ctrl.current?.cancel(), []);

  // 随内容自动长高:置空重测,夹在一行(40)到约五行(132)之间,超出框内滚动
  useLayoutEffect(() => {
    const ta = taRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = `${Math.min(Math.max(ta.scrollHeight, 40), 132)}px`;
  }, [text]);

  const startRec = () => {
    if (sending || active) return;
    baseRef.current = text;
    setRec("connecting");
    setLevel(0);
    ctrl.current = createVoice({
      onState: setRec,
      onPartial: (full) => setText(join(baseRef.current, full)),
      onLevel: setLevel,
      onDone: (final) => {
        if (final) setText(join(baseRef.current, final));
        ctrl.current = null;
        setRec("idle");
        setLevel(0);
      },
      onError: (msg) => {
        ctrl.current = null;
        setRec("idle");
        setLevel(0);
        onNotice?.(msg, true);
      },
    });
  };

  const toggleRec = () => (active ? ctrl.current?.stop() : startRec());

  const submit = async () => {
    const t = text.trim();
    if (!t || sending) return;
    if (await onSend(t)) setText("");
  };

  const now = Date.now();

  return (
    <div className="fixed inset-x-0 bottom-0 z-20 border-t border-hairline bg-paper/85 backdrop-blur-md">
      {/* 录音时:输入框上方浮一条声波,跟随说话抖动 */}
      {active && (
        <div className="mx-auto flex max-w-md items-center justify-center gap-2.5 px-4 pt-2.5">
          <span className="flex h-6 items-end gap-[3px]">
            {BARS.map((w, i) => {
              const wobble = 0.5 + 0.5 * Math.abs(Math.sin(now / 180 + i));
              const h = 3 + level * 20 * w * wobble;
              return (
                <span
                  key={i}
                  style={{ height: `${h}px` }}
                  className="w-[3px] rounded-full bg-burn"
                />
              );
            })}
          </span>
          <span className="text-[12px] text-ink-soft">
            {rec === "connecting"
              ? "连接中…"
              : rec === "finishing"
                ? "识别中…"
                : "正在聆听"}
          </span>
        </div>
      )}

      <div className="mx-auto flex max-w-md items-end gap-2 px-4 py-2.5 pb-[max(0.625rem,env(safe-area-inset-bottom))]">
        <div className="relative min-w-0 flex-1">
          <textarea
            ref={taRef}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              // 回车发送,Shift+回车换行;中文输入法组词中的回车不算发送
              if (
                e.key === "Enter" &&
                !e.shiftKey &&
                !e.nativeEvent.isComposing
              ) {
                e.preventDefault();
                submit();
              }
            }}
            disabled={sending}
            rows={1}
            placeholder={
              sending
                ? "记录中…"
                : active
                  ? ""
                  : "说一句,比如:卧推60公斤10个"
            }
            className="block max-h-[132px] w-full resize-none overflow-y-auto rounded-[20px] bg-card py-2 pl-4 pr-11 text-[15px] leading-[22px] shadow-[0_1px_2px_rgba(38,35,29,0.06)] ring-1 ring-black/[0.04] outline-none placeholder:text-ink-soft/60 disabled:opacity-60"
          />
          {/* 麦克风:嵌在输入框内部右下角,点开点关 */}
          <button
            type="button"
            onClick={toggleRec}
            disabled={sending}
            aria-label={active ? "停止语音输入" : "语音输入"}
            aria-pressed={active}
            className={`absolute right-1.5 bottom-1.5 flex size-7 items-center justify-center rounded-full transition-colors disabled:opacity-40 ${
              active ? "bg-burn text-white" : "text-intake"
            }`}
          >
            {rec === "connecting" || rec === "finishing" ? (
              <LoaderCircle size={15} className="animate-spin" />
            ) : active ? (
              <span className="relative flex">
                <Mic size={15} />
                <span className="absolute -inset-1.5 rounded-full bg-burn/40 animate-ping" />
              </span>
            ) : (
              <Mic size={15} />
            )}
          </button>
        </div>
        <button
          type="button"
          onClick={submit}
          disabled={!text.trim() || sending || active}
          className="flex size-10 shrink-0 items-center justify-center rounded-full bg-ink text-paper transition-opacity disabled:opacity-25"
          aria-label="发送"
        >
          {sending ? (
            <LoaderCircle size={18} className="animate-spin" />
          ) : (
            <ArrowUp size={18} strokeWidth={2.5} />
          )}
        </button>
      </div>
    </div>
  );
}
