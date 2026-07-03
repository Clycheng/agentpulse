# AgentPulse Roadmap

> 目标不是每天都热血沸腾，而是每天都把产品往前推一点点。

AgentPulse 的第一阶段目标很清楚：做出一个普通人真的能用的 AI 公司工作台。用户不需要理解 Agent、Workflow、Tool Schema、Runtime，只需要像老板一样招聘员工、交代任务、查看进度、拍板关键决策。

> ⚠️ **架构以 [AGENTS.md](AGENTS.md) 和 [docs/decisions/](docs/decisions/) 为准。** 本文件的产品愿景、MVP 边界、执行节奏方法论仍然有效；但「Agent 底层设计」一节中的 Runtime 选型已按 2026-07-03 的架构决策（Hermes 为唯一员工运行时基座，见 [ADR 0001](docs/decisions/0001-hermes-as-agent-runtime.md)）更正，不再是多 CLI 适配方案。

## 一句话目标

让普通人可以用 AgentPulse 自己搭建一支 AI 员工团队，完成一人公司的日常工作。

第一版先聚焦 **一人自媒体公司**：

- 老板秘书负责接收想法、拆任务、提醒拍板。
- 内容员工负责选题、脚本、文章、官网文案。
- 运营员工负责渠道、增长实验、数据复盘。
- 销售/客服员工负责线索、客户问题、话术沉淀。
- 财务/行政员工负责记录、报表、合同和提醒。

## MVP 不做什么

为了防止项目越做越散，前 30 天先明确不做这些：

- 不做复杂登录注册。
- 不做支付和套餐。
- 不做云端多租户。
- 不做插件市场。
- 不做复杂工作流画布。
- 不做全自动外部发布。
- 不做多模型管理后台。
- 不做企业权限系统。

先把一条主流程做穿：

```text
创建/招募 AI 员工
-> 分配部门和职责 Prompt
-> 在消息里 @ 员工或群聊交代事情
-> 生成任务
-> Agent 执行并回报
-> 需要风险动作时请求用户拍板
-> 结果沉淀到任务和资料库
```

## 当前状态

| 模块                  | 状态                 | 下一步                         |
| --------------------- | -------------------- | ------------------------------ |
| 官网 `apps/web`       | 已有脚手架           | 后面补产品介绍、愿景、等待列表 |
| 桌面端 `apps/desktop` | 已有可交互原型       | 继续完善主流程和稳定 UI        |
| 后端 `services/api`   | FastAPI + PostgreSQL API | 继续补任务、审批、运行步骤模型 |
| README                | 已写产品愿景         | 后续保持高层介绍               |
| ROADMAP               | 当前文件             | 每完成一周更新一次             |

## 30 天推进节奏

### 第 1 周：把桌面端主流程做成 Demo

这一周只追求一个目标：打开桌面端，用户能看懂 AgentPulse 是什么，并完成一条假的但完整的业务链路。

第 1 天：整理产品边界

- 确认 MVP 只做“一人自媒体公司”。
- 补齐 README 和 ROADMAP。
- 写清楚哪些功能暂时不做。

第 2 天：稳定桌面端框架

- 保留消息、员工、人才市场、任务、资料库五个主模块。
- 默认进入消息页。
- UI 收敛成稳定办公风格。

第 3 天：员工创建流程

- 创建员工表单完善：名称、描述、部门、职责 Prompt。
- 创建后进入员工列表。
- 员工详情能看到 Prompt、Skills、MCP 权限占位。

第 4 天：人才市场招聘流程

- 人才市场可以查看岗位能力。
- 点击招募后选择部门。
- 招募完成后进入组织架构。

第 5 天：消息和任务联动

- 消息中支持 `@员工`。
- 发送消息后可以生成任务。
- 任务中心展示负责人、来源会话、状态、进度。

第 6 天：群聊协作原型

- 创建群聊时选择多个员工。
- 群聊消息可以 @ 多个员工。
- 模拟秘书拆任务、员工回复、任务更新。

第 7 天：录制第一版 Demo

- 路径：招募员工 -> 建群 -> @员工 -> 生成任务 -> 查看任务 -> 员工交付。
- 写一段 Demo 脚本。
- 记录体验问题，放进 backlog。

