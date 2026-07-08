# 数据模型 + API 契约（唯一真相源）

> 本文件是 AgentPulse 后端**表结构 / 字段 / 接口 / 错误码**的唯一权威规格。任何人/AI 照此可直接编码，无需再猜。
> 分两类：`【已实现】`= 当前代码就是这样（读自 `services/api` 实际实现，2026-07-07）；`【目标】`= TD-02/TD-03 要新增，字段已钉死可直接建。
> 改动本文件所列任何 schema/接口，必须同步改代码 + 更新本文件；表结构改动**必须两处都改**（见 §0 双 schema 硬约束）。

## 0. 全局约定（必读，否则直接踩坑）

- **⚠️ 双 schema 硬约束**：`services/api/app/core/database.py` 里 **`init_postgres()`（生产）和 `init_sqlite()`（测试）各写了一份完整建表 SQL**。**任何加表/加列都必须在这两个函数里都改**，否则测试(SQLite)和生产(Postgres)结构分叉、测试过了线上崩。加列优先用文件末尾的 `ensure_column(conn, table, col, decl)` 幂等助手（它对两种方言都生效）。
- **ID 格式**：主键都是 `TEXT`，格式 `<entity>_<hex>`（如 `task_ab12…`、`brief_77…`），由 `new_id("<entity>")` 生成。
- **时间**：所有 `*_at` 是 `TEXT`，ISO8601 UTC 字符串，由 `now_iso()` 生成。
- **多值字段序列化边界**：DB 里存 JSON 字符串的列以 `_json` 结尾（如 `participant_agent_ids_json`）；对应的 **API DTO 字段去掉 `_json` 后缀、类型是数组/对象**（如 `participant_agent_ids: list[str]`）。编排层负责 `json.dumps/loads` 互转。**看到 `_json` = DB 列；看到无后缀 = API 字段。**
- **鉴权**：所有业务接口经 `Depends(get_workspace_id)` / `get_current_user_id` / `get_current_user`（`services/api/app/api/deps.py`）拿到 workspace 和 user，**请求体里不传 workspace_id/user_id**。
- **错误约定**：service 层校验失败抛 `ValueError`；route 层 catch 成 `HTTPException(400, detail=str(e))`。资源不存在/不属于本 workspace → `404`。

---

## 1. 表结构

### 1.1 `consensus_briefs` 【已实现】
共识纪要。讨论的结构化产出；Task 创建的门控依据。一个讨论可产出多个 brief，一个 brief 可拆多个 Task。

| 列 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | TEXT | PK | `brief_xxx` |
| `workspace_id` | TEXT | NOT NULL, FK→workspaces ON DELETE CASCADE | |
| `discussion_conversation_id` | TEXT | NOT NULL, FK→conversations ON DELETE CASCADE | 从哪个讨论产生 |
| `status` | TEXT | NOT NULL DEFAULT `'draft'`, CHECK IN (`draft`,`confirmed`,`rejected`,`superseded`) | |
| `goal` | TEXT | NOT NULL | 目标（唯一必填语义字段） |
| `scope` | TEXT | NOT NULL DEFAULT `''` | 范围 |
| `constraints` | TEXT | NOT NULL DEFAULT `''` | 约束 |
| `success_criteria` | TEXT | NOT NULL DEFAULT `''` | 成功标准 |
| `owner_agent_id` | TEXT | FK→agents ON DELETE SET NULL, 可空 | 负责人 |
| `participant_agent_ids_json` | TEXT | NOT NULL DEFAULT `'[]'` | 参与者 agent id 数组的 JSON。**API 侧字段名 `participant_agent_ids`** |
| `created_by_agent_id` | TEXT | NOT NULL, FK→agents ON DELETE CASCADE | 谁整理出的 |
| `supersedes_brief_id` | TEXT | FK→consensus_briefs ON DELETE SET NULL, 可空 | 取代哪个旧 brief |
| `derived_from_brief_id` | TEXT | FK→consensus_briefs ON DELETE SET NULL, 可空 | 派生自哪个 brief |
| `created_at` | TEXT | NOT NULL | |
| `confirmed_at` | TEXT | 可空 | 确认时间 |
| `confirmed_by_user_id` | TEXT | FK→users ON DELETE SET NULL, 可空 | 谁确认的（reject 也写此列，见 §3 待办 G5） |

