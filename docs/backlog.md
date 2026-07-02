# AgentPulse 第一阶段 Backlog

本文把“一人自媒体公司”MVP 拆成可执行、可验收、可排期的 Epic / Story / Task，并给出 issue 分配矩阵。状态建议遵循 `docs/workflow.md`：需求不清保持 Backlog，满足研发启动门槛后进入 Todo。

## 阶段计划

| Stage   | 目标                                                  | 并行性                                                         | 状态建议                 |
| ------- | ----------------------------------------------------- | -------------------------------------------------------------- | ------------------------ |
| Stage 1 | 先完成无上游 issue 依赖的 MVP PRD                     | 不并行触发依赖 PRD 的任务                                      | Todo                     |
| Stage 2 | MVP 取舍、agent 体系、UX 文案基线                     | PRD 草案通过后可并行草拟；最终验收等待 PRD 确认                | Backlog，等 Stage 1 验收 |
| Stage 3 | 系统架构、接口契约、本地 runtime 设计                 | architecture 依赖 PRD 和 agent-system；runtime design 依赖架构 | Backlog                  |
| Stage 4 | 后端核心模型、桌面工作台骨架、官网表达                | 后端、桌面、官网可并行；桌面需跟随后端接口契约                 | Backlog                  |
| Stage 5 | 接入任务流、运行日志、用户确认节点、本地 runtime 原型 | API 和桌面强依赖；runtime 可先做接口原型                       | Backlog                  |
| Stage 6 | QA、风险修复、复盘、下一轮 backlog                    | 严格等待 Stage 4/5 交付                                        | Backlog                  |

真实创建子 issue 时，Stage 1 只放“无上游 issue 依赖、可以立即验收”的任务。依赖 PRD、agent-system 或 architecture 的任务默认进入后续 Stage / Backlog；只有在 issue 描述中明确写出“可并行草拟，但最终验收等待上游产出”时，才允许提前创建为同阶段或相邻阶段的草拟任务。

## Epic 1：产品范围和用户路径

目标：明确第一阶段只做“一人自媒体公司”从目标输入到内容计划产出的闭环。

### Story 1.1：一人自媒体公司 MVP PRD

- 背景：README 已定义 MVP 方向，但还需要可执行 PRD。
- 目标：明确目标用户、核心场景、成功标准、非目标。
- 范围：公司工作区、3 个 AI 员工、内容目标输入、任务拆解、进度展示、用户确认节点。
- 不做：CRM、财务、客服、跨行业模板、真实发布平台接入。
- 验收标准：
  - 输出 `docs/prd.md`。
  - 至少包含 3 条用户故事和 1 条完整端到端流程。
  - Founder 能判断哪些需求延期。
- 依赖：README、现有项目背景。
- 风险：范围膨胀。
- 建议 assignee：agentpulse-product-strategist。
- 状态建议：Stage 1 / Todo。

### Story 1.2：MVP 取舍和不做清单

- 背景：多智能体平台容易过早做大。
- 目标：明确第一阶段的硬边界。
- 范围：必须做、可以假实现、明确不做、后续阶段再做。
- 验收标准：
  - 输出 `docs/mvp.md` 或 PRD 中独立章节。
  - 每个延期项有原因。
  - 高风险外部动作都有确认策略。
- 依赖：Story 1.1。
- 风险：Founder 未确认导致研发返工。
- 建议 assignee：agentpulse-founder。
- 状态建议：Stage 2 / Backlog；可在 PRD 草案后并行草拟，最终验收等待 PRD 确认。

## Epic 2：多智能体协作和审批机制

目标：把“AI 公司 / AI 员工 / 任务协作”设计成普通用户能理解、研发能实现的模型。

### Story 2.1：AI 员工角色和任务 handoff 设计

- 背景：MVP 需要默认 3 个 AI 员工。
- 目标：定义老板助理、内容策划、运营执行的职责、输入、输出、handoff。
- 范围：角色模板、任务拆解规则、结果交接、失败处理。
- 验收标准：
  - 输出 `docs/agent-system.md`。
  - 每个 AI 员工有职责、能力边界、示例任务、不可做事项。
  - 定义从用户目标到子任务的拆解流程。