### 第 2 周：后端数据模型和 API

这一周目标：前端不再只靠内存，后端开始接管核心数据。

第 8 天：建数据库基础

- 选择 PostgreSQL 作为产品主数据库。
- 使用 `AGENTPULSE_DATABASE_URL` 管理连接串。
- 本地通过 `docker compose up -d postgres` 启动数据库。
- 测试环境允许使用临时 SQLite 隔离数据。
- 后续引入 Alembic 管理正式 migration。

第 9 天：建核心表

- `workspaces`
- `departments`
- `agents`
- `agent_templates`
- `conversations`
- `messages`
- `tasks`
- `runs`
- `run_steps`
- `approvals`

第 10 天：员工 API

- `POST /api/agents` 创建自定义员工。
- `GET /api/agents` 获取员工列表。
- `GET /api/agents/{id}` 查看员工详情。
- `PATCH /api/agents/{id}` 更新 Prompt、部门、权限。

第 11 天：人才市场 API

- `GET /api/agent-templates` 获取岗位模板。
- `POST /api/agents/recruit` 从模板招募员工。
- 招募时生成 Agent 实例，而不是直接复用模板。

第 12 天：消息 API

- `GET /api/conversations`
- `POST /api/conversations`
- `GET /api/conversations/{id}/messages`
- `POST /api/conversations/{id}/messages`

第 13 天：任务 API

- `POST /api/tasks`
- `GET /api/tasks`
- `PATCH /api/tasks/{id}`
- 任务和消息、负责人、Run 关联起来。

第 14 天：前后端联调 Demo

- 桌面端读取后端员工、会话、任务。
- 创建员工、招募员工、创建任务可持久化。
- 录制第二版 Demo。

### 第 3 周：Agent Runtime 最小闭环

这一周目标：让一个 AI 员工可以被真实调用，而不是只模拟回复。

第 15 天：LLM Provider 抽象

> ⚠️ 已被 ADR 0001 取代：不自建 LLM Provider 抽象层，改为对接 Hermes 的 Runs API（见 [ARCHITECTURE.md](docs/ARCHITECTURE.md) §3.4）。

- 定义统一接口：`complete()` 或 `stream()`
- 先支持一个模型提供方。
- 配置 API Key 和模型名。

第 16 天：Agent Prompt 组装

> ⚠️ 已被 ADR 0001 取代：系统 Prompt 的组装（人格+记忆+技能+工具）由 Hermes 的 `SOUL.md`/Memory/Skills 承担，AgentPulse 不自建 Prompt 组装逻辑；仍需要的是把"相关任务/最近上下文"这类业务上下文传给 Hermes（作为 Run 的输入）。

- 系统 Prompt = 产品安全规则 + 公司上下文 + 员工职责 + 工具权限 + 输出格式。
- 用户 Prompt = 当前消息 + 相关任务 + 最近上下文。
- 输出先用自然语言，后面再加结构化格式。

第 17 天：单 Agent 调用

> ⚠️ 已被 ADR 0001 取代："调 LLM 得到回复"改为"调 Hermes Runs API 驱动对应 profile 执行"。

- `POST /api/runs` 创建一次 Agent 执行。
- Runner 加载 Agent、消息上下文、任务上下文。
- 调 LLM 得到回复。
- 回复写回 messages。

第 18 天：Run 过程可见

- 保存 `runs` 和 `run_steps`。
- 前端可以看到：排队中、思考中、执行中、已完成、失败。
- 每一步写日志，但不要暴露太多技术细节给普通用户。

第 19 天：工具调用 Broker 雏形

> ⚠️ 已被 ADR 0001 取代：不自建 Tool Broker，工具执行与风险分级由 Hermes 的 toolsets/skills 承担，AgentPulse 只需配置员工的工具权限并接住 Hermes 抛出的 `approval_required` 事件。

- 定义 Tool Registry。
- 第一批工具只做安全的本地工具：读资料库、写草稿、生成任务。
- 每个工具声明风险等级。

第 20 天：审批机制

- 高风险工具调用必须创建 `approval`。
- 用户点同意后再继续执行。
- 拒绝后 Agent 要给出替代方案。

