# 0010. 数据库持久调度与 Hermes 动态公司工具

- 状态: 已接受
- 日期: 2026-07-23
- 决策者: 项目所有者

## 背景

AgentPulse 已能让多名员工讨论、生成共识 brief，并由 Hermes profile 执行一轮对话；但确认 brief 后仍由桌面端额外创建一个普通任务，任务之间没有依赖，也没有服务端常驻调度。Run 依附聊天请求，进程重启后不会恢复。Hermes 同时没有受约束的公司内部接口，无法安全地汇报进度、提交结构化产出或请求计划调整。

TD-11 要把第一个自媒体垂直场景做成完整闭环：老板只确认一次，服务端按 brief 的分工自动接力执行，最终交付可追踪的待发布内容包。

## 决策

1. PostgreSQL/SQLite 中的 `task_plans`、`tasks`、`task_dependencies` 和 `runs` 是执行状态的唯一真相源。后台 worker 只领取数据库中满足依赖的 queued Run，通过短租约和续租防止重复执行；进程重启后回收过期租约并按 attempt 上限重试。
2. 共识 brief 在确认前必须包含 3-6 个经校验的 work item。launch 在一个事务中确认 brief、创建根任务/子任务/依赖并入队首批任务；`brief_id UNIQUE` 提供跨请求和并发幂等。
3. Hermes 仍是唯一员工运行时，但不能直接写 AgentPulse 数据库。每个任务 Run 获得绑定 workspace/plan/task/run/agent 的短期签名 token，并在 ACP `new_session` 时用 `acp.schema.HttpMcpServer` 动态注入 `/mcp/company-tools/`。
4. 公司工具只暴露受约束的业务意图：检索资料、汇报进度、提交产出、创建范围内子任务、请求支援和阻塞任务。后端负责鉴权、归属、依赖环、调整次数和交付 schema 校验。
5. 普通中间产出允许 Markdown；最终任务只能用合法 `content_package_v1` 完成。没有调用 `submit_output` 时，RunService 可把最终回复保存为 Markdown 兜底，但不能把不合法的最终内容包标为完成。
6. 审批决定存数据库并由正在执行的 Run 轮询。HTTP API 只记录决定；RunService 决定 Run 的后续状态。该机制不再依赖单进程 Future 才能恢复。

## 理由

- 数据库租约让调度可观察、可恢复，也适配未来多进程部署；内存队列无法满足重启恢复。
- brief 是老板唯一一次拍板的合同，完整分工必须在拍板前出现，不能在确认后静默改变目标或成功标准。
- 动态 MCP token 把 Hermes 的权限缩小到单次 Run，无需修改 profile 配置，也避免把数据库凭证交给员工运行时。
- 将执行状态迁移留在 RunService，能避免审批 API 把仍在解释拒绝结果的 Run 提前标为完成。

## 后果

- `services/api` 增加常驻调度 worker、计划服务和 MCP streamable HTTP 服务；部署时必须保证 MCP URL 对 Hermes 子进程可达。
- 自动调整仅允许在已确认范围内执行，最多两次。范围变化必须回群讨论并生成 derived brief。
- TD-11 不调用任何真实发布/发送平台。对外动作在 TD-10 业务闸门和 TD-09 出站适配完成后接入。
- SQLite 继续用于测试和本地开发；两套初始化 schema 与 `ensure_column` 必须同步维护。
- RunService 在记录 tool call/result RunStep 后必须提交当前事务。否则 SQLite 长写事务会阻塞独立的租约心跳和 MCP 工具连接，导致仍在工作的 Run 被错误回收。
