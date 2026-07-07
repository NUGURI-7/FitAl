# CLAUDE.md

本文件为 Claude Code 在此仓库工作时的指导文档。

## 项目概述

一句话记录型健身/饮食 app:用户输入自然语言(如"我刚做了20个俯卧撑"/"吃了200克鸡胸肉"),LLM 解析为结构化数据入库,前端展示每日摄入/消耗汇总。

- **纯记录工具,不做任何建议/计划/教练功能**
- 自用 + 少量朋友使用,无并发/商业化考量
- 后端:Python (FastAPI + Tortoise ORM + PostgreSQL)
- 前端多端分阶段(2026-07-06 用户修正定位):**设计从 iOS app 出发**,Web 是该设计的快速实现(轻量工具定位,先行验证、发链接即用)→ **iOS 原生(Swift + SwiftUI)为主产品** → 安卓原生远期(有真实安卓用户再评估)。**Web 只按手机宽度设计,不做 PC 适配**(PC 打开即居中窄栏);**前端一律用图标库,不用 emoji**。各端独立目录、独立代码,界面代码不跨端复用,后端契约对所有端通用;Web 具体功能形态待与用户对齐。**Web 技术栈(2026-07-06 定,07-07 补充)**:React + Vite + Tailwind + shadcn/ui(组件源码拷入项目,按 iOS 观感重调样式;不用 Vant 等现成移动端组件库),图标 Lucide,图表 ECharts。**前端体验标准(2026-07-07 用户定):按 To C 消费级做,拒绝 To B 后台风**——界面要有动效(入场/数字滚动/微交互/呼吸浮动)与质感(渐变/柔影/有机形态),不做基础组件素色堆叠;深色大块背景已被用户否决,质感在浅色纸感体系内做。**已否决(2026-07-07 用户定)**:不做"数据只存设备"的 iOS 本地版,所有端一律走服务器后端(主流服务型架构);后端换 SQLite 只是"服务器不装 PG"的自托管便利,不等于数据在手机本地,勿混淆
- 这是一个新项目,按下方"当前阶段"推进

## 核心架构决策(已定稿,不要更改)

以下决策经过充分讨论,除非用户明确要求,**不得偏离**:

1. **LLM 只做三件事:解析、名称映射、拆解。绝不做算术,绝不输出建议性文字。**
   - 数值计算(MET × 体重 × 时长、每100g热量 × 克重)一律在后端 Python 代码中完成
   - 复合菜(如番茄炒蛋)由 LLM 拆解为多条食材记录
2. **解析优先级(严格顺序):**
   1. 用户自己报了热量数字 → 直接采用,`source="user_reported"`
   2. 命中该用户的自定义食物表(user_foods,按"份"定义)→ 用用户定义值,`source="user_food"`
   3. 能匹配到静态表 → LLM 只负责口语名→标准名映射,数值查表计算,`source="met_table"` / `"food_table"`
   4. 表中没有 → LLM 估算,`source="llm_estimated"`(必须标记,前端需区分展示)
   - **补油显式原则**(2026-07-02 用户定):炒/煎/炸类只报了食材没报油 → 自动补一条"烹调油(约10g)"独立记录,标 `llm_estimated`,可删可改;绝不把油隐性折进菜品热量。用户报了油则用用户的
   - **表外食物的估算策略——AI 定结构,表定数值**(2026-07-02 定):表里没有的食物,LLM 优先拆解为表内食材(只估克重,不估热量)或锚定最相近的表内条目取值;实在无法借表,才允许 LLM 直接报热量数。三种路径一律标 `llm_estimated`
   - **表外力量动作归强度档**(2026-07-02 定):met 表不按动作穷举(运动生理学上动作名不影响耗能,强度和时长才影响)。表里没有同名条目的力量动作,LLM 判断强度归入"力量训练(中等/大强度)"取 MET 值,动作名/负重/次数保留用户原话照存,source 记 `met_table`。训练进度数据的准确性与表无关
3. **LLM 输出必须用 Pydantic structured output 强约束**(discriminated union:`ExerciseRecord | FoodRecord | WeightRecord`),接口响应为 `list[ParseResult]`(一句话可能含多条记录;"今天75公斤"也是一句话记录)
4. **静态数据走内存 dict,不用数据库、不用 RAG、不用向量检索**
   - `data/food.json`:约 1657 条,源自《中国食物成分表(第6版)》,字段:name/kcal/protein/fat/cho/fiber(每100g)
   - `data/met.json`:常见运动 MET 值表,含中文别名和按次数换算时长的规则(note 字段)
   - 进程启动时加载,精确匹配 + 简单别名匹配;模糊的口语对齐是 LLM 的职责,不是检索的职责
