# 执行看板（唯一任务状态源 · AI 冷启动从这里知道"下一步干什么"）

> **任何 worker AI 开工流程**：读完 [README.md](README.md) 的"Worker AI 执行协议" → 在本文件挑「现在就做」里最靠前、且会话类型匹配的任务 → **开工第一个动作 = 把该任务状态改成 `🔵 进行中` 并 commit+push 本文件**（防止多 AI 撞车）→ 做完按协议验收/回填 → 状态改 `✅ 完成(commit)` 再 push。
> 任务状态**只在本文件标**（TD 文件里只有设计和验收标准，不标状态），避免两处漂移。

## ✅ 架构漂移已修复（2026-07-09）——TD-02-T5 完成，TD-03-T2/T3 解锁

`orchestration/discussion.py::run_discussion_round` 曾是死码（生产路由手写重复讨论循环 + `_llm_select_speaker`）。TD-02-T5 已把 `send_message`/`send_message_stream` 的讨论循环统一收回到 `run_discussion_round`（重写为 async 事件流），发言人选择唯一入口收敛到 `resolve_next_speaker`/`select_next_speaker`，路由层只注入"如何执行一轮 turn"和"如何调主持人 LLM"。三条禁止模式 grep 全干净，新增生产路径断言测试。**TD-03-T2 及以后现可开工。**

## 现在就做（按此顺序领）

| 序 | 任务 | 一句话 | 会话要求 | 状态 |
|---|---|---|---|---|
| 1 | [TD-06-T2](TD-06-agent-self-evolution.md)(主动能力升级申请) | approvals.payload_json schema done; next: ProfileProvisioner add_capability/reload_gateway | **agentpulse** | 🔵 进行中(step 1/6) |
| 2 | TD-08-T3 **剩余 UI 收尾**(空闲思考开关设置项，可选) | 前端 + IdleThinkService 均已完成✅ | 否（前端）| ⚪ |

## 有依赖，等前置完成后做

| 任务 | 等什么 | 会话要求 |
|---|---|---|
| TD-06-T3(成长轨迹 UI) | TD-06-T1✅ + TD-06-T2；`GET /api/agents/{id}/skills` 已就绪✅ | 否（前端）/ agentpulse（验 SOUL） |
| TD-09-T3 **剩余**(ChannelReply 把回复发回原渠道 + 微信/widget 适配器) | **agentpulse**（需 Hermes 集成验证）|
| TD-09-T3(ChannelReply + 网页 Widget) | TD-09-T2✅ — deps met, ready to move | 否 |

## 已完成

