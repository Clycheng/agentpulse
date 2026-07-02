# AgentPulse

> An AI company workbench for solo founders, creators, and operators.

AgentPulse 是一个面向普通人和一人公司的 **AI 公司工作台**。它不是又一个聊天机器人，而是试图把“一个人经营一家公司”这件事重新组织成：公司、AI 员工、任务、资料库、工具、审批和可追踪的协作流程。

用户不需要理解 agent、workflow、tool schema、runtime、DAG 这些技术概念。用户只需要像老板一样描述目标、招聘 AI 员工、拉群讨论、查看进度，并在关键节点拍板。

```text
创建公司 -> 招聘 AI 员工 -> 交代目标 -> 自动拆解任务
-> 多员工协作执行 -> 展示进度和产出 -> 高风险动作等待用户确认
```

## Why AgentPulse

大模型让“一个人完成很多工作”变得可能，但现有产品通常卡在两个极端：

- **聊天机器人太轻**：用户反复和一个窗口对话，过程不可追踪，任务不能沉淀，协作感弱。
- **自动化平台太重**：workflow、节点、触发器、工具权限、JSON 配置，对普通用户太复杂。

AgentPulse 想探索中间那条路：

> 让普通人用“经营公司”的心智使用 AI，而不是用“配置系统”的心智使用 AI。

我们希望解决这些问题：

- 一个人同时做老板、策划、运营、销售、客服、财务，工作上下文容易碎。
- AI 能给答案，但很难像团队一样接力执行、汇报进度、保留过程。
- 普通用户不知道如何设计 prompt、拆任务、配置工具、控制权限。
- AI 自动化一旦涉及发布、发送、覆盖文件、外部账号，很容易失控。
- 业务资料、历史产出、品牌语气和任务结果没有形成长期记忆。

AgentPulse 的答案是：把 AI 能力包装成一家公司，而不是一堆模型参数。

## What It Is

AgentPulse 的第一阶段聚焦 **一人自媒体公司**。这是一个足够具体、足够高频、也足够容易验证的场景。

第一版用户应该可以：

- 创建或进入一个内容工作室。
- 获得默认 AI 员工，例如老板秘书、内容主笔、运营负责人、销售顾问、客服专员、财务助理。
- 像在公司群里一样交代目标。
- 让秘书或负责人拆解任务、拉群、分配员工。
- 在首页看到“待我拍板”“员工动态”“任务进展”。
- 在消息里看到执行结果、确认请求和任务创建事件。
- 在任务中心看到负责人、状态、进度和操作。
- 在资料库里管理公司资料、Skills 技能和 MCP 工具连接。
- 在高风险动作前手动确认，例如发布、发送、覆盖文件、连接外部账号。

## Product Principles

AgentPulse 的设计原则很简单，也很硬：

- **用户是老板，不是系统管理员**：不把 prompt、schema、workflow DAG 直接丢给普通用户。

- **AI 是员工，不是神谕**：每个 AI 员工有角色、边界、职责、可用工具和当前任务。

- **任务是一等公民**：对话只是入口，真正沉淀的是任务、状态、过程、产出和确认记录。

- **过程必须可见**：用户要知道谁在做、做到哪、用了什么资料、产出了什么。

- **高风险动作必须等待确认**：发布、发送、删除、覆盖、授权、计费、外部写入，都不能绕过用户。

- **先垂直闭环，再平台化**：先把“一人自媒体公司”跑通，再扩展销售、客服、财务、跨境电商等场景。

## Current Status

当前项目已经是一个可运行的 monorepo，并完成了第一版桌面端原型。

| Area           | Status        | Notes                                                             |
| -------------- | ------------- | ----------------------------------------------------------------- |
| Web 官网       | Scaffolded    | Vite + React + TypeScript                                         |
| Desktop 工作台 | MVP workbench | Electron + React，已实现消息、员工、人才市场、群聊、任务闭环      |
| Admin 后台     | Scaffolded    | 官方人才分类、员工模板、Prompt、Skills、MCP 权限管理入口          |
| Backend API    | MVP API ready | FastAPI + PostgreSQL，已接入登录、员工、群聊、任务、DeepSeek 调用 |
| Product docs   | In progress   | PRD、workflow、backlog、Dust 调研已沉淀                           |
| Agent runtime  | Planned       | 后续实现本地任务运行、工具调用、事件流                            |

