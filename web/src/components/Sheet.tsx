import type { ReactNode } from "react";
import { X } from "lucide-react";

/** 通用底部抽屉:点遮罩或关闭键收起 */
export function Sheet({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
}) {
  return (
    <div className="fixed inset-0 z-40">
      <button
        type="button"
        onClick={onClose}
        aria-label="关闭"
        className="fade-in absolute inset-0 bg-ink/35"
      />
      <div className="sheet-up absolute inset-x-0 bottom-0 max-h-[85dvh] overflow-y-auto rounded-t-3xl bg-paper shadow-[0_-8px_32px_rgba(38,35,29,0.18)]">
        <div className="mx-auto max-w-md px-5 pb-[max(1.25rem,env(safe-area-inset-bottom))]">
          <div className="sticky top-0 z-10 flex items-center justify-between bg-paper pt-4 pb-2">
            <h2 className="text-[17px] font-bold">{title}</h2>
            <button
              type="button"
              onClick={onClose}
              aria-label="关闭"
              className="flex size-8 items-center justify-center rounded-full bg-hairline/70 text-ink-soft active:bg-hairline"
            >
              <X size={16} strokeWidth={2.5} />
            </button>
          </div>
          {children}
        </div>
      </div>
    </div>
  );
}
