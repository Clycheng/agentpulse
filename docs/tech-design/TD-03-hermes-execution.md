# TD-03：执行层换成真·Hermes（Run/RunStep + HermesBackend）

- 关联 ADR：[0001](../decisions/0001-hermes-as-agent-runtime.md)（Hermes 为唯一运行时）、[0005](../decisions/0005-hermes-poc-safety-findings.md)（workdir 绝对路径隔离、结构性门控）
- ⚠️ 执行会话要求：**本阶段会真起 Hermes 进程**，**必须在 cwd 锚定于 `/Users/liuxiajiang/Desktop/code/agentpulse` 的会话里做**，绝不在 UnitPulse worktree 会话里做（[ADR 0005](../decisions/0005-hermes-poc-safety-findings.md) 的事故就是这么来的）。

## 技术设计

### 目标
把员工"干活"从现在的**临时直连 DeepSeek 回一段话**，换成**真·Hermes profile 执行**——员工有独立人格/技能/记忆，能调工具、能在高风险动作前抛审批。这是"套壳聊天 → 真 AI 公司"的关键一跃。

### 范围
- **做**：Run/RunStep 数据模型与生命周期；`HermesBackend` 适配层（对接 Hermes HTTP Runs API + SSE）；每个员工 = 一个 Hermes profile；workdir 绝对路径隔离；把审批门接到 Hermes 的 `approval_required`；结果流式写回聊天/任务。
- **不做**：Hermes 部署到远程服务器的运维（本阶段先本机跑通）；多员工大规模并发调度；cron/idea 中心（[ADR 0003](../decisions/0003-server-side-24x7-idea-center.md)，后续）。

### 现状与要替换的东西
- 现有 `runs` 表：`id/workspace_id/conversation_id/agent_id/status/input_message_id/output_message_id/provider/model/usage_json/error/created_at/completed_at`——是"一次 LLM 调用日志"，**无 run_steps、无分步生命周期**。
- 现有执行入口：`workspace.py::complete_agent_reply` → `DeepSeekChatClient().complete()`。**TD-03 用 `HermesBackend` 替换这里的执行部分**，但 Run 记账/写回消息的骨架可复用。

### 数据模型
- **扩 `runs`**：加 `hermes_profile_id`（对应哪个员工的 profile）、`hermes_run_id`（Hermes 侧的 run id，用于关联/续跑）、`workdir`（本次 Run 的绝对路径隔离目录）、`task_id`（Run 必关联 Task，见 ADR 0006 §4）。状态机扩成 `queued → running → waiting_user(审批) → completed/failed`。
- **新增 `run_steps` 表**：`id/run_id/type(message|thinking|tool_call|tool_result|approval_required|status|final)/status/title/detail/payload_json/created_at`——直接映射 Hermes Runs API / ACP 的事件语义（见 [ARCHITECTURE.md](../ARCHITECTURE.md) §3.4）。这是"任务过程可见"的数据源。

### 模块设计
- 新增 `services/api/app/runtime/hermes_client.py`（对应 [ADR 0001](../decisions/0001-hermes-as-agent-runtime.md) 里说的 `HermesBackend`）：
  - `async def run(ctx: RunContext) -> AsyncIterator[AgentEvent]`：内部 `POST /v1/runs` → SSE `GET /v1/runs/{id}/events` → 解析成统一 `AgentEvent`（message/thinking/tool_call/tool_result/approval_required/status/final/usage）。
  - `RunContext` 至少含：`run_id / workspace_id / agent_id(→profile) / conversation_id / task_id / prompt / workdir(绝对路径) / timeout`。
  - **workdir 硬约束**：创建 Run 前必须先 `mkdir` 一个绝对路径隔离目录（如 `<server_data_root>/runs/<run_id>/`）并绑定，**绝不用 Hermes 默认相对 `.`**（[ADR 0005](../decisions/0005-hermes-poc-safety-findings.md) 发现一）。这是不可跳过的前置步骤，建议在 `HermesBackend` 里强制校验 `workdir` 为绝对路径否则抛错。
