# FitAl 项目状态(context)

> 活文档:当前进度、最近改动、待决策。每次有意义的改动后更新;保持精简,旧内容压缩进历史摘要。
> 稳定内容(架构决策/契约/工作规则)在 `../CLAUDE.md`,产品定义在 `product.md`。

## 任务清单(按顺序执行,不分里程碑阶段)

- [x] 后端骨架(已验收:云端 PG 迁移建表成功,pytest /health 通过)
- [x] 数据表:food.json(1575 条)/ met.json(50 条起始集)已生成并校验
- [ ] 解析链路:/records/parse 跑通,curl 可验证
- [ ] 真实使用打磨:按实际解析错例优化映射
- [ ] iOS 前端(SwiftUI,不设 deadline)

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

## 待决策

1. **Record 类型专属字段怎么存**:单表 + JSONB 详情字段(倾向) vs 拆 exercise/food 两张子表 —— 做解析链路设计 models 时定
2. **LLM 库与模型选型**:倾向 PydanticAI,底层模型未定 —— 写 `app/ai/` 时定

## 历史摘要

- 2026-07-02:项目启动。定稿 CLAUDE.md;建立三文档体系;批准并执行后端骨架(CoCoWork 参考模式已吸收,参考清单随之删除);DB 方案改为云端直连。
