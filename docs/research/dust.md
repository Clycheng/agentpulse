# Dust 调研：对 AgentPulse MVP 的借鉴建议

## 范围和结论

本文基于 Dust 公开文档、API Reference 和开源仓库信息，提炼其 agent / assistant 模型、工具边界、执行流和协作机制，并转成 AgentPulse 第一阶段“一人自媒体公司”MVP 的产品、架构、runtime 和任务模型建议。

核心结论：

1. Dust 的强项不是把 agent 做成“自动执行黑盒”，而是把 agent 配置、知识范围、工具权限、执行过程和人工确认做成可治理对象。
2. AgentPulse MVP 不应复制 Dust 的企业级 workspace / space / connector 全量体系，而应保留其思想：默认最小权限、工具分级授权、任务过程可见、外部动作可确认。
3. 对一人自媒体公司来说，第一阶段最重要的不是连接很多 SaaS，而是稳定跑通“目标输入 -> 任务拆解 -> 多员工协作 -> 内容产出 -> 用户确认 -> 归档复盘”的闭环。
4. Dust 的 `Run agent`、Triggers、Events streaming、Spaces 权限模型，对 AgentPulse 的后续 runtime 和多智能体协作有直接参考价值，但第一阶段需要做轻量化实现。

## 公开来源

- Dust 文档索引：<https://docs.dust.tt/llms.txt>
- 创建 agent：<https://docs.dust.tt/docs/quickstart-agent.md>
- agent 管理：<https://docs.dust.tt/docs/managing-agents.md>
- 工具能力：<https://docs.dust.tt/docs/tools.md>
- 工具管理和 space 级权限：<https://docs.dust.tt/docs/tools-management.md>
- 权限和访问控制：<https://docs.dust.tt/docs/access-controls-and-permissions.md>
- 数据源和 Spaces：<https://docs.dust.tt/docs/what-are-data-sources.md>、<https://docs.dust.tt/docs/data.md>
- Triggers：<https://docs.dust.tt/docs/triggers.md>
- Events streaming：<https://docs.dust.tt/reference/events.md>
- 对话 API 和用户确认：<https://docs.dust.tt/reference/post_api-v1-w-wid-assistant-conversations-cid-messages-mid-validate-action.md>、<https://docs.dust.tt/reference/post_api-v1-w-wid-assistant-conversations-cid-messages-mid-answer-question.md>
- 导出 / 导入 agent 配置：<https://docs.dust.tt/reference/get_api-v1-w-wid-assistant-agent-configurations-sid-export-yaml.md>、<https://docs.dust.tt/reference/post_api-v1-w-wid-assistant-agent-configurations-import.md>
- Dust GitHub 组织：<https://github.com/dust-tt>

## Dust 的 agent / assistant 模型

Dust 把 agent 定义为一个可配置的工作对象，而不是单次 prompt。一个 agent 至少包含：

- Instructions：行为准则、任务边界、工具使用策略。
- Tools & Knowledge：可用工具和知识来源，例如数据源检索、网页搜索、文件生成、图片生成、Agent Memory、Run agent、第三方工具。
- Handle、description、tags：让团队知道何时调用这个 agent。
- Publish / editors：谁能使用，谁能编辑。
- Triggers：可选的定时或 webhook 自动触发。

这套模型的关键点是：agent 的“能力”不是只写在提示词里，而是由配置、数据范围、工具授权和可见的管理入口共同决定。

对 AgentPulse 的启发：

- AI 员工需要有产品化字段，不应只存一段 system prompt。
- 员工卡片应同时展示“能做什么”“可用资料”“可用工具”“需要确认的动作”“最近任务表现”。
- 默认 3 个员工应各自有明确工具边界：
  - 老板助理：拆解目标、分配任务、汇总结果；不直接发布内容。
  - 内容策划：检索资料、生成选题、设计内容结构；不修改重要文件。
  - 运营执行：整理发布草稿、导出 Markdown / 表格、准备发布说明；不绕过用户确认发外部平台。

## 知识、数据源和权限边界

Dust 用 workspace、connections、spaces、data sources 组织知识：

- Workspace 是协作环境。
- Connections 负责连接外部系统并同步数据。
- Spaces 是数据和工具访问边界，可开放给所有成员，也可限制给部分用户。
- 用户只能基于自己有权限访问的 spaces 创建或使用相关 agent。

这说明 Dust 把“agent 能读什么”放在产品和权限层，而不是完全交给模型自行判断。