语义字段（goal/scope/constraints/success_criteria）API 层限长 **≤500 字符**；`participant_agent_ids` API 层限 **≤12 个**。

### 1.2 `tasks` 【已实现，`consensus_brief_id` 为本项目新增】
| 列 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | TEXT | PK | `task_xxx` |
| `workspace_id` | TEXT | NOT NULL, FK→workspaces CASCADE | |
| `title` | TEXT | NOT NULL | API 限长 ≤160 |
| `description` | TEXT | NOT NULL DEFAULT `''` | API 限长 ≤2000 |
| `priority` | TEXT | NOT NULL DEFAULT `'P2'` | P0/P1/P2 |
| `owner_agent_id` | TEXT | FK→agents SET NULL, 可空 | |
| `status` | TEXT | NOT NULL DEFAULT `'进行中'` | 待认领/进行中/待确认/阻塞/已完成 |
| `progress` | INTEGER | NOT NULL DEFAULT 0 | 0–100 |
| `conversation_id` | TEXT | FK→conversations SET NULL, 可空 | 来源会话 |
| `due_date` | TEXT | 可空 | |
| `parent_task_id` | TEXT | FK→tasks SET NULL, 可空 | 子任务 |
| `consensus_brief_id` | TEXT | FK→consensus_briefs SET NULL, 可空* | **门控依据**。经 `ensure_column` 加列。*建任务时：无 parent 则必填且须 confirmed（见 §2.5 门控） |
| `created_at` / `updated_at` | TEXT | NOT NULL | |

### 1.3 `conversations`（相关列）【`discussion_status` 为新增】
| 列 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `discussion_status` | TEXT | NOT NULL DEFAULT `'discussing'`, CHECK IN (`discussing`,`aligned`) | 讨论态。经 `ensure_column` 加列。⚠️ 现在**没接线**（brief confirm 不会改它），见 §3 G3 |

（`conversations` 其余列 id/workspace_id/kind/name 等见 database.py，本项目未改。）

### 1.4 `messages`（相关列）【已实现】
`id / conversation_id / sender_type(user|agent|system) / sender_id / content / provider / model / created_at`。
- 共识纪要卡片是一条 `sender_type='system'` 且 `content` 以 **`BRIEF_CARD:` 前缀** + brief JSON 的消息（前端据此渲染卡片）。这是当前"卡片"的传递方式。

### 1.5 `runs` 【已实现=旧结构；TD-03 要扩】
当前列：`id / workspace_id / conversation_id / agent_id / status / input_message_id / output_message_id / provider(默认'deepseek') / model / usage_json / error / created_at / completed_at`。
- 现状：只是"一次 LLM 调用日志"，无分步。TD-03 的扩列/新表见 §5。

---

## 2. 现有 API 契约 【已实现】

### 2.1 `POST /api/briefs` → 201/200 `BriefOut`
建 draft 纪要（agent 调）。请求体 `CreateBriefRequest`：
```
discussion_conversation_id: str            (必填)
goal: str                                  (必填, 1–500)
scope: str = ""                            (≤500)
constraints: str = ""                      (≤500)
success_criteria: str = ""                 (≤500)
owner_agent_id: str | null = null
participant_agent_ids: list[str] = []      (≤12)
created_by_agent_id: str                   (必填)
supersedes_brief_id: str | null = null
derived_from_brief_id: str | null = null
```
错误：校验失败/会话不存在 → `400`。