- 依赖：Story 1.1。
- 风险：角色过多或职责重叠。
- 建议 assignee：agentpulse-agent-architect。
- 状态建议：Stage 2 / Backlog；可在 PRD 草案后并行草拟，最终验收等待 PRD 确认。

### Story 2.2：用户确认节点和风险边界

- 背景：发布内容、发送邮件、修改重要文件等动作必须可控。
- 目标：定义高风险动作的确认策略。
- 范围：确认触发条件、确认 UI 信息、允许/拒绝/修改后的状态流转。
- 验收标准：
  - `docs/agent-system.md` 或独立章节列出高风险动作分类。
  - 每类动作都有确认前展示信息和用户选择。
  - 明确第一阶段不执行真实外部发布，只生成待确认草稿。
- 依赖：Story 2.1。
- 风险：确认节点缺失会影响用户信任。
- 建议 assignee：agentpulse-agent-architect。
- 状态建议：Stage 2 / Backlog；依赖 agent-system 的角色和 handoff 边界。

## Epic 3：系统架构和接口契约

目标：为后端、桌面端、本地 runtime 建立共同接口，不让实现各自发散。

### Story 3.1：核心数据模型和状态机

- 背景：README 只有建议模块，需要可落地模型。
- 目标：定义 workspace、agent、task、run、message、tool、memory 的第一阶段字段。
- 范围：字段、状态机、关系、最小持久化策略。
- 验收标准：
  - 输出 `docs/architecture.md`。
  - 包含任务状态机和 run/message 事件关系。
  - 明确哪些字段第一阶段可内存实现，哪些需要持久化。
- 依赖：Story 1.1、Story 2.1。
- 风险：模型不稳定会导致前后端返工。
- 建议 assignee：agentpulse-system-architect。
- 状态建议：Stage 3 / Backlog；依赖 PRD 和 agent-system。

### Story 3.2：API 和实时事件契约

- 背景：桌面工作台需要读取任务、员工和日志。
- 目标：定义 REST API 和 WebSocket/SSE 事件契约。
- 范围：workspace 初始化、agent 列表、task CRUD、run events、确认节点。
- 验收标准：
  - `docs/architecture.md` 中包含接口清单和示例 payload。
  - 桌面端可据此实现 mock 或真实 API client。
  - 确认节点有 request/approve/reject 状态。
- 依赖：Story 3.1。
- 风险：实时事件过早复杂化。
- 建议 assignee：agentpulse-system-architect。
- 状态建议：Stage 3 / Backlog；依赖核心数据模型和状态机。

## Epic 4：后端 MVP

目标：实现支撑桌面工作台的最小 FastAPI 后端。

### Story 4.1：FastAPI 领域模块骨架

- 背景：后端当前只有健康检查。
- 目标：建立 workspace、agent、task、run、message 的模块结构。
- 范围：路由、schema、service 层、内存存储或轻量持久化占位。
- 验收标准：
  - `services/api/app` 下有清晰模块拆分。
  - 保留 `/api/health`。
  - 新增基础测试。
  - `npm run test:api` 通过。
- 依赖：Story 3.1。
- 风险：未确定数据库前避免过度封装。
- 建议 assignee：agentpulse-backend-engineer。
- 状态建议：Stage 4 / Backlog。

### Story 4.2：任务和运行事件 API

- 背景：桌面端需要展示任务看板和执行日志。
- 目标：实现任务创建、状态更新、run event 追加和查询。
- 范围：REST API 优先；实时流可以先提供模拟或轮询接口。
- 验收标准：
  - 可创建一个内容目标任务。
  - 可生成/查询子任务和 run events。
  - 测试覆盖正常流和非法状态流转。
- 依赖：Story 4.1、Story 3.2。
- 风险：状态机和前端展示不一致。
- 建议 assignee：agentpulse-backend-engineer。
- 状态建议：Stage 5 / Backlog。