第 21 天：真实 Agent Demo

- 用户发消息给秘书。
- 秘书真实回复并创建任务。
- 内容员工执行一个简单内容产出。
- 结果写回任务和消息。

### 第 4 周：多 Agent 协作

这一周目标：让 AgentPulse 从“一个 AI 员工”变成“一支 AI 团队”。

第 22 天：任务路由器

- 解析消息中的 @ 员工。
- 没有 @ 时，默认给秘书判断。
- 秘书可以建议负责人和参与员工。

第 23 天：任务拆解器

- 秘书把一个目标拆成多个子任务。
- 每个子任务分配给不同 Agent。
- 任务中心能展示父子任务。

第 24 天：群聊协作协议

- 群聊里 Agent 回复要带角色感。
- 员工不能互相无限对话。
- 每轮协作必须有停止条件。

第 25 天：协作结果汇总

- 负责人汇总多个员工产出。
- 秘书给老板生成决策摘要。
- 高风险建议必须进入待拍板。

第 26 天：资料库记忆

- 公司资料、品牌语气、历史产出进入资料库。
- Agent 调用前检索相关资料。
- 先做关键词检索，后面再做向量检索。

第 27 天：任务交付物

- 任务可以有交付物：文案、表格、报告、计划。
- 交付物可以被资料库保存。
- 消息里展示交付卡片。

第 28 天：第三版 Demo

- 老板提出一个内容增长目标。
- 秘书拆解。
- 内容、运营、销售多个员工协作。
- 老板拍板后得到一份可用方案。

### 第 5 周：打磨和公开展示

第 29 天：官网首页

- 讲清楚 AgentPulse 是什么。
- 放 Demo 截图。
- 加等待列表或联系方式。

第 30 天：公开版本整理

- README 更新到最新状态。
- ROADMAP 打勾已完成项。
- 清理明显 bug。
- 推送 GitHub。
- 准备一条朋友圈/推文/视频脚本。

## 每天的最小行动

每天只做一个小闭环，不追求大而全。

推荐节奏：

1. 打开 ROADMAP，选今天唯一任务。
2. 用 10 分钟写清楚“完成标准”。
3. 用 60-120 分钟实现。
4. 运行一次验证命令。
5. 截一张图或录 30 秒 Demo。
6. 写一句今天完成了什么。

每天完成标准必须是可见的：

- 页面上出现新入口。
- 表单能保存。
- 一条 API 能跑通。
- 一条任务能生成。
- 一次 Agent 调用能返回。
- 一个流程能演示。

## Agent 底层设计

AgentPulse 里的 Agent 不应该只是一个 Prompt。它应该是一个“AI 员工实例”，由身份、职责、上下文、工具权限、运行记录共同组成。

### 核心概念

| 概念            | 说明                                             |
| --------------- | ------------------------------------------------ |
| `AgentTemplate` | 人才市场里的岗位模板，例如内容主笔、运营负责人   |
| `Agent`         | 用户公司里的真实 AI 员工实例                     |
| `Department`    | 部门，用于组织管理和默认路由                     |
| `Conversation`  | 私聊或群聊                                       |
| `Message`       | 用户、系统、Agent 的消息                         |
| `Task`          | 可追踪工作项                                     |
| `Run`           | 一次 Agent 执行                                  |
| `RunStep`       | Run 中的一步，例如思考、调用工具、等待审批、完成 |
| `Tool`          | Agent 可调用能力                                 |
| `Approval`      | 用户拍板节点                                     |
| `Memory`        | 公司资料、历史结果、品牌语气                     |

### Agent 如何创建

有两种创建方式。

#### 方式一：从人才市场招募

用户看到的是“招聘员工”，底层做的是：

```text
选择 AgentTemplate
-> 选择部门
-> 复制模板字段生成 Agent
-> 写入 agents 表
-> 绑定默认 skills/tools
-> 生成一条入职系统消息
-> 出现在组织架构和私聊列表
```

需要保存的字段：

```text
id
workspace_id
department_id
name
role
description
system_prompt
responsibilities
skills
tool_permissions
status
created_from_template_id
created_at
updated_at
```

#### 方式二：用户自定义创建

用户看到的是“创建员工”，底层做的是：