AgentPulse MVP 不需要实现企业级多用户权限，但需要建立等价的轻量边界：

| Dust 概念 | AgentPulse MVP 建议 |
| --- | --- |
| Workspace | Company Workspace，一人自媒体公司 |
| Space | 资料库分区，例如品牌资料、内容素材、客户反馈、私密资料 |
| Connection | 文件导入、网页链接、手动粘贴资料；外部 SaaS 连接延期 |
| Data source | Knowledge Source，支持 Markdown / 文本 / 表格的最小索引 |
| Agent access | 员工可见资料范围 |

MVP 建议：

- 第一阶段只做一个公司 workspace，但内部要有资料库分区字段，避免后续迁移困难。
- 默认资料分区：
  - `brand`: 品牌定位、语气、禁用词、目标人群。
  - `content`: 选题、历史内容、素材。
  - `operations`: 发布计划、复盘记录。
  - `private`: 私密资料，默认不给任何员工自动读取。
- 每次 agent 运行时记录实际检索了哪些资料，而不是只记录“有资料库权限”。

## 工具系统和权限分级

Dust 的工具分为默认能力和第三方能力。默认能力包括网页搜索、文件生成、图片生成、Agent Memory、Run agent 等；第三方工具如 Gmail、GitHub、Notion、Slack、Zendesk 等需要管理员配置，且有个人凭证或 workspace 凭证差异。

Dust 的经验值得借鉴：

- 工具要有明确名称和描述，否则 agent 不知道何时使用。
- 工具不应全部默认打开，数据源和工具越多，检索和决策质量可能越差。
- 第三方写操作必须通过授权和权限范围管理。

AgentPulse MVP 的工具分级建议：

| 级别 | 工具类型 | 示例 | 默认策略 |
| --- | --- | --- | --- |
| L0 只读上下文 | 读取任务、读取资料库、读取历史产出 | 搜索品牌资料、读取选题库 | 默认允许，但记录来源 |
| L1 本地生成 | 生成 Markdown、表格、图片提示词、发布草稿 | 输出一周内容计划 | 默认允许，产出进入待确认区 |
| L2 本地写入 | 保存文件、覆盖导出、更新资料库 | 保存 `content-plan.md` | 需要用户确认目标路径和变更摘要 |
| L3 外部读取 | 网页搜索、读取外部账号数据 | 搜索热点、读取 Notion | 首次授权确认，运行时记录 |
| L4 外部写入 | 发邮件、发布内容、创建日程、更新 CRM | 发布小红书、发送合作邮件 | MVP 不真实执行，只生成待确认草稿 |
| L5 高风险动作 | 删除、批量修改、计费、权限变更 | 删除资料、连接付费工具 | MVP 禁止执行 |

第一阶段建议只实现 L0-L2 的产品闭环，L3 可以先用公开网页搜索，L4-L5 只做设计和 UI 占位。

## 执行流、事件和可观测性

Dust 的 Events streaming 把一次对话中的关键状态拆成事件：用户消息、agent 消息、检索参数、工具运行、工具成功、token 流、agent 成功、agent 错误等。这对产品体验很重要，因为用户能看到 agent 在做什么，而不是只等最终答案。

AgentPulse 的 runtime 应把“任务执行”拆成可持久化事件：

```text
task_created
task_assigned
run_started
agent_thought_summarized
tool_selected
tool_started
tool_succeeded
tool_failed
handoff_requested
approval_requested
approval_resolved
artifact_created
run_succeeded
run_failed
```

注意：`agent_thought_summarized` 只展示面向用户的简要说明，不暴露完整 chain-of-thought。

MVP 前端不需要做复杂 DAG，先做 timeline 即可：

1. 老板助理理解目标并拆解任务。
2. 内容策划读取品牌资料和历史内容。
3. 内容策划生成选题和内容结构。
4. 运营执行整理为可发布草稿。
5. 系统请求用户确认是否保存、导出或后续发布。

## 多 agent 协作和 handoff

Dust 支持在对话中调用多个 agent，也有 `Run agent` 工具让一个 agent 委派另一个专门 agent。它的最佳实践强调“chain agents in a conversation”，也就是复杂任务可以由多个专业 agent 接力完成。

AgentPulse 应把这个机制产品化为“员工交接”，而不是让用户手动 `@agent`。

MVP handoff 规则：

