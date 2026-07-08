/** 食物名展示清理:官方成分表的书面名带一堆编制术语(代表值/fat3g/标三/特等),
 * 对普通用户太生硬。列表里只删这几类纯术语,保留一切有意义的描述(瘦/干/鲜/蒸/部位/加糖等);
 * 完整学名收进详情。纯展示层,不动任何数值。 */

/** 该括号片段是否为可丢弃的编制术语 */
function isJargon(seg: string): boolean {
  return (
    seg === "代表值" ||
    seg === "特等" ||
    /^标[一二三四]$/.test(seg) || // 粳米/籼米的精度分级
    /^fat\d+(\.\d+)?g$/i.test(seg) // 肉类脂肪含量档,如 fat3g
  );
}

/** 去掉括号里的纯术语片段;括号内若因此清空则连括号一并去掉 */
export function cleanFoodName(raw: string): string {
  return raw
    .replace(/[（(]([^）)]*)[）)]/g, (_whole, inner: string) => {
      const kept = inner
        .split(/[，,]/)
        .map((s) => s.trim())
        .filter((s) => s && !isJargon(s));
      return kept.length ? `(${kept.join("，")})` : "";
    })
    .trim();
}