```text
填写名称、描述、部门、工作职责 Prompt
-> 校验 Prompt 是否为空
-> 生成 Agent 实例
-> 默认不给危险工具权限
-> 写入 agents 表
-> 出现在组织架构
```

自定义创建时，不要让用户一开始配置复杂参数。第一版只给四个字段：

- 员工名称
- 描述
- 部门
- 工作职责 Prompt

Skills、MCP、工具权限可以后置到“高级配置”。

### Agent 如何调用

Agent 调用不是前端直接请求模型，而是后端创建一次 `Run`。

```text
用户发送消息
-> 后端保存 Message
-> Router 判断要不要触发 Agent
-> 创建 Task 或 Run
-> Runner 通过 Hermes Runs API 驱动对应员工的 Hermes profile 执行
   （人格组装/技能检索/工具调用都是 Hermes 内部完成，AgentPulse 不自建）
-> 写入 RunStep
-> 产出 Message / Task / Artifact
-> WebSocket 推送给前端
```

最小接口可以这样设计：

```text
POST /api/conversations/{id}/messages
POST /api/runs
GET  /api/runs/{id}
GET  /api/runs/{id}/steps
POST /api/approvals/{id}/approve
POST /api/approvals/{id}/reject
```

> 见 [ADR 0001](docs/decisions/0001-hermes-as-agent-runtime.md)：`Runner` 内部调用的是 Hermes 的 **Runs API**（`POST /v1/runs` → SSE `/events` → `/approval`）。

### 调用链路示例

用户在群聊里输入：

```text
@阿澜 帮我规划下本周小红书投放节奏
```

底层执行：

```text
1. MessageService 保存用户消息
2. MentionParser 识别 @阿澜
3. AgentRouter 选中 agent=阿澜
4. TaskService 可选生成任务
5. RunService 创建 run
6. RunService 调用阿澜对应的 **Hermes profile**（其 SOUL.md 人格、Skills 技能、Memory 记忆已内置）
7. 通过 Hermes Runs API 驱动执行，流式获取思考/工具调用/结果事件
8. 返回投放计划
9. MessageService 写入阿澜回复
10. EventBus 推送给桌面端
```

如果 Agent 想调用危险工具，例如“发送邮件”：

```text
1. Hermes 识别工具风险等级为 high，抛出 approval_required 事件（session/request_permission）
2. AgentPulse 后端据此创建 Approval
3. Run 状态变成 waiting_user
4. 前端显示待拍板卡片
5. 用户同意后，后端调 Hermes 的 approval 接口放行继续执行
6. 用户拒绝后，Agent 生成替代方案
```

### Runtime = Hermes（已定案，见 ADR 0001）

> 本节原先参照 Multica 的"Server + 本地 Daemon + 多 CLI Backend Adapter"模式，规划了 Codex/Claude/Kimi/Hermes 多 Runtime 适配、分阶段接入的路线。**2026-07-03 已改为单一 Hermes 基座**，不做多 CLI 适配层——理由和完整调研见 [ADR 0001](docs/decisions/0001-hermes-as-agent-runtime.md) 与 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) §3。Multica 的分层思路（Server 管状态/队列、执行细节下沉到运行时、统一事件流回传）仍有参考价值，但"多 CLI 适配"这部分不再适用于 AgentPulse。

结论：

```text
AgentPulse 自建的是 Orchestrator（协作编排层：群讨论、Task/Run/RunStep/Approval），
不自建 Agent 协议 / 工具系统 / 多 Runtime 适配层。
唯一的员工运行时是 Hermes：每个员工 = 一个 Hermes profile。
```

原因：

- 目标用户是普通人/一人公司（文案、运营、客服、销售…），不是写代码，工程师型 CLI（Codex/Claude Code）不是合适的默认基座。
- Hermes 原生已具备本项目需要的能力：人格(SOUL.md)、技能(Skills)、记忆与学习循环、多模态路由、7×24 daemon、多实例(profiles)、跨实例编排(kanban)——不用我们逐个造。
- 单基座让适配层从"养多个 CLI"简化为"对接一个 Hermes"，大幅降低复杂度。

### 建议的底层架构

产品层不直接绑定某个 CLI，拆成四层：