| 任务 | commit | 备注 |
|---|---|---|
| **TD-03-T4 审批 suspend/resume 闭环**：`runner._make_approval_resolver`→ACP `request_permission` 拦截→建 approval+waiting_user→Future 挂起→`/approvals/{id}/resolve` 调 `resolve_pending` 唤醒→续跑或驳回；SOUL 铁律增强 clarify 指令；3 新单测 + 210 全过零回归 | 2026-07-13 | 代码无需 Hermes 即可测；批准后 run 续跑、驳回后 run 结束、超时→failed |
| **TD-01-T2 端到端手测**：4/5 步 API 级验证通过（brief 创建→拒绝→确认→建任务、门控拒绝），1 步 xfail（DeepSeek SOCKS 代理环境问题，不影响业务流程） | 2026-07-13 | 新增 `test_e2e_brief_lifecycle.py`（4 passed + 1 xfailed）；TD-01-T1/T1b 之前已实现；**brief 全链路已验证** |
| **TD-03-T5 员工↔profile 生命周期（自动供给）**：`build_provisioner_from_settings` 按 `hermes_provisioning` 选 LocalHermes/RecordOnly；`supply.provision` 走真 provisioner——建 profile+写 SOUL(角色/职责/铁律)+配 model(`deepseek/deepseek-v4-flash`)+toolsets+装 skills+写 DeepSeek key→回填 `hermes_profile`/status=ready；profile 名合法化(lowercase alnum)。**真机 e2e 过**：provision→真 Hermes profile(model+SOUL+key)可跑，spec ready。招人→真员工全自动 | 2026-07-10(见 CHANGELOG) | 配 `AGENTPULSE_HERMES_PROVISIONING=true` 开启 |
| **TD-03-T3 后半：热路径切换**：`send_message_stream` 的 DM + 群讨论两条路径都改成经 `runner.stream_agent_run` 调 Hermes（员工有 ready profile 时），否则回退临时 DeepSeek——**零回归**（现有 205 测试全过，无 profile 的 agent 走原路径）；`runner` 加 `resolve_hermes_profile` + 流式 `stream_agent_run`；approval_required 走 deny-by-default + SSE `approval` 事件。**真机 e2e 过**：DM 经 `/messages/stream` → runs(provider=hermes,completed)+run_steps(message,final)+agent 消息 "OK" 落库 | 2026-07-10(见 CHANGELOG) | 审批 suspend/resume 与自动供给留 T4/T5 |
| **TD-03-T3 写半：RunService**（`runtime/runner.py`）：`start_run` 消费 backend 事件流→按 TD-03-T1 生命周期建 run/转状态、聚合 thinking/message 各落 1 run_step、tool 逐条落、结果写回 agent message；**真机 e2e 过**（RunService→HermesBackend→真 Hermes→run_steps+message"OK"）。2 常开(fake backend)+1 guarded e2e；全套 205 过 | 2026-07-10(见 CHANGELOG) | 剩热路径切换+审批闭环 |
| **TD-03-T2 HermesBackend（ACP 传输）**：`runtime/hermes_client.py`——起 `hermes --profile <p> acp` 子进程、用 `agent-client-protocol==0.9.0` 走 ACP、把 session_update 流映射成 `AgentEvent`(message/thinking/tool_call/tool_result/approval_required/usage/final)；approval→选 offered option；fs 读写限制在 workdir 内(ADR 0005)。**真机 e2e 实测通过**：agentpulse profile 跑"reply OK"→收到 thinking 流+message"OK"+usage+final。3 e2e 单测(HERMES_E2E=1) + 2 常开安全测；全套 203 过 | 2026-07-10(见 CHANGELOG) | agent-client-protocol 入 requirements |
| **Hermes 接入地基**：本机 Hermes v0.18.2 验证——真实 DeepSeek key 经 isolated profile 一次性跑通("OK")；**发现 REST /v1/runs 已不存在**→ 新增 [ADR 0007](../decisions/0007-hermes-v0.18-interface-acp.md)(改用 ACP 传输、作废端口模型)；实现 **TD-04-T6 `LocalHermesProvisioner`**(真 CLI 建/配/删 profile，强制绝对 workdir)+ 2 always-on 安全单测 + 1 guarded e2e(HERMES_E2E=1 实测过) | 2026-07-10(见 CHANGELOG) | 201 测试全过；DeepSeek key 存 gitignored .env |
| Idea 中心前端（TD-08-T3 前端半）：桌面端新增「想法」视图（侧栏入口 + 摘要 + 分类过滤 + 想法卡片 + 接受/忽略/转为讨论）；转为讨论走 `/api/ideas/{id}/convert` 后自动重载并跳进新群。接 TD-08-T1 API | 2026-07-10(见 CHANGELOG) | 纯前端；tsc 无错、浏览器实测 seed 2 条→列出→转讨论跳转全走通、无 console 报错。idle 自动生成 idea 仍等 Hermes(TD-08-T2) |
| TD-07-T2 前端半（创建员工"按职位快速配置"）：CreateAgentModal 拉 `/api/role-bundles` 渲染 12 个角色芯片，点选自动填能力+名称+部门 + "已选 N 项能力"摘要；顺手把该弹窗残留的写死紫色能力芯片改成 teal token。**TD-07-T2 全部完成** | 2026-07-10(见 CHANGELOG) | 纯前端；tsc 无错、浏览器实测选角色自动配好、无 console 报错 |
| 渠道管理前端（TD-09-T3 前端半）：桌面端新增「渠道」视图（侧栏入口 + 创建表单 + 列表卡片 + webhook URL 复制 + 启停），接 TD-09-T2 的 `/api/channels`；tsc 通过、浏览器实测创建/列出/复制/停用全走通 | 2026-07-10(见 CHANGELOG) | 纯前端；tsc 无错、无 console 报错 |
| TD-07-T2 API 半：`GET /api/role-bundles`(列 12 预配角色+resolved 效果) + `POST /api/agents` 新增 `role_spec.role_bundle_key`(展开并入 capability_keys) | 2026-07-10(见 CHANGELOG) | 199 测试全过；只差"按职位选"前端 UI |
| TD-07-T1(业务能力目录扩展)：`capability_catalog.py` 补 31 个业务能力(客服/内容/数据/HR/法务/财务/项目) + `ROLE_BUNDLES`(12 预配角色) + `get_role_bundle`/`list_role_bundles`；对齐 social_content 与真相源；10 新单测(条目合法性/MCP 必带 creds/角色 bundle key 全在 catalog/解析不报错) | 2026-07-10(见 CHANGELOG) | 纯常量+单测；194 测试全过；TD-07-T2 解锁 |
| TD-09-T2(渠道管理 API + 公开 webhook 端点)：`services/channels.py`(CRUD/stats/HMAC 验签/token) + `routes/channels.py`(/api/channels 认证 CRUD + 软删) + `routes/webhooks.py`(公开 `/webhooks/{type}/{token}` 验签→route_inbound→尽力触发 agent 回复) + email 适配器；8 单测(CRUD/webhook 入站/去重/验签/未知或停用 token/不支持类型/mock LLM 触发回复) | 2026-07-10(见 CHANGELOG) | 纯 API，可 curl 验证；184 测试全过；TD-09-T3 解锁 |
| TD-09-T1(channel_configs 表 + Router 核心)：`channel_configs` 表 + `conversations.source_channel/external_conversation_id` + `messages.external_message_id`(双 schema+迁移)；`app/channels/`(router `route_inbound`/`find_or_create_conversation`/dedup + generic 适配器 + 注册表)；6 单测(归一化/dedup/按外部用户归会话/固定群路由/自定义路径) | 2026-07-10(见 CHANGELOG) | 纯数据+适配器；176 测试全过；TD-09-T2 解锁 |
| TD-08-T1(ideas 表 + API)：`ideas` 表 + `agent_specs` 3 列 + `conversations.idea_id`(双 schema+迁移)；`schemas/idea.py` + `services/ideas.py`(CRUD/review/convert/idle-thinking) + `routes/ideas.py`(GET/POST/review/convert + PATCH idle-thinking)；8 单测(CRUD/流转/CHECK/convert 建会话并回链 idea_id) | 2026-07-10(见 CHANGELOG) | 纯数据+API；170 测试全过；TD-08-T2 仍等 Hermes |
| TD-03-T1(Run/RunStep 数据模型)：runs 扩 task_id/hermes_profile_id/hermes_run_id/workdir，新增 run_steps 表，approvals 加 run_id+type，agents 加 hermes_gateway_port(两 schema 都改+ensure_column 迁移)；新增 `runtime/runs.py` 生命周期状态机(queued→running→waiting_user/clarify→completed/failed) + 13 单测 | 2026-07-09(见 CHANGELOG) | 纯 schema+lifecycle；162 测试全过；解锁 TD-03-T2 |
| TD-02-T5(路由归位)：send_message/stream 讨论循环统一收回 run_discussion_round(改为 async 事件流)，删除路由层 `_llm_select_speaker`/`_extract_mention_simple`/`_build_discussion_context`，发言人选择收敛到 `resolve_next_speaker`；+8 编排单测 +1 生产路径断言测试 | 2026-07-09(见 CHANGELOG) | 三条 grep 全干净；149 测试全过；解锁 TD-03-T2/T3 |
| 架构复核：发现 TD-02 路由层重复实现漂移，新增 TD-02-T5 阻塞项 | 2026-07-08(见 CHANGELOG) | 纯发现+文档纠正，代码未改 |
| 验证事实回填 DATA-MODEL/TD-03/04/05/ARCHITECTURE + workdir 架构决策 + 看板重建 | 2026-07-08(见 CHANGELOG) | |
| TD-02 T1–T4(多 agent 讨论编排+372 行测试) + SSE 流式 | `b61005e` | ⚠️ 编排函数本身正确，但**未被路由实际调用**——见上方漂移说明，需 TD-02-T5 完成整合 |
| 一键启动脚本 `npm run dev` | `4ec9e96` |
| SQLite 20 个失败测试修复 | `141592f` |
| TD-04-T5(API+前端最小闭环) | `c4d1e3e` |
| TD-04-T4(供给编排+状态机) | `81af20d` |
| TD-04-T3(role_spec 起草+SOUL 生成) | `f55d0b1` |
| TD-04-T2(ProfileProvisioner+RecordOnly) | `0ed930d` |
| TD-04-T1(agent_specs/capabilities 建表+DTO) | `cd52af8` |
| TD-05-T1(capability_catalog) | `dd595de` |
| TD-01-T1b(TaskOut consensus_brief_id) | `0c745b0` |
| TD-01-T1(讨论态接线) | `a9b2b06` |
| PLAYBOOK V1–V7 验证报告 | `19c209b` |
| 群讨论第一片(ADR 0006 实现) | `c2054bf` |
| 全部设计文档(架构/DATA-MODEL/TD-01~05/剧本/本看板) | 见 CHANGELOG 2026-07-03~08 |

## 维护规则
- 领任务/完成任务的 AI **必须**更新本文件并 push（这就是认领锁）。
- 新增 TD/task 时同步登记到上面两张表。
- **链接必须指向真实存在的文件**；完成状态必须带真实 commit 号，不写"待提交"。
- 状态含义：⚪ 待领 / 🔵 进行中(注明领取方+日期) / ✅ 完成(注明 commit) / ⛔ 阻塞(注明等什么)。
