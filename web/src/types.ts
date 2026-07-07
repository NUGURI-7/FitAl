export type Source =
  | "user_reported"
  | "user_food"
  | "food_table"
  | "met_table"
  | "llm_estimated";

export interface RecordItem {
  id: number;
  name: string;
  /** 份量描述:"150 g" / "60kg × 12" / "30 分钟" / "1 勺" */
  detail: string;
  kcal: number;
  /** 运动净耗;饮食为 null */
  kcalNet: number | null;
  source: Source;
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
  dateLabel: string;
  weekdayLabel: string;
  intakeKcal: number;
  burnKcal: number;
  weightKg: number | null;
  groups: Group[];
}
