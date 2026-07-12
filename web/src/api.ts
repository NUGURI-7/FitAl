import { cleanFoodName } from "@/lib/foodName";
import type {
  DaySummary,
  DishEntry,
  Group,
  GroupEntry,
  RecordItem,
  Source,
} from "@/types";

// ── 登录态(契约 2026-07-12):令牌存 localStorage,请求头 Bearer 带上;
// 任一业务请求 401(令牌被删/失效)即清本地令牌、整界面踢回登录页 ──────────

const TOKEN_KEY = "fital_token";

export const getToken = () => localStorage.getItem(TOKEN_KEY);

function setAuth(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
}

function clearAuth() {
  localStorage.removeItem(TOKEN_KEY);
}

/** 守卫回调:App 挂载时注册,401 时被调,切回登录页 */
let onUnauthorized: (() => void) | null = null;
export function setUnauthorizedHandler(fn: (() => void) | null) {
  onUnauthorized = fn;
}

function authHeaders(): Record<string, string> {
  const t = getToken();
  // 令牌只可能是 URL-safe ASCII;存储被改坏时当没登录处理,免得 fetch 在浏览器侧就炸
  return t && /^[!-~]+$/.test(t) ? { Authorization: `Bearer ${t}` } : {};
}

/** 登录/注册自身的 401/403 是业务错误(密码不对/码无效),不触发踢回守卫 */
const isAuthCall = (url: string) => url.startsWith("/api/auth/");

// ── 后端响应结构(契约②③④) ─────────────────────────────────────────────

interface ApiFoodItem {
  id: number;
  food_name: string;
  kcal: number;
  grams: number | null;
  protein: number | null;
  fat: number | null;
  cho: number | null;
  fiber: number | null;
  source: Source;
}

/** 餐次明细两种形态(2026-07-08 菜层):菜=成分归拢,合计后端现算 */
interface ApiMealDish {
  type: "dish";
  dish_name: string;
  total_grams: number;
  kcal_total: number;
  items: ApiFoodItem[];
}

type ApiMealEntry = (ApiFoodItem & { type: "food" }) | ApiMealDish;

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
  bmr_kcal: number | null;
  burn_net_kcal: number;
  weight: number | null;
  meals: ApiGroup<ApiMealEntry>[];
  sessions: ApiGroup<ApiExerciseItem>[];
}

async function requestJSON(url: string, init?: RequestInit) {
  const res = await fetch(url, {
    ...init,
    headers: { ...authHeaders(), ...init?.headers },
  });
  if (res.status === 401 && !isAuthCall(url)) {
    clearAuth();
    onUnauthorized?.();
    throw new Error("登录已失效,请重新登录");
  }
  if (!res.ok) {
    let msg = `请求失败(${res.status})`;
    try {
      const e = await res.json();
      if (typeof e.detail === "string") msg = e.detail;
    } catch {
      /* 保持默认错误文案 */
    }
    throw new Error(msg);
  }
  return res.json();
}

// ── 登录/注册/退出(契约 2026-07-12):注册当场发令牌,免二次登录 ──────────

export interface RegisterBody {
  inviteCode: string;
  /** 登录标识:字母数字下划线3-20位,注册后不可改 */
  username: string;
  /** 纯显示名,可重名;留空后端默认用用户名 */
  nickname: string;
  password: string;
  heightCm: number;
  sex: "male" | "female";
  birthYear: number;
}

export async function register(b: RegisterBody): Promise<void> {
  const d = await requestJSON("/api/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      invite_code: b.inviteCode,
      username: b.username,
      nickname: b.nickname || null,
      password: b.password,
      height_cm: b.heightCm,
      sex: b.sex,
      birth_year: b.birthYear,
    }),
  });
  setAuth(d.token);
}