### 2.2 `POST /api/briefs/{brief_id}/confirm` → `BriefOut`
老板确认。空请求体（user 来自 token）。`status: draft→confirmed`，写 `confirmed_at`/`confirmed_by_user_id`。错误 `400`（如 brief 不存在/非 draft）。
> ⚠️ 应同时把 `discussion_conversation_id` 对应会话置 `aligned`——**当前未做**，见 §3 G3。

### 2.3 `POST /api/briefs/{brief_id}/reject` → `BriefOut`
老板拒绝。空请求体。`status: draft→rejected`。错误 `400`。

### 2.4 `GET /api/briefs/{brief_id}` → `BriefOut`
不存在或不属于本 workspace → `404`。

**`BriefOut`（响应 DTO）**：§1.1 全部字段，但 `participant_agent_ids_json` → 出参为 `participant_agent_ids: list[str]`。

### 2.5 `POST /api/tasks` → `TaskOut`（含**门控**）
请求体 `CreateTaskRequest`：`title(1–160,必填) / description(≤2000) / priority / owner_agent_id? / status / progress(0–100) / conversation_id? / due_date? / parent_task_id? / consensus_brief_id?`。
**门控逻辑**（`orchestration/gate.py::validate_task_creation_gate`，在 `create_task()` 第一步执行）：
- `consensus_brief_id` 有值 → 该 brief 须存在于本 workspace 且 `status=='confirmed'`，否则 `ValueError`→`400`。
- `consensus_brief_id` 空 但 `parent_task_id` 有值 → 放行（子任务继承父的 brief）。
- 两者都空 → 拒绝 `400`（"Task creation requires a confirmed consensus_brief_id, or parent_task_id"）。

> ⚠️ **`TaskOut` 当前不含 `consensus_brief_id`**（DB 有、建任务能传，但返回读不回）→ 见 §3 G2。

---

## 3. 已知不对齐 / 缺口（拿到 design 前必须知道，附解决方案）

| # | 问题 | 影响 | 解决（归属 task） |
|---|---|---|---|
| G1 | ADR 0006 把 DB 列写成 `participant_agent_ids`，实际是 `participant_agent_ids_json` | 照 ADR 建表会错 | 以本文件为准；ADR 0006 加勘误指向本文件（本次已加） |
| G2 | `TaskOut` 缺 `consensus_brief_id` 字段 | 前端/消费方读不回任务的 brief 溯源 | 给 `TaskOut` 加 `consensus_brief_id: str \| null` 并在查询里带出 → **TD-01-T1 附带修** |
| G3 | brief confirm/reject 未调 `set_discussion_status`，`conversations.discussion_status` 永远停在 `discussing` | 状态机是死的 | 接线：confirm→会话 `aligned`；新建/reject→保持/回 `discussing` → **TD-01-T1** |
| G4 | `database.py` 双 schema（init_postgres / init_sqlite）需手工同步 | 漏改一处→生产/测试分叉 | 加列一律走 `ensure_column`；新建表两函数都加；本文件 §0 已列为硬约束 |
| G5 | reject 也写 `confirmed_by_user_id`（列名语义偏差） | 轻微；"谁拒绝的"存在"谁确认的"列 | 可接受；如需清晰后续可加 `resolved_by_user_id`，暂不改 |

---

## 4. 【目标】TD-02 新增契约（多 agent 讨论）

不新增表；扩 `orchestration/discussion.py` 的函数契约（纯 `services/api`，不碰 Hermes）：

