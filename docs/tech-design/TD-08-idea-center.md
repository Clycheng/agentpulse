# TD-08：Idea 中心（员工空闲时主动想业务）

- 关联 ADR：[0003](../decisions/0003-server-side-24x7-idea-center.md)（服务端 7×24 + idea 中心决策）、[0001](../decisions/0001-hermes-as-agent-runtime.md)（Hermes cron/daemon）
- 执行会话：**大部分任务任意会话**（建表/API/前端）；idle 触发的 reflection run 须在 agentpulse 锚定会话验证。

## 产品目标

"没有 idle 员工"——员工没有活干的时候，不只是等着，而是在主动想：
- 我最近处理的问题有没有可优化的模式？
- 公司下一步可以试什么方向？
- 我注意到什么风险/机会？

这些想法进入 **Idea 中心**（独立于任务中心），老板定期翻看，好的 idea 一键转成讨论/任务。

---

## 技术设计

### Idea 数据模型

```
ideas
  id                    TEXT  PK  idea_xxx
  workspace_id          TEXT  NOT NULL  FK→workspaces CASCADE
  source_agent_id       TEXT  NOT NULL  FK→agents CASCADE
  title                 TEXT  NOT NULL  限长 ≤120
  description           TEXT  NOT NULL  idea 正文，限长 ≤1000
  category              TEXT  NOT NULL  CHECK IN (improvement|opportunity|risk|learning)
  status                TEXT  NOT NULL DEFAULT 'new'
                              CHECK IN (new|reviewed|accepted|dismissed|converted)
  converted_brief_id    TEXT  可空  FK→consensus_briefs SET NULL（转为 brief 时填）
  created_at            TEXT  NOT NULL
  reviewed_at           TEXT  可空
```

`agent_specs` 扩列（两 schema 都加）：
- `last_idle_think_at TEXT 可空`：上次 idle 反思时间
- `idle_think_interval_hours INTEGER NOT NULL DEFAULT 6`：触发间隔（小时），可按员工调整
- `idle_thinking_enabled BOOLEAN NOT NULL DEFAULT TRUE`：可关闭（部分工种不适合主动 idea）

### Idea 产生流程（Idle Reflection）

触发时机：**后端 cron（每小时检查一次）**，满足以下条件则触发该员工的 idle reflection run：
1. `agent_specs.idle_thinking_enabled = true`
2. `agent_specs.status = 'ready'`
3. 距 `last_idle_think_at` 超过 `idle_think_interval_hours`
4. 该 agent 无活跃 Run（`runs` 里无 status IN ('queued','running','waiting_user','waiting_clarify')）

```
后端 cron 触发
→ IdleThinkService.trigger_reflection(conn, agent_id)
→ 构建反思 prompt（见下方模板）
→ 创建 runs(type='idle_reflection', task_id=null)   # 特殊 run，不绑 task
→ HermesBackend.run(ctx)  →  agent 产出 1-3 个 idea（强制 JSON 格式）
→ 解析 JSON → 写入 ideas 表（每个 idea 一行）
→ agent_specs.last_idle_think_at = now
→ 推前端通知：「小秘有 2 个新想法」
```

**反思 Prompt 模板**（注入 agent 的 SOUL.md 里，作为空闲时的行为指引）：
> 「当你没有待处理的任务时，用以下视角反思最近的工作并产出想法：
> 1. **改进（improvement）**：最近工作中有没有可以做得更好的流程/方式？
> 2. **机会（opportunity）**：你观察到什么值得尝试的方向或增长点？
> 3. **风险（risk）**：有没有需要关注的潜在问题？
> 4. **学习（learning）**：你学到了什么值得记录分享的经验？
>
> 输出严格 JSON：`[{"title":"...", "description":"...", "category":"improvement|opportunity|risk|learning"}]`
> 每次 1-3 条，言简意赅，不要凑数，没有值得说的就输出 `[]`。」

### Idea 转化流程

```
老板在 idea 中心看到 idea
→ 「转为讨论」→ POST /api/ideas/{id}/convert
    → 建新 group conversation（participants 含相关 agent）
    → 第一条系统消息 = idea 内容（作为讨论起点）
    → conversations.idea_id = idea.id（追溯来源）
    → ideas.status = 'converted', converted_brief_id 待讨论后填
→ 「标记接受」→ ideas.status = 'accepted'（记录，不建对话）
→ 「忽略」→ ideas.status = 'dismissed'
```

---

## API 契约

| 接口 | 方法 | 请求体 | 响应 |
|---|---|---|---|
| `/api/ideas` | GET | `?status=new&agent_id=...&category=...` | `IdeaOut[]` 分页 |
| `/api/ideas/{id}` | GET | — | `IdeaOut` |
| `/api/ideas/{id}/review` | POST | `{"action":"accept"|"dismiss"}` | 更新后的 `IdeaOut` |
| `/api/ideas/{id}/convert` | POST | 空体 | `{"conversation_id":str, "idea":IdeaOut}` |
| `/api/agents/{id}/idle-thinking` | PATCH | `{"enabled":bool,"interval_hours":int}` | `AgentSpecOut` |

**`IdeaOut`**：ideas 表全部字段 + `source_agent_name: str`（join agent.name）。

---

## 前端设计要点

- **Idea 中心**独立入口（侧边栏），不嵌入任务中心
- 按 agent / category 过滤，未读优先
- 每条 idea 展示：员工头像 + 名字 + 类别标签（改进/机会/风险/学习）+ 正文 + 时间
- 右侧操作：「转为讨论」「接受」「忽略」
- 顶部摘要：「本周共 12 条想法，来自 3 位员工」
- 通知徽章：有新 idea 时侧边栏显示数字

---

## Tech-Tasks

### TD-08-T1：ideas 表 + API
- 改动点：`ideas` 表（双 schema）；`agent_specs` 扩列 3 个（双 schema）；`conversations` 加 `idea_id FK`；`schemas/idea.py` 新增 `IdeaOut` + 4 个 API 路由。
- 验收：单测覆盖 idea CRUD + status 流转 CHECK 约束；convert 接口建出 conversation 且 idea_id 正确关联。
- 依赖：无（纯数据模型 + API）。需 agentpulse 会话：否。估算：1 天。

### TD-08-T2：IdleThinkService + cron 触发
- 改动点：`runtime/idle_think.py`（新增）—— `trigger_reflection()` 构建 prompt + 调 HermesBackend + 解析 JSON + 写 ideas；后端 cron（`apscheduler` 或系统 cron）每小时扫一次符合条件的 agent 触发。
- 验收：端到端——让一个 agent 空闲 > interval_hours → ideas 表自动多出记录；JSON 解析失败/空数组不报错；`last_idle_think_at` 正确更新。
- 依赖：TD-03-T2（HermesBackend）+ TD-04-T6（工作的 profile）。需 agentpulse 会话：是。估算：1.5 天。

### TD-08-T3：Idea 中心前端
- 改动点：桌面端新增 Idea 中心页面（侧边栏入口 + 列表 + 操作）；通知徽章；agent_specs 设置里加"空闲思考"开关。
- 验收：新 idea 出现在列表；convert 后能进入新会话；关闭 idle_thinking 后 cron 不再触发该员工。
- 依赖：TD-08-T1 + TD-08-T2。需 agentpulse 会话：否。估算：1.5 天。

## Definition of Done
- 员工空闲 6 小时后自动产出想法，出现在 Idea 中心。
- 老板能接受/忽略/转化为讨论，被转化的 idea 直接开启一个有相关员工的群聊。
- 员工可单独关闭 idle thinking（如客服 agent 不适合 idea 生成）。
