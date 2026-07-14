# ADR 0008：统一的人类介入审批模型（技术危险 + 业务危险）

- 状态：**已接受（机制已实测证明）· 全量落地待分片实现**
- 日期：2026-07-14
- 关联：[ADR 0002](0002-...)（讨论对齐门须结构性强制）、[ADR 0005](0005-hermes-poc-safety-findings.md)（SOUL 铁律不保证被遵守，门要靠结构强制）、[ADR 0007](0007-hermes-v0.18-interface-acp.md)（ACP 传输）、[TD-03-T4](../tech-design/TD-03-hermes-execution.md)

## 背景 / 问题

2026-07-14 对真 Hermes 做审计,发现 **TD-03-T4「审批 suspend/resume」在真运行时不生效**:让真 agent 执行 `rm -rf`,它**直接跑成功、`request_permission` 触发 0 次**。北极星「老板拍板制」（安全支柱）在执行层**没有被强制**;此前的"审批闭环"验证全靠 fake backend + seed 的 approval 行。同时 `clarify` 工具在 ACP 会话未暴露给模型;`capability_upgrade` 无真触发入口。

项目所有者的目标（本 ADR 要满足的）：
1. 像 Cursor / Windsurf / Claude Code / Codex 那样——**执行过程中遇到权限/需人类拍板的动作时,暂停并给人三/多选项:允许一次 / 永远允许 / 拒绝**。
2. 审批范围**不止电脑危险操作,还含业务危险操作**（如"改对外文案是否影响业务""发布""花钱""对外发送"）。
3. **人介入得越多,agent 越会学**——哪些还要问、哪些不必问。

## 根因（实测）

Hermes 的审批由 `approvals.mode` 决定,三档（`tools/approval.py::_normalize_approval_mode`）：
- `manual` = 提示人类（走 ACP `request_permission` → 我们的 client 回调）
- `smart` = 用辅助 LLM 自动判（日志 "Auxiliary approval: using auto"）——**危险命令被自动放行**
- `off` = 直接放行（等价 yolo）

我们的员工 profile **没配 `approvals` 块**,被 smart/auto 兜住 → 危险命令裸跑。ACP adapter 其实**已经**把 `request_permission` 桥到危险命令审批（`acp_adapter/permissions.py` + `server.py:1421`），选项就是 **Allow once / Allow for session / Allow always / Deny / Deny always**。

## 决定性实验（已验证）

一次性 profile 配 `approvals.mode: manual` → 让 agent 执行 `rm -rf /tmp/x`：
- `request_permission` **精确触发 1 次**,payload 含命令 + 风险描述("delete in root path") + 我们注入的 `approval_id`/`category`;deny 后命令被拦。

→ **技术危险动作的真审批门,靠 `approvals.mode: manual` + 现有 ACP resolver 即可打通**,且天然拿到"允许一次/本会话/永久/拒绝"多选项。

## 决定

**统一审批模型 = harness 拦截 + 多选项 + 持久规则 + 记忆学习**,覆盖两类动作:

### 1. 技术危险动作（rm/部署/推代码/写系统路径…）
- 供给员工 profile 时设 `approvals.mode: manual`（`LocalHermesProvisioner.configure`）。
- Hermes → ACP `request_permission` → `HermesBackend` resolver → 现有 `approval_bridge` 挂起 → 前端卡片给 **允许一次 / 永远允许 / 拒绝**（映射 ACP `allow_once` / `allow_always` / `reject_once`；`allow_session` 可选）。
- "永远允许" = 写进 Hermes `approvals.allow` 允许名单（或我们侧规则库），下次同类自动放行。

### 2. 业务危险动作（发布/花钱/对外发送/改对外文案…）
- Hermes 永不 gate 这些 → 必须由**我们**建成"受控业务工具"（我们侧 tool / MCP）,agent 调用即被我们拦下判风险 + 走**同一套审批 UI 与多选项**。
- 风险判定是编排层策略（可含 LLM 预判 + 规则），不是 agent 自觉（ADR 0005：SOUL 铁律不保证）。

### 3. 学习（北极星④）
- "永远允许/永远拒绝" = 持久规则（按 workspace/agent/动作模式）。
- 每次人类批/拒写进 agent 记忆/技能 → 下次自己把已知低风险归类、只对真正不确定的升级问人 → **问的次数递减**。

### 4. 求援（clarification）— 修正既有设计
- 实测 `clarify` 工具 ACP 未暴露给模型;agent 缺信息时**本就会发普通消息问**、结束当轮。→ **求援不需要专门的审批卡**:agent 消息里问 → 老板正常回 → 下轮带答案继续。删除/降级"求援卡"这一路的伪装。

### 5. 能力升级（capability_upgrade）
- 无 agent 真触发入口 → 改为**老板发起的授予**（员工档案里"+授予能力"→ `execute_upgrade`,已是真代码）或纳入业务工具门。删除"agent 主动申请"的伪装。

## 待实现（分片）

1. `LocalHermesProvisioner.configure` 设 `approvals.mode: manual`（+ timeout）;供给时对已存在 profile 也补写。
2. `hermes_client` 审批返回值核对:approve 要返回 Hermes 认得的 outcome 类型（`AllowedOutcome` vs 我们现在给的 `SelectedPermissionOutcome`）并按 **option_id**（allow_once/allow_always/deny）选择,而非仅按 kind；否则"批准"可能被 Hermes 读成 deny。**接线前必须对真 Hermes 复测 approve 真放行。**
3. `approval_bridge`/resolver:决定字符串扩成 `allow_once|allow_always|deny`,贯通到 ACP option_id。
4. 前端审批卡:加"永远允许"按钮（现只有批准/驳回）。
5. 挂起超时:Hermes 侧默认 60s fail-closed;我们 await-in-place 需与之对齐（要么加长、要么承接超时）。
6. 业务受控工具（发布/花钱/对外发送）设计与门接入（独立 TD）。
7. 删除/降级 clarification 求援卡 + capability_upgrade「agent 主动申请」的伪装,改为上述真路径。

## 影响 / 风险

- `approvals.mode: manual` 会让员工在危险动作前真的停下等人——这正是要的,但要处理超时与 UI 承接,否则 run 卡住。
- 共享 profile 跨会话争用（实测 agentpulse 的 working_dir 被别的会话改过）——供给应保证 per-employee profile 隔离。
- 本 ADR 只锁定**方向与已验证机制**;每条"待实现"仍需真机复测后才算完成（不再靠 seed 假装）。
