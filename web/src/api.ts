import type { DaySummary, Group, RecordItem, Source } from "@/types";

/** 单人使用期固定用户(2026-07-06 定案,多用户时再做选人) */
export const USER_ID = 1;

// ── 后端 /days 响应结构(契约③) ──────────────────────────────────────────

interface ApiFoodItem {
  id: number;
  food_name: string;
  kcal: number;
  grams: number | null;
  source: Source;
}

interface ApiExerciseItem {
  id: number;
  exercise_name: string;
  kcal: number;
  kcal_net: number | null;
  duration_min: number | null;
  load_kg: number | null;
  reps: number | null;
  source: Source;
}

interface ApiGroup<T> {
  id: number;
  name: string | null;
  start: string;
  end: string;
  kcal_total: number;
  items: T[];
}

interface ApiDay {
  date: string;
  intake_kcal: number;
  burn_kcal: number;
  weight: number | null;
  meals: ApiGroup<ApiFoodItem>[];
  sessions: ApiGroup<ApiExerciseItem>[];
}

// ── 视图映射 ─────────────────────────────────────────────────────────────

const hm = (iso: string) =>
  new Date(iso).toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });

function timeRange(start: string, end: string): string {
  const a = hm(start);
  const b = hm(end);
  return a === b ? a : `${a} – ${b}`;
}

const kcal = (n: number) => Math.round(n);

function foodItem(i: ApiFoodItem): RecordItem {
  return {
    id: i.id,
    name: i.food_name,
    detail: i.grams != null ? `${+i.grams} g` : "按份记",
    kcal: kcal(i.kcal),
    kcalNet: null,
    source: i.source,
  };
}

function exerciseItem(i: ApiExerciseItem): RecordItem {
  const parts: string[] = [];
  if (i.load_kg != null && i.reps != null) {
    parts.push(`${+i.load_kg}kg × ${i.reps}`);
  } else if (i.reps != null) {
    parts.push(`× ${i.reps} 次`);
  }
  if (i.duration_min != null) parts.push(`${+i.duration_min.toFixed(1)} 分钟`);
  return {
    id: i.id,
    name: i.exercise_name,
    detail: parts.join(" · ") || "—",
    kcal: kcal(i.kcal),
    kcalNet: i.kcal_net != null ? kcal(i.kcal_net) : null,
    source: i.source,
  };
}

function toGroup(
  kind: "meal" | "session",
  g: ApiGroup<ApiFoodItem> | ApiGroup<ApiExerciseItem>,
): Group {
  return {
    id: g.id,
    kind,
    name: g.name ?? (kind === "meal" ? "一顿饭" : "一场训练"),
    timeRange: timeRange(g.start, g.end),
    kcalTotal: g.kcal_total, // 保留小数,统一在渲染处取整,避免多处取整口径不一

    items:
      kind === "meal"
        ? (g.items as ApiFoodItem[]).map(foodItem)
        : (g.items as ApiExerciseItem[]).map(exerciseItem),
  };
}

// ── 接口调用 ─────────────────────────────────────────────────────────────

export async function fetchDay(dateISO: string): Promise<DaySummary> {
  const res = await fetch(`/api/days/${dateISO}?user_id=${USER_ID}`);
  if (!res.ok) throw new Error(`加载失败(${res.status})`);
  const d: ApiDay = await res.json();
  return {
    intakeKcal: d.intake_kcal,
    burnKcal: d.burn_kcal,
    weightKg: d.weight,
    groups: [
      ...d.meals.map((m) => toGroup("meal", m)),
      ...d.sessions.map((s) => toGroup("session", s)),
    ],
  };
}

/** 发一句话记录:走对话接口(SSE),返回后端的模板回执 */
export async function sendChat(text: string): Promise<string> {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: USER_ID, text }),
  });
  if (!res.ok) {
    let msg = `发送失败(${res.status})`;
    try {
      const e = await res.json();
      if (typeof e.detail === "string") msg = e.detail;
    } catch {
      /* 保持默认错误文案 */
    }
    throw new Error(msg);
  }

  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  let reply = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let idx: number;
    while ((idx = buf.indexOf("\n\n")) >= 0) {
      const block = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      let event = "";
      let data = "";
      for (const line of block.split("\n")) {
        if (line.startsWith("event: ")) event = line.slice(7).trim();
        else if (line.startsWith("data: ")) data += line.slice(6);
      }
      if (event === "reply" && data) {
        try {
          reply = (JSON.parse(data) as { text?: string }).text ?? "";
        } catch {
          /* 数据块解析失败则沿用已有回执 */
        }
      }
    }
  }
  return reply || "已记录";
}
