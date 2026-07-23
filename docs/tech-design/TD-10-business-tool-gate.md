# TD-10：业务受控工具门（修订版）

- 关联：[ADR 0008](../decisions/0008-human-in-the-loop-approval-model.md)、[ADR 0010](../decisions/0010-durable-task-dispatch-and-company-tools.md)、[ADR 0011](../decisions/0011-controlled-business-actions.md)、[TD-07](TD-07-business-capability-catalog.md)、[TD-11](TD-11-autonomous-content-execution.md)
- 执行会话：**是**。Hermes、MCP 与真实桌面验证的 cwd 必须锚定 AgentPulse，遵守 ADR 0005。

## 目标与边界

让员工执行发邮件、发布、退款、改预算、提交薪酬或付款等业务动作时，AgentPulse 在真实外部调用前强制检查能力、凭证和 `risk_gate`，必要时等待老板批准。拒绝、超时或缺少配置时不得调用 provider，Hermes 获得结构化结果并正常解释。

v1 真实实现 `send_email`；其他五个工具只完成授权、审批和 provider registry 骨架，未配置时诚实返回错误。不做动态金额策略、真实社媒/支付集成、TD-09 渠道出站或 TD-11 brief 范围变更。

## 技术设计

### 1. MCP 与 Run 边界

- 保留 `/mcp/company-tools` 的任务专用 token 和六个内部工具，不向聊天 Run开放。
- 新增 `/mcp/business-tools` 及独立 `business_tool` token，绑定 workspace/conversation/run/agent/可选 task。服务端按 runs、agents、agent_capabilities 和 capability catalog 再次校验。
- RunService 在创建或接管数据库 Run 后查询员工已启用的 `business_tool` 能力，并把业务 MCP 追加到 `RunContext.mcp_servers`。任务调度器仍只负责注入 company tools。
- FastMCP 可以静态列出全部业务工具，但每次调用都按 token 和员工能力 fail closed；未授权工具永不落动作记录。

### 2. 凭证与能力

- `CapabilityDef.business_tool` 映射：`email_sending/send_email`、`social_content/publish_social_content`、`refund_processing/process_refund`、`ad_bidding/update_ad_bid`、`payroll_processing/submit_payroll`、`payment_execution/execute_payment`。
- `agent_credentials` 按 workspace/agent/name 唯一，保存 Fernet 密文和时间戳。密文 key 从 `auth_secret_key` 以固定 domain separator 派生，版本前缀用于后续轮换。
- `POST /agents/{id}/credentials` upsert 密文，并在一个事务中刷新所有依赖该凭证的能力；业务凭证不调用 `ProfileProvisioner.write_credentials`。DELETE 撤销并把依赖能力设回 `credential_missing`。
- API/桌面只显示每个 required credential 是否配置，不返回密文或明文。

### 3. 持久动作与审批

- `business_actions` 保存 run/task/conversation/agent、tool/capability、规范化参数与 hash、状态、approval、租约、attempt、provider/external id、结果和错误。状态为 `pending_approval/approved/executing/succeeded/rejected/expired/failed`。
- 对任务调用，dedupe scope 是 task + tool + args hash；对聊天调用是 run + tool + args hash。活动或成功记录用 partial unique index 防重复；拒绝、过期和终态失败允许重新申请。
- `business_tool_policies` 唯一绑定 workspace + agent + tool。`approval` 命中策略后直接 approved；`prohibited_auto` 忽略策略并拒绝 `scope=always`。
- MCP handler 创建动作和 `approvals.type=business_tool` 行后，每 250ms 轮询数据库。50 秒未决定则原子标记 approval/action expired；批准后等待 worker 结果。等待期间 Run 为 `waiting_user`，返回结果前恢复 `running`。
- 审批 API 只更新 approval、action 和可选长期策略，不调用 provider。聊天用待审批查询接口每秒恢复卡片；任务计划快照携带动作摘要。

### 4. BusinessActionWorker 与 Resend

- worker 每秒领取 approved 或租约过期的 executing 动作，租约 30 秒、最多两次 attempt；pending 动作只由审批决定或 50 秒超时收敛。
- Resend provider 用 `httpx` 调 `POST https://api.resend.com/emails`，发送 `Authorization`、JSON 和 `Idempotency-Key: business-action/<id>`；响应 id 持久保存。
- `send_email(to[], subject, body, channel_id?, reply_to?)` 仅支持纯文本和最多 50 个收件人。邮件渠道必须是 active、provider=resend、绑定当前员工，并包含 from_address/from_name；未指定 channel 时只能自动选中唯一匹配项。
- provider 不存在、渠道/凭证缺失或参数非法时在审批前返回明确错误，不创建审批。其他五个工具 v1 都走这一诚实失败路径。

## API 契约

- `POST /mcp/business-tools/`：per-Run Bearer token 的 MCP streamable HTTP 端点。
- `GET /api/business-tools`：工具、能力、风险、required credentials、provider 实现状态。
- `GET /api/business-actions`：按 agent/task/run/status 查询当前 workspace 审计记录。
- `GET /api/conversations/{id}/approvals?status=pending`：聊天审批恢复。
- `GET /api/agents/{id}/business-tool-policies`、`DELETE .../{tool}`：查看与撤销长期放行。
- `POST/DELETE /api/agents/{id}/credentials...`：保存/撤销凭证，仅返回配置状态。
- `POST /api/approvals/{id}/resolve`：`business_tool` 分支记录一次/长期批准或拒绝；付款等 `prohibited_auto` 禁止长期批准。

## Tech-Tasks

### TD-10-T1：持久门、密钥托管与邮件试点

实现双 schema、SQLite/PostgreSQL 约束升级、业务 token/MCP、凭证库、动作服务/worker、审批分支、Resend provider 和公开 API。单测覆盖密文、越权、风险分支、租约恢复、幂等和 provider 合约；守护 E2E 使用 `delivered@resend.dev`。

### TD-10-T2：桌面闭环与其余工具骨架

实现邮件渠道字段、员工凭证/策略/动作视图、聊天审批轮询与业务卡片；注册另外五个未配置工具。desktop lint/build 和桌面/移动截图验证拒绝、允许一次、长期允许与撤销。

## Definition of Done

- 业务密钥未出现在 Hermes profile、日志、审批 payload、RunStep 或 API 响应。
- 无审批/策略时 provider 调用次数为零；拒绝和超时不执行；批准后真实执行且重启/重试不重复。
- 聊天和任务 Run 都能使用业务门，且聊天永远拿不到 company tools。
- 未实现工具从不返回成功；`payment_execution` 从不长期放行。
- 全套 pytest、desktop lint/build、三条架构边界 grep 和真实 UI 截图通过；有 Resend key 时再声明真发信 E2E 通过。