- 老板助理是默认入口，负责目标澄清、任务拆解和结果汇总。
- 内容策划只接收明确的内容目标、受众、平台、时间范围和品牌约束。
- 运营执行只接收已确认的选题 / 草稿 / 发布计划，不负责重新定义战略。
- Reviewer 可以暂不作为独立员工，第一阶段由老板助理执行质量检查，避免员工过多。

handoff 数据结构建议：

```json
{
  "from_agent_id": "chief_assistant",
  "to_agent_id": "content_planner",
  "reason": "需要生成一周内容选题和结构",
  "input_summary": "账号定位、目标平台、时间范围、品牌语气",
  "expected_output": "7 条选题、每条包含标题、角度、脚本大纲、素材需求",
  "constraints": ["不得虚构用户案例", "不得直接发布"],
  "approval_required": false
}
```

## 用户确认节点

Dust API 中存在 action validation 和 answer question 等对话级交互能力，说明 agent 运行中可以暂停等待用户确认或补充信息。AgentPulse 的用户确认节点应比普通“确认弹窗”更结构化。

必须确认的动作：

- 发布或发送到外部平台。
- 发送邮件、私信、评论、客服回复。
- 修改、覆盖、删除本地重要文件。
- 写入或更新资料库中的长期记忆。
- 使用用户私密资料或外部账号凭证。
- 产生费用、调用付费 API、购买服务。

确认请求应包含：

- 动作类型：保存、发布、发送、连接、删除等。
- 执行者：哪个 AI 员工提出。
- 目标对象：文件路径、平台、账号、收件人、资料库分区。
- 变更摘要：新增、修改、删除什么。
- 风险说明：可能外部可见、可能覆盖文件、可能消耗额度。
- 用户选择：批准、拒绝、修改后再执行、只保存为草稿。

任务状态建议：

```text
running -> waiting_user -> running
running -> waiting_user -> cancelled
running -> waiting_user -> completed_as_draft
```

## 对 AgentPulse PRD 的建议

PRD 应吸收 Dust 的“可配置 agent + 可治理工具”思路，但用普通用户语言表达：

- 不说“创建 assistant configuration”，而说“雇一个 AI 员工”。
- 不说“data source / retrieval action”，而说“给员工开放哪些资料”。
- 不说“tool validation”，而说“重要动作需要老板确认”。
- 不说“conversation event stream”，而说“员工工作进度和操作记录”。

建议把 MVP 用户故事写成：

1. 作为一人自媒体创作者，我可以创建一个“内容工作室”，并获得 3 个默认 AI 员工。
2. 我可以输入“下周为小红书账号做内容计划”，系统自动拆成策划、撰写、运营整理任务。
3. 我可以看到每个员工正在读取什么资料、调用什么工具、产出什么内容。
4. 在系统保存重要文件或准备发布前，我必须能查看变更并选择批准、拒绝或改成草稿。

PRD 非目标：

- 不做真实多用户企业权限。
- 不做全量 SaaS connector marketplace。
- 不做自动发布到小红书、公众号、抖音等外部平台。
- 不做复杂 trigger 自动化。
- 不做通用 workflow builder。

## 对系统架构的建议

建议后端核心模型：

```text
Workspace
Agent
AgentPermission
KnowledgeSource
ToolDefinition
ToolGrant
Task
TaskAssignment
Run
RunEvent
Artifact
ApprovalRequest
```

关键设计：

- `Agent` 存角色配置，不存运行态。
- `Task` 表达业务任务，`Run` 表达一次执行尝试。
- `RunEvent` 作为实时 UI 和审计日志的共同来源。
- `ApprovalRequest` 独立建模，不塞进普通 message，便于状态机和权限检查。
- `Artifact` 记录产出文件、草稿、表格、计划等，不把结果只放在聊天消息里。

最小字段建议：

```json
{
  "agent": {
    "id": "content_planner",
    "name": "内容策划",
    "role": "把业务目标转成选题、内容结构和素材需求",
    "instructions": "...",
    "allowed_tool_ids": ["knowledge_search", "web_search", "artifact_create"],
    "knowledge_scope_ids": ["brand", "content"],
    "requires_approval_for": ["external_write", "file_overwrite", "memory_write"]
  }
}
```

## 对本地 runtime 的建议

Dust 的 Computer、文件生成、MCP 和第三方工具说明其 runtime 方向是让 agent 在受控环境里工作。AgentPulse 桌面端也需要本地 runtime，但第一阶段应保守：

