const pad = (n: number) => String(n).padStart(2, "0");

/** 本地日历日 → YYYY-MM-DD(后端按本地时区切日) */
export function toISODate(d: Date): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

export function addDays(d: Date, n: number): Date {
  const r = new Date(d);
  r.setDate(r.getDate() + n);
  return r;
}

export function isToday(d: Date): boolean {
  return toISODate(d) === toISODate(new Date());
}

export function dateLabel(d: Date): string {
  const diff =
    (new Date(toISODate(new Date())).getTime() -
      new Date(toISODate(d)).getTime()) /
    86400000;
  if (diff === 0) return "今天";
  if (diff === 1) return "昨天";
  if (diff === 2) return "前天";
  return `${d.getMonth() + 1}月${d.getDate()}日`;
}

export function subLabel(d: Date): string {
  const week = `周${"日一二三四五六"[d.getDay()]}`;
  // 大标题已是具体日期(非今/昨/前天)时,副标题只留星期,避免重复
  return dateLabel(d).includes("月")
    ? week
    : `${d.getMonth() + 1}月${d.getDate()}日 ${week}`;
}
