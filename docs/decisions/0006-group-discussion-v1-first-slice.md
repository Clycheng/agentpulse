# 0006. 群讨论协议 v1 第一片：讨论态 + 共识 brief + Task 创建门（对齐用人工确认）

- 状态: 已接受并已实现（2026-07-07, commit `c2054bf`，14 tests 通过；仅单测，尚未端到端手测 UI）
- 日期: 2026-07-05（计划）/ 2026-07-06（设计细节确认）/ 2026-07-07（实现）
- 决策者: 项目所有者认可

## 背景

[ADR 0002](0002-self-built-group-discussion.md) 定了"自研群讨论协作层"的方向，[ADR 0005](0005-hermes-poc-safety-findings.md) 用实测证明"讨论对齐后才能开工"必须是编排层的结构性强制、不能靠 SOUL.md 自觉。但这两条都是原则，没落到"下一步具体写什么代码"。

2026-07-05 做了一次冷读测试（一个零上下文的 AI 只读本仓库判断能否继续），结论：产品愿景/架构方向/硬规矩都清楚，但**最近这一步的具体计划没写进仓库**，冷读者会因此照旧版"先实现 Runner/HermesBackend"去做，与本条计划岔开。本 ADR 就是把已认可的"第一片"计划落进仓库，消除这个歧义。

## 决策

**下一步先做群讨论协议的第一片，且这一片刻意不碰 Hermes**（在现有临时的 DeepSeek 直连执行层上就能把编排骨架跑通，以后换真 Hermes 时编排层设计不用重来）：

1. **会话/群聊引入"讨论态 → 已对齐"的状态机**。一件事进来先处于"讨论中"，不自动建任务。
2. **引入"共识 brief"数据对象**（目标 / 范围 / 约束 / 负责人等），作为讨论阶段的结构化产出。
3. **Task 创建 API 强制要求携带 consensus_brief，缺失即拒绝创建**——这是 ADR 0005 要的"结构性强制门"。**现有 `services/api/app/services/workspace.py` 里 `TASK_INTENT_PATTERNS` 正则 + `extract_task_intent`"发一句话就自动建任务"的逻辑要被移除/替换**——它正是"稀里糊涂开干"的反例。
4. **对齐判定 v1 = 人工确认，不做 LLM 自动判"讨论完了没"**：由秘书/负责员工整理出纪要，老板点"确认纪要 → 生成任务"才真正建 Task。更可靠，也避免过度设计。

**本片明确不做**（留给后续 slice）：多 agent 发言路由 / 轮流接力 / SelectorGroupChat 那套（[ADR 0002](0002-self-built-group-discussion.md) / ARCHITECTURE §4 的完整 AutoGen 骨架）；也不做真正接 Hermes 驱动执行。

## 理由

- 顺序符合 ROADMAP 的 Runtime 集成优先级（群讨论协议排在深度接 Hermes 之前）。
- 直接落地 ADR 0005 的教训（结构性门控），且这是纯后端逻辑/数据模型，不需要真跑 Hermes 就能建骨架。
- 不需要把工作挪到"cwd 锚定在 agentpulse 的会话"——本片全在 `services/api` 内改代码/schema，不起 Hermes 进程，不触发 [ADR 0005](0005-hermes-poc-safety-findings.md) 的隔离风险；等到真正接 Hermes 驱动那一步再遵循隔离规矩另开会话。

## 已确认设计细节（2026-07-06）

以下设计细节已与项目所有者确认，可直接实现：

### 1. consensus_brief schema

**群/brief/Task 关系模型**：
- 群是持续存在的协作空间，一个群可以讨论很多任务（相关或不相关）
- 每次讨论产出一个 brief（共识纪要）
- 一个 brief 可以产出多个 Task（拆解）
- Task 创建必须关联一个 `confirmed` 状态的 brief
- 子 Task 可以继承父 Task 的 brief（不需要新 brief）

**表结构**（`consensus_briefs` 表）：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | string | 是 | `brief_xxx` |
| `workspace_id` | string | 是 | 所属 workspace |
| `discussion_conversation_id` | string | 是 | 从哪个讨论产生 |
| `status` | enum | 是 | `draft` / `confirmed` / `rejected` / `superseded` |
| `goal` | string(≤500) | 是 | **目标**：要达成什么（唯一必填语义字段） |
| `scope` | string(≤500) | 否 | **范围**：包含什么，不包含什么 |
| `constraints` | string(≤500) | 否 | **约束**：时间/资源/技术限制 |
| `success_criteria` | string(≤500) | 否 | **成功标准**：怎样算完成 |
| `owner_agent_id` | string | 否 | **负责人**：谁牵头执行 |
| `participant_agent_ids` | json array | 否 | **参与者**：哪些员工参与 |
| `created_by_agent_id` | string | 是 | 谁整理出这个 brief |
| `supersedes_brief_id` | string | 否 | 取代/更新哪个旧 brief |
| `derived_from_brief_id` | string | 否 | 基于哪个 brief 派生 |
| `created_at` | timestamp | 是 | |
| `confirmed_at` | timestamp | 否 | 老板确认的时间 |
| `confirmed_by_user_id` | string | 否 | 谁确认的 |

