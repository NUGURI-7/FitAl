import { useState } from "react";
import { ArrowUp } from "lucide-react";

/** 底部固定输入框:一句话记录(发送逻辑第二步接后端) */
export function InputBar() {
  const [text, setText] = useState("");

  return (
    <div className="fixed inset-x-0 bottom-0 z-20 border-t border-hairline bg-paper/85 backdrop-blur-md">
      <div className="mx-auto flex max-w-md items-center gap-2 px-4 py-2.5 pb-[max(0.625rem,env(safe-area-inset-bottom))]">
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="说一句,比如:卧推60公斤10个"
          className="h-10 min-w-0 flex-1 rounded-full bg-card px-4 text-[15px] shadow-[0_1px_2px_rgba(38,35,29,0.06)] ring-1 ring-black/[0.04] outline-none placeholder:text-ink-soft/60"
        />
        <button
          type="button"
          disabled={!text.trim()}
          className="flex size-10 shrink-0 items-center justify-center rounded-full bg-ink text-paper transition-opacity disabled:opacity-25"
          aria-label="发送"
        >
          <ArrowUp size={18} strokeWidth={2.5} />
        </button>
      </div>
    </div>
  );
}