```text
Agent Product Layer
  Agent / Department / Prompt / Skills / Tool Permissions

Orchestration Layer（AgentPulse 自研）
  群讨论协议 / Task / Run / RunStep / Approval / Router

Runtime Layer
  HermesBackend（唯一运行时，通过 Hermes Runs API / ACP 驱动）

Execution Layer
  Hermes gateway 进程（服务器常驻 daemon）/ profile 隔离 / HERMES_HOME
```

核心抽象（对接 Hermes 而非自建多后端）：

```python
class HermesBackend:
    async def run(self, context: RunContext) -> AsyncIterator[AgentEvent]:
        # 内部：POST /v1/runs -> SSE GET /v1/runs/{id}/events -> 解析为 AgentEvent
        ...
```

`RunContext` 至少包含：

```text
run_id
workspace_id
agent_id          # 对应哪个 Hermes profile
conversation_id
task_id
prompt
timeout
resume_session_id
```

`AgentEvent` 至少包含（直接映射 Hermes Runs API / ACP 的事件语义）：

```text
message
thinking
tool_call
tool_result
approval_required   # 对应 Hermes 的 session/request_permission
status
error
final
usage
```

后端只认识这一套统一事件，因为底层永远是 Hermes——不再需要"不关心底层是哪个 CLI"这层抽象，因为已经没有多个 CLI 要抽象。

### Agent 如何创建到运行

创建 Agent 时，只创建“员工配置”，不启动进程：

```text
创建/招募员工
-> 写入 agents 表
-> 绑定 department、prompt、tools、runtime_profile
-> status = idle
```

真正运行发生在用户发消息或任务触发时：

```text
用户发消息
-> AgentRouter 选中 Agent
-> RunService 创建 Run
-> RuntimeResolver 根据 agent.runtime_profile 解析出对应的 Hermes profile
-> HermesBackend.run() 驱动该 profile 执行，产生事件流（内部已含人格组装/工具调用）
-> RunStepService 保存过程
-> MessageService 写回结果
```

`runtime_profile` 记录的是"这个员工对应哪个 Hermes profile、用什么模型"：

```json
{
  "id": "runtime_hermes_default",
  "type": "hermes_profile",
  "hermes_profile": "muobai",
  "model": "deepseek-v3",
  "config": {
    "hermes_base_url": "http://hermes-gateway:8642"
  }
}
```

### Hermes 部署在哪里（见 ADR 0003）

Hermes **不是"检测用户本机装了哪些 CLI"的本地 daemon**，而是**常驻在 AgentPulse 后端服务器上的 daemon**（Docker/systemd，headless）。后端 / 官网 / 后台 / 客户端可以分处不同机器，通过 API 互联；客户端只是窗口，关不关机不影响服务器上员工的工作。

后端负责：

- 为每个新员工创建一个 Hermes **profile**（独立 HERMES_HOME：人格/技能/记忆/模型隔离）。
- 通过 Hermes 的 **Runs API** 驱动对应 profile 执行、接收流式事件、解审批门。
- 用 **cron** 给员工编排"空闲即思考/学技能"（idea 中心，见 [ADR 0003](docs/decisions/0003-server-side-24x7-idea-center.md)），以及定时/常驻任务。
- 需要多员工协同时，用 **`hermes kanban`** 做跨 profile 编排。

不需要"检测本机 CLI、启动子进程、解析 stdout 协议"这类本地 daemon 逻辑——Hermes 自己就是一个可远程调用的服务。

### Runtime 集成优先级

建议按这个顺序做（取代原先的多 CLI 优先级列表）：

1. **Hermes 地基验证**：本机装 Hermes，建 2 个 profile，从后端用 HTTP Runs API 跑通"后端 → Hermes → 流式事件 → 审批 → 写回"。
2. **群讨论协议**（AgentPulse 自研，照 AutoGen 骨架，见 [ADR 0002](docs/decisions/0002-self-built-group-discussion.md)）：拉群、发言路由、对齐门、共识 brief。
3. **7×24 / idea 中心**：cron 编排空闲思考、kanban 编排多员工协同。
4. **多模态**：按需给员工配 `auxiliary.vision` / STT，见 [ADR 0004](docs/decisions/0004-multimodal-via-hermes.md)。