## Epic 5：桌面工作台 MVP

目标：让用户在桌面端完成“一人自媒体公司”的任务闭环。

### Story 5.1：桌面工作台信息架构

- 背景：桌面端是主工作台，需要从一开始承载公司/员工/任务概念。
- 目标：实现工作台基础布局。
- 范围：侧边导航、公司概览、AI 员工列表、任务看板、任务详情入口。
- 验收标准：
  - `apps/desktop` 首屏不是营销页，而是可操作工作台。
  - 能看到 3 个默认 AI 员工。
  - 能看到任务状态分组。
  - `npm run lint` 对 desktop 相关类型检查通过。
- 依赖：Story 1.1、Story 2.1。
- 风险：界面过度装饰，降低工具效率。
- 建议 assignee：agentpulse-desktop-engineer。
- 状态建议：Stage 4 / Backlog。

### Story 5.2：内容目标输入和任务详情

- 背景：MVP 需要用户提交目标并看见拆解结果。
- 目标：实现目标输入、任务详情、执行日志和产出展示。
- 范围：目标表单、拆解结果列表、日志 timeline、Markdown 产出区。
- 验收标准：
  - 用户能输入“为小红书账号生成一周内容计划”。
  - 系统展示拆解后的子任务和负责人。
  - 任务详情展示日志、当前状态、最终产出。
  - 外部发布动作只显示“待确认”，不真实发布。
- 依赖：Story 4.2；可先用 mock。
- 风险：API 未完成时需保持 mock 与契约一致。
- 建议 assignee：agentpulse-desktop-engineer。
- 状态建议：Stage 5 / Backlog。

## Epic 6：官网和普通用户表达

目标：让外部用户理解 AgentPulse 不是聊天机器人，而是 AI 公司工作台。

### Story 6.1：官网首屏和场景表达

- 背景：官网是早期用户理解产品的入口。
- 目标：围绕“一人自媒体公司”重写首页表达。
- 范围：首屏、核心场景、AI 员工、任务闭环、早期访问 CTA。
- 验收标准：
  - `apps/web` 首屏清楚表达产品对象和 MVP 场景。
  - 展示真实产品概念：公司、员工、任务、审批、产出。
  - 不夸大成全行业自动化平台。
  - `npm run build:web` 通过。
- 依赖：Story 1.1、Story 6.2。
- 风险：营销文案与产品实际能力不一致。
- 建议 assignee：agentpulse-web-engineer。
- 状态建议：Stage 4 / Backlog。

### Story 6.2：新手引导和空状态文案

- 背景：普通用户不理解 agent、run、workflow 等技术词。
- 目标：把技术概念翻译成公司工作语言。
- 范围：员工、任务、审批、资料库、复盘的界面文案。
- 验收标准：
  - 输出 `docs/ux-writing.md`。
  - 为桌面端关键空状态和按钮提供文案。
  - 不直接暴露 prompt、JSON schema、workflow DAG 等术语。
- 依赖：Story 1.1、Story 2.1。
- 风险：文案过拟人导致能力误解。
- 建议 assignee：agentpulse-ux-writer。
- 状态建议：Stage 2 / Backlog；可在 PRD 草案后并行草拟，最终验收等待 PRD 和 agent-system。

## Epic 7：本地 runtime 和工具边界

目标：为未来本地文件、浏览器、导出工具留出接口，但第一阶段不追求完整自动化。

### Story 7.1：本地 runtime 原型设计

- 背景：桌面端未来需要本地执行环境。
- 目标：定义任务工作目录、工具接口、provider 接入边界。
- 范围：设计文档优先，代码只做最小占位。
- 验收标准：
  - 输出 `docs/runtime.md`。
  - 说明文件读写、网页搜索、Markdown/表格导出的权限边界。
  - 标注哪些工具第一阶段只 mock。
- 依赖：Story 3.1、Story 3.2。
- 风险：过早实现真实工具会带来安全和权限问题。
- 建议 assignee：agentpulse-runtime-engineer。
- 状态建议：Stage 3 / Backlog。

