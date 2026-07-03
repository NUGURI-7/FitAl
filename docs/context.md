# FitAl 项目状态(context)

> 活文档:当前进度、最近改动、待决策。每次有意义的改动后更新;保持精简,旧内容压缩进历史摘要。
> 稳定内容(架构决策/契约/工作规则)在 `../CLAUDE.md`,产品定义在 `product.md`。

## 任务清单(按顺序执行,不分里程碑阶段)

- [x] 后端骨架(已验收:云端 PG 迁移建表成功,pytest /health 通过)
- [x] 数据表:food.json(1575 条)/ met.json(50 条起始集)已生成并校验
- [ ] 洗数据链路(/chat intent=record→AI 洗→raw)+ 修正/删除接口
- [ ] 聚合链路(raw→AI 聚合→new):meals/sessions + ai_memories
- [ ] 展示接口:/days、/weights、用户管理
- [ ] 真实使用打磨:按实际解析错例优化映射与记忆
- [ ] 读代理(同一 /chat 入口新 intent:自然语言查数,周报是查询的一种)→ 澄清式反问
- [ ] 响应式 Web 前端(移动端优先,PC 能用即可)
- [ ] iOS 原生前端(SwiftUI,不设 deadline)

当前位置:数据表已交付,下一步 **解析链路**。

## 当前状态(2026-07-02)

- **数据表已交付**:
  - `app/data/food.json` 1575 条(330KB),源自《中国食物成分表第6版》的 Sanotsu 开源提取版(视觉模型最新修正版),经 `scripts/build_food_json.py` 清洗:Tr→0、缺失→null、能量 Atwater 粗校验、与 OCR 版交叉比对;方括号别名已拆出(番茄→西红柿)
  - 排除 82 条进 `scripts/food_needs_review.json`:其中"野生蔬菜类(048)"整类疑似 kJ 错灌 kcal 列(≈4.18 倍规律),对饮食记录零影响;高频食物抽查全部对上教科书值(鸡胸脯肉118/鸡蛋139/粳米345)
  - `app/data/met.json` 50 条起始集(名称/别名/MET/count_seconds 按次换算秒数),数值依据 Compendium of Physical Activities;缺啥边用边补
  - foodwake 弃用(粗纤维≠膳食纤维、溯源断裂);源仓库无明确许可,自用不分发,风险已知

- 后端骨架已交付:`backend/`(pyproject / app/{main,config,db,models,api}.py / migrations / tests)
- **数据库改为云端 PostgreSQL**(用户决策,推翻原"本地 docker compose"方案):连接串填 `backend/.env` 的 `DATABASE_URL`,外部连接一律由用户处理;CLAUDE.md 已同步
- 根目录 uv init 残留(main.py / pyproject.toml / .python-version)已删,新增根 `.gitignore`
- 已验证(不依赖 DB 的部分):`ruff format + check` 全过;`from app.main import app` 导入成功;`tortoise init` + `makemigrations --name initial` 离线生成 `0001_initial.py`(users / records 两表,外键级联)
- 骨架尚未提交 git

## 设计对齐进度(2026-07-02,与用户逐块过设计)

- [x] 核心流程(LLM 只听懂/后端算数/可修正)+ 输入画像:短句、高频、一次一条
- [x] 力量按组记录:消耗=组动作+距上一组间隔,>20min 算新场,程序聚合
- [x] 数据库定稿:四张表拆表方案(见 CLAUDE.md「数据库」),餐次/场次现算不存
- [x] 身体档案:身高/性别/出生年份进 users,修正 MET;体重历史 weight_records
- [x] 补油显式原则:没报油自动补独立条目,标 AI 估算可删
- [x] 主流程定稿:userinput→AI 洗→raw→AI 聚合→new→展示;三条铁律;七张表;ai_memories 记忆
- [x] 接口契约 v3:chat 单入口(SSE,intent 路由)+ REST 展示/修正接口
- [x] 读写不对称:写=管线+微循环校验重试;读=只读工具 agent;无 LangGraph
- [x] LLM 选型:PydanticAI + deepseek-v4-flash(deepseek-chat 将于 2026/07/24 弃用);双库策略:测试 SQLite/生产云 PG,不自建仓储层

**设计全部收官(2026-07-02)。下一步:写洗数据链路,动手前先按新表结构改 models + 迁移。**

## 待决策

1. Web 端具体产品功能形态(页面/交互细节)—— 开做 Web 前与用户对齐

## 待用户

`backend/.env` 补一行 `DEEPSEEK_API_KEY=sk-xxx`(DeepSeek 开放平台申请)

## 历史摘要

- 2026-07-02:项目启动。定稿 CLAUDE.md;建立三文档体系;批准并执行后端骨架(CoCoWork 参考模式已吸收,参考清单随之删除);DB 方案改为云端直连。