5. **运动消耗用修正 MET 公式**(2026-07-02 用户扩定,取代旧"只用体重"):以体重+身高+性别+出生年份估算基础代谢(Mifflin-St Jeor)修正 MET,消耗更贴合个体;仍不引入体脂/手环等测量数据。身体档案一次性填,零日常负担
   - **消耗口径双存**(2026-07-02 用户定):主数字=总耗(MET 全额,与市面 app 口径一致);每条运动记录同时存净耗(减去同时段基础代谢,即按 MET−1 计),展示以总耗为主、净耗后续按需露出
   - **力量训练按组记录时,时长由后端从时间戳推断**(2026-07-02 与用户对齐):距上一组 ≤20 分钟 → 本组时长=实际间隔(间隔天然已含本组动作,不重复计);首组或 >20 分钟 → 时长=动作时间(次数×换算秒数),并视为新一场。聚合是程序的事,用户只管一组一句正常说,不要求报时长
6. **不做注册登录/auth**,多用户仅为简单的用户选择(users 表)
7. **不接入外部 agent 平台,不用 LangGraph/LangChain 等编排框架**;AI 逻辑收敛在 `app/ai/`,编排=顺序函数调用
   - **读写不对称**(2026-07-02 定):写路径=管线+每步微循环(schema 校验/查表命中为硬反馈,失败带错重试,重试尽降级 llm_estimated),笔在代码手里;读路径(后续读代理)=PydanticAI 只读工具 agent,模型有完全自由——只读结构上无害
8. **数据库迁移用 Tortoise 内置迁移系统**(`tortoise init / makemigrations / migrate`);不依赖 generate_schemas 自动建表
9. **LLM 选型**(2026-07-03 用户扩定为通用接入):PydanticAI + **任意 OpenAI 兼容端点**,不绑定单一供应商。`.env` 四项:`LLM_BASE_URL` / `LLM_MODEL` / `LLM_API_KEY`(**允许空**,兼容无鉴权本地部署)/ `LLM_EXTRA_BODY`(端点私有参数 JSON,可空)。当前默认 deepseek-v4-flash(需 `{"thinking":{"type":"disabled"}}` 关思考模式才能用结构化输出;旧 deepseek-chat 2026/07/24 弃用勿选)。换端点只改 `.env` 不改代码
   - 程序内语音输入(流式 STT,WebSocket,不做整段往返)排在前端阶段,后端当前不实现;流式语音厂商用户已选定(待告知接入)
   - **模型设置界面永久不做**(2026-07-07 用户定):不支持用户自定义/切换模型,模型全局唯一,换模型=管理员改 `.env`;key 永不暴露给前端
   - **不做思考过程展示**(2026-07-04 用户定):写路径思考模式必须关(与结构化输出冲突),回复为模板拼接;将来有真实需求再议

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
      schema.py        # Pydantic 输出 schema(Exercise/Food/Weight union)
      parser.py        # 洗数据:LLM 调用 + structured output
      lookup.py        # 内存 dict 加载与查表、消耗/热量计算
      aggregate.py     # 聚合:规则归组 + AI 裁决模糊边界/起名(raw→new)
    data/
      food.json
      met.json
  scripts/             # 一次性脚本(如 food.json 预处理)
  tests/
docs/
  product.md           # 产品定义:做什么/不做什么/典型输入输出
  todo.md              # 任务看板:已办/进行中/待办/等用户(唯一任务清单)
  context.md           # 活文档:当前状态、最近改动、待决策
notes/                 # 项目问答笔记,纯 QA 体,前后端各一份(backend-qa.md / frontend-qa.md)
web/                   # 响应式 Web 前端,移动端优先(后端跑通后建立)
ios/                   # SwiftUI 前端(Web 之后,独立于 backend)
```

### 后端 Import 约定

- `pyproject.toml` 位于 `backend/` 目录下,不在仓库根目录(polyglot monorepo:backend / ios / 远期 android 各自独立管理依赖)
- 所有后端内部 import 使用 `from app.xxx` 形式,例如 `from app.models import User`
- 运行后端命令时在 `backend/` 目录下执行

## 核心接口契约(v2,2026-07-02)

```
POST /chat                             # 唯一对话入口(SSE 流式):记录与查看都走它
  请求: { "user_id": 1, "text": "卧推60公斤10个" }
  intent=record(v1 仅此):洗数据→raw→聚合→new
    事件流: event:records(入库 raw 记录卡片,带 session_id/meal_id)
            event:reply(模板拼接的一句话回执,零 LLM 成本)
  intent=query(后续,读代理):event:answer 流式回答;周报=查询的一种
  intent=clarify(后续):event:clarify 澄清反问
  读代理/澄清走同一入口的新 intent,不另设端点、不建占位

PATCH  /records/exercise/{id} | /records/food/{id}   # 修正,只落 raw
  改输入量(克数/次数/时长)→ 后端重算 kcal
  直接改 kcal → 采用用户数,source 改 user_reported