```python
# 选下一个发言人：@优先；否则主持人(默认小秘)LLM 选；返回 None = 该停了
def select_next_speaker(conn, conversation_id: str, member_agent_ids: list[str],
                        last_message: Row | None) -> str | None: ...

# 非流式：跑一轮讨论，返回本轮结果摘要（用于单测/非流式 send_message 兼容层）
def run_discussion_round(conn, *, workspace_id: str, conversation_id: str,
                         max_agent_turns: int = 4) -> dict:
    # 返回: {"turns": int, "converged": bool, "brief_id": str | None, "speaker_ids": list[str]}

# 流式变体：给 send_message_stream 用，yield 每条 agent 发言 token（TD-02-T5 新增）
async def run_discussion_round_stream(conn, *, workspace_id: str, conversation_id: str,
                                      max_agent_turns: int = 4) -> AsyncIterator[dict]:
    # yield {"type": "token"|"turn_start"|"turn_end"|"converged"|"brief_created",
    #        "agent_id": str|None, "content": str, "brief_id": str|None}
    # 路由层消费此 generator，把 token 类事件转成 SSE text/event-stream 推前端
    # turn_start/turn_end 用于前端渲染"小秘正在发言..."等状态
```
- 约束：讨论态(`discussing`)下只允许产出 message/提问/brief 草稿，不允许执行类动作（为 TD-03 铺路）。
- 收敛：主持人判断"背景够拆任务" → 调 `POST /api/briefs` 出草稿；到 `max_agent_turns` 上限也强制产一版。
- **TD-02-T5 的接线点**：`send_message_stream` 改为 `async for event in run_discussion_round_stream(...)` 然后按 event.type 推 SSE；非流式 `send_message` 改为调非流式版本（降级为 API 兼容层）。
- 开放项（实现前定，见 [TD-02](TD-02-multi-agent-discussion.md) §开放问题）：主持人是否可配、发言人选择用 LLM 还是轮询。**这几项定了要回填本文件。**

---

## 5. 【目标】TD-03 新增契约（接 Hermes 执行）

### 5.1 `runs` 扩列（两 schema 都加）
新增：
- `task_id TEXT NOT NULL FK→tasks CASCADE`（Run 必属 Task）
- `hermes_profile_id TEXT`（对应员工 profile 名，对应 `agent_specs.hermes_profile`）
- `hermes_run_id TEXT`（Hermes 侧 run id，用于调 approval/stop 接口）
- `workdir TEXT NOT NULL`（**绝对路径**隔离目录，格式 `<data_root>/agents/<profile>/work/runs/<run_id>`，见 §5.3 workdir 架构决策）

`status` 状态机扩为：`queued → running → waiting_user | waiting_clarify → completed | failed`
- `waiting_user`：高风险操作触发 Tirith 审批，等老板拍板
- `waiting_clarify`：agent 主动求援（需求不清），等人回答后继续（见 §5.5）

**`approvals` 扩列（两 schema 都加）**：
- `run_id TEXT REFERENCES runs(id) ON DELETE SET NULL`（可空——旧的任务状态审批无 run）。**没有它，老板批准后找不到该恢复哪个 Run**（恢复 = 用 `runs.hermes_run_id` 调 Hermes `POST /v1/runs/{hermes_run_id}/approval`）。
- `type TEXT NOT NULL DEFAULT 'high_risk' CHECK IN ('high_risk','clarification','capability_upgrade')`：三种审批类型。

  | type | 含义 | payload_json schema | decision 合法值 |
  |---|---|---|---|
  | `high_risk` | Tirith 高危操作审批 | `{}` 或 tool 信息 | `approved` / `rejected` |
  | `clarification` | agent 执行中求援 | `{"question":str,"missing_context":str,"answer":str(批准后填)}` | `answered` |
  | `capability_upgrade` | agent 申请新能力 | `{"capability_description":str,"suggested_capability_key":str\|null,"approved_capability_key":str\|null,"failed_task_id":str\|null,"run_id":str\|null}` | `approved` / `rejected` |

**`agents` 扩列（两 schema 都加）**：
- `hermes_gateway_port INTEGER`（可空——员工未完成供给时为空）。端口分配规则：基础端口 `8642` + `agent_specs` 里按 workspace 顺序的序号（如第 1 个员工 8642，第 2 个 8643）；`RunService` 按此字段找 gateway 地址 `http://127.0.0.1:{port}`。供给时（TD-04-T6）由 `LocalHermesProvisioner` 写入。