- 新增 `services/api/app/runtime/runner.py`：`RunService` 创建 Run→建 workdir→调 `HermesBackend.run()`→逐事件写 `run_steps`→遇 `approval_required` 建 Approval 并把 Run 置 `waiting_user`→老板批准后调 Hermes approval 接口续跑→`final` 时把结果写回 message/task。
- 员工→profile 映射：`agents` 表加 `hermes_profile` 字段（或复用现有字段约定），招募/创建员工时创建对应 Hermes profile（写 SOUL.md）。
- 审批闭环：Hermes 抛 `approval_required` → 后端建 Approval（复用现有审批表/前端审批卡片！第一次会话做的那个内联审批卡片正好用上）→ 老板在聊天里点批准 → 后端调 `POST /v1/runs/{id}/approval` 放行。

### 时序（一次任务执行）
```
Task(已过 brief 门控) → RunService 建 Run(queued) → 建绝对路径 workdir
→ HermesBackend.run(ctx): POST /v1/runs → SSE 事件流
   ├─ message/thinking/tool_call/tool_result → 写 run_steps + 流式推前端
   ├─ approval_required → 建 Approval，Run=waiting_user，前端弹审批卡片
   │     └─ 老板批准 → POST /v1/runs/{id}/approval → 继续
   └─ final → 写回 agent 消息 + 更新 Task 产出/进度，Run=completed
```

### 字段级细化（worker AI 直接照此实现）

**SSE 事件 → run_steps 映射表**（`runner.py` 的核心 switch，事件形状为实测所得）：
| Hermes SSE `event` | AgentEvent.type | run_steps 落法 | 其他动作 |
|---|---|---|---|
| `message.delta` | `message` | **缓冲不逐条落**；聚合到 turn 结束落 1 行(type=message, payload=全文) | 逐 delta 推前端 |
| `reasoning.available` | `thinking` | 1 行(payload=text) | 仅任务详情展示 |
| `tool.started` | `tool_call` | 1 行(title=tool 名, payload=preview) | 推前端 |
| `tool.completed` | `tool_result` | 1 行(payload=duration/error) | 推前端 |
| `approval_required`〔触发条件待核 V5〕 | `approval_required` | 1 行 | **建 `approvals` 行(带 run_id) + `runs.status=waiting_user` + 停止消费 SSE** |
| `run.completed` | `final` | 1 行(payload=output/usage) | 写回 agent 消息 + 更新 task + `runs.status=completed` |
| (连接错误/超时) | `error` | 1 行 | `runs.status=failed` + `runs.error` |

**RunService 签名**（`runtime/runner.py`〔新增〕）：
```python
async def start_run(conn, *, task_id: str, agent_id: str, prompt: str) -> str  # 返回 run_id
    # 建 runs(queued) → mkdir workdir(绝对,V7 定语义) → status=running → 消费 HermesBackend.run(ctx)
async def resume_after_approval(conn, *, approval_id: str, decision: Literal["approved","rejected"]) -> None
    # 经 approvals.run_id 找 runs.hermes_run_id → POST {hermes}/v1/runs/{id}/approval → 继续消费 SSE
```

**前端拿进度（v1 决策：轮询，不建 WS）**：新增 `GET /api/runs/{run_id}` 与 `GET /api/runs/{run_id}/steps?after=<step_id>`（增量拉取）；桌面端任务详情 2s 轮询。WebSocket/SSE 推送留到体验优化片，避免本片引入新基建。（此两接口回填 DATA-MODEL §5 后为准。）