DELETE 同路径                          # 删记录(如删自动补的油)
  修正/删除均触发所在聚合增量重算

GET /days/{date}?user_id=1             # 数据展示主接口,只读 new 层
  { "intake_kcal", "burn_kcal", "weight",
    "bmr_kcal",        # 全天基础代谢(2026-07-07 加):该日结束前最近体重+档案算,无体重为空
    "burn_net_kcal",   # 当天运动净耗合计(净摄入=摄入−基础代谢−净耗,总耗含运动时段
                       # 基础代谢会重复扣;净耗缺失的记录按总耗计)
    "meals":    [ { "name", "start", "kcal_total", "items": [...] } ],
    "sessions": [ { "name", "start", "end", "kcal_total", "items": [...] } ] }

GET /weights?user_id=1&days=30         # 体重曲线(默认30天,2026-07-06 用户定)
GET /users  /  POST /users             # 暂缓(2026-07-06 用户定):单人使用期不实现,
                                       # 前端固定用户;真有多用户再做。昵称已有全局唯一约束
```

用户体重/身体档案由后端按 user_id 读取后注入 prompt,前端不传。

## 数据主流程与数据库(2026-07-02 定稿)

主流程:**userinput → AI 洗数据(解析/映射/查表计算)→ raw 层 → AI 聚合(归组/起名)→ new 层 → 数据展示**。各环节以函数为边界,后续允许在环节间插入新步骤。

三条铁律:
1. **raw 是唯一事实源**:修正/删除只落 raw;new 层可随时整层从 raw 重算,坏了重建,永不手补
2. **算术归代码,判断归 AI**(2026-07-04 用户定;2026-07-07 用户再改,餐次收回给代码):求和/公式是代码。**餐次=时段制,纯代码零 AI**——用户明说哪顿归哪顿(AI 只负责从话里提取明说的槽:早餐/午餐/下午茶/晚餐/其余,没明说不填),否则按本地时钟落固定时段(早5-10/午10-15/下午茶15-17/晚17-22/其余22-5);组名=时段名,一天每槽至多一组,同槽自动合并。**AI 归组仅保留运动场次**——解析时附带"当天开放场次摘要+当前时间",AI 判断延续/新开并起名,没给名按时段兜底
3. **聚合在写入时增量触发**:每次入库顺带归组;展示接口零 AI 调用

七张表:
- `users`:昵称、身高、性别、出生年份(修正 MET 公式用;体重不放这里)
- `weight_records`:user / weight_kg / created_at。"当前体重"=最新一条,消耗计算取它,体重曲线由此出

raw 层(碎片粒度,怎么说的怎么存,"鸡蛋100g"一条、"卧推60kg×10"一条):
- `exercise_records`:user / raw_text / source / kcal(总耗) / kcal_net(净耗) / created_at + exercise_name / met / duration_min / load_kg(可空) / reps(可空) + session_id(可空)
- `food_records`:user / raw_text / source / kcal / created_at + food_name / grams / protein / fat / cho / fiber + meal_id(可空)

new 层(聚合粒度,AI+规则维护,可重算):
- `meals`:user / name(AI 起名) / start / end / kcal_total
- `sessions`:user / name / start / end / kcal_total

个性化:
- `user_foods`:user / name(用户内唯一) / unit(份/勺/碗,自由文本) / kcal 及营养(每单位,营养可空)。对话中"记住……"即可建;查表优先级高于标准表
- `ai_memories`:user / kind(alias|habit|correction) / content / updated_at。纠正发生时即时学;每日首次请求顺带触发巩固(不引入调度器)

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

双库策略:**单元测试跑内存 SQLite**(不依赖云库),开发/生产连云 PG。跨方言能力由 Tortoise ORM 提供,**不自建仓储层/repository 抽象**。

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

任务看板在 `docs/todo.md`,当前状态与待决策在 `docs/context.md`(均为活文档,本文件不记进度)。不分里程碑阶段,按顺序清单推进。

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
6. 文档分工:本文件只放稳定内容(规则/已定稿决策/契约);进度、最近改动、待决策写 `docs/context.md`,每次有意义的改动后更新它并保持精简(旧内容压缩进历史摘要);产品定义在 `docs/product.md`;问答笔记在 `notes/`(纯 QA 体,前后端各一份,面向"别人问项目细节"),每完成一个功能块顺手补条目。不参照本仓库之外的跨项目文档(如 Amoy 根目录的 CODING-STYLE.md,那是 CoCoWork 专属约定)
7. 保持简单直接,禁止过度设计;不引入本文档未列出的新依赖/新组件,除非先说明理由并征得同意
8. 回复使用中文
9. 用户指令始终优先于本文档
