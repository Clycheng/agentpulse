<div align="center">

# AgentPulse

**雇一支 AI 员工团队，像经营公司一样使用 AI**

*Hire a team of AI employees. Run them like a real company.*

![License: MIT](https://img.shields.io/badge/License-MIT-green.svg) ![Status: Alpha](https://img.shields.io/badge/Status-Alpha-orange.svg) ![Platform: Desktop](https://img.shields.io/badge/Platform-macOS%20%7C%20Windows%20%7C%20Linux-blue.svg)

[产品愿景](#愿景) · [核心特性](#-核心特性) · [快速开始](#-快速开始) · [常见问题](#-常见问题) · [开发者](#-开发者)

<!-- TODO: 此处放桌面工作台 hero 截图/演示 GIF（群聊讨论 + 共识纪要卡片 + 任务看板一屏） -->

</div>

---

AgentPulse 是一个面向普通人和一人公司的开源 **AI 公司工作台**。它不是又一个聊天机器人：你在这里**招聘 AI 员工**（内容主笔、运营、销售、客服、财务……），像老板一样在群里交代目标，员工们**先讨论清楚再干活**，任务和产出全程可追踪，所有高风险动作都等你拍板。

AgentPulse is an open-source **AI company workbench** for solo founders and creators: hire AI employees, assign goals in group chat, let them discuss before executing, track everything, and approve risky actions — no prompts, no workflow DAGs, no config files.

## ✨ 核心特性

- **🧑‍💼 一句话雇一个员工** — 说"我要一个小红书运营"，就得到一个有人格、有技能、有边界的 AI 员工，不用写 prompt、不用配置任何东西。
- **💬 先讨论，再执行** — 员工像真人同事：背景不清会在群里追问你，讨论出「共识纪要」你点了确认，才开始干活——绝不稀里糊涂开工。
- **📋 任务全程可追踪** — 谁在做、做到哪、产出了什么，任务中心一目了然；对话会散，任务和产出永远留痕。
- **🛡 老板拍板制** — 发布、部署、花钱、对外发送……所有高风险动作强制停下等你确认，AI 永远越不过这道门。
- **🌱 员工越用越懂你** — 每个员工有长期记忆，会在工作中沉淀技能：改过的口径、踩过的坑，下次不会再犯。
- **🌙 7×24 不下班** — 员工住在服务器上：定时复盘数据、主动产出选题和想法，你睡觉时公司还在转。
- **🔓 开源、模型自由** — MIT 协议；接任何 OpenAI 兼容模型（默认 DeepSeek），图片/音频/视频照样处理。

## 💡 它是怎么工作的

```text
1. 创建你的公司      →  获得默认班底（秘书、主笔、运营、客服、财务）
2. 群里说出目标      →  "下周帮我做小红书内容规划"
3. 员工讨论澄清      →  "主打什么主题？发几篇？有直播要配合吗？"
4. 你确认共识纪要    →  一键生成任务，员工开始执行
5. 关键节点你拍板    →  发布前、花钱前，必须经过你
```

## 🚀 快速开始

> 要求：Node.js 20+ · Python 3.12+ · Docker（跑 PostgreSQL）

```bash
git clone git@github.com:Clycheng/agentpulse.git && cd agentpulse
npm install
cd services/api && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && cd ../..
docker compose up -d postgres

export AGENTPULSE_DEEPSEEK_API_KEY="你的 DeepSeek API Key"
npm run dev:api        # 后端
npm run dev:desktop    # 桌面工作台
```

打开桌面应用，注册进入你的公司即可。更多配置见 [docs/](docs/)。

## 🆚 和现有产品的区别

| | 聊天机器人 (ChatGPT 类) | 自动化平台 (Dify/n8n 类) | **AgentPulse** |
|---|---|---|---|
| 心智模型 | 和一个窗口反复对话 | 配置节点、触发器、JSON | **经营一家公司** |
| 多角色协作 | ❌ 单一助手 | 🟡 靠人编排 | ✅ 员工群里讨论、接力 |
| 过程与产出沉淀 | ❌ 聊完即散 | 🟡 面向工程师 | ✅ 任务/进度/产出全留痕 |
| 危险动作管控 | ❌ | 🟡 靠自己配置 | ✅ 强制审批，绕不过 |
| 上手门槛 | 低 | 高 | **低**（自然语言雇人派活） |

## ❓ 常见问题

**和 ChatGPT 有什么区别？**
ChatGPT 是一个窗口一个助手，聊完即散。AgentPulse 是一支持续存在的团队：每个员工有自己的人格、技能和记忆，任务留痕，7×24 在服务器上工作，不依赖你开着窗口。

**AI 员工会失控吗？会乱花钱、乱发布吗？**
不会。所有高风险动作（对外发布、部署上线、任何花钱操作）都被系统强制拦下等你确认；"花钱且不可逆"的事（比如买域名）永远由你亲自完成。这是产品的硬性设计，不是对 AI 的口头要求。

**需要懂技术吗？**
不需要。产品语言是「公司、员工、群聊、任务、审批」，不是 prompt、workflow、DAG。会用微信群，就会用 AgentPulse。

**支持哪些模型？**
任何 OpenAI 兼容 API，默认 DeepSeek。用纯文本模型也能处理图片、音频、视频（系统自动转换）。

**现在能用吗？**
Alpha 阶段：桌面工作台、群聊、任务、共识纪要与审批已可用；多员工自动讨论和真实执行能力正在接入。欢迎试用与反馈。

## 🗺 路线图

- ✅ 桌面工作台：群聊、员工、任务、审批、共识纪要
- 🚧 多员工群内自动讨论与分工
- 🚧 员工真实执行能力（写码、发布、部署等，带审批门）
- 📋 一句话定制任意工种员工 · 技能市场 · idea 中心
- 📋 更多场景模板：销售、客服、财务、跨境电商

详见 [ROADMAP.md](ROADMAP.md)。

## 🧑‍💻 开发者

技术栈：Electron + React（桌面）· FastAPI + PostgreSQL（后端）· [Hermes Agent](https://github.com/NousResearch/hermes-agent)（员工运行时）。

- **参与开发 / AI 接手**：从 [AGENTS.md](AGENTS.md) 开始（项目北极星 + 开发规范）
- **架构与技术设计**：[docs/tech-design/](docs/tech-design/) · 决策记录：[docs/decisions/](docs/decisions/)

## 📄 License

[MIT](LICENSE)

---

<sub>关键词：AI员工 · AI数字员工 · AI公司 · 一人公司 · 多智能体协作 · ai-agents · multi-agent · ai-employees · ai-workforce · autonomous-agents · agent-orchestration · solo-founder</sub>