### ✅ 开放问题已全部实测关闭（2026-07-08 [验证报告](../research/hermes-verification-2026-07-07.md)，事实已回填 [DATA-MODEL §5.3](DATA-MODEL-AND-API.md)）
1. **进程模型(V4)**：❌ 不支持单网关多 profile → **一员工一 gateway 一端口**(8642+)。本机阶段脚本拉起固定几个；`RunService` 需按 agent 解析出对应端口。
2. **审批(V5)**：Hermes 审批系统=**Tirith**，config `approvals.mode: manual` + `tirith.enabled: true`，四级权限可 per-tool 覆盖；`approval_required` → `POST /v1/runs/{id}/approval`。**T4 实现照此配置；生产严禁 `HERMES_YOLO_MODE`。**
3. **模型名**：`deepseek-v4-flash`/`deepseek-v4-pro`（不是 `deepseek-chat`）。
4. **workdir(V7,架构决策)**：Runs API **无 per-run cwd** → 采用"**profile 级绝对 work root(`terminal.working_dir`) + Runner 每 Run 建子目录 `<work_root>/runs/<run_id>` 并写进 prompt**"。硬边界=员工自己的 work root，软约定=子目录；不可信任务后续升级 `terminal.backend: docker`(container_persistent: false)。`runs.workdir` 存子目录绝对路径。T2/T3 照此实现。

## Tech-Tasks

### TD-03-T1：Run/RunStep 数据模型
- 改动点：扩 `runs` 表（+hermes_profile_id/hermes_run_id/workdir/task_id、状态机）；新增 `run_steps` 表；`agents` 表关联 profile。
- 验收：迁移可用；单测覆盖 Run 生命周期状态转换。
- 依赖：无（但设计要跟 T2 对齐）。
- 需 agentpulse 会话：否（纯 schema + 单测）。
- 估算：1 天。

### TD-03-T2：HermesBackend 适配层
- 改动点：`runtime/hermes_client.py`——`run(ctx)` 走 HTTP Runs API + SSE，产出统一 `AgentEvent`；**强制 workdir 绝对路径校验**。
- 验收：**端到端**——从后端驱动一个真 profile 跑通"POST /v1/runs → SSE 事件 → final"，事件正确解析；workdir 落在指定绝对目录、绝不落到进程 cwd。
- 依赖：TD-03-T1；本机装好的 Hermes（第一次会话已验证可行）。
- 需 agentpulse 会话：**是**（起 Hermes）。
- 估算：2–3 天。

### TD-03-T3：RunService 编排 + 替换执行层
- 改动点：`runtime/runner.py`——建 Run/workdir、逐事件写 run_steps、结果写回；把 `complete_agent_reply` 的执行部分从 DeepSeek 直连切到 `HermesBackend`。
- 验收：任务执行走 Hermes；run_steps 有完整过程；前端能看到分步进度。
- 依赖：TD-03-T2。
- 需 agentpulse 会话：是。
- 估算：2 天。

### TD-03-T4：审批闭环接 Hermes approval_required
- 改动点：Hermes `approval_required` → 建 Approval + Run=waiting_user + 前端审批卡片（复用首个会话做的内联审批卡片）；老板批准 → 调 Hermes approval 放行续跑；选一个高风险工具做端到端验证。
- 验收：端到端——一个高风险动作触发审批卡片，批准后继续、驳回后停止/给替代方案。
- 依赖：TD-03-T3。
- 需 agentpulse 会话：是。
- 估算：1.5 天。

### TD-03-T5：员工↔profile 生命周期
- 改动点：招募/创建员工时创建对应 Hermes profile（写 SOUL.md、配模型），删除员工时清理。
- 验收：新建员工后其 profile 存在且人格生效；多员工人格互相隔离（第一次会话已验证机制可行）。
- 依赖：TD-03-T2。
- 需 agentpulse 会话：是。
- 估算：1–1.5 天。

## Definition of Done
- 一个任务能被真·Hermes 员工执行，过程分步可见，高风险动作走审批闭环，结果回到聊天/任务。
- workdir 绝对路径隔离已强制（ADR 0005 发现一落地）。
- 全程在 agentpulse 锚定会话完成，收尾查 UnitPulse 未被污染。
- 更新 AGENTS.md §4（Hermes 集成 → 已接入）+ CHANGELOG + 本文件状态。