### 5.2 `run_steps` 新表
| 列 | 类型 | 约束 |
|---|---|---|
| `id` | TEXT | PK `step_xxx` |
| `run_id` | TEXT | NOT NULL FK→runs CASCADE |
| `type` | TEXT | NOT NULL, IN (`message`,`thinking`,`tool_call`,`tool_result`,`approval_required`,`status`,`final`) |
| `status` | TEXT | NOT NULL |
| `title` | TEXT | NOT NULL DEFAULT `''` |
| `detail` | TEXT | NOT NULL DEFAULT `''` |
| `payload_json` | TEXT | NOT NULL DEFAULT `'{}'` |
| `created_at` | TEXT | NOT NULL |

### 5.3 `HermesBackend` 接口（`services/api/app/runtime/hermes_client.py`）
```python
@dataclass
class RunContext:
    run_id: str; workspace_id: str; agent_id: str        # agent_id → 决定用哪个 Hermes profile
    conversation_id: str; task_id: str
    prompt: str; workdir: str                            # workdir 必须绝对路径，否则构造即抛错
    timeout: int = 600

@dataclass
class AgentEvent:                                        # 直接映射 Hermes SSE 事件
    type: str          # message|thinking|tool_call|tool_result|approval_required|status|final|usage
    payload: dict

class HermesBackend:
    async def run(self, ctx: RunContext) -> AsyncIterator[AgentEvent]: ...
```
内部走 Hermes HTTP（实测契约，[ADR 0005](../decisions/0005-hermes-poc-safety-findings.md) / [ARCHITECTURE §3.4](../ARCHITECTURE.md)）：
- 起网关：`hermes -p <profile> gateway run`，env `API_SERVER_ENABLED=true API_SERVER_PORT=8642 API_SERVER_KEY=<key>`。
- `POST http://127.0.0.1:8642/v1/runs`，头 `Authorization: Bearer <key>`，body `{"input": "<prompt>"}` → `{"run_id","status":"started"}`。
- `GET /v1/runs/{id}/events`（SSE，`Bearer`）→ `data: {"event":"message.delta","delta":...}` … `{"event":"run.completed","output":...,"usage":...}`。
- 审批：事件 `approval_required` → `POST /v1/runs/{id}/approval`（放行）；`/v1/runs/{id}/stop`（中止）。
- **模型名**：DeepSeek 侧实测可用 `deepseek-v4-flash` / `deepseek-v4-pro`（**不是** `deepseek-chat`），profile config.yaml `model: deepseek/deepseek-v4-flash`。