### Story 7.2：导出和资料库最小闭环

- 背景：内容计划需要可保存、可复用。
- 目标：定义并实现 Markdown 产出保存和资料库占位。
- 范围：本地 Markdown 导出、任务结果归档、资料库入口占位。
- 验收标准：
  - 用户能看到任务产出保存位置或下载入口。
  - 重要文件修改前有确认节点。
  - 资料库第一阶段可以只展示占位和后续计划。
- 依赖：Story 5.2、Story 7.1。
- 风险：文件权限和用户确认不足。
- 建议 assignee：agentpulse-runtime-engineer。
- 状态建议：Stage 5 / Backlog。

## Epic 8：QA 和复盘

目标：确保每轮交付可验证、风险可追踪、问题能回到 backlog。

### Story 8.1：第一阶段 QA 验收清单

- 背景：MVP 涉及 web、desktop、api、runtime，容易缺少统一验收。
- 目标：建立端到端 QA 清单。
- 范围：命令验证、手动流程、风险检查、确认节点检查。
- 验收标准：
  - 输出 QA 报告或 `docs/qa-checklist.md`。
  - 覆盖 `npm run lint`、`npm run build`、`npm run test:api`。
  - 覆盖一人自媒体公司端到端任务流程。
- 依赖：Stage 2/3 研发交付。
- 风险：没有真实 API 或 runtime 时需定义 mock 验收标准。
- 建议 assignee：agentpulse-qa-reviewer。
- 状态建议：Stage 6 / Backlog。

### Story 8.2：复盘和下一轮 backlog

- 背景：项目目标是形成闭环，而不是一次性产出。
- 目标：总结范围、质量、协作、风险和流程问题。
- 范围：已完成项、未完成项、返工原因、下一轮 issue。
- 验收标准：
  - 输出复盘评论或文档。
  - 至少新增或建议下一轮 backlog 项。
  - 明确继续、暂停或取消的事项。
- 依赖：Story 8.1。
- 风险：复盘只总结不转行动。
- 建议 assignee：agentpulse-program-manager。
- 状态建议：Stage 6 / Backlog。

## Issue 分配矩阵

| 建议 issue                                      | Stage | 优先级 | 建议 assignee                  | 初始状态 | 依赖                                           |
| ----------------------------------------------- | ----- | ------ | ------------------------------ | -------- | ---------------------------------------------- |
| AGENT-MVP-PRD：一人自媒体公司 MVP PRD          | 1     | High   | agentpulse-product-strategist | Todo     | README                                         |
| AGENT-MVP-SCOPE：MVP 取舍和不做清单            | 2     | High   | agentpulse-founder            | Backlog  | AGENT-MVP-PRD                                 |
| AGENT-AGENT-SYSTEM：AI 员工角色和 handoff      | 2     | High   | agentpulse-agent-architect    | Backlog  | AGENT-MVP-PRD                                 |
| AGENT-UX-WRITING：新手引导和空状态文案         | 2     | Medium | agentpulse-ux-writer          | Backlog  | AGENT-MVP-PRD、AGENT-AGENT-SYSTEM            |
| AGENT-ARCH：核心模型、状态机、接口契约         | 3     | High   | agentpulse-system-architect   | Backlog  | AGENT-MVP-PRD、AGENT-AGENT-SYSTEM            |
| AGENT-RUNTIME-DESIGN：本地 runtime 原型设计    | 3     | Medium | agentpulse-runtime-engineer   | Backlog  | AGENT-ARCH                                    |
| AGENT-API-CORE：FastAPI 领域模块骨架           | 4     | High   | agentpulse-backend-engineer   | Backlog  | AGENT-ARCH                                    |
| AGENT-DESKTOP-SHELL：桌面工作台信息架构        | 4     | High   | agentpulse-desktop-engineer   | Backlog  | AGENT-MVP-PRD、AGENT-AGENT-SYSTEM            |
| AGENT-WEB-HOME：官网首屏和场景表达             | 4     | Medium | agentpulse-web-engineer       | Backlog  | AGENT-MVP-PRD、AGENT-UX-WRITING              |
| AGENT-API-TASKS：任务和运行事件 API            | 5     | High   | agentpulse-backend-engineer   | Backlog  | AGENT-API-CORE                                |
| AGENT-DESKTOP-TASKFLOW：内容目标输入和任务详情 | 5     | High   | agentpulse-desktop-engineer   | Backlog  | AGENT-DESKTOP-SHELL、AGENT-API-TASKS         |
| AGENT-RUNTIME-EXPORT：导出和资料库最小闭环     | 5     | Medium | agentpulse-runtime-engineer   | Backlog  | AGENT-DESKTOP-TASKFLOW、AGENT-RUNTIME-DESIGN |
| AGENT-QA-MVP：第一阶段 QA 验收清单             | 6     | High   | agentpulse-qa-reviewer        | Backlog  | Stage 4/5 交付                                 |
| AGENT-RETRO：复盘和下一轮 backlog              | 6     | Medium | agentpulse-program-manager    | Backlog  | AGENT-QA-MVP                                  |

