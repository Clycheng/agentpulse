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

# 跑一轮讨论：选人→组 prompt(transcript + 该员工人格 + "讨论态只讨论不执行"约束)
#   →调临时执行层(现有 complete_agent_reply)→写回消息→返回是否已可收敛
def run_discussion_round(conn, *, workspace_id, conversation_id,
                         max_agent_turns: int = 4) -> dict: ...
```
- 约束：讨论态(`discussing`)下只允许产出 message/提问/brief 草稿，不允许执行类动作（为 TD-03 铺路）。
- 收敛：主持人判断"背景够拆任务" → 调 `POST /api/briefs` 出草稿；到 `max_agent_turns` 上限也强制产一版。
- 开放项（实现前定，见 [TD-02](TD-02-multi-agent-discussion.md) §开放问题）：主持人是否可配、发言人选择用 LLM 还是轮询。**这几项定了要回填本文件。**

---

## 5. 【目标】TD-03 新增契约（接 Hermes 执行）

### 5.1 `runs` 扩列（两 schema 都加）
新增：`task_id TEXT NOT NULL FK→tasks CASCADE`（Run 必属 Task）、`hermes_profile_id TEXT`（对应员工 profile）、`hermes_run_id TEXT`（Hermes 侧 run id）、`workdir TEXT NOT NULL`（**绝对路径**隔离目录）。`status` 状态机扩为 `queued→running→waiting_user→completed|failed`。

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

### 5.4 审批复用
Hermes `approval_required` → 建现有 `approvals` 行（§1 的 ApprovalOut 结构）+ Run→`waiting_user` → 前端复用**已有的内联审批卡片**（首个会话所建）。老板批准 → 调 `.../approval` 续跑。

开放项（见 [TD-03](TD-03-hermes-execution.md) §开放问题）：单网关多 profile vs 一 profile 一进程、进程管理、审批粒度用哪个高风险工具验证。**定了回填本文件。**