**✅ 2026-07-08 验证回填**（原〔待核〕已清，全文出处：[验证报告](../research/hermes-verification-2026-07-07.md)）：
- **`POST /v1/runs` 请求体实测形状**：`{"input", "session_id"?, "instructions"?, "conversation_history"?, "previous_response_id"?}`——**没有 cwd/workdir 参数**。
- **workdir 语义(架构决策)**：`terminal.working_dir` 是 **profile 级**绝对路径配置。采用"**profile 级绝对 work root + 每 Run 子目录约定**"：每员工 profile 配 `terminal.working_dir = <data_root>/agents/<profile>/work`(绝对，绝不继承进程 cwd——满足 ADR 0005)；Runner 每次 Run 前 `mkdir <work_root>/runs/<run_id>` 并在 prompt 中指定该子目录为本次工作区。硬边界=员工自己的 work root(即使 agent 不守约定,污染也出不了它自己的 root)；软约定=子目录。不可信任务后续用 `terminal.backend: docker` + `container_persistent: false` 加强。`runs.workdir` 列存该子目录绝对路径。
- **审批系统=Tirith**：config.yaml `approvals: {mode: manual|smart|off, timeout: <秒>, cron_mode: deny|approve}` + `tirith: {enabled: true}`；四级权限(read-only / low-risk writes / high-risk writes / destructive)，可 per-tool 覆盖；`HERMES_YOLO_MODE=1` 会跳过审批——**生产严禁**。
- **拓扑**：❌ 不支持单网关多 profile → **一员工一 gateway 进程一端口**(8642, 8643, …)。端口存在 `agents.hermes_gateway_port`（见 §5.1 agents 扩列），`RunService` 用 `http://127.0.0.1:{agent.hermes_gateway_port}` 访问该员工 gateway。端口冲突检测：provisioner 写入前 `SELECT MAX(hermes_gateway_port) FROM agents WHERE workspace_id=?`，取最大值 +1（初始值 8642）。
- **MCP 配置**：`hermes mcp add <name> --url <endpoint>` 或 `--command <cmd> --args ... --env KEY=VALUE`(stdio)，`--auth oauth|header`；落 profile 级 config.yaml。
- **技能安装**：`hermes skills install <github-path|url>`、`hermes skills tap add <repo>`；落 `profiles/<name>/skills/`。
- **profile 打包**：`hermes profile export <name> -o x.tar.gz`(含 config/.env/SOUL/skills/memory,不含 sessions) / `import --name <new>` / `install <git-url>` 均可用。⚠️ **import 会自动写 wrapper 到 `~/.local/bin/`**(即使原来用了 --no-alias)——供给流程 import 后必须清理该 wrapper。
- **toolsets 真名**(25 个,全表见验证报告 V1)：常用=`terminal` `file`(⚠️不是 files) `code_execution` `web` `browser` `vision` `image_gen` `tts` `skills` `memory` `todo` `clarify` `delegation` `cronjob` `computer_use`。开关：`hermes tools enable|disable <name>`。

### 5.4 审批复用（高危操作）
Hermes `approval_required` 事件（`type=high_risk`）→ 建 `approvals` 行（`type='high_risk'`）+ `runs.status=waiting_user` → 前端复用**已有的内联审批卡片**。老板批准 → `decision='approved'` → `resume_after_approval` 调 `POST /v1/runs/{hermes_run_id}/approval` 续跑；驳回 → `decision='rejected'` → `POST /v1/runs/{hermes_run_id}/stop`。

### 5.5 执行中求援（clarification_required）【TD-03-T4 新增】

**触发机制**：利用 Hermes 原生 `clarify` toolset。agent SOUL.md 里加指令：「遇到需求不清楚、依赖信息缺失时，调用 `clarify` 工具并附上问题和缺失的上下文，等待答复，不允许臆测继续」。`clarify` 工具调用 → Hermes 产生 `approval_required` 事件，`metadata.category='clarification'`（在 prompt 里约定）→ RunService 识别此类事件建 `approvals`（`type='clarification'`）。

**数据流（worker AI 直接照此实现）**：
```
agent 调 clarify 工具
→ Hermes SSE: approval_required + metadata.category='clarification'
→ RunService:
    建 approvals(type='clarification', payload_json={"question":..., "missing_context":...})
    runs.status = 'waiting_clarify'
    群里推 system 消息（type='CLARIFY_CARD:{...}'）→ 前端渲染提问卡片
→ 人/AI 在群里回答（POST /api/approvals/{id}/answer, body={"answer":"..."}）
    → approvals.payload_json.answer = 答案, decision = 'answered'
    → resume_after_clarification:
        把答案拼进 prompt 续跑 Hermes（POST /v1/runs/{hermes_run_id}/approval）
        runs.status = 'running'
```

**新增 API**：`POST /api/approvals/{id}/answer`，body `{"answer": str}`，仅 `type='clarification'` 的 approval 可调，否则 400。

开放项（见 [TD-03](TD-03-hermes-execution.md) §开放问题）：审批粒度用哪个高风险工具验证端到端。**定了回填本文件。**

---

## 6. 【目标】Agent 供给（NL→定制员工，TD-04/TD-05）

对应 [ARCHITECTURE-DETAILED.md](ARCHITECTURE-DETAILED.md) §4.1/§5.1 与 [agent-model-and-capabilities.md](agent-model-and-capabilities.md) §3。本节为权威 schema。