### 后端模块建议

第一版后端目录可以这样拆：

```text
services/api/app/
  api/routes/
    agents.py
    agent_templates.py
    conversations.py
    messages.py
    tasks.py
    runs.py
    approvals.py
  core/
    config.py
    database.py
  models/
    agent.py
    conversation.py
    message.py
    task.py
    run.py
    approval.py
  schemas/
    agent.py
    message.py
    task.py
    run.py
  services/
    agent_service.py
    message_service.py
    task_service.py
    run_service.py
  runtime/
    router.py          # 决定这条消息该由哪个员工(profile)处理
    runner.py          # 创建 Run，驱动对应 Hermes profile 执行
    hermes_client.py   # 对接 Hermes Runs API(POST /v1/runs、SSE /events、/approval)
    approvals.py
```

> 不再需要自建 `prompt_builder.py` / `llm_provider.py` / `tool_broker.py`——人格组装、模型调用、工具执行都由 Hermes 承担（见 [ADR 0001](docs/decisions/0001-hermes-as-agent-runtime.md)）。

### 第一版 Agent Runtime 不要做太复杂

不要一上来做分布式、多进程、复杂 DAG。MVP 先用一个同步或后台任务 Runner：

```text
Run queued
-> Run running
-> append step: load_context
-> append step: call_model
-> append step: save_result
-> Run completed
```

等这个跑通后，再加：

- WebSocket 流式事件
- 工具调用
- 审批暂停/恢复
- 多 Agent 子任务
- 队列和并发控制

## 数据模型草案

> 注：`Agent` 这里的 `system_prompt`/`skills`/`tool_permissions` 是产品层展示用的元数据；实际专业能力由对应 **Hermes profile** 的 `SOUL.md`/Skills/toolsets 承载（见 [ADR 0001](docs/decisions/0001-hermes-as-agent-runtime.md)），落地时需加一个 `hermes_profile_id` 之类的字段做关联。

### Agent

```json
{
  "id": "agent_123",
  "workspace_id": "workspace_123",
  "department_id": "dept_content",
  "name": "墨白",
  "role": "内容主笔",
  "description": "负责品牌叙事、公众号文章、官网文案",
  "system_prompt": "你是一名内容主笔...",
  "skills": ["copywriting", "seo"],
  "tool_permissions": ["knowledge.read", "draft.write"],
  "status": "idle"
}
```

### Run

```json
{
  "id": "run_123",
  "workspace_id": "workspace_123",
  "agent_id": "agent_123",
  "conversation_id": "conv_123",
  "task_id": "task_123",
  "status": "running",
  "input_message_id": "msg_123",
  "created_at": "2026-07-02T00:00:00Z"
}
```

### RunStep

```json
{
  "id": "step_123",
  "run_id": "run_123",
  "type": "tool_call",
  "status": "waiting_approval",
  "title": "准备发送邮件",
  "detail": "该操作会向客户邮箱发送内容，需要老板确认",
  "payload": {}
}
```

## 近期最重要的 5 个任务

1. 桌面端消息和任务联动。（已完成初版：审批卡片内联聊天 + 关联任务栏，见 CHANGELOG）
2. 后端 Agent/Message/Task 数据模型。
3. 从人才市场招募 Agent 的 API。
4. 自定义创建 Agent 的 API。
5. ~~单 Agent 真实调用模型并写回消息~~ → **Hermes 地基验证**：本机 Hermes + 后端 HTTP Runs API 跑通"驱动 → 流式事件 → 审批 → 写回"（见 [ADR 0001](docs/decisions/0001-hermes-as-agent-runtime.md)）。

## 每周复盘模板

每周只回答 5 个问题：

- 本周做出了哪个可演示流程？
- 哪个地方最容易让用户困惑？
- 哪个技术点卡住了？
- 下周只做哪 3 件事？
- 哪些想法先放弃？

## 判断项目是否在前进

如果每周都有一个更完整的 Demo，项目就在前进。

如果一周都在换技术栈、改目录、写抽象、想商业模式，但没有用户可见变化，项目就在原地打转。

AgentPulse 的第一阶段，不追求完美，追求闭环。
