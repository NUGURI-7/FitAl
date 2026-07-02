# CLAUDE.md

本文件为 Claude Code 在此仓库工作时的指导文档。

## 项目概述

一句话记录型健身/饮食 app:用户输入自然语言(如"我刚做了20个俯卧撑"/"吃了200克鸡胸肉"),LLM 解析为结构化数据入库,前端展示每日摄入/消耗汇总。

- **纯记录工具,不做任何建议/计划/教练功能**
- 自用 + 少量朋友使用,无并发/商业化考量
- 后端:Python (FastAPI + Tortoise ORM + PostgreSQL)
- 前端:iOS 原生 (Swift + SwiftUI),独立目录,后期开发;安卓是远期考虑(iOS 版本完成后再评估),当前不设计、不预留
- 这是一个新项目,按下方"当前阶段"推进

## 核心架构决策(已定稿,不要更改)

以下决策经过充分讨论,除非用户明确要求,**不得偏离**:

1. **LLM 只做三件事:解析、名称映射、拆解。绝不做算术,绝不输出建议性文字。**
   - 数值计算(MET × 体重 × 时长、每100g热量 × 克重)一律在后端 Python 代码中完成
   - 复合菜(如番茄炒蛋)由 LLM 拆解为多条食材记录
2. **解析优先级(严格顺序):**
   1. 用户自己报了热量数字 → 直接采用,`source="user_reported"`
   2. 能匹配到静态表 → LLM 只负责口语名→标准名映射,数值查表计算,`source="met_table"` / `"food_table"`
   3. 表中没有 → LLM 估算,`source="llm_estimated"`(必须标记,前端需区分展示)
3. **LLM 输出必须用 Pydantic structured output 强约束**(discriminated union:`ExerciseRecord | FoodRecord`),接口响应为 `list[ParseResult]`(一句话可能含多条记录)
4. **静态数据走内存 dict,不用数据库、不用 RAG、不用向量检索**
   - `data/food.json`:约 1657 条,源自《中国食物成分表(第6版)》,字段:name/kcal/protein/fat/cho/fiber(每100g)
   - `data/met.json`:常见运动 MET 值表,含中文别名和按次数换算时长的规则(note 字段)
   - 进程启动时加载,精确匹配 + 简单别名匹配;模糊的口语对齐是 LLM 的职责,不是检索的职责
5. **运动消耗公式只用体重**:kcal = MET × 体重(kg) × 时长(h)。不引入身高/体脂/BMR/TDEE
6. **不做注册登录/auth**,多用户仅为简单的用户选择(users 表)
7. 不接入 CoCoWork 或任何外部 agent 平台;AI 逻辑收敛在 `app/ai/` 模块内,一次 LLM 调用解决
8. **数据库迁移用 Tortoise 内置迁移系统**(`tortoise init / makemigrations / migrate`),**杜绝 aerich**;不依赖 generate_schemas 自动建表

## 目录结构

```
backend/
  pyproject.toml       # 后端依赖管理(uv),自包含,不放在仓库根目录
  .env.example
  app/
    main.py            # FastAPI 入口:lifespan + 挂路由,不写业务逻辑
    config.py          # pydantic-settings 读 .env(扁平单文件,不建 core/ 包)
    db.py              # TORTOISE_ORM 配置
    models.py          # Tortoise 模型:users, records
    api.py             # 路由(骨架期仅 /health,业务端点按契约实现,不写占位假端点)
    migrations/        # Tortoise 内置迁移文件(CLI 生成,不手写)
    ai/
      schema.py        # Pydantic 输出 schema(ExerciseRecord/FoodRecord union)
      parser.py        # LLM 调用 + structured output
      lookup.py        # 内存 dict 加载与查表、消耗/热量计算
    data/
      food.json
      met.json
  scripts/             # 一次性脚本(如 food.json 预处理)
  tests/
docs/
  product.md           # 产品定义:做什么/不做什么/典型输入输出
  context.md           # 活文档:当前进度、最近改动、待决策
ios/                   # SwiftUI 前端(后期建立,独立于 backend)
```

### 后端 Import 约定