**Task 表新增字段**：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `consensus_brief_id` | string | 是* | Task 创建的门控条件（子 Task 可为空，继承父） |

\* 有 `parent_task_id` 时可为空（继承父 Task 的 brief）

### 2. 编排层代码位置

新建 `services/api/app/orchestration/` 模块，独立于 `services/`：

```
services/api/app/
├── orchestration/      # ← 新增：群讨论编排层
│   ├── __init__.py
│   ├── discussion.py   # 讨论态状态机（Conversation.discussion_status）
│   ├── brief.py        # consensus_brief CRUD
│   └── gate.py         # Task 创建门控检查
├── ...
```

**职责划分**：
- `discussion.py`：讨论态状态机（`discussing` → `aligned`）、发言路由逻辑占位
- `brief.py`：consensus_brief 的 CRUD、状态转换（`draft` → `confirmed`）
- `gate.py`：Task 创建前的门控检查（必须有 confirmed brief，否则拒绝）

### 3. "已对齐"信号 v1 的确切形式

**UI 交互流程**：
- 员工判断讨论差不多够了 → 主动发送 brief 草稿到群里（系统消息）
- 群聊界面显示「共识纪要卡片」：
  - 标题：📋 共识纪要（待确认）
  - 内容：goal / scope / constraints / 负责人
  - 按钮：「确认并创建任务」「不对，继续讨论」
- 老板点「确认并创建任务」→ brief → `confirmed` → Task 创建 API → Task 生成
- 群聊收到系统消息：「已创建任务：xxx」

**API 设计**：

| API | 动作 | 角色 |
|---|---|---|
| `POST /api/briefs` | 员工创建 brief 草稿 | agent |
| `POST /api/briefs/{id}/confirm` | 老板确认 brief | user |
| `POST /api/briefs/{id}/reject` | 老板拒绝 brief | user |
| `POST /api/tasks` | 创建 Task（必须有 confirmed brief） | user/agent |

**员工触发时机**：v1 为员工自发判断（prompt 中加规则，但 API 门控是硬保障）

### 4. Task 与 Run 的关系

**确认原则**：
- Run 必须关联 Task，不能脱离 Task 存在
- Task 创建时自动创建 Run（调用 Hermes profile 执行）

**但本片不涉及 Hermes**：
- Run 的定义（表结构、状态同步）留到接 Hermes 驱动时再定
- 本片只做 brief + Task 门控 + 讨论态状态机
- 现有临时执行层（直连 DeepSeek）保持不变

### 5. Hermes 多 profile 进程管理

本片不涉及，留到接 Hermes 驱动那一步再定。此处仅记录它是已知的开放项。

## 实现清单

基于上述设计细节，本片实现内容：

1. **数据库**：
   - 新增 `consensus_briefs` 表
   - `tasks` 表新增 `consensus_brief_id` 字段
   - `conversations` 表新增 `discussion_status` 字段（`discussing` / `aligned`）

2. **编排模块**：
   - `app/orchestration/discussion.py`：讨论态状态机
   - `app/orchestration/brief.py`：consensus_brief CRUD
   - `app/orchestration/gate.py`：Task 创建门控

3. **API**：
   - `POST /api/briefs`：创建 brief 草稿
   - `POST /api/briefs/{id}/confirm`：确认 brief
   - `POST /api/briefs/{id}/reject`：拒绝 brief
   - `POST /api/tasks`：增加门控检查（必须有 confirmed brief）

4. **移除旧逻辑**：
   - 删除 `services/api/app/services/workspace.py` 中 `TASK_INTENT_PATTERNS` 和 `extract_task_intent`

5. **前端适配**（最小）：
   - 群聊界面显示「共识纪要卡片」（系统消息类型）
   - 卡片上显示「确认并创建任务」「不对，继续讨论」按钮

**不做**：多 agent 发言路由、接 Hermes 驱动执行、Run 表定义。

## 后果

- 现有"正则自动建任务"逻辑将被移除/门控，`extract_task_intent` 相关测试与前端行为需同步调整。
- 完成本片后更新 AGENTS.md §4 的"当前状态"与"下一步"，避免下一个 AI 读到过期状态。
- 这一片跑通后，才在其上叠加"多 agent 发言路由"和"接 Hermes 真执行"两片。
