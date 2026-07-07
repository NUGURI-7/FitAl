export type Source =
  | "user_reported"
  | "user_food"
  | "food_table"
  | "met_table"
  | "llm_estimated";

export interface RecordItem {
  id: number;
  kind: "food" | "exercise";
  name: string;
  /** 份量描述:"150 g" / "60kg × 12" / "30 分钟" / "1 勺" */
  detail: string;
  kcal: number;
  /** 运动净耗;饮食为 null */
  kcalNet: number | null;
  source: Source;
  // 原始数值:编辑与营养展示用(饮食/运动各自适用的字段,其余为 null)
  grams: number | null;
  protein: number | null;
  fat: number | null;
  cho: number | null;
  fiber: number | null;
  durationMin: number | null;
  loadKg: number | null;
  reps: number | null;
}

export interface Group {
  id: number;
  kind: "meal" | "session";
  name: string;
  timeRange: string;
  kcalTotal: number;
  items: RecordItem[];
}

export interface DaySummary {
  intakeKcal: number;
  burnKcal: number;
  /** 全天基础代谢(该日结束前最近体重+档案算);从未称重为空 */
  bmrKcal: number | null;
  /** 当天运动净耗合计(净摄入公式用,避免与基础代谢重复扣) */
  burnNetKcal: number;
  weightKg: number | null;
  groups: Group[];
}