export async function login(username: string, password: string): Promise<void> {
  const d = await requestJSON("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  setAuth(d.token);
}

/** 退出登录:服务器删本枚令牌(幂等);无论成败本地登录态都清 */
export async function logout(): Promise<void> {
  try {
    await requestJSON("/api/auth/logout", { method: "POST" });
  } catch {
    /* 服务器不可达也照样退出本地 */
  } finally {
    clearAuth();
  }
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
  const name = cleanFoodName(i.food_name);
  return {
    id: i.id,
    kind: "food",
    name,
    rawName: name !== i.food_name ? i.food_name : null,
    detail: i.grams != null ? `${+i.grams} g` : "—",
    kcal: kcal(i.kcal),
    kcalNet: null,
    source: i.source,
    grams: i.grams,
    protein: i.protein,
    fat: i.fat,
    cho: i.cho,
    fiber: i.fiber,
    durationMin: null,
    loadKg: null,
    reps: null,
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
    kind: "exercise",
    name: i.exercise_name,
    rawName: null,
    detail: parts.join(" · ") || "—",
    kcal: kcal(i.kcal),
    kcalNet: i.kcal_net != null ? kcal(i.kcal_net) : null,
    source: i.source,
    grams: null,
    protein: null,
    fat: null,
    cho: null,
    fiber: null,
    durationMin: i.duration_min,
    loadKg: i.load_kg,
    reps: i.reps,
  };
}

function dishEntry(d: ApiMealDish): DishEntry {
  return {
    kind: "dish",
    name: d.dish_name,
    totalGrams: d.total_grams,
    kcalTotal: d.kcal_total,
    items: d.items.map(foodItem),
  };
}

function mealEntry(e: ApiMealEntry): GroupEntry {
  return e.type === "dish" ? dishEntry(e) : foodItem(e);
}

function toGroup(
  kind: "meal" | "session",
  g: ApiGroup<ApiMealEntry> | ApiGroup<ApiExerciseItem>,
): Group {
  return {
    id: g.id,
    kind,
    name: g.name ?? (kind === "meal" ? "一顿饭" : "一场训练"),
    timeRange: timeRange(g.start, g.end),
    kcalTotal: g.kcal_total, // 保留小数,统一在渲染处取整,避免多处取整口径不一
    items:
      kind === "meal"
        ? (g.items as ApiMealEntry[]).map(mealEntry)
        : (g.items as ApiExerciseItem[]).map(exerciseItem),
  };
}

// ── 接口调用 ─────────────────────────────────────────────────────────────

export async function fetchDay(dateISO: string): Promise<DaySummary> {
  const d: ApiDay = await requestJSON(`/api/days/${dateISO}`);
  return {
    intakeKcal: d.intake_kcal,
    burnKcal: d.burn_kcal,
    bmrKcal: d.bmr_kcal,
    burnNetKcal: d.burn_net_kcal,
    weightKg: d.weight,
    groups: [
      ...d.meals.map((m) => toGroup("meal", m)),
      ...d.sessions.map((s) => toGroup("session", s)),
    ],
  };
}

/** 修正记录:饮食传 grams/kcal,运动传 duration_min/load_kg/reps/kcal,
 * 体重传 weight_kg;只发改动的字段 */
export async function patchRecord(
  kind: "food" | "exercise" | "weight",
  id: number,
  body: Record<string, number>,
): Promise<void> {
  await requestJSON(`/api/records/${kind}/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function deleteRecord(
  kind: "food" | "exercise" | "weight",
  id: number,
): Promise<void> {
  await requestJSON(`/api/records/${kind}/${id}`, { method: "DELETE" });
}

export interface UserProfile {
  id: number;
  /** 登录标识,只读展示 */
  username: string;
  nickname: string;
  heightCm: number;
  sex: "male" | "female";
  birthYear: number;
}

export async function fetchUser(): Promise<UserProfile> {
  const d = await requestJSON("/api/users/me");
  return {
    id: d.id,
    username: d.username,
    nickname: d.nickname,
    heightCm: d.height_cm,
    sex: d.sex,
    birthYear: d.birth_year,
  };
}

/** 改身体档案:只发改动的字段(nickname/height_cm/sex/birth_year) */
export async function patchUser(
  body: Record<string, string | number>,
): Promise<void> {
  await requestJSON("/api/users/me", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export interface UserFoodItem {
  id: number;
  name: string;
  form: string | null;
  /** 每100克热量 */
  kcal: number;
  updatedAt: Date;
}

export async function fetchUserFoods(): Promise<UserFoodItem[]> {
  const d = await requestJSON("/api/user-foods");
  return (
    d.foods as {
      id: number;
      name: string;
      form: string | null;
      kcal: number;
      updated_at: string;
    }[]
  ).map((f) => ({
    id: f.id,
    name: f.name,
    form: f.form,
    kcal: f.kcal,
    updatedAt: new Date(f.updated_at),
  }));
}

export async function deleteUserFood(id: number): Promise<void> {
  await requestJSON(`/api/user-foods/${id}`, { method: "DELETE" });
}

export interface MemoryItem {
  id: number;
  kind: "alias" | "habit" | "correction";
  content: string;
  updatedAt: Date;
}

export async function fetchMemories(): Promise<MemoryItem[]> {
  const d = await requestJSON("/api/memories");
  return (
    d.memories as {
      id: number;
      kind: MemoryItem["kind"];
      content: string;
      updated_at: string;
    }[]
  ).map((m) => ({
    id: m.id,
    kind: m.kind,
    content: m.content,
    updatedAt: new Date(m.updated_at),
  }));
}

export async function deleteMemory(id: number): Promise<void> {
  await requestJSON(`/api/memories/${id}`, { method: "DELETE" });
}

export interface WeightPoint {
  id: number;
  at: Date;
  kg: number;
}

export async function fetchWeights(days = 30): Promise<WeightPoint[]> {
  const d = await requestJSON(`/api/weights?days=${days}`);
  return (
    d.weights as { id: number; weight_kg: number; created_at: string }[]
  ).map((w) => ({ id: w.id, at: new Date(w.created_at), kg: w.weight_kg }));
}

/** /chat 状态事件(契约 event:status):处理进度,纯增量 */
export type ChatStatus =
  | { stage: "triage" }
  | { stage: "extract"; tracks: string[] }
  | { stage: "track_done"; track: string }
  | { stage: "saving" };

/** 发一句话记录:走对话接口(SSE),返回后端的模板回执;
 * 状态事件按到达顺序回调给 onStatus(过程面板消费) */
export async function sendChat(
  text: string,
  onStatus?: (s: ChatStatus) => void,
): Promise<string> {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ text }),
  });
  if (res.status === 401) {
    clearAuth();
    onUnauthorized?.();
    throw new Error("登录已失效,请重新登录");
  }
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
      } else if (event === "status" && data && onStatus) {
        try {
          onStatus(JSON.parse(data) as ChatStatus);
        } catch {
          /* 状态事件坏了不影响主链路 */
        }
      }
    }
  }
  return reply || "已记录";
}
