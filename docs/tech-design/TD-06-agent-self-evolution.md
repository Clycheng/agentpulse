# TD-06：Agent 自进化（技能沉淀 + 主动升级申请）

- 关联 ADR：[0001](../decisions/0001-hermes-as-agent-runtime.md)（Hermes 原生 memory / cron / /learn）、[0003](../decisions/0003-server-side-24x7-idea-center.md)（空闲不 idle）
- 执行会话：**必须在 agentpulse 锚定会话**（涉及真实 Hermes profile 写文件/重载）。

## 产品目标

用户眼里发生的事：
1. 新员工入职后，**越用越懂**这家公司——不是因为换了更聪明的模型，而是因为每次工作都在沉淀经验到技能里。
2. 员工"卡住"时**不只会说不行**，而是识别出自己缺什么工具，主动申请，老板一键批准后自动装好，员工继续工作。

用户不需要知道 SOUL.md / SKILL.md / MCP 是什么，**这些细节全部在系统内部自动发生**。

---

## 技术设计

### 子机制一：技能自动沉淀（Experience → Skill）

**触发方式**：每完成 `reflection_interval`（默认 5）个 Run 后，后端调度一次"反思 cron"。

**数据流**：
```
runs(completed) ──N个后──▶ ReflectionService
    ├─ 从 run_steps 拉最近 N 个 Run 的执行流水（type=tool_call/tool_result/message/final）
    ├─ LLM prompt："你刚完成了这些任务，提炼出 1-3 条可复用的工作经验，以 SKILL.md 片段格式输出"
    ├─ 输出：新技能片段（Markdown，含 # 标题 + 步骤/策略）
    ├─ 写入：ProfileProvisioner.update_skill(profile_name, skill_name, content)
    │         → `hermes skills learn '<content>'` 或直接写文件到 profiles/<name>/skills/auto/
    ├─ agent_specs.runs_since_last_reflection = 0，last_skill_reflection_at = now
    └─ 写一条 run_steps(type='skill_learned', title=技能名, payload=片段摘要)
```

**SOUL.md 模板新增规则**（所有员工统一注入，TD-04-T3 的 `draft_soul_md` 里加）：
> 「每完成一项任务，思考一个值得记住的经验——遇到的坑、有效的工具调用顺序、客户偏好等。用 `skills` 工具的 learn 功能保存下来（一句话即可）。系统会定期整理这些碎片成正式技能。」

**边界**：沉淀的是"怎么做"（SKILL.md 流程知识），不是修改 SOUL.md 人格或扩展工具权限——那些走子机制二的审批通道。

---

### 子机制二：主动能力升级申请（Capability Gap → Upgrade Request）

**触发方式**：agent 在执行中遭遇"有任务但没工具/没权限完成"时，**主动通过 `clarify` toolset 提交升级申请**（而非强行失败）。

**SOUL.md 模板新增规则**（所有员工统一注入）：
> 「如果遇到因缺少工具、MCP 连接或权限导致无法完成任务的情况，不要猜测绕路，而是立即用 `clarify` 工具提交能力升级申请，内容包含：需要什么能力（尽量用具体名称，如"GitHub MCP"）、为什么需要、哪个任务卡在这里。等老板批准后你会自动获得该能力。」

**数据流**：
```
agent 调 clarify（category='capability_upgrade'）
→ RunService 识别 → 建 approvals(type='capability_upgrade')
    payload_json = {
      "capability_description": "需要 GitHub MCP 才能推代码",
      "suggested_capability_key": "git_push",   # agent 猜的，人工确认
      "failed_task_id": "task_xxx",
      "run_id": "run_xxx"
    }
→ runs.status = 'waiting_clarify'（复用已有状态）
→ 前端群里推升级申请卡片（不同于普通审批卡，展示"能力申请"UI）
→ 老板审核：确认 capability_key（可修改 agent 猜的）→ POST /api/approvals/{id}/answer
    decision='approved', payload_json.approved_capability_key='git_push'
→ UpgradeService:
    1. 从 capability_catalog 取该 key 的 bundle（skills/toolsets/mcp/required_credentials）
    2. ProfileProvisioner.add_capability(profile_name, capability_key, bundle)
       → 写新 toolsets 到 config.yaml → 安装新 MCP → 更新 agent_capabilities 表
    3. 若有 required_credentials → 建新的 credential_missing capability → 向用户索要
    4. gateway 热重载（hermes gateway reload）或重启
    5. Run.status = 'running'（若原 Run 还活着则续跑，否则通知可重试）
→ 前端：员工卡片显示新能力徽章
```

**`ProfileProvisioner` 新增方法**（[TD-04 接口](TD-04-agent-provisioning.md)扩展）：
```python
class ProfileProvisioner(Protocol):
    # ...原有方法...
    def update_skill(self, profile_name: str, skill_name: str, content: str) -> None:
        # hermes skills learn '<content>' 或写文件到 skills/auto/<skill_name>.md
    def add_capability(self, profile_name: str, capability_key: str,
                       bundle: CapabilityBundle) -> None:
        # 追加 toolsets → configure()；安装新 MCP；install_skills()；触发 reload
    def reload_gateway(self, profile_name: str) -> None:
        # hermes -p <name> gateway reload（热重载；若不支持则 stop + start）
```