- 每个 task 创建独立工作目录，例如 `.agentpulse/runs/<task_id>/`。
- runtime 只能在工作目录内生成文件，写出到用户指定位置必须走确认。
- 工具调用统一经过 `ToolBroker`，不要让 agent 直接调用系统命令或外部 API。
- 每个工具调用必须生成 `RunEvent`。
- 工具返回值分为用户可见摘要和内部结构化结果。
- 对外部账号、浏览器自动化、邮件发送保持接口占位，不在 MVP 默认开启。

runtime 执行流建议：

```text
API creates task
Runtime claims task
Runtime loads agent config and scoped knowledge
Agent plans next step
ToolBroker validates tool permission
Runtime emits tool events
ArtifactStore saves outputs
ApprovalManager pauses on risky action
Runtime resumes or stops based on user decision
API streams events to desktop
```

## 对任务模型的建议

Dust 以 conversation 为主线，AgentPulse 应以 task 为主线，因为普通用户更像在经营一家公司，而不是只聊天。

建议任务模型：

```text
Task
  - goal
  - owner_agent_id
  - status
  - priority
  - parent_task_id
  - stage
  - expected_artifact_type
  - approval_policy

Run
  - task_id
  - agent_id
  - status
  - started_at
  - ended_at
  - provider
  - model

RunEvent
  - run_id
  - type
  - actor
  - summary
  - payload
  - visibility
```

MVP 状态机建议沿用项目现有 README 的简化版，但增加审批结果：

```text
queued -> assigned -> running -> waiting_user -> running -> completed
                         |              |           |
                         v              v           v
                       failed        cancelled   completed_as_draft
```

任务拆解建议：

1. 用户目标先进入老板助理。
2. 老板助理生成 2-4 个子任务，不能超过 4 个，避免 MVP 复杂化。
3. 子任务按 stage 排序：策划 -> 草稿 -> 运营整理 -> 确认归档。
4. 每个子任务必须有负责人、输入、输出、验收标准和风险标记。
5. 高风险任务默认停在 `waiting_user`，不能自动进入外部执行。

## MVP 采用 / 延后清单

建议立即采用：

- agent 角色配置字段：说明、职责、工具、资料范围、禁止事项。
- 资料库分区和员工可见范围。
- 工具分级授权和确认节点。
- run event timeline。
- artifact 作为一等对象。
- 老板助理主导 handoff。

建议轻量实现：

- 网页搜索：只作为调研工具，结果必须标来源。
- Agent Memory：第一阶段改名为“公司记忆”，仅手动确认后写入。
- Triggers：仅保留模型字段，不开放自动执行。
- Run agent：内部 handoff，不暴露给用户配置。

建议延期：

- 企业级多用户、群组和 workspace 角色。
- 完整 connector 管理后台。
- 个人凭证和 workspace 凭证差异化。
- 真实外部发布、邮件发送、CRM 写入。
- 复杂 workflow builder 和 webhook 自动化。
- 第三方 MCP server marketplace。

## 风险和待验证项

风险：

- 如果只做聊天 UI，会丢掉 Dust 最值得借鉴的治理能力。
- 如果第一阶段工具过多，用户会难以理解权限边界，agent 也更容易误用资料。
- 如果不把审批建成状态机，后续外部写操作会变成安全债。
- 如果 artifact 不独立建模，内容计划、草稿、表格和复盘会散落在消息里，难以复用。

待验证：

- 一人自媒体用户是否能理解“员工可见资料范围”这一概念，还是需要用更生活化文案。
- 默认 3 个员工是否足够覆盖内容计划闭环，是否需要轻量 reviewer。
- 本地 runtime 的工作目录和导出确认是否会增加用户操作成本。
- 公开网页搜索结果如何做来源展示和可信度标记。
- 公司记忆写入应由谁发起：员工建议、老板助理汇总，还是用户手动保存。

## 需要交给其他成员继续处理

- PRD 细化：交给 agentpulse-product-strategist，把本文建议转成 `docs/prd.md` 的用户故事和验收标准。
- 系统数据模型：交给 agentpulse-system-architect，把本文模型转成 `docs/architecture.md` 的字段和 API 契约。
- runtime 工具协议：交给 agentpulse-runtime-engineer，补充 `docs/runtime.md` 的 ToolBroker、工作目录和权限实现方案。
- 桌面端体验：交给 agentpulse-desktop-engineer 和 agentpulse-ux-writer，把“员工、资料、任务、审批、产出”翻译成可操作 UI。
