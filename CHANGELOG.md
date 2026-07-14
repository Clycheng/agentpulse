# Changelog

本文件记录 AgentPulse 值得留痕的改动。**每次做完实质工作请在顶部追加一条**（见 [AGENTS.md](AGENTS.md) §5）。
架构/方向级决策另记在 [docs/decisions/](docs/decisions/)。格式参考 [Keep a Changelog](https://keepachangelog.com/)。

## [Unreleased]

### 2026-07-14（TD-06-T3：成长轨迹前端 —— 让自进化「可见」）
- **feat(desktop)**: 员工详情抽屉 `AgentDetail` 新增「成长轨迹」区，把 TD-06-T1/T2 的后端成果接成用户能看的界面。
  - **已获得能力**：拉 `GET /api/agents/{id}/spec` 的 `capabilities`，渲染能力徽章 + 状态（`已启用`/`待补凭证`/`待生效`/`已停用`，`credential_missing` 用 warning 色、`disabled` 用 subtle 色）。
  - **已习得技能（自动沉淀）**：拉 `GET /api/agents/{id}/skills`，卡片显示 SKILL.md 首行标题 + 正文摘要；空态"干活满一定轮次后会自动沉淀可复用技能"。
  - **触发反思**按钮：调 `POST /api/agents/{id}/reflect`，内联显示"新沉淀 N 条技能 / 这轮暂无 / 错误信息"，成功后刷新技能列表。
  - `AgentDetail` 加 `token` prop；`styles.css` 加 `.growth-head`/`.growth-sub`/`.cap-badge`/`.skill-card`/`.button.small`（全用现有 teal / warning token，浅深主题通用）。
  - **浏览器实测**：起独立 API(8001)+renderer(5175，`.env.local` 指过去，避开另一会话占用的 8000/5174)→登录 demo 工作区→员工→阿伦→成长轨迹正确渲染（`social_content 已启用` + `email_sending 待补凭证` + 技能空态）；`tsc --noEmit` 无错、无 console 报错、截图留证。
  - 剩余：聊天内「审批/求援/能力升级」卡片（SSE `approval` 事件已带 category+approval_id，前端按类型渲染并调 `/resolve`\|`/answer`）另立一项。

### 2026-07-14（TD-06-T2：主动能力升级申请 —— 北极星④自进化第二半）
- **feat(runtime+api)**: 员工碰到"有任务但缺工具"时主动申请升级，老板一键批准即自动把能力装到它的 Hermes profile。
  - `runtime/upgrade.py::execute_upgrade`：读老板确认的 `approved_capability_key` → `resolve_bundle` 校验并合并出 toolsets/skills/mcp/creds/risk_gate → `ProfileProvisioner.add_capability`（真装：`tools enable` + `skills install` + `gateway reload`）→ upsert `agent_capabilities` 行（有 `required_credentials` → `credential_missing` 交给现有凭证流程要，否则 `enabled`）。未知 key / 无 profile → `UpgradeError`。
  - `runner._persist_run_approval`：加 `capability_upgrade` 分支——标题"员工申请能力升级"、`payload_json` 存 `capability_description` + `suggested_capability_key`。
  - `routes/workspace.py` `/approvals/{id}/resolve`：识别 `type=capability_upgrade`——批准时先 `execute_upgrade`（用老板确认或 agent 建议的 key）装好能力，再唤醒挂起的 run。`ResolveApprovalRequest` 加可选 `approved_capability_key`（老板可改 agent 猜的 key）。
  - **顺带修 bug**：另一会话重写 resolve 端点时把 `approved`/`rejected` 原样传给 `approval_bridge.resolve_pending`，但 `hermes_client` 的 permission 映射只认 `allow_once`/`deny` → **批准会被误映射成拒绝**。已改为 `bridge_decision = "allow_once" if approved else "deny"`，高危审批的批准路径现在真的放行。
  - SOUL(`_build_soul`)：铁律加"因缺工具/MCP/权限无法完成时，用 `clarify` 提交 `capability_upgrade` 申请，等老板批准自动获得能力"。
  - **零回归**：新增 `test_upgrade.py` 6 例（无凭证→enabled、有凭证→credential_missing、未知 key/无 profile→报错、幂等 upsert 不重复、resolve 端点全链：批准→装 write_code→`agent_capabilities` 落行 + run 续跑）；全套 **250 通过 + 7 skipped**。三条架构 grep 干净。
  - 说明：TD-06-T2 的 provisioner 方法（`add_capability`/`reload_gateway`）由另一会话先行提交（step 2/6，commit `e3a8101`），本次补齐 UpgradeService + 审批创建/解析接线 + SOUL + 测试，完成整条闭环。
  - Verified: execute_upgrade 经生产路径 `POST /api/approvals/{id}/resolve`（type=capability_upgrade 批准分支）调用。

### 2026-07-13（清理：合并两套 TD-03-T4 的残留债务）
- **chore(cleanup)**: 两个会话平行实现了 TD-03-T4，快进合并后留下债务，本次清理（方向未跑偏——三条架构 grep 干净、生产路径已收敛到 `make_bridge_resolver`）：
  - 删除死码 `runner._make_approval_resolver`（已被 `make_bridge_resolver`+`_persist_run_approval` 取代、不在生产路径）及其 `tests/test_approval_suspend.py`（258 行只测死码，正是 AGENTS.md §5 警告的反模式）；去掉 `runner.py` 重复定义的 `_now_iso` 与随之无用的 `asyncio`/`json`/`new_id` import。
  - 恢复被 `a7d3227` 从 CHANGELOG 误删的 5 条 2026-07-13 记录（下列 T4/TD-06-T1/TD-08-T2/许可证/截图）。
  - 全套 **测试通过、零回归**。

### 2026-07-13（TD-03-T4：审批 suspend/resume + 求援 —— 北极星「老板拍板制」双向闭环）
- **feat(runtime+api)**: 高风险动作现在能**挂起 run → 等老板批 → 原地续跑同一个 run**（此前是 deny-by-default 只能拒）。
  - `runtime/approval_bridge.py`：进程内 Future 注册表（单 uvicorn 进程）。`await_decision(approval_id)` 挂起、`resolve_pending(approval_id, decision)` 用 `call_soon_threadsafe` 线程安全唤醒。因 ACP 是 stdio 子进程、run 状态活在子进程里，**只能唤醒活协程、不能 detach 重连**——所以续跑=唤醒挂起中的 `request_permission`，不是重发 Hermes。
  - `hermes_client.py`：`request_permission` 生成 `approval_id`、发 `approval_required` 事件（带 approval_id + category）、`await permission_resolver(...)` **原地挂起**（ACP 会话与 run 一起停住），拿到决定再映射成 allow/deny 选项返回；run() 事件循环在挂起期**禁用超时**。
  - `runner.py`：`make_bridge_resolver()`（resolver 注册并 await 桥）；`stream_agent_run` 收到 approval_required → 落 `approvals`(带 `run_id`+`type`) + 转 run 到 `waiting_user`/`waiting_clarify` + commit + 推 SSE。`_persist_run_approval` 按 category 生成标题/风险级。
  - 热路径 `_stream_reply_events` 注入 `make_bridge_resolver()`，员工高危动作真正挂起等批（idle/reflection 仍传 None → deny-by-default，安全）。
  - `/api/approvals/{id}/resolve`：run 关联审批 → 转 run 回 `running` + `resolve_pending(allow_once/deny)`，**跳过**旧的"审批即完成任务"逻辑（那是给非 run 的手动审批卡的）；批准→agent 续跑执行，驳回→agent 收到 reject 走替代/收尾。
  - `/api/approvals/{id}/answer`（新）：clarification 类——记录答复为会话消息 + 唤醒续跑。**已知限制**：ACP permission 响应只带 allow/deny，答复**文本**目前经会话历史带回（agent 下一轮读到），真·inline 注入待 Hermes resume API，跟进项。
  - SOUL 已含"需求不清先问 / 高危等老板"铁律（无需改）。
  - **零回归**：`test_approval_flow.py` 9 例（桥 await/resolve、未知 resolve 返回 False、fake backend 全链路挂起→approve 续跑 / deny 走替代、resolve 端点转 run、answer 记录消息+续跑、非 clarification /answer→404）。三条架构 grep 干净。
  - Verified: make_bridge_resolver 经生产路径 `workspace.py::_stream_reply_events` → `stream_agent_run` 注入；resolve/answer 经 `POST /api/approvals/{id}/resolve|answer` 驱动 `approval_bridge.resolve_pending`。

### 2026-07-13（TD-06-T1：技能自动沉淀 —— 北极星④「越用越懂你」后端闭环）
- **feat(runtime)**: `app/runtime/reflection.py` —— 员工把最近工作提炼成可复用技能，沉淀进自己的 Hermes profile。
  - `_summarize_recent_steps`：拉该员工最近 N 个 completed run 的 `run_steps`（tool_call/tool_result/message/final）压成流水文本。
  - `run_reflection`：注入提炼 prompt（强制严格 JSON）→ 经员工自己的 Hermes profile 执行 → `parse_skills` 容错解析（去围栏/取数组/校验/裁剪/最多 3 条）→ 逐条 `ProfileProvisioner.update_skill` 写进 profile `skills/auto/<name>.md` → 重置 `runs_since_last_reflection` + stamp `last_skill_reflection_at`（空输出/后端异常/无流水也会 stamp，不 hot-loop）。不绑会话、不建 runs 行。
  - `bump_reflection_counter`：`runner.stream_agent_run` 每完成一个 run 给该 agent +1，到 `reflection_interval`（默认 5）触发；实际反思由后台 `run_reflection_tick` 跑（off hot path）。
  - `ProfileProvisioner` 加 `update_skill` / `list_skills`（RecordOnly 记内存 + LocalHermes 读写 `skills/auto/`；**修复**：全中文技能名会 sanitize 成空导致文件名 `skill.md` 互相覆盖 → 空 slug 时用名字 sha1 哈希保唯一）。
  - schema：`agent_specs` 加 `runs_since_last_reflection`/`last_skill_reflection_at`/`reflection_interval`（双 schema，ensure_column 迁移）。
  - API：`GET /api/agents/{id}/skills`（成长轨迹）+ `POST /api/agents/{id}/reflect`（手动触发，调试/演示）。
  - SOUL：`_build_soul` 追加"每完成一项任务就用 skills.learn 记一条经验"的自我进步指令。
  - cron：后台循环在 idle tick 后追加 `run_reflection_tick`（复用 `idle_thinking_cron` 开关 + 同一 backend/provisioner）。
  - **真机验证**：LocalHermesProvisioner 对真 agentpulse profile 的 `update_skill`/`list_skills` 物理写读通过（并清理）；`test_run_reflection_real_hermes`（`HERMES_E2E=1`）跑通。
  - **零回归**：新增 `test_reflection.py` 14 单测；三条架构 grep 干净。
  - 偏差说明：TD-06 设计里的 `run_steps(type='skill_learned')` 因 `run_steps.type` 有 CHECK 白名单**暂略**；技能可见性改由 `GET /skills` 读 profile 技能目录提供，不影响 DoD。
  - Verified: bump_reflection_counter 经生产路径 `runner.stream_agent_run` 完成分支调用；run_reflection 经 `POST /api/agents/{id}/reflect` 与后台 `main.py::_idle_cron_loop` 驱动。

### 2026-07-13（TD-08-T2：空闲员工主动想 idea —— 北极星⑤后端闭环）
- **feat(runtime)**: `app/runtime/idle_think.py` —— 落地"没有 idle 员工"：员工空闲够久就自发反思并产出 idea。
  - `find_due_idle_agents`：选出符合条件的员工（`agent_specs.status='ready'` + `idle_thinking_enabled` + 有 `hermes_profile` + 距 `last_idle_think_at` 超过 `idle_think_interval_hours` + 无活跃 run）。
  - `trigger_reflection`：注入反思 prompt（改进/机会/风险/学习，强制严格 JSON 输出）→ 经与 RunService 相同的 `RunBackend` 接口调 Hermes → `parse_ideas` 容错解析 → 写入 `ideas` 表 → stamp `last_idle_think_at`。空数组/解析失败/后端异常都会 stamp 且不抛，避免 cron hot-loop。不绑会话、不建 runs 行。
  - `run_idle_tick`：一轮扫描所有 due 员工逐个反思，返回 `{agents_processed, ideas_created}`。
  - cron：`main.py` startup 起后台 asyncio 循环，`config.py` 加 `idle_thinking_cron`（默认 false）+ `idle_cron_interval_seconds`（默认 3600）；默认关，测试/无 Hermes 环境不受影响。
  - **零回归**：新增 `test_idle_think.py` 12 常开单测 + 1 guarded e2e（`HERMES_E2E=1`，真机跑通）。三条架构 grep 干净。
  - Verified: run_idle_tick 经生产路径 `main.py::_idle_cron_loop`（startup 后台循环，`idle_thinking_cron` 开启时）驱动。

### 2026-07-13（许可证改用 PolyForm Noncommercial + README 截图）
- **docs(license)**: 把自写的"学习免费/商业需授权"自定义协议换成业界成熟标准 **[PolyForm Noncommercial License 1.0.0](LICENSE)**（非商业用途免费、商业另需授权），法律措辞更规范可靠。商业授权联系方式从 README 移到独立的 [COMMERCIAL.md](COMMERCIAL.md)；README 不再出现商业授权招揽内容，License 徽章/段落同步更新。
- **docs(readme)**: 新增桌面工作台真实截图——顶部 hero（群讨论 → 共识纪要 → 老板拍板）+「界面预览」画廊（任务中心 / 人才市场 / 想法中心 / 深色主题），图存 `docs/images/`。截图前把后端(SQLite)+前端端到端跑通并走查了登录→群讨论→共识纪要卡→任务→人才市场→想法全流程，生产 UI 路径均正常。

### 2026-07-10（TD-03-T5：自动供给 —— 招人即真员工）
- **feat(api+runtime)**: 招一个员工（带 role_spec）就自动创建一个**可运行的 Hermes profile**，热路径随即自动路由到它——不再手动置 spec。
  - `profile_provisioner.build_provisioner_from_settings()`：按 `settings.hermes_provisioning` 选 `LocalHermesProvisioner`（真 CLI）或 `RecordOnlyProvisioner`（默认，测试/无 Hermes 环境）。
  - `orchestration/supply.provision`：默认走配置选出的 provisioner；能力就绪时——建 profile → **写 SOUL.md**（`_build_soul`：角色/职责/工作方式 + "不清楚先问、高风险等老板"铁律）→ 配 `deepseek/deepseek-v4-flash`+toolsets → 装 skills → **写 DeepSeek key 进 profile .env**（员工即刻可跑）→ 回填 `agent_specs.hermes_profile`+status=ready；profile 名合法化为 lowercase alnum（Hermes 要求）。
  - `config.py`：加 `hermes_provisioning`（默认 false）。
  - **真机 e2e 过**（`test_auto_provision.py`，`HERMES_E2E=1`）：`provision` 开供给开关 → 真 Hermes profile 落地（config 有 v4-flash、SOUL 含角色、.env 有 key）、spec ready，然后清理。
  - **零回归**：默认 RecordOnly，全套 **207 通过 + 5 skipped**；新增 2 常开 wiring 测（SOUL/credentials 被记录、profile 名格式、flag off→RecordOnly）。
  - 至此 TD-03 主链闭环：**招人→自动建真 profile→发消息→Hermes 执行→run_steps+回写**，全部真机验证过。只剩 TD-03-T4 审批 suspend/resume（现 deny-by-default，安全）。

### 2026-07-10（TD-03-T3 后半：热路径切换 —— 员工在 App 里真的经 Hermes 干活）
- **feat(api+runtime)**: 把跑着的消息流从"临时 DeepSeek"切成"经 RunService 调 Hermes"，**有 ready profile 的员工走 Hermes、其余回退 DeepSeek（零回归）**。
  - `runtime/runner.py`：`start_run` 重构为流式 `stream_agent_run`（边持久化 run_steps + 回写 message，边 yield `{type:chunk|message|tool_call|...}` 给 SSE）；新增 `resolve_hermes_profile(agent_id)`（`agent_specs.hermes_profile` 且 status=ready 才走 Hermes）。
  - `routes/workspace.py`：新增共享 `_stream_reply_events`——按 agent 是否有 ready profile 选 Hermes(`stream_agent_run`+`HermesBackend`) 或 DeepSeek 回退；`send_message_stream` 的**群讨论 turn_executor 与 DM/单人两条分支都改用它**（run_discussion_round 契约不变）。Hermes prompt = 讨论上下文 + 老板消息（人格来自 profile SOUL）。approval_required → SSE `approval` 事件（deny-by-default，安全）。
  - `core/config.py`：加 `hermes_work_root`（绝对，空则运行时解析为 cwd 下绝对 `.hermes-data`）+ `hermes_bin`。
  - **真机 e2e 过**（`test_hot_path_hermes.py`，`HERMES_E2E=1`）：把一个 agent 的 `agent_specs` 置 `hermes_profile=agentpulse`/ready → DM 经 `/messages/stream` 发消息 → 断言产生 `runs(provider='hermes',completed)` + `run_steps(message,final)` + agent 消息 "OK" 落库。
  - **零回归**：现有 205 测试全过（无 profile 的 agent 一律走原 DeepSeek 路径，行为不变）；4 guarded e2e。
  - 剩余：审批 suspend/resume 闭环（TD-03-T4）、招人自动建 profile（`LocalHermesProvisioner` 接进 supply，TD-03-T5）——现在要手动置 spec。

### 2026-07-10（TD-03-T3 写半：RunService —— run→run_steps→回写消息）
- **feat(runtime)**: `app/runtime/runner.py::start_run` —— 把一次 Hermes 执行完整落库。
  - 消费 backend（`HermesBackend` 或测试用 fake）的 `AgentEvent` 流：按 TD-03-T1 生命周期建 `runs`(queued→running→completed/failed)；thinking/message 分别缓冲、每轮各落 1 条 `run_steps`；tool_call/tool_result/approval_required 逐条落；聚合出的 agent 回复经 `add_message` 写回会话；`final` 步 + 状态转移 + `output_message_id` 回填；错误→run=failed 记 error。
  - **真机 e2e 过**：RunService → HermesBackend(ACP) → 真 Hermes(`agentpulse` profile, DeepSeek) → run 完成、run_steps 有 message+final、agent 消息 "OK" 落库。
  - 测试：新增 `test_runner.py`——2 常开（fake backend：断言 thinking 聚合成一条、tool_call 逐条、message 回写、run 完成并回填 output_message_id；error→failed）+ 1 guarded 真机 e2e（`HERMES_E2E=1`，实测过）。全套 **205 通过 + 3 skipped**。
  - 剩余（TD-03-T3 后半，需 agentpulse 会话）：把群讨论/回复热路径的执行从临时 DeepSeek 切成经 RunService 调 Hermes（员工↔profile 映射）+ approval 挂起/续跑闭环。

### 2026-07-10（TD-03-T2：HermesBackend —— 员工经 ACP 真执行）
- **feat(runtime)**: `app/runtime/hermes_client.py` —— 让 AI 员工**真正跑起来**（照 [ADR 0007](docs/decisions/0007-hermes-v0.18-interface-acp.md) 走 ACP，不是 REST）。
  - 起 `hermes --profile <p> acp` 子进程，用官方 `agent-client-protocol==0.9.0`（已入 requirements）走 ACP（newline JSON-RPC，`use_unstable_protocol=True` 对齐 agent 侧）：`initialize` → `session/new(cwd=绝对 workdir)` → `session/prompt`。
  - 把 ACP `session_update` 流映射成统一 `AgentEvent`（message / thinking / tool_call / tool_result / usage / status / final）；`request_permission` → 发 `approval_required` 事件 + 由注入的 resolver 决策并**总是选中 agent 提供的某个选项**（默认 deny=选 reject_once）；`read/write_text_file` 限制在 `workdir` 内（ADR 0005，路径逃逸即抛错）；terminal 工具默认拒绝。
  - `RunContext`/`AgentEvent` 数据类；`run()` 是 async 生成器，子进程/连接在 finally 里干净收尾，带超时。
  - **真机 e2e 实测通过**：`agentpulse` profile 收到 "reply OK" → 流式 thinking（"The user wants me to…"）+ message "OK" + usage(tokens) + final(end_turn)，16 事件映射正确。
  - 测试：新增 `test_hermes_backend.py`——2 常开安全测（workdir 必须绝对、`_safe_path` 拒绝逃逸）+ 1 guarded 真机 e2e（`HERMES_E2E=1`，实测过：断言到 final + message 含 "OK"）。全套 **203 通过 + 2 skipped**。
  - 解锁 TD-03-T3（RunService：消费事件流写 run_steps + 结果回写 + 审批挂起/续跑）。

### 2026-07-10（Hermes 接入地基 + TD-04-T6 供给器 + ADR 0007 接口修正）
- **feat(runtime)**: 真正把 Hermes 接进项目的第一步（本机 Hermes v0.18.2，项目所有者提供真实 DeepSeek key）。
  - **key 验证**：新建 isolated profile `agentpulse`（`deepseek/deepseek-v4-flash`、绝对 workdir、key 写进 profile 的 gitignored `.env`），`hermes --profile agentpulse -z "..."` 实测返回结果——key + 模型 + agent loop 全通。key 存 `services/api/.env`（gitignored），未入库/日志/commit。
  - **重大接口修正（[ADR 0007](docs/decisions/0007-hermes-v0.18-interface-acp.md)）**：v0.18.2 **没有** 旧设计假设的 REST `POST /v1/runs`+SSE（`hermes gateway` 现在是消息平台网关）。程序化接口是 `hermes acp`（ACP，stdio JSON-RPC，`--check` OK）与 `hermes serve`（JSON-RPC/WS）。决定 `HermesBackend` **改用 ACP** 传输；`agents.hermes_gateway_port`（端口/一员工一网关）作废；作废 DATA-MODEL/TD-03 §5.3 的 REST 段（已加醒目标注）。
  - **TD-04-T6 `LocalHermesProvisioner`**（`app/runtime/profile_provisioner.py`）：用实测过的 `hermes` CLI 真建/配/删 profile——`profile create --no-alias --no-skills`、`config set model`、`config set terminal.working_dir <绝对路径>`（ADR 0005 硬约束，构造函数强制 `work_root` 绝对）、`tools enable`、`skills install --yes`、凭证追加进 profile `.env`（值不入日志）。
  - 测试：新增 `test_local_provisioner.py`——2 条 always-on（work_root 必须绝对、hermes 不存在报错），1 条 guarded e2e（`HERMES_E2E=1` 真跑 hermes：建 profile→配 model+绝对 workdir+toolsets→写 SOUL/creds→删，已实测通过）。全套 **201 通过 + 1 skipped**。
  - DeepSeek 实测事实：provider `deepseek`、key env `DEEPSEEK_API_KEY`、base `https://api.deepseek.com/v1`、模型 `deepseek/deepseek-v4-flash`|`-pro`。

### 2026-07-10（Idea 中心前端：桌面端「想法」视图）
- **feat(desktop)**: 把 TD-08-T1 的 idea API 接成界面（TD-08-T3 前端半），落地北极星"没有 idle 员工 → idea 中心"的用户界面。
  - `main.tsx`：`View` 增加 `ideas`，侧栏新增「想法」入口（lightbulb 图标）；新增 `IdeasView` 组件——自取 `GET /api/ideas`，顶部摘要（共 N 条 / 来自几位员工）+ 分类过滤 tabs（改进/机会/风险/学习）+ 想法卡片（员工头像取 per-agent hue、分类标签配色、标题、正文、时间）+ 三个动作：转为讨论 / 接受 / 忽略。
  - "转为讨论"走 `POST /api/ideas/{id}/convert` → 由 App 回调重载 bootstrap 并 `openChat` 跳进新建的讨论群（首条系统消息=想法内容）。
  - `styles.css`：新增想法视图样式，全部用 teal 设计 token。
  - 验证：`tsc --noEmit` 无错；浏览器实测经 API 播种 2 条想法 → 列表正确渲染、分类标签/头像正常 → 点"转为讨论"成功建群并自动跳转、群里第一条即想法内容、无 console 报错。idle 自动产 idea（TD-08-T2）仍待 Hermes。

### 2026-07-10（TD-07-T2 前端半：创建员工"按职位快速配置"）
- **feat(desktop)**: 把"按职位一键招人"接到创建员工弹窗，TD-07-T2 完整闭环。
  - `CreateAgentModal` 新增 `token` 入参 + 拉取 `GET /api/role-bundles`；顶部新增"按职位快速配置（可选）"芯片行（12 个预配角色），点选即把该角色的能力清单写入选择、并在名称/部门为空时自动填成角色名；再点一次取消。
  - 新增"已选 N 项能力：…"摘要行，让通过角色选中的业务能力（即使不在手动能力网格里）也可见。
  - 顺手清理：该弹窗残留的写死紫色（`#6c5ce7`/`#f0edff`）能力芯片改用 teal 设计 token（`.cap-chip` / `.role-bundle-chip` 类 + `styles.css`），与全局重做一致。
  - 验证：`tsc --noEmit` 无错；浏览器实测点"数据分析师"→ 芯片高亮、名称/部门自动填、摘要显示 `data_query · data_analysis · report_generation`、无 console 报错。

### 2026-07-10（渠道管理前端：桌面端「渠道」视图）
- **feat(desktop)**: 把 TD-09-T2 的渠道 API 接成界面（TD-09-T3 前端半）。
  - `apps/desktop/src/main.tsx`：`View` 增加 `channels`，侧栏新增「渠道」入口（hub 图标）；新增 `ChannelsView` 组件——自取 `GET /api/channels`，含创建表单（名称/类型/默认分配员工）、渠道卡片列表（类型标签、启用状态带 pulse 点、webhook 完整 URL + 一键复制、停用），全部走 `apiRequest`。
  - `styles.css`：新增渠道视图样式（表单/卡片/URL 行/状态点），全部用现有 teal token 与 pulse-ring 动画。
  - 验证：`tsc --noEmit` 无错；浏览器实测创建 2 个渠道 → 卡片正确渲染带完整 webhook URL、复制/停用可用、无 console 报错。TD-09-T3 仅剩 ChannelReply 回发 + 微信/widget 适配器（需真实账号）。

### 2026-07-10（TD-07-T2 API 半：按职位招人的后端契约）
- **feat(api)**: 为"按职位一键招人"提供后端契约（前端"按职位选"UI 待做）。
  - `GET /api/role-bundles`（`routes/catalog.py`，认证）：列出 12 个预配角色及其 `capability_keys` 与 `resolved`（合并后的 toolsets/mcp/creds/risk_gate），供创建员工弹窗渲染选项。
  - `POST /api/agents` 的 `role_spec` 新增可选 `role_bundle_key`：有值时经 `get_role_bundle` 展开并"bundle 优先去重"并入 `capability_keys`（可与手动勾选叠加）；未知角色 → 400。
  - 测试：新增 `test_role_bundles_api.py` 5 例（列角色 + 认证要求、按角色建员工能力自动填齐、bundle 与显式 key 合并、未知角色 400）。全套 **199 测试通过**（+5）。

### 2026-07-10（TD-07-T1：业务岗位能力目录扩展）
- **feat(api)**: 让"用一句话招人"覆盖业务岗，不只是技术岗。
  - `orchestration/capability_catalog.py` 在技术岗种子外补齐 **7 大类 31 个业务能力**：客服（customer_service/ticket_management/refund_processing/customer_data_lookup）、内容运营（content_writing/image_creation/email_drafting/email_sending/seo_content/ad_analysis/ad_bidding）、数据（data_query/data_analysis/report_generation/web_scraping）、HR、法务、财务（含 `payment_execution` = `prohibited_auto`，花钱不可逆永不自动）、项目管理。
  - 新增 `ROLE_BUNDLES`（12 个预配角色：客服专员/数据分析师/HR 专员…→ 能力清单）+ `get_role_bundle(name)`/`list_role_bundles()` 访问器；供 TD-07-T2"按职位一键招人"用。
  - 对齐修正：种子里 `social_content` 的 toolsets 由代码侧 `[web,vision]` 补成与 DATA-MODEL §6.3 真相源一致的 `[web,vision,image_gen]`（此前 TD-05 代码与真相源不一致）。
  - 测试：`test_capability_catalog.py` 扩到 33 例——把"CATALOG 恰好 8 个种子键"的断言改为"种子键 ⊆ CATALOG"，新增业务条目合法性（description/risk_gate 合法、有 MCP 必声明凭证）、`ROLE_BUNDLES` 全部 key 都在 catalog、每个角色能 resolve_bundle 不报错、未知角色报错。全套 **194 测试通过**（+10）。DATA-MODEL §6.3 同步。

### 2026-07-10（TD-09-T2：渠道管理 API + 公开 Webhook 端点）
- **feat(api)**: 把 TD-09-T1 的 channel router 接成一条可 curl 验证的完整入站链路。
  - `app/services/channels.py`：渠道 CRUD（create 生成 `token` + 返回 `webhook_url`、list、get+stats、patch、软删 active=0）、`channel_stats`（今日入站数 / 活跃外部用户数）、`verify_signature`（URL token 为主凭证；config 里配了 `secret` 则额外校验 `X-Signature` = HMAC-SHA256(raw_body)）。
  - `app/api/routes/channels.py`：`/api/channels` 认证 CRUD（含 target_agent/target_conversation 归属校验）。
  - `app/api/routes/webhooks.py`：**公开** `POST /webhooks/{channel_type}/{token}`（不挂 /api、无 JWT）——按 token+type 查 active 渠道 → 验签 → 解析 JSON → `route_inbound` → 若渠道 pin 了 target_agent，经现有 `complete_agent_reply` **尽力触发一次回复**（执行层报错则吞掉、仍返回 200，消息已落库）。
  - 新增 email 适配器（SendGrid/Mailgun inbound-parse 风格，按 from/text 归一化）；注册表现覆盖 generic_webhook + email；微信(XML+加密)/widget 留 TD-09-T3。
  - 测试：新增 `test_channels_api.py` 8 例（CRUD + 未知 target 拒绝、webhook 入站落库、去重、stats、未知/停用 token→404、缺/对 HMAC 签名→401/200、不支持渠道类型→400、mock LLM 下 target_agent 触发 agent 回复）。全套 **184 测试通过**（+8）。DATA-MODEL §9.2/9.3 标记已实现。

### 2026-07-10（TD-09-T1：外部渠道数据模型 + Router 核心）
- **feat(api)**: 外部渠道接入地基——外部消息(微信/邮件/网页/通用 webhook)进来后归一化成标准消息、进入普通会话流，**agent 完全不感知渠道**（纯数据 + Router，不接 webhook 端点/不碰 Hermes）。
  - schema（双 schema + `ensure_column`）：新增 `channel_configs`（channel_type CHECK、token UNIQUE、config_json、target_agent_id/target_conversation_id、active 存 INTEGER 0/1）；`conversations` 加 `source_channel`/`external_conversation_id`；`messages` 加 `external_message_id`（webhook 重发去重）。
  - `app/channels/`：`adapters/`(base `ChannelMessage` + `generic` 适配器按可配置点路径 `message_path`/`user_id_path`/`message_id_path` 提取 + 注册表 `get_adapter`)；`router.py` 的 `route_inbound`(归一化→找/建会话→去重→落 `sender_type='user'` 消息)、`find_or_create_conversation`(pin 固定群 / 按 `(source_channel, external_user_id)` 归线程)、`message_already_processed`。留 TD-09-T2 触发 agent 回复的接缝。
  - 测试：新增 `test_channels.py` 6 例（建会话+消息+外部字段、按 external_message_id 去重、同一外部用户归一会话且不同用户分开、pin 固定群路由、无 message_id 不去重、自定义嵌套路径 + 缺内容报错）。全套 **176 测试通过**（+6）。DATA-MODEL §9.1 标记已实现。

### 2026-07-10（TD-08-T1：Idea 中心数据模型 + API）
- **feat(api)**: 落地北极星 §1.5「没有 idle 员工 → idea 中心」的后端地基（纯数据 + API，不接 Hermes）。
  - schema（双 schema + `ensure_column` 迁移）：新增 `ideas` 表（category/status 带 CHECK 约束，`converted_brief_id` 追溯转化）；`agent_specs` 加 `last_idle_think_at`/`idle_think_interval_hours`/`idle_thinking_enabled`；`conversations` 加 `idea_id`（追溯从哪个 idea 转来的会话）。
  - `app/services/ideas.py`：create/get/list（按 new 优先 + status/agent/category 过滤）/review（accept→accepted、dismiss→dismissed）/convert（建 group 会话 + 拉入 source agent + 首条系统消息=idea 内容 + 回链 `conversations.idea_id` + idea→converted）/set_idle_thinking。
  - `app/api/routes/ideas.py`（注册进 main）：`GET/POST /api/ideas`、`GET /api/ideas/{id}`、`POST /api/ideas/{id}/review`、`POST /api/ideas/{id}/convert`、`PATCH /api/agents/{id}/idle-thinking`；业务逻辑在 service 层，路由只做 HTTP。
  - 两处实现偏差（已回填 DATA-MODEL §8）：`idle_thinking_enabled` 两方言统一存 `INTEGER 0/1`（迁移用单一定义字符串），API 序列化为 bool；idle-thinking 接口返回精简的 `IdleThinkingSettings` 而非 `AgentSpecOut`（无 spec 的员工返回 404）。
  - 测试：新增 `test_ideas.py` 8 例（CRUD、new 优先与过滤、review、convert 建会话并直查 DB 断言 `idea_id` 回链、重复 convert 拒绝、schema 422、DB CHECK 约束、idle-thinking 更新与无 spec 404）。全套 **170 测试通过**（+8）。DATA-MODEL §8.1 标记已实现。

### 2026-07-09（前端重做：桌面端设计系统升级）
- **feat(desktop)**: 用 impeccable 前端 skill 重做桌面端 UI（`apps/desktop/src/styles.css`，纯样式层，不动 `main.tsx` 逻辑/结构，功能不受影响）。
  - **方向**：从"通用浅色 + SaaS 蓝 + 扁平卡片"升级为「一人 AI 公司运营驾驶舱」。register=product（对标 Linear/Raycast 的克制）。配色策略 Restrained：中性 ink 底 + **单一品牌色 teal「脉搏」**（语义=员工 7×24 在工作），teal 只用于主操作/选中/focus/live 状态；success/warning/danger 与品牌色分色相；保留并沿用 per-agent `hue`（外壳克制、人物带色）。
  - **Token 层重写**：`:root`（浅色）+ `[data-theme='dark']`（近黑 cockpit + 更亮 teal）全套 token——中性梯度、品牌 teal 家族（含 `--on-primary`/`--primary-strong`）、语义色带 soft 变体、4 级 `--shadow-*` 高度、teal `--ring`、圆角(含 pill)、`--ease-out`；字体 Latin=Inter + CJK=Noto Sans SC。
  - **组件精修**：全局 `:focus-visible` teal ring + 交互过渡 + `prefers-reduced-motion` 兜底 + `pulse-ring` 关键帧（仅 live 指示器）；按钮/小按钮补齐 hover/active/disabled 全套状态与阴影；侧栏品牌 mark 改 teal 渐变芯片、active 导航加 teal 指示条；search-box 变真输入(border+focus ring)、composer focus ring + send 全状态、卡片加 xs 阴影、pill 圆角、清理残留写死蓝（auth 渐变/focus 改 teal token）。
  - **对比度**：按 skill 要求把 `--subtle`（placeholder/timestamp）在两套主题都调到达标。
  - 浏览器预览验证：消息/人才市场/任务/员工四视图 + 浅色&深色两主题均已截图确认级联正确、无 console 报错。新增 `apps/desktop/AGENTS.md` 固化设计系统，防后续 AI 改回通用蓝。

### 2026-07-09（TD-03-T1：Run/RunStep 数据模型）
- **feat(api)**: 为接 Hermes 执行铺好数据地基（纯 schema + 生命周期，不起 Hermes）。
  - `database.py` 两套 schema（SQLite + Postgres）+ `ensure_column` 迁移：`runs` 扩 `task_id`/`hermes_profile_id`/`hermes_run_id`/`workdir`（新列暂可空，NOT NULL 与"每个 Run 必属 Task"由 TD-03-T3 的 RunService 在应用层强制）；新增 `run_steps` 表（映射 Hermes SSE 事件：message/thinking/tool_call/tool_result/approval_required/status/final）；`approvals` 加 `run_id`（批准后据此恢复对应 Run）+ `type`（high_risk/clarification/capability_upgrade，行为在 T4）；`agents` 加 `hermes_gateway_port`（一员工一 gateway 一端口）。引用 `runs` 的 FK 列走 `ensure_column`（在 runs 建表之后加），规避 Postgres 前向引用报错。
  - 新增 `app/runtime/runs.py`：Run 生命周期状态机（`queued → running → waiting_user|waiting_clarify → completed|failed`，非法转移抛 `RunStateError`，终态 stamp `completed_at`）+ `create_run`/`transition_run`/`append_run_step`/`list_run_steps`（支持 `after_step_id` 增量拉取，对接 TD-03 前端轮询契约）。
  - 测试：新增 `test_run_lifecycle.py` 13 例——状态机合法/非法转移、终态无出边、失败记 error、run_steps 追加+增量列出、以及对真实 `init_db()` 跑迁移并断言新列/新表存在且幂等。全套 **162 测试通过**（+13）。
  - DATA-MODEL §5.1/§5.2 标记为已实现；解锁 TD-03-T2（HermesBackend，需 agentpulse 会话起 Hermes）。

### 2026-07-09（TD-02-T5：路由归位，修复架构漂移）
- **fix(api+orchestration)**: 消除 2026-07-08 复核发现的结构性漂移，把群讨论编排真正收回编排层。
  - `orchestration/discussion.py::run_discussion_round` 从"只被单测调用的死码 + 同步 dict 返回"**重写为 async 事件流**（yield `speaker`/`chunk`/`message`/`error`/`end` 事件），成为群讨论的**唯一生产入口**。`send_message`（非流式）和 `send_message_stream`（流式）都改为 `async for event in run_discussion_round(...)` 驱动它——路由层只注入 `turn_executor`（如何执行一轮 agent 回复 + 持久化）和 `llm_complete`（主持人 LLM 执行层薄封装，由新的 `make_speaker_selector()` 构造），再把事件翻译成各自传输格式（SSE 帧 / 累积列表）。
  - 发言人选择逻辑（@提及 → 主持人 LLM → 轮询降级）全部收敛到编排层：新增 `resolve_next_speaker`（端到端解析，内部经注入的 `llm_complete` 调 LLM），路由层的 `_llm_select_speaker`/`_extract_mention_simple` **删除**；`_build_discussion_context` 迁移为编排层 `build_discussion_context`。
  - 编排层保持零外部 HTTP：LLM 调用一律经注入回调，`app/orchestration/` 内无 `httpx`/`requests`/`hermes_client`。
  - 测试：`test_discussion.py` 按新 async 契约重写 `TestRunDiscussionRound`，新增 `TestResolveNextSpeaker`/`TestParseSpeakerJson`/`TestBuildDiscussionContext`（覆盖从路由迁入的 LLM 选人逻辑）；`test_workspace_flow.py` 新增 `test_stream_group_discussion_routes_through_orchestration`——mock `run_discussion_round`，向 `/messages/stream` 发真 HTTP 请求断言生产路径确实经过编排入口（不是单测直调函数的假验收）。全套 **149 测试通过**（较基线 137 +12）。
  - 三条禁止模式 grep 全干净（路由无业务循环/私有 LLM 选人、生产入口真调 run_discussion_round、编排无直连 HTTP）。
  - Verified: run_discussion_round called via production path POST /api/conversations/{id}/messages/stream（及 /messages）；解锁 TD-03-T2/T3。

### 2026-07-08（架构复核：发现真实漂移）
- **docs(architecture-audit)**: 用户直接质问"AI 干的活方向有没有飘"，做了一次彻底代码复核（不只是接口签名，而是追调用链），确认**是，且是结构性漂移，需要纠正**：
  - `orchestration/discussion.py::run_discussion_round`(TD-02 设计的核心编排入口)在生产环境是**死代码**——只被单测调用，`api/routes/workspace.py` 的 `send_message`/`send_message_stream` 从未真正调用它。372 行单测全过，但只测了一个生产请求走不到的函数，给出"TD-02 已完成"的假象。
  - 路由层里独立写了**两份重复的讨论循环**(非流式/流式各一份)，外加一套单独的 `_llm_select_speaker`+`_extract_mention_simple`(跟编排层的 `select_next_speaker` 功能重叠、优先级还反过来)，直接违反 ARCHITECTURE-DETAILED.md §3.1 的边界层职责("不写业务逻辑")。
  - 风险点：TD-03-T3 原计划替换 `complete_agent_reply` 的执行部分，但该函数只被前端已弃用的非流式 `/messages` 调用；前端现在只走 `/messages/stream`(`_stream_agent_reply`)。若不纠正直接做 TD-03，会把 Hermes 接到用户实际走不到的死路径。
  - **纠正**：新增 [TD-02-T5](docs/tech-design/TD-02-multi-agent-discussion.md#td-02-t5)（路由归位：重复实现收回 orchestration 层，唯一化发言人选择入口），列为看板最高优先级，**TD-03-T2 及以后新增依赖 TD-02-T5**（TD-03-T1 纯 schema 不受影响）。TD-03 设计文档同步更正真实执行入口。看板"已完成"表补注该风险，避免误读为"TD-02 已可靠交付"。
  - 未直接修改代码（分工：本侧只出设计/纠正，实现交给 worker AI）。

### 2026-07-08（架构侧收尾）
- **docs(backfill)**: 完成验证报告(`19c209b`)遗留的回填义务——V1–V7 实测事实写入 DATA-MODEL §5.3(Runs API 真实请求体/Tirith 审批配置/一 profile 一 gateway 一端口/MCP·skills·profile 打包命令/25 个 toolset 真名)；§6.3 catalog 种子改用真名(`file` 不是 `files`)；TD-03 开放问题全关(含 **workdir 架构决策**：Runs API 无 per-run cwd → profile 级绝对 work root + 每 Run 子目录约定，硬边界在员工 work root)；TD-04-T6/TD-05/ARCHITECTURE/agent-model 的〔待核〕全部替换为实测事实。
- **docs(board)**: 重建执行看板——修复指向不存在文件的坏链接、错乱编号；"待提交"条目全部换成真实 commit 号(TD-02=`b61005e`、TD-04-T3=`f55d0b1`、T4=`81af20d` 等)；新队列=端到端手测 / TD-03-T1 / TD-04-T6(已解锁)。维护规则加两条：链接必须指向真实文件、完成必须带 commit 号。
- **chore(cleanup)**: 删除验证会话遗留的 `~/.local/bin/vtest3` wrapper(报告自标的污染)；UnitPulse 干净检查通过；全量测试 137 passed 复核通过。

### 2026-07-08（四）
- **docs(readme)**: README 全面重写——修掉 ADR 0001 之前的过时内容(旧 mermaid 里的 Local Runtime/Tool Broker/多 LLM Provider、Roadmap Phase 3 的 provider adapters、"Agent runtime: Planned" 状态)，对齐当前架构(自研编排层 + Hermes 每员工一 profile)与真实进度(群讨论第一片✅、Hermes PoC✅)。SEO/GEO 优化：双语定义句前置 + 英文 Overview、徽章、三方对比表(vs 聊天机器人 vs 自动化平台)、FAQ 问答区(6 问，LLM 引用友好)、关键词/Topics 区、按读者分流的文档导航表、精简 Quick Start。

### 2026-07-08（三）
- **docs(tech-design)**: 新增 [EXECUTION-BOARD.md](docs/tech-design/EXECUTION-BOARD.md)——唯一任务状态源，让任何 AI 冷启动读仓库即知"下一步做什么"(现在就做队列/依赖阻塞表/已完成表/认领锁规则：开工第一动作=改看板为进行中并 push)，不再需要人类口头派单。AGENTS.md §4"下一步"改为第一跳指看板；执行协议第 2/5 条改为"领任务/完成都在看板标状态"(TD 文件不标，防两处漂移)。

### 2026-07-08（二）
- **docs(tech-design)**: 分工定版——本侧只产设计文档，实现由 worker AI 执行。为此补齐三块：① [HERMES-VERIFICATION-PLAYBOOK](docs/tech-design/HERMES-VERIFICATION-PLAYBOOK.md)(把清〔待核〕变成可执行剧本 V1–V7：toolsets 真名/MCP 语法/技能安装/单网关多 profile/审批触发/打包分发/workdir 语义，含硬性安全前置与回填清单)；② TD-03 加深到字段级(SSE事件→run_steps 映射表、RunService 签名、v1 前端轮询决策、**发现并补上 `approvals.run_id` schema 缺口**——没它批准后找不到该恢复哪个 Run，已进 DATA-MODEL §5.1)；③ TD-02 加深到字段级(send_message 接线点、配置常量、发言人选择严格 JSON 契约+降级、收敛判定契约、prompt 约束、防刷屏)。README 新增 V 线(建议最先执行)与"Worker AI 执行协议"6 条。

### 2026-07-08
- **docs(tech-design)**: 新增 [TD-05](docs/tech-design/TD-05-capability-catalog.md)(能力映射表：代码常量模块+resolve_bundle 合并规则+risk_gate 只升不降+domain_register 永远 prohibited_auto) 与 [TD-04](docs/tech-design/TD-04-agent-provisioning.md)(Agent 供给完整详细设计：v1 入口=创建员工表单而非聊天以解耦 TD-02；供给分逻辑/物理两段，`ProfileProvisioner` 接口把接缝正好切在〔待核〕Hermes 边界上，RecordOnly 实现让 T1–T5 全部可先做可测；role_spec LLM 起草+代码硬校验；SOUL 生成；凭证不落库直写 profile .env；供给状态机+幂等重试；6 个 task 中仅 T6 需 agentpulse 锚定会话)。阶段表新增 D 线(与 B/C 可并行)。

### 2026-07-07（深夜）
- **docs(tech-design)**: 新增 [ARCHITECTURE-DETAILED.md](docs/tech-design/ARCHITECTURE-DETAILED.md)——实现级系统架构脊梁：组件全景(对齐真实模块树)/运行时拓扑与部署/分层职责+接口/完整数据模型/三条核心时序(NL→agent 供给、讨论→任务、任务→Hermes 执行)/横切关注点(鉴权/凭证/审批/隔离/错误/双schema/流式/幂等)/Hermes 边界契约(调用面+假设+待核清单)/分期与组件深化索引(TD-04 供给、TD-05 catalog 待建)。
- **docs(tech-design)**: [DATA-MODEL-AND-API.md](docs/tech-design/DATA-MODEL-AND-API.md) 新增 §6"Agent 供给"权威 schema——`agent_specs`/`agent_capabilities` 两张新表(精确列/约束/状态机)、capability_catalog 种子(8 个 capability_key→bundle+risk_gate)、4 个新增 API 契约(POST /api/agents 扩 role_spec、credentials、provision、spec)；架构文档 §4.1 改为引用此节，杜绝两处漂移(G1 教训)。

### 2026-07-07（夜）
- **docs(tech-design)**: 新增 [agent-model-and-capabilities.md](docs/tech-design/agent-model-and-capabilities.md)，回答"系统怎么实现"的核心架构问题：agent = 基础 profile + 人格(SOUL.md) + 技能(教流程) + 工具/MCP(给执行力) + 凭证 + 模型；小秘书=编排角色(职责+工具面不同，非更强底座)；一句话→role_spec→自动 provision 出定制 agent 的数据流；前端工程师/小红书运营两个工种的能力逐条落地(每能力=技能+工具/MCP+凭证+风险审批门+现成开源程度)，含诚实边界(域名/生产部署/花钱须人工；小红书无开放发布 API)；能力主要靠组装现成积木(内置工具+MCP 生态+cli-anything+技能 tap)。文末列"待核清单"(per-profile MCP 语法、profile install、per-tool 风险配置等，编码前须对 Hermes 实测确认)。附注：本轮两路联网研究因环境 web 工具连续 600s 超时失败，本文档基于本会话早前成功研究 + 本机实测 Hermes 一手材料写成，推断处均标注可信度。

### 2026-07-07（傍晚）
- **docs(tech-design)**: 把 tech-design 拉到"任何人/AI 拿到即可开工"的标准。新增 [DATA-MODEL-AND-API.md](docs/tech-design/DATA-MODEL-AND-API.md)(唯一真相源：所有表/字段/类型/约束/接口/错误码精确规格，含 TD-02/TD-03 的目标 schema) 和 [the-loop.md](docs/tech-design/the-loop.md)(闭环走查锚文档，带真实数据)。核对实现代码发现并记录 4 处不对齐(G1–G5)：DB `participant_agent_ids_json` vs API `participant_agent_ids`(ADR 0006 写错，已加勘误)；`TaskOut` 缺 `consensus_brief_id`(加 TD-01-T1b 修)；`discussion_status` 未接线(TD-01-T1)；`database.py` 双 schema(init_postgres/init_sqlite)须两处同步改的硬约束。README/AGENTS.md 已指向这两份新文档。

### 2026-07-07（下午）
- **docs(tech-design)**: 新增 `docs/tech-design/` 目录，把"从第一片已完成 → 第一个真正可用的垂直闭环"的剩余工作拆成技术设计 + tech-task：[TD-01](docs/tech-design/TD-01-verify-and-harden-slice-1.md)(端到端手测并收尾第一片)、[TD-02](docs/tech-design/TD-02-multi-agent-discussion.md)(多 agent 群讨论，照 AutoGen 骨架)、[TD-03](docs/tech-design/TD-03-hermes-execution.md)(执行层换真·Hermes：Run/RunStep + HermesBackend + workdir 隔离 + 审批闭环)。每个 TD 含技术设计 + 编号 tech-task(带验收标准/依赖/是否需 agentpulse 锚定会话)。推荐顺序 A→B→C。AGENTS.md §4"下一步"与文档索引已指向这些。

### 2026-07-07
- **feat(orchestration)**: 实现 [ADR 0006](docs/decisions/0006-group-discussion-v1-first-slice.md) 群讨论协议第一片(commit `c2054bf`)：新增 `consensus_briefs` 表 + `tasks.consensus_brief_id` + `conversations.discussion_status`；新建 `orchestration/`(discussion/brief/gate)模块；`/api/briefs` 路由(create/confirm/reject/get)；**从 `send_message` 移除正则自动建任务**，Task 创建改为必须携带 confirmed brief 的门控(`gate.py`)；前端渲染共识纪要卡片(BRIEF_CARD 前缀)+ 确认/继续讨论按钮。14 tests 通过。
- **docs**: 同步文档到实际状态(上一条实现提交遗漏了此步)——`AGENTS.md` §4 从"群讨论 ❌ 未实现"更新为"🟢 第一片已实现(仅单测,未端到端手测)"并重列下一步三选项；ADR 0006 状态行标注已实现。另经实测复核 `services/api` 测试确为 14 passed、UnitPulse 仓库未被本次实现污染。

### 2026-07-05（下午）
- **docs**: 做了一次"冷读 handoff 测试"（一个零上下文 AI 只读仓库判断能否继续），结论：大方向/架构/硬规矩都接得住，但"最近这一步的具体计划"没写进仓库、且 AGENTS.md §4 旧"下一步"与实际商定计划不一致。据此新增 [ADR 0006](docs/decisions/0006-group-discussion-v1-first-slice.md) 把已认可的"群讨论协议第一片"计划（讨论态 + 共识 brief + Task 创建门、对齐用人工确认、本片不碰 Hermes）落进仓库，并附"待与所有者敲定"清单（consensus_brief schema、编排模块位置、对齐信号形式等）；同步更新 AGENTS.md §4"下一步"指向 ADR 0006，消除歧义。

### 2026-07-05
- **docs**: 完成 Hermes 本机地基验证——pip 装 `hermes-agent`、建多个 profile、用 DeepSeek 作主模型、HTTP Runs API + SSE 流式事件全链路跑通，多 profile 人格隔离验证成立。同时发现两个必须处理的坑并记为 [ADR 0005](docs/decisions/0005-hermes-poc-safety-findings.md)：① `terminal.working_dir` 默认相对路径不可信任，必须显式绝对路径隔离（验证中曾误写文件到无关的真实项目仓库，已确认全部为全新文件并清理干净，未造成数据丢失）；② SOUL.md 硬性规则不保证被遵守，印证 ADR 0002 的讨论对齐门必须由编排层结构性强制。已同步更新 `docs/ARCHITECTURE.md` §3.10 和 `AGENTS.md` §4。

### 2026-07-04
- **docs(research)**: 新增 `docs/research/skill-source-repos.md`——调研 `HKUDS/CLI-Anything`、`msitarzewski/agency-agents`、`anbeime/skill` 三个仓库能否为 Hermes 员工补技能。结论：前两个已自带官方 Hermes 集成，可分别作"工具接入"(约150项软件自动化)和"人格/技能素材"(250+ agent 人格，映射到默认员工编制)；第三个授权状态不清晰，仅作发现索引、逐一审计后引用。已列出可实现清单和建议顺序，尚未拍板/实现。
- **docs**: 补全 AGENTS.md 文档索引——之前遗漏了已存在的 `docs/prd.md`/`docs/backlog.md`/`docs/workflow.md`/`docs/research/`；并消除 `docs/ARCHITECTURE.md`(本次新增) 与 `docs/workflow.md`/`docs/backlog.md` 里提到的 Architecture 阶段产出物 `docs/architecture.md`(旧规划，从未创建) 之间的命名歧义——明确两者是同一份文档。

### 2026-07-03
- **docs**: 消除 `ROADMAP.md` 与 ADR 0001–0004 的技术歧义——不再只加警告，直接改写「Agent 底层设计」一节里所有假设"多 CLI 适配 / Codex 优先 / 本机检测多运行时"的内容(Multica 结论、Runtime 取舍表、建议架构、本机 Daemon、Runtime 优先级、后端模块目录、Day 15–19 计划)，改为与"Hermes 为唯一基座"一致的正确版本；产品愿景/MVP 边界/执行节奏方法论保留不变。
- **docs**: 对齐 AGENTS.md 开放标准 / Claude Code 官方实践——`CLAUDE.md` 改用 `@AGENTS.md` import(会话开头自动加载)；AGENTS.md 补充"文档随项目生长"约定(嵌套 AGENTS.md 就近生效 + `.claude/rules` 路径域 + skills)。
- **docs**: 新增项目基准文档，供后续 AI/开发者接手即对齐、防跑偏：
  - `AGENTS.md`（北极星 + 架构决策 + 开发规范 + 文档索引）、`CLAUDE.md`（指向 AGENTS.md）
  - `docs/ARCHITECTURE.md`（详细架构 + 调研结论 + 出处）
  - `docs/decisions/` ADR：0001 Hermes 为基座、0002 自研群讨论、0003 服务端7×24+idea中心、0004 多模态经 Hermes
  - 本 `CHANGELOG.md`
- **决策**：确定技术路线 = Hermes 为员工运行时基座 + 自研群讨论协作层(照 AutoGen) + 服务端 7×24 + idea 中心。详见 ADR 0001–0004。
- **feat(desktop)**: 聊天内联审批卡片——审批请求直接出现在对应会话，老板可当场批准/驳回（`apps/desktop`）。
- **feat(desktop)**: 聊天头部关联任务栏——会话正在驱动的任务以可点击 chip 展示（等级+状态），点击开任务详情。

<!-- 追加新条目到此区块顶部；发版时归档为带版本号的小节 -->