### 6.1 `agent_specs` 新表（一个员工一行：用户期望 + 供给状态 + 自进化跟踪）
| 列 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | TEXT | PK | `spec_xxx` |
| `agent_id` | TEXT | NOT NULL, FK→agents ON DELETE CASCADE, UNIQUE | 一对一 |
| `workspace_id` | TEXT | NOT NULL, FK→workspaces CASCADE | |
| `role_name` | TEXT | NOT NULL | 如"前端工程师"，API 限长 ≤80 |
| `source_request` | TEXT | NOT NULL DEFAULT `''` | 用户原始 NL 需求，≤2000 |
| `responsibilities_json` | TEXT | NOT NULL DEFAULT `'[]'` | 职责数组(API 字段 `responsibilities: list[str]`，≤12 条，每条 ≤200) |
| `hermes_profile` | TEXT | 可空 | 对应 Hermes profile 名。命名规则：`wk<workspace前6>-<agent前6>`，建前查重 |
| `status` | TEXT | NOT NULL DEFAULT `'draft'`, CHECK IN (`draft`,`provisioning`,`blocked_on_credentials`,`ready`,`failed`) | 供给状态机：draft→provisioning→(blocked_on_credentials⇄)→ready；任一步失败→failed |
| `runs_since_last_reflection` | INTEGER | NOT NULL DEFAULT 0 | 距上次技能反思已完成的 Run 数；到 reflection_interval 时触发（TD-06-T1） |
| `last_skill_reflection_at` | TEXT | 可空 | 上次技能沉淀时间（TD-06-T1） |
| `reflection_interval` | INTEGER | NOT NULL DEFAULT 5 | 每隔几个 Run 自动反思一次，可按员工调整（TD-06-T1） |
| `created_at` / `updated_at` | TEXT | NOT NULL | |

### 6.2 `agent_capabilities` 新表（员工被授予的每项能力一行）
| 列 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | TEXT | PK | `cap_xxx` |
| `agent_id` | TEXT | NOT NULL, FK→agents CASCADE | |
| `workspace_id` | TEXT | NOT NULL, FK→workspaces CASCADE | |
| `capability_key` | TEXT | NOT NULL | catalog 主键，如 `write_code`/`run_tests`/`git_push`/`deploy_preview`/`deploy_prod`/`domain_register`/`seo_audit`/`social_content`。同一 agent 内 UNIQUE(agent_id, capability_key) |
| `skill_refs_json` | TEXT | NOT NULL DEFAULT `'[]'` | SKILL 名数组 |
| `toolset_refs_json` | TEXT | NOT NULL DEFAULT `'[]'` | Hermes toolset 名数组〔具体合法值待核〕 |
| `mcp_refs_json` | TEXT | NOT NULL DEFAULT `'[]'` | MCP server 名数组〔配置语法待核〕 |
| `required_credentials_json` | TEXT | NOT NULL DEFAULT `'[]'` | 凭证名数组，如 `["GITHUB_TOKEN"]` |
| `risk_gate` | TEXT | NOT NULL DEFAULT `'auto'`, CHECK IN (`auto`,`approval`,`prohibited_auto`) | auto=直接干；approval=弹审批卡片；prohibited_auto=永远人工(花钱/不可逆) |
| `status` | TEXT | NOT NULL DEFAULT `'pending'`, CHECK IN (`pending`,`credential_missing`,`enabled`,`disabled`) | |
| `created_at` / `updated_at` | TEXT | NOT NULL | |

