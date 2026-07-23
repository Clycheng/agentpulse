# TD-11: 自媒体 AI 公司自动执行闭环

- 关联: [ADR 0010](../decisions/0010-durable-task-dispatch-and-company-tools.md)、[ADR 0006](../decisions/0006-group-discussion-v1-first-slice.md)、[ADR 0007](../decisions/0007-hermes-v0.18-interface-acp.md)
- 执行会话: **agentpulse**（需要真实 Hermes 与桌面端验收）

## 目标与边界

新 workspace 默认拥有小秘、内容策划、内容主笔、运营执行和“内容经营群”。群讨论收敛为带完整分工的 brief；老板点击一次“确认并启动”后，任务按依赖自动执行并在重启后恢复，最终交付结构化 `content_package_v1`。

首版不调用小红书、抖音、微信或邮件发送 API。普通交付自动完成；只有缺失信息、技术/业务风险动作和两次执行失败才打扰老板。

## 技术设计

### Brief 合同

`consensus_briefs.work_items_json` 保存 3-6 个 work item：`key`、`title`、`description`、`owner_agent_id`、`expected_output`、`output_type`、`depends_on_keys`、`final_delivery`。负责人必须属于讨论群，key 唯一、依赖存在且无环，并且只能有一个 `final_delivery=true, output_type=content_package_v1` 的最终项。

生成 prompt 提供群成员的 id、岗位和职责，要求严格 JSON。第一次解析/校验失败后允许一次 JSON 修复；第二次仍失败则继续讨论，不落残缺 brief。

### Launch 与持久状态

`POST /api/briefs/{id}/launch` 在同一事务内：检查 brief 状态与所有负责人 ready Hermes profile；确认 draft brief；创建唯一 task plan、根任务、子任务和依赖；为无前置依赖的任务各创建 attempt 1 queued Run。重复调用返回既有计划，rejected/superseded 禁止启动，legacy confirmed brief 可以补建计划。

`task_plans` 记录 brief、根任务、状态、`revision_count` 和完成时间；`task_dependencies` 记录有向边；tasks 增加 plan/item/交付合同字段和“待执行”状态；runs 增加 attempt、租约和开始时间，同一任务同一 attempt 唯一。

### 调度状态机

后台 worker 每 2 秒扫描；每 workspace 同时最多 2 个 running Run。领取采用 30 秒租约并每 10 秒续租。进程重启时，过期 running Run 标记 failed；若只执行过一次则建立 attempt 2，否则任务进入阻塞。

只有全部前置任务已完成的子任务可入队。任务成功后入队后继；根任务进度按子任务汇总，全部完成后根任务和计划自动完成归档。`POST /api/tasks/{id}/resume` 仅在任务没有活跃 Run 时接受老板补充信息并创建下一 attempt。

### Hermes 执行与公司工具

RunService 同时支持新建聊天 Run和执行数据库中已有 queued Run。任务 prompt 包含 brief、当前任务、前置产出、匹配资料、引用规则和目标交付 schema；每个任务 Run 必须带真实 `task_id`。

`RunContext.mcp_servers` 动态注入 `acp.schema.HttpMcpServer`。每 Run token 绑定 workspace/plan/task/run/agent，并设置短期过期时间。`/mcp/company-tools/` 暴露：

- `search_company_knowledge`
- `report_progress`
- `submit_output`
- `create_subtask`
- `request_support`
- `block_task`

工具只调用 AgentPulse 服务函数，不能直接接受任意 SQL。服务端验证 token、任务归属、当前负责人、依赖环、brief 范围和最多两次计划调整。

普通内容任务 prompt 明确禁止 terminal/shell 和下载脚本，检索应优先使用公司资料与网页工具。RunService 在持久化 tool call/result 后提交事务，使 10 秒独立心跳和 MCP 写请求不会被 SQLite 长事务阻塞。

### 产出与审批

中间任务允许 Markdown；未调用 `submit_output` 时以最终回复兜底。最终任务必须提交合法 `content_package_v1`：平台、受众、目标、排期内容、来源、假设；每条内容包含发布时间/顺序、类型、标题、开场钩子、正文或脚本、CTA、素材建议、来源引用。事实性内容引用资料 ID 或 URL，无法验证的信息进入 assumptions。

审批 resolver 每 250ms 查询数据库，50 秒后将 pending 审批置 expired 并 deny。resolve API 只写批准/拒绝决定；拒绝结果返回 Hermes 继续解释，不由 API 提前完成 Run。

### 桌面端

brief 卡片用自然语言列出负责人、交付和接力关系，只调用 launch。活跃计划每 3 秒刷新快照；快照包含任务、Run 摘要、审批、产出和阻塞原因，任务详情据此同步更新。最终内容包提供发布日历、逐篇预览、来源/未知项以及 Markdown 导出。

## Tech-Tasks

### TD-11-T1: 合同与 launch

实现双数据库 schema、brief work item 校验、计划模型、launch/confirm 幂等服务和查询/resume API。

验收: brief 非法负责人/重复 key/未知依赖/环/最终交付错误均拒绝；launch 原子、并发幂等，legacy confirmed 可补建，失败事务无部分任务。

### TD-11-T2: 调度与 Run 重构

实现数据库租约 worker、依赖接力、并发限制、重启恢复、一次重试、阻塞与根任务聚合；RunService 可执行既有 queued Run。

验收: 调度时钟可注入，依赖、租约、恢复、重试和两次调整上限均有确定性测试。

### TD-11-T3: 动态 MCP 与交付

固定 `mcp==1.26.0`、`sse-starlette==2.1.3`，ACP 注入动态 MCP；实现六个公司工具、token 权限和内容包校验/Markdown 导出。

验收: token 过期/越权、六工具、依赖环、范围保护、最终交付失败重试均有测试；真实 Hermes 能看到并调用工具。

### TD-11-T4: 默认团队与桌面端

workspace 创建四人团队和内容经营群，开启供给时创建 profile；桌面端接 launch/计划轮询/运行轨迹/内容包视图。

验收: 新 workspace 一次得到完整团队；desktop `tsc`/build 通过，桌面和移动窗口均无重叠，Markdown 可导出。

### TD-11-T5: 全链路验收

清除测试环境真实 key/profile 泄漏；跑全套 pytest、desktop build、三条架构 grep。真实桌面 UI 完成“小红书周计划”讨论、一次确认、自动接力、API 重启恢复和内容包交付，并保存截图证据。

TD-11 完成后按 TD-10 → TD-09 → TD-08 的顺序继续。

## 真实验收记录（2026-07-23）

- 新建 workspace 后四人团队与“内容经营群”自动出现；四个 Hermes profile 均完成供给。
- 群里讨论“小红书一周三篇健康餐计划”，生成三项依赖分工 brief。老板只点一次“确认并启动”。
- API 在首项执行期间真实重启；过期 Run 被回收，后续 attempt 恢复执行。策划和主笔分别交付 Markdown，运营通过动态 MCP 提交 `content_package_v1`；计划、根任务和三项子任务最终均为 completed/100%。
- 全套 API 测试：325 passed / 8 skipped；desktop TypeScript/Vite/Electron build 与 `pip check` 通过；三条架构边界 grep 通过。
- 桌面截图：[完整内容包抽屉](../images/td11-content-package-desktop.png)；390×844 移动截图：[响应式内容包抽屉](../images/td11-content-package-mobile.png)。移动视口 `scrollWidth=390`、drawer width=390，无横向裁切。
