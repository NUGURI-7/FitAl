import { Fragment, useEffect, useRef, useState } from "react";
import type { LucideIcon } from "lucide-react";
import {
  Bookmark,
  Database,
  Dumbbell,
  Sparkles,
  UtensilsCrossed,
} from "lucide-react";
import type { ChatStatus } from "@/api";

const TRACK_META: Record<string, { label: string; icon: LucideIcon }> = {
  eat: { label: "饮食", icon: UtensilsCrossed },
  exercise: { label: "运动", icon: Dumbbell },
  remember: { label: "记住", icon: Bookmark },
};

type NodeState = "pending" | "active" | "done";

interface Node {
  key: string;
  label: string;
  icon: LucideIcon;
  state: NodeState;
}

interface Props {
  /** 后端状态事件,按到达顺序追加(只增不减) */
  events: ChatStatus[];
  /** 流已结束(拿到回执或请求失败) */
  done: boolean;
  /** 收场动画播完,可以卸载了 */
  onGone: () => void;
}

/** 事件到达节奏与展示节奏解耦:事件只决定能不能往前走,
 * 每步至少亮一小会儿,快句子(纯体重一秒多)不闪跳 */
const MIN_STEP_MS = 450;
const FAST_STEP_MS = 160; // 流已结束时快进积压事件
const HOLD_MS = 480; // 全亮定格再收
const OUT_MS = 240; // 收场动画时长(与 .proc-out 一致)

/** 发送后的液态玻璃过程面板:流程节点逐个点亮,走完收起让位回执 */
export function ProcessPanel({ events, done, onGone }: Props) {
  const [applied, setApplied] = useState(0); // 已应用到画面的事件数
  const [closing, setClosing] = useState(false);
  const lastStep = useRef(performance.now());
  const onGoneRef = useRef(onGone);
  onGoneRef.current = onGone;

  useEffect(() => {
    if (applied >= events.length) return;
    const min = done ? FAST_STEP_MS : MIN_STEP_MS;
    const wait = Math.max(0, min - (performance.now() - lastStep.current));
    const t = setTimeout(() => {
      lastStep.current = performance.now();
      setApplied((a) => a + 1);
    }, wait);
    return () => clearTimeout(t);
  }, [applied, events.length, done]);

  const allApplied = applied >= events.length;
  useEffect(() => {
    if (!done || !allApplied || closing) return;
    const t = setTimeout(() => setClosing(true), HOLD_MS);
    return () => clearTimeout(t);
  }, [done, allApplied, closing]);

  useEffect(() => {
    if (!closing) return;
    const t = setTimeout(() => onGoneRef.current(), OUT_MS);
    return () => clearTimeout(t);
  }, [closing]);

  // 从已应用的事件推导画面状态
  let tracks: string[] | null = null;
  const doneTracks = new Set<string>();
  let saving = false;
  for (const e of events.slice(0, applied)) {
    if (e.stage === "extract") tracks = e.tracks;
    else if (e.stage === "track_done") doneTracks.add(e.track);
    else if (e.stage === "saving") saving = true;
  }
  // 走到入库才算成功:成功收场全节点点亮;整句失败没有入库事件,保持原状收起
  const finished = done && allApplied && saving;

  const nodes: Node[] = [
    {
      key: "triage",
      label: "理解",
      icon: Sparkles,
      state: finished || tracks !== null ? "done" : "active",
    },
  ];
  if (tracks !== null) {
    for (const t of tracks) {
      const meta = TRACK_META[t] ?? { label: t, icon: Sparkles };
      nodes.push({
        key: t,
        label: meta.label,
        icon: meta.icon,
        // 各路并发:出现即活跃;入库开始说明各路都已收束
        state: finished || saving || doneTracks.has(t) ? "done" : "active",
      });
    }
    nodes.push({
      key: "saving",
      label: "入库",
      icon: Database,
      state: finished ? "done" : saving ? "active" : "pending",
    });
  }

  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-20 z-50 flex justify-center px-6">
      <div
        className={`relative overflow-hidden rounded-2xl bg-paper/70 px-4 py-2 shadow-[0_8px_30px_rgba(38,35,29,0.18)] ring-1 ring-black/[0.08] backdrop-blur-xl ${
          closing ? "proc-out" : "rise"
        }`}
      >
        <span className="pointer-events-none absolute inset-0 rounded-2xl bg-[radial-gradient(circle_at_30%_0%,rgba(255,255,255,0.9),rgba(255,255,255,0)_65%)]" />
        <div className="relative flex items-center gap-1.5">
          {nodes.map((n, i) => {
            const Icon = n.icon;
            const prevDone = i > 0 && nodes[i - 1].state === "done";
            return (
              <Fragment key={n.key}>
                {i > 0 && (
                  <span
                    className={`h-0.5 w-4 shrink-0 rounded-full ${
                      n.state === "done"
                        ? "bg-intake/60"
                        : prevDone && n.state === "active"
                          ? "proc-flow bg-intake/15"
                          : "bg-ink/10"
                    }`}
                  />
                )}
                <span className="unfold flex w-9 flex-col items-center gap-1">
                  <span
                    className={`flex size-7 items-center justify-center rounded-full transition-colors duration-300 ${
                      n.state === "done"
                        ? "bg-intake text-white"
                        : n.state === "active"
                          ? "node-pulse bg-intake-soft text-intake"
                          : "bg-ink/[0.05] text-ink-soft/50"
                    }`}
                  >
                    <Icon size={13} strokeWidth={2.5} />
                  </span>
                  <span
                    className={`text-[10px] leading-none ${
                      n.state === "pending"
                        ? "text-ink-soft/50"
                        : "text-ink-soft"
                    }`}
                  >
                    {n.label}
                  </span>
                </span>
              </Fragment>
            );
          })}
        </div>
      </div>
    </div>
  );
}