- `pyproject.toml` 位于 `backend/` 目录下,不在仓库根目录(polyglot monorepo:backend / ios / 远期 android 各自独立管理依赖)
- 所有后端内部 import 使用 `from app.xxx` 形式,例如 `from app.models import User`
- 运行后端命令时在 `backend/` 目录下执行

## 核心接口契约

```
POST /records/parse
请求: { "text": "刚做了20个俯卧撑", "user_id": 1 }
响应: list[ParseResult](解析结果,已入库)

PATCH /records/{id}    # 解析错误时允许手动修正数字
```

用户体重等固定信息由后端按 user_id 读取后注入 prompt,前端不传。

## 数据库

仅两张表:
- `users`:昵称、体重(体重参与消耗计算)
- `records`:user 外键、record_type、原始 text、解析后字段、source、created_at

## 开发命令

```bash
cd backend
uv sync                          # 安装依赖
uv run uvicorn app.main:app --reload   # 启动开发服务
uv run tortoise makemigrations --name <描述>   # 模型变更后生成迁移
uv run tortoise migrate          # 应用迁移
uv run pytest                    # 测试
ruff check && ruff format        # lint
```

数据库为**云端 PostgreSQL**(不跑本地容器):连接信息以 `PG_HOST / PG_PORT / PG_USER / PG_PASSWORD / PG_DATABASE` 分字段填在 `backend/.env`,由用户维护;涉及外部服务的连接配置一律交给用户处理。

## 环境与密钥

- LLM API key、数据库连接串放 `.env`,**绝不硬编码、绝不提交**
- `data/*.json` 是项目必需品,**必须提交进仓库**(合计 <1MB)

## Git 提交规范

```
<type>: <英文短标题,不超过 70 字符>

- 中文要点 1
- 中文要点 2

Co-Authored-By: Claude <当次实际模型名> <noreply@anthropic.com>
```

- `type`:`feat` / `fix` / `refactor` / `chore` / `docs`
- 标题行英文、简洁;body 写中文要点即可,不需要额外英文摘要
- 一个 commit 聚焦一件事
- 署名写当次实际执行提交的模型(如 `Claude Fable 5`),不硬编码某个型号——模型会更换

## 当前阶段

任务清单与实时进度在 `docs/context.md`(活文档,本文件不记进度)。不分里程碑阶段,按顺序清单推进。

固定优先级:后端核心链路(/records/parse)最高;它跑通前不做任何前端和部署工作。

## 已知的坑

- 食物表标准名与口语不一致(库里是"鸡胸脯肉""粳米(标一)",用户说"鸡胸肉""大米"),映射交给 LLM prompt,不要试图用字符串相似度硬解
- 每类食物有"(代表值)"条目,作为该类默认匹配项
- 俯卧撑等按"次数"报告的运动,需经 met.json 中 note 的换算规则转为时长,再进公式
- 表中数值字段可能出现 "Tr"(微量)、"—"(缺失)等非数字字符串,预处理和查表时必须处理

## 工作规则

1. 先读后写:动手前先读相关现有文件
2. 契约先行:新增模块/接口前,先扩写「核心接口契约」/「数据库」等契约类章节,获得批准后才写代码——用户审的是契约,不审代码细节
3. 用户不深读代码:每次改动后用一两句话说明改了什么、如何验证
4. 自检必须给真实证据:改动后必须实际执行验证命令(curl/pytest),把真实终端输出贴出来,不能只说"应该没问题"就声明完成
5. 核心业务逻辑(公式计算、解析优先级判断等有确定输入输出的部分)必须配 pytest 单测,测试函数名用中文描述行为,作为可读的规格替代代码审查
6. 文档分工:本文件只放稳定内容(规则/已定稿决策/契约);进度、最近改动、待决策写 `docs/context.md`,每次有意义的改动后更新它并保持精简(旧内容压缩进历史摘要);产品定义在 `docs/product.md`。不参照本仓库之外的跨项目文档(如 Amoy 根目录的 CODING-STYLE.md,那是 CoCoWork 专属约定)
7. 保持简单直接,禁止过度设计;不引入本文档未列出的新依赖/新组件,除非先说明理由并征得同意
8. 回复使用中文
9. 用户指令始终优先于本文档
