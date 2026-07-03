# FitAl 任务看板

> 唯一的待办/已办清单,每次有进展就更新。当前状态细节与待决策见 `context.md`。

## ✅ 已完成

- [x] 三文档体系 + 全部设计定稿:架构主流程、七张表、chat 契约 v3、读写不对称、LLM 选型(2026-07-02)
- [x] 后端骨架:FastAPI + Tortoise 连云端 PG,`/health` 可用,内置迁移体系跑通
- [x] 静态数据:food.json 1575 条(清洗 + 三道校验,排除 82 条坏数据)、met.json 50 条起始集
- [x] 七张表落库:迁移 0002 已应用云端;单测切内存 SQLite
- [x] lookup.py:查表两级匹配 + 全部热量公式,14 个单测全过
- [x] 数据补全:旧版独有 20 条主食(馒头/花卷/油条/煮面条等)质检后并入,food.json 1575→1595;查表键标点归一化。面包/饺子/包子源头无数据,走估算兜底
- [x] met.json 补杠铃五动作(卧推/杠铃深蹲/硬拉/推举/杠铃划船,MET 6.0),50→55 条;组间隔公式精确化入档 CLAUDE.md
- [x] 估算策略定稿存档:表外食物"AI 定结构,表定数值";表外力量动作归强度档、动作名照存——均已写入 CLAUDE.md 决策 2
- [x] met 表扩到 80 条(常见健身房动作按肌群补齐,复合 6.0/孤立 3.5)
- [x] 消耗口径双存(主显总耗,净耗同存)+ 自定义食物表 user_foods:迁移 0003 已应用云端,查表优先级=自报>自定义>标准表>估算

## 🔨 进行中

- [ ] 解析器:schema.py + parser.py(PydanticAI + deepseek-v4-flash)+ 离线测试

## 📋 待办(按顺序)

- [ ] /chat 端点(intent=record):解析入库 raw + 力量组间隔消耗
- [ ] 聚合链路 aggregate.py:规则归组 + AI 起名 → meals/sessions
- [ ] 修正/删除接口(PATCH/DELETE,触发聚合重算)
- [ ] 展示接口:/days、/weights、/users
- [ ] ai_memories 记忆:纠正即时学 + 每日首次请求巩固
- [ ] 真实使用打磨(错例驱动)
- [ ] 读代理(自然语言查数,周报是查询的一种)→ 澄清式反问
- [ ] 响应式 Web 前端(移动端优先;动工前先对齐功能形态)
- [ ] iOS 原生前端(SwiftUI,不设 deadline)

## ⏳ 等用户

- [ ] `backend/.env` 填 `DEEPSEEK_API_KEY`(platform.deepseek.com)——解析器联调前必须
