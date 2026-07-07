# AgentPulse — AI 公司工作台 · AI Company Workbench

> **雇一支 AI 员工团队，像经营公司一样使用 AI。**
> Hire a team of AI employees and run them like a real company — built for solo founders, creators, and one-person businesses.

![License: MIT](https://img.shields.io/badge/License-MIT-green.svg) ![Status: Alpha](https://img.shields.io/badge/Status-Alpha-orange.svg) ![Backend: FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg) ![Runtime: Hermes Agent](https://img.shields.io/badge/Agent%20Runtime-Hermes-blueviolet.svg) ![Desktop: Electron + React](https://img.shields.io/badge/Desktop-Electron%20%2B%20React-47848F.svg)

## Overview (English)

**AgentPulse is an open-source AI company workbench** that lets one person operate like a full team: hire AI employees (autonomous agents with personas, skills, memory, and tool permissions), assign goals in a group chat, let the agents **discuss and align before executing**, track tasks on a board, and approve high-risk actions (publishing, deploying, spending) before they happen.

- **AI employees, not chatbots** — each employee is a persistent agent (one [Hermes](https://github.com/NousResearch/hermes-agent) profile: persona + skills + memory + tools/MCP + model) that learns on the job and works 24×7 on the server.
- **Discuss first, execute second** — a self-built multi-agent orchestration layer forces alignment: no task can be created without a boss-confirmed consensus brief. Structural safety, not prompt hopes.
- **The boss stays in control** — irreversible or costly actions (deploy to production, buy a domain, publish externally) always stop for human approval.

Keywords: *AI employees, AI workforce, multi-agent collaboration, autonomous agents, AI company OS, agent orchestration, one-person company, solo founder tools, Hermes agent, MCP.*

---

## AgentPulse 是什么

AgentPulse 是一个面向普通人和一人公司的 **AI 公司工作台**（AI 数字员工平台）。它不是又一个聊天机器人，而是把"一个人经营一家公司"重新组织成：**公司、AI 员工、群讨论、任务、资料库、工具、审批**和可追踪的协作流程。

用户不需要理解 agent、workflow、tool schema、runtime、DAG 这些技术概念——只需要像老板一样：**描述目标 → 招聘 AI 员工 → 拉群讨论 → 查看进度 → 关键节点拍板**。

```text
创建公司 -> 招聘 AI 员工 -> 交代目标 -> 群里讨论对齐 -> 确认共识纪要
-> 自动生成任务 -> 员工执行 -> 展示进度和产出 -> 高风险动作等老板确认
```

## 为什么做 AgentPulse

大模型让"一个人完成很多工作"变得可能，但现有产品卡在两个极端之间：

| | 聊天机器人 (ChatGPT 类) | 自动化平台 (工作流/DAG 类) | **AgentPulse** |
|---|---|---|---|
| 心智模型 | 反复对话一个窗口 | 配置节点/触发器/JSON | **经营一家公司** |
| 过程可追踪 | ❌ 聊完即散 | 🟡 面向工程师 | ✅ 任务/进度/产出全留痕 |
| 多角色协作 | ❌ 单一助手 | 🟡 靠人编排 | ✅ 多员工群里讨论、接力 |
| 任务沉淀 | ❌ | 🟡 | ✅ 任务是一等公民 |
| 危险动作管控 | ❌ 无概念 | 🟡 靠配置 | ✅ 结构性审批门，绕不过 |
| 上手门槛 | 低 | 高 | **低**（自然语言雇人、派活） |

> 让普通人用"经营公司"的心智使用 AI，而不是用"配置系统"的心智使用 AI。

## 能做什么（第一阶段：一人自媒体公司）

- 创建内容工作室，获得默认 AI 员工：老板秘书、内容主笔、运营负责人、销售顾问、客服专员、财务助理。
- **一句话定制新员工**：说"我要一个前端工程师"，系统自动生成人格、配好技能和工具权限、列出需要你提供的凭证。
- 像在公司群里一样交代目标；**员工像真人一样先在群里提问、澄清背景**，讨论明白才开工。
- 讨论收敛成「共识纪要」，老板点确认才生成任务——**没有确认的纪要，任务根本建不出来**（代码级强制）。
- 在任务中心看负责人、状态、进度；在消息里看执行结果、确认请求。
- 员工 7×24 在服务器上工作：定时复盘、产出想法进「idea 中心」、自我学习新技能。
- 高风险动作（发布、部署生产、花钱、外部写入）**必须**等老板拍板。

## 产品原则

- **用户是老板，不是系统管理员**：不把 prompt、schema、workflow DAG 丢给普通用户。
- **AI 是员工，不是神谕**：每个员工有角色、边界、职责、可用工具和当前任务。
- **先讨论，再执行**：背景不清必须先问，达成共识才开工——由编排层结构性强制，不靠 AI 自觉。
- **任务是一等公民**：对话只是入口，沉淀的是任务、状态、过程、产出和确认记录。
- **过程必须可见**：谁在做、做到哪、用了什么资料、产出了什么。
- **高风险动作必须等待确认**：发布、发送、删除、覆盖、授权、计费、外部写入，都不能绕过用户。
- **先垂直闭环，再平台化**：先跑通"一人自媒体公司"，再扩展销售、客服、财务等场景。

## 架构

三层：**产品层**（公司/员工/任务/审批 UI）+ **自研协作编排层**（群讨论协议、共识纪要、任务门控）+ **[Hermes](https://github.com/NousResearch/hermes-agent) 运行时**（每个员工 = 一个独立 profile：人格 SOUL.md + 技能 + 记忆 + 工具/MCP + 模型，服务器常驻 7×24）。

```mermaid
flowchart LR
  User["老板 Boss"] --> Desktop["桌面工作台 Desktop"]
  Desktop --> API["FastAPI 后端"]
  API --> DB["PostgreSQL"]
  API --> Orch["协作编排层(自研)<br/>群讨论 · 共识纪要 · 任务门控"]
  Orch --> Hermes["Hermes 运行时<br/>每员工一个 profile"]
  Hermes --> Cap["人格 SOUL · 技能 Skills · 记忆 Memory"]
  Hermes --> Tools["工具 / MCP<br/>终端 · GitHub · 部署 · 150+ 软件"]
  Hermes --> Gate["高风险审批门"] --> User
```

| 核心对象 | 含义 |
|---|---|
| `workspace` | 一家公司 / 业务空间 |
| `agent` | AI 员工（角色、职责、技能、工具权限，对应一个 Hermes profile） |
| `consensus_brief` | 共识纪要——讨论的结构化产出，任务创建的门控依据 |
| `task` / `run` | 可追踪工作项 / 一次员工执行过程（步骤、工具调用、审批） |
| `approval` | 用户确认节点，控制高风险动作 |
| `memory` / `skill` | 公司长期资料与员工技能（越用越懂你的公司） |

## 当前状态

| 模块 | 状态 |
|---|---|
| 桌面工作台 (Electron + React) | ✅ MVP：消息、员工、人才市场、群聊、任务、审批卡片、共识纪要卡片 |
| 后端 API (FastAPI + PostgreSQL) | ✅ 登录、员工、群聊、任务 + **群讨论第一片**（共识纪要 + 任务创建门控，已过测试） |
| Hermes 运行时集成 | 🟡 本机地基验证通过（多 profile 隔离、HTTP Runs API 流式全链路）；接入后端进行中 |
| 多 agent 群讨论 / 员工自动供给 | 📋 设计完成（详见 [docs/tech-design/](docs/tech-design/)），待实现 |
| 官网 / 后台 | 🏗 脚手架 |

## Quick Start

### Requirements

- Node.js 20+ / npm 10+ / Python 3.12+ / PostgreSQL 16+（或 Docker）

### 安装与启动

```bash
npm install                          # Node 依赖（.npmrc 已配国内镜像）

cd services/api                      # Python 依赖
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd ../..

docker compose up -d postgres        # 数据库（默认 postgresql://agentpulse:agentpulse@127.0.0.1:55432/agentpulse）

export AGENTPULSE_DEEPSEEK_API_KEY="你的 DeepSeek API Key"
export AGENTPULSE_DEEPSEEK_MODEL="deepseek-v4-flash"

npm run dev:api                      # 后端  http://localhost:8000/api/health
npm run dev:desktop                  # 桌面端（renderer :5174）
npm run dev:web                      # 官网 :5173（可选）
npm run dev:admin                    # 后台 :5175（可选）
```

自定义数据库/后端地址：`AGENTPULSE_DATABASE_URL` / `VITE_AGENTPULSE_API_URL`。Electron 装完缺二进制时：`npm rebuild electron --workspace @agentpulse/desktop`。

```bash
npm run lint | build | test:api | format   # 常用命令
```

## FAQ

**AgentPulse 和 ChatGPT 这类聊天助手有什么区别？**
ChatGPT 是"一个窗口一个助手"，聊完即散。AgentPulse 是一支**持续存在的 AI 员工团队**：每个员工有独立人格、技能和记忆，任务/进度/产出全部留痕，员工在服务器上 7×24 工作，不依赖你开着窗口。

**和 Dify、Coze、n8n 这类平台有什么区别？**
那些是给会配置工作流的人用的。AgentPulse 面向不懂技术的老板：不用画 DAG、不用写 prompt、不用配 JSON——自然语言雇人、群里派活、关键节点拍板。

**AI 员工会失控吗？会乱花钱、乱发布吗？**
不会。高风险动作（部署生产、注册域名、对外发布、任何花钱操作）被**代码级审批门**拦住，必须老板点确认；"花钱且不可逆"的操作（如买域名）永远由人亲自完成。这是结构性强制，不是"提示词里让 AI 自觉"。

**AI 员工的能力是怎么实现的？**
每个员工 = 一个 [Hermes Agent](https://github.com/NousResearch/hermes-agent) profile：人格（SOUL.md）+ 技能（SKILL.md，可自动学习沉淀）+ 长期记忆 + 工具/MCP 授权（终端、GitHub、部署 CLI、150+ 软件……）。多员工协作编排层（群讨论、共识纪要、任务门控）为自研。

**支持哪些大模型？**
任何 OpenAI 兼容 API。默认 DeepSeek（文本模型即可——图片/音频/视频经辅助模型自动转文本，员工照样"看图听音"）。

**开源吗？**
MIT 协议开源。

## 文档

| 读者 | 入口 |
|---|---|
| 想了解产品 | 本 README、[ROADMAP.md](ROADMAP.md) |
| AI / 开发者接手开发 | [AGENTS.md](AGENTS.md)（北极星+规范，第一读）→ [docs/tech-design/](docs/tech-design/)（架构+规格+任务看板） |
| 架构决策为什么这么定 | [docs/decisions/](docs/decisions/)（ADR） |

## 愿景

AgentPulse 的长期目标是成为**普通人的 AI 公司操作系统**：创作者拥有内容团队，个体户拥有销售、客服和财务助理，咨询顾问拥有研究员、文案、项目经理。

> 当一个人可以指挥一支 AI 团队时，一人公司会变成什么样？

AgentPulse 就是这个问题的实验场。

---

**关键词 / Topics**: AI员工 · AI数字员工 · AI公司 · 一人公司 · AI团队协作 · 多智能体 · ai-agents · multi-agent · ai-employees · ai-workforce · agent-orchestration · autonomous-agents · hermes-agent · mcp · fastapi · electron · solo-founder · ai-company

## License

[MIT License](LICENSE)