桌面端已包含：

- 默认进入消息会话
- AI 员工和组织树
- 官方人才市场与招募详情
- 创建员工与招募员工
- 群聊创建、邀请员工、@ 点名
- 任务中心、任务创建、任务推进、会话关联任务
- 资料库与能力
- 员工详情抽屉
- 新手引导
- DeepSeek 真实调用链与运行记录
- 关联任务自动注入 Agent 回复上下文

## Architecture

AgentPulse 会采用“产品界面 + 后端 API + 本地 Runtime”的架构。桌面端不是简单壳子，而是未来本地执行能力的入口。

```mermaid
flowchart LR
  User["User / Boss"] --> Desktop["Desktop Workbench"]
  User --> Web["Website / Docs"]

  Desktop --> API["FastAPI Backend"]
  Web --> API

  API --> DB["PostgreSQL"]
  API --> Queue["Task Queue"]
  API --> Realtime["WebSocket Event Stream"]

  Queue --> Runtime["Local Agent Runtime"]
  Runtime --> Agents["AI Employees"]
  Runtime --> Tools["Tool Broker"]
  Runtime --> Files["Local Workspace"]
  Runtime --> Providers["LLM Providers / CLI"]

  Agents --> Memory["Company Memory"]
  Tools --> Integrations["Browser / Email / Docs / Sheets / MCP"]
```

核心对象会围绕这些概念建模：

| Domain      | Meaning                                       |
| ----------- | --------------------------------------------- |
| `workspace` | 一家公司或一个业务空间                        |
| `agent`     | AI 员工，包含角色、职责、技能、工具权限       |
| `task`      | 可追踪工作项，包含负责人、状态、优先级、产出  |
| `run`       | 一次 agent 执行过程，包含步骤、日志、工具调用 |
| `message`   | 用户、系统、员工之间的消息和事件              |
| `tool`      | 文件、搜索、浏览器、邮件、表格、MCP 等能力    |
| `memory`    | 公司长期资料、品牌语气、客户信息、历史结果    |
| `approval`  | 用户确认节点，用于控制高风险动作              |

任务状态第一阶段采用面向用户的简单状态机：

```text
进行中 -> 待确认 -> 已完成
  ^
  |
阻塞
```

## Repository Layout

```text
agentpulse/
  apps/
    web/              # 官网，Vite + React + TypeScript
    desktop/          # 桌面工作台，Electron + Vite + React + TypeScript
    admin/            # 官方后台，维护人才市场分类、模板、Prompt、Skills、MCP
  services/
    api/              # 后端 API，FastAPI
  docs/
    prd.md            # 一人自媒体公司 MVP PRD
    workflow.md       # 第一阶段研发闭环
    backlog.md        # 第一阶段 backlog
    research/
      dust.md         # Dust 调研与架构启发
```

## Tech Stack

| Layer    | Stack                                                      |
| -------- | ---------------------------------------------------------- |
| Monorepo | npm workspaces                                             |
| Web      | Vite, React, TypeScript                                    |
| Desktop  | Electron, Vite, React, TypeScript                          |
| Admin    | Vite, React, TypeScript                                    |
| API      | FastAPI, Pydantic Settings, Uvicorn, psycopg               |
| Database | PostgreSQL for app data, SQLite only for isolated tests    |
| Tests    | Pytest, TypeScript checks                                  |
| UI Icons | Material Symbols in desktop prototype, lucide-react in web |

## Quick Start

### Requirements

- Node.js 20+
- npm 10+
- Python 3.12+
- PostgreSQL 16+ or Docker

The repository includes `.npmrc` with npm and Electron mirrors for faster installs in China.

### Install Node Dependencies

```bash
npm install
```

If Electron binary is missing after install, rebuild it:

```bash
npm rebuild electron --workspace @agentpulse/desktop
```

### Install Python Dependencies