### 6.3 capability_catalog（能力映射表——系统静态资产，不建表）
实现为代码内常量 `services/api/app/orchestration/capability_catalog.py`〔本项目新增〕：`dict[capability_key] -> {"skills":[...],"toolsets":[...],"mcp":[...],"required_credentials":[...],"risk_gate":"auto|approval|prohibited_auto","description":str}`。初始条目按 [agent-model-and-capabilities.md](agent-model-and-capabilities.md) §4 表。改 catalog = 改代码 + 本文件同步。种子(v1)：
种子(v1，toolset 名已按 2026-07-08 [验证报告](../research/hermes-verification-2026-07-07.md) V1 实测真名校正——注意是 `file` 不是 `files`)：
```
write_code      → toolsets[terminal,file,code_execution]                      risk=auto
run_tests       → toolsets[terminal]                                          risk=auto
git_push        → toolsets[terminal] + mcp[github] + creds[GITHUB_TOKEN]      risk=approval
deploy_preview  → toolsets[terminal] + creds[平台token]                        risk=auto
deploy_prod     → toolsets[terminal] + creds[平台token]                        risk=approval
domain_register → (API 包装工具) + creds[注册商key+付费方式]                    risk=prohibited_auto
seo_audit       → toolsets[terminal,web]  (lighthouse 经 terminal 跑)          risk=auto
social_content  → toolsets[web,vision,image_gen] (发布环节人工，见能力文档 §5)   risk=approval
```

### 6.4 新增 API 契约
| 接口 | 请求体 | 响应 | 错误 |
|---|---|---|---|
| `POST /api/agents`（扩展现有） | 现有字段 + 可选 `role_spec: {role_name, source_request?, responsibilities[], capability_keys[]}` | 现有 AgentOut + `spec: AgentSpecOut` | 未知 capability_key→400 |
| `GET /api/agents/{id}/spec` | — | `AgentSpecOut`（含 `capabilities: list[AgentCapabilityOut]`） | 404 |
| `POST /api/agents/{id}/credentials` | `{"credential_name":"GITHUB_TOKEN","value":"..."}` | 更新后的 `AgentSpecOut` | 该 agent 无此凭证需求→400 |
| `POST /api/agents/{id}/provision` | 空体（幂等，重试供给） | `AgentSpecOut` | spec 不存在→404 |

**AgentSpecOut**：§6.1 字段(json 列 → 数组字段，去 `_json` 后缀)。**AgentCapabilityOut**：§6.2 同理。
**凭证安全**：`value` 不落业务 DB——直接写入 `profiles/<hermes_profile>/.env`，DB 只把对应 capability `status: credential_missing→enabled`。支付/域名类凭证不走此接口（prohibited_auto，人工在自己设备上操作）。

双 schema 提醒：§6.1/§6.2 建表须同时加进 `init_postgres()` 和 `init_sqlite()`（§0 G4）。

---

## 7. 【目标】Agent 自进化（TD-06）

### 7.1 `ProfileProvisioner` 新增方法（对接 TD-04 接口）
```python
def update_skill(self, profile_name: str, skill_name: str, content: str) -> None:
    # 写入 profiles/<name>/skills/auto/<skill_name>.md
    # 或调 hermes skills learn '<content>'

def add_capability(self, profile_name: str, capability_key: str,
                   bundle: CapabilityBundle) -> None:
    # 追加 toolset → configure(); 安装 skills; 配 MCP; 更新 agent_capabilities 表

def reload_gateway(self, profile_name: str) -> None:
    # hermes -p <name> gateway reload（若不支持则 stop + start）
```

### 7.2 新增 API 契约（TD-06）
| 接口 | 请求体 | 响应 | 错误 |
|---|---|---|---|
| `GET /api/agents/{id}/skills` | — | `{"auto_skills":[{"name":str,"created_at":str,"preview":str}]}` | 404 |
| `POST /api/agents/{id}/reflect` | 空体（调试用，手动触发反思） | `{"skills_added": int, "skill_names": list[str]}` | spec 不存在/profile 未就绪→400 |

审批答复（能力升级分支）：复用现有 `POST /api/approvals/{id}/answer`，body `{"decision":"approved","payload":{"approved_capability_key":"git_push"}}`；后端按 `approvals.type='capability_upgrade'` 分发到 `UpgradeService.execute_upgrade()`。