---

## 数据模型（DATA-MODEL §5.1 和 §6.1 扩展，两 schema 都加）

**`agent_specs` 扩列**：
| 列 | 类型 | 说明 |
|---|---|---|
| `runs_since_last_reflection` | INTEGER NOT NULL DEFAULT 0 | 距上次反思已完成的 Run 数，到 reflection_interval 时触发 |
| `last_skill_reflection_at` | TEXT 可空 | 上次技能沉淀时间，ISO8601 |
| `reflection_interval` | INTEGER NOT NULL DEFAULT 5 | 每隔几个 Run 触发一次反思（可按员工调整） |

**`approvals.type` CHECK 扩展**：在已有 `'high_risk'|'clarification'` 基础上加 `'capability_upgrade'`。

**`capability_upgrade` 类 approval 的 `payload_json` schema**：
```json
{
  "capability_description": "string — agent 描述的缺口",
  "suggested_capability_key": "string | null — agent 猜的 catalog key",
  "approved_capability_key": "string | null — 人审批时填写/确认",
  "failed_task_id": "string | null",
  "run_id": "string | null"
}
```

**新增 API**：
- `GET /api/agents/{id}/skills` → 列出当前已沉淀的自动技能（前端"员工档案"展示成长轨迹）
- `POST /api/agents/{id}/reflect` → 手动触发一次技能反思（调试/测试用）
- 审批答复复用现有 `POST /api/approvals/{id}/answer`，后端按 type 分发处理逻辑

---

## Tech-Tasks

### TD-06-T1：技能自动沉淀（Reflection Cron）
- 改动点：
  1. `agent_specs` 扩列（双 schema）；
  2. `services/api/app/runtime/reflection.py`（新增）：`ReflectionService.run_reflection(conn, agent_id)` — 拉 run_steps → LLM 提炼 → `ProfileProvisioner.update_skill`；
  3. 在 RunService 的 Run 完成路径里：`agent_specs.runs_since_last_reflection += 1`，到阈值则调 `ReflectionService`；
  4. `ProfileProvisioner` 新增 `update_skill`（LocalHermesProvisioner 实现）；
  5. `GET /api/agents/{id}/skills` + `POST /api/agents/{id}/reflect`（调试接口）。
- 验收：完成 5 个 Run 后，agent 的 skills 目录下多出自动生成的 SKILL.md 文件；内容与执行流水相关；`GET /api/agents/{id}/skills` 能列出；`POST /api/agents/{id}/reflect` 可手动触发。
- 依赖：TD-03-T3（run_steps 有真实数据）+ TD-04-T6（真实 Hermes profile）。
- 需 agentpulse 会话：是。
- 估算：2 天。

### TD-06-T2：主动能力升级申请
- 改动点：
  1. `approvals.type` 扩 CHECK + payload_json schema（双 schema）；
  2. `services/api/app/runtime/upgrade.py`（新增）：`UpgradeService.execute_upgrade(conn, approval_id)` — 读 approved_capability_key → catalog → `ProfileProvisioner.add_capability` → credential 缺口 → gateway reload；
  3. `POST /api/approvals/{id}/answer` 里按 type='capability_upgrade' 分支调 `UpgradeService`；
  4. `ProfileProvisioner` 新增 `add_capability` + `reload_gateway`（LocalHermesProvisioner 实现）；
  5. SOUL.md 生成模板（`draft_soul_md`）加升级申请指令。
- 验收：端到端——agent 碰到缺工具的任务 → 前端出现升级申请卡片 → 老板批准 → profile 获得新 MCP/toolset → agent 能完成之前失败的任务类型；有 credential_missing 的情况也要验证。
- 依赖：TD-03-T4（clarification + approval 机制完整）+ TD-04-T6（ProfileProvisioner 能写 profile）。
- 需 agentpulse 会话：是。
- 估算：2–2.5 天。

### TD-06-T3：SOUL.md 模板注入 + 手动触发 UI
- 改动点：
  1. `draft_soul_md`（TD-04-T3 所建）在生成所有员工 SOUL 时自动追加 §两段规则（经验沉淀指令 + 升级申请指令）；
  2. 桌面端"员工档案"页面加"已习得技能"列表（调 `GET /api/agents/{id}/skills`）和"能力申请历史"。
- 验收：新招募员工的 SOUL.md 自动含这两段规则；桌面端能看到员工技能成长轨迹。
- 依赖：TD-06-T1 + TD-06-T2。需 agentpulse 会话：否（前端）/ 是（验 SOUL）。
- 估算：1 天。

## Definition of Done
- 招募一个员工 → 干 5 个任务 → 技能目录自动增长（用户在档案页能看到）。
- 员工遭遇工具缺失 → 主动申请 → 老板批准 → 员工能力升级 → 继续工作。
- 用户全程**不需要知道 SOUL.md / SKILL.md / MCP 是什么**，只需在升级申请时点"批准"。
- 更新 AGENTS.md §4 + CHANGELOG + 本文件状态。