```bash
cd services/api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Start PostgreSQL

AgentPulse 现在默认使用 PostgreSQL 作为后端主存储。最简单的本地启动方式：

```bash
docker compose up -d postgres
```

默认连接串：

```text
postgresql://agentpulse:agentpulse@127.0.0.1:55432/agentpulse
```

如果你使用自己的数据库，启动 API 前设置：

```bash
export AGENTPULSE_DATABASE_URL="postgresql://user:password@host:5432/agentpulse"
```

测试环境会使用临时 SQLite 文件隔离数据，不影响本地 PostgreSQL。

### Run The Desktop Workbench

```bash
npm run dev:desktop
```

The desktop app opens an Electron window. The renderer dev server runs at:

```text
http://localhost:5174
```

### Run The Website

```bash
npm run dev:web
```

```text
http://localhost:5173
```

### Run The Admin Console

```bash
npm run dev:admin
```

```text
http://localhost:5175
```

当前后台第一版用于维护官方人才市场的产品边界：官方岗位类目、员工模板、默认 Prompt、Skills、MCP 权限、发布状态和版本。MVP 先读取种子模板，后续会接管理员登录、PostgreSQL 持久化和模板审核发布流程；普通用户只在桌面端浏览人才、查看完整档案并招募到自己的部门。

### Run The API

```bash
npm run dev:api
```

```text
http://localhost:8000
http://localhost:8000/api/health
```

### Configure DeepSeek

第一版 Agent Runtime 使用 DeepSeek 跑通 `llm_api` 闭环。启动 API 前配置：

```bash
export AGENTPULSE_DEEPSEEK_API_KEY="你的 DeepSeek API Key"
export AGENTPULSE_DEEPSEEK_MODEL="deepseek-v4-flash"
```

桌面端默认请求：

```text
http://127.0.0.1:8000/api/runs/llm-chat
```

如果 API 地址不同，可以设置：

```bash
export VITE_AGENTPULSE_API_URL="http://127.0.0.1:8000/api"
```

## Useful Commands

```bash
npm run lint        # TypeScript checks for web and desktop
npm run build       # Build web and desktop
npm run test:api    # Run FastAPI tests
npm run format      # Format the repository with Prettier
```

## Roadmap

### Phase 0: Foundation

- Monorepo scaffold
- Web scaffold
- Desktop scaffold
- FastAPI scaffold
- Product docs and MVP PRD
- Desktop collaboration workbench prototype

### Phase 1: MVP Workbench

- Workspace model
- Default secretary employee
- Agent creation and template recruitment
- Group chat with members and mentions
- Task creation, assignment, status updates, and conversation links
- Message-driven DeepSeek agent replies
- Related task context injection into agent prompts

### Phase 2: Real Agent Loop

- Backend models for workspace, agent, task, run, message, approval
- WebSocket event stream
- Task queue
- Agent run lifecycle
- Tool call records
- Persisted task history

### Phase 3: Local Runtime

- Local isolated run directories
- File read/write tools
- Markdown and table export
- Browser/search tools
- LLM provider adapters
- Human confirmation gates for external actions

### Phase 4: Templates And Scale

- Industry templates
- Agent templates
- Workflow templates
- Company memory
- Permission model
- Connector marketplace
- Multi-scenario expansion

## Design Reference

AgentPulse is inspired by systems like Multica and Dust, especially these ideas:

- Task-first collaboration, not chat-only interaction.
- Local daemon/runtime for work that needs files, browsers, and user environment.
- Real-time event streams so users can see progress.
- Agents with explicit tools, permissions, and handoff boundaries.
- Human confirmation for risky external actions.

But AgentPulse deliberately hides technical machinery from normal users. The product language is:

```text
company, employee, department, task, group chat, file, skill, tool, approval
```

not:

```text
agent graph, workflow DAG, tool schema, run trace, vector index, provider config
```

## Documentation

- [MVP PRD](docs/prd.md)
- [Workflow](docs/workflow.md)
- [Backlog](docs/backlog.md)
- [Dust Research](docs/research/dust.md)

## Project Goal

AgentPulse 的长期目标是成为普通人的 AI 公司操作系统：

- 一个创作者可以拥有内容团队。
- 一个个体户可以拥有销售、客服和财务助理。
- 一个咨询顾问可以拥有研究员、文案、项目经理。
- 一个普通人可以把业务目标交给一支可控、可追踪、可协作的 AI 团队。

最终，我们想回答一个问题：

> 当一个人可以指挥一支 AI 团队时，一人公司会变成什么样？

AgentPulse 就是这个问题的实验场。

## License

AgentPulse is open-source software licensed under the [MIT License](LICENSE).