## 并行和等待关系

- Stage 1 只启动 AGENT-MVP-PRD；这是后续产品、agent、架构、研发任务的共同上游。
- Stage 2 中，MVP scope、agent-system、ux-writing 可在 PRD 草案后并行草拟，但最终验收必须等待 PRD 确认。
- Stage 3 中，architecture 必须等待 PRD 和 agent-system；runtime design 必须等待 architecture。
- Stage 4 中，API core、desktop shell、web home 可以并行；desktop shell 可先用 mock，但必须跟随 architecture 的接口命名。
- Stage 5 中，API tasks 必须先于 desktop taskflow 的真实接口接入；desktop 可先实现 mock 流程。
- Stage 6 必须等待可运行交付，不提前开始最终验收。

## 创建子 issue 的建议

如果在 Multica 中创建真实子 issue，建议按阶段使用 `--stage`：

- 创建前阻塞检查：先运行 `git status --short`。如果存在非 `docs/` 工作树改动，必须确认归属；不能在 INT-10 中静默接受，也不能擅自回滚。
- Stage 1：只创建无上游 issue 依赖的任务为 `--stage 1 --status todo`。当前建议只启动 AGENT-MVP-PRD。
- Stage 2：依赖 PRD 的任务创建为 `--stage 2 --status backlog`。只有描述明确写出“可并行草拟，但最终验收等待 PRD”时，才可在 PRD 草案形成后提升。
- Stage 3：依赖 PRD 和 agent-system 的 architecture/runtime 任务创建为 `--stage 3 --status backlog`。
- Stage 4：实现类骨架任务创建为 `--stage 4 --status backlog`，等 Stage 3 架构契约通过后再提升。
- Stage 5：任务流、运行日志、导出闭环创建为 `--stage 5 --status backlog`，等 Stage 4 可用骨架通过后再提升。
- Stage 6：QA 和复盘创建为 `--stage 6 --status backlog`，研发交付后再提升。

不要把研发任务只分配给 Builder Squad；当前 squad 不会自动 fan-out。研发 issue 应直接分配给 `agentpulse-backend-engineer`、`agentpulse-desktop-engineer`、`agentpulse-web-engineer`、`agentpulse-runtime-engineer` 等具体 agent。

## 第一阶段完成定义

第一阶段 Done 的最小标准：

- `docs/prd.md`、`docs/agent-system.md`、`docs/architecture.md`、`docs/runtime.md`、`docs/ux-writing.md` 中的必要内容已完成或明确延期。
- 后端提供工作区、员工、任务、运行事件的最小 API 或 mock 契约。
- 桌面端可展示一人自媒体公司的 AI 员工、任务看板、任务详情和内容计划产出。
- 官网清楚表达 MVP 场景和早期访问入口。
- 高风险外部动作只生成待确认草稿，不自动发布或发送。
- QA 跑过适用命令，并记录无法运行的原因。
- 复盘输出下一轮 backlog。
