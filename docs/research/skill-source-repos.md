# 技能来源调研：三个可集成到 Hermes 员工的第三方仓库

## 范围和结论

起因：如果人类需要某个能力，但当前 AI 员工没有这个技能，能不能靠集成第三方开源仓库的现成能力来补上？针对项目所有者指定的三个候选仓库做了深度调研（各自独立 subagent 实查仓库内容——克隆/API 读 README、目录结构、SKILL.md 样本，而非凭仓库名猜测）。

核心结论：

1. 三个仓库里有 **两个已经自带官方 Hermes 集成**（`HKUDS/CLI-Anything` 的 `hermes-skill`、`msitarzewski/agency-agents` 的 `integrations/hermes/`），说明这条"给 Hermes 员工接第三方能力"的路子在社区已经跑通，不是我们要发明新协议。
2. 三个仓库分别对应三种不同的集成方式，不能一刀切：**CLI-Anything → 工具接入**（让员工现学现用外部软件）；**agency-agents → 人格/技能素材**（生成 SOUL.md 和 SKILL.md 的原料）；**anbeime/skill → 仅作发现索引**，因为授权状态不清晰，不能整仓库拉取。
3. 本文是**调研记录，不是架构决策**——不新增 ADR，待真正着手实现某一条时再决定是否需要 ADR（例如"是否引入 CLI-Anything 作为标准工具"可能够格立一条 ADR）。
4. **2026-07-04 项目所有者拍板：暂不集成 `anbeime/skill`**（原因见下方该仓库小节：授权状态不清晰）。当前只推进 CLI-Anything 和 agency-agents 两条。若后续想引用它里面的单个技能（如 Anthropic 原生 docx/xlsx/pdf/pptx），需重新评估并单独审计对应子技能的 LICENSE，而不是恢复整体集成。

## 一、HKUDS/CLI-Anything —— ⭐ 强推荐，已有官方 Hermes 集成

**是什么**：把 GUI/桌面软件包装成可被 agent 调用的 CLI + SKILL.md 的框架和注册表。已支持 Blender、GIMP、LibreOffice、Zoom、Obsidian、QGIS、FreeCAD、Krita、n8n 等约 150 款软件。

**关键能力**：
- **~150 个预制 "harness"**：每个软件一个可 `pip install` 的 Click CLI 包（如 `cli-anything-blender`），支持 `--json` 机器可读输出、REPL 模式、undo/redo 状态（FreeCAD 一个软件就有 258 个子命令、17 个分组）。
- **CLI-Hub 包管理器**（`pip install cli-anything-hub`）：`cli-hub list/search/info/install/update/uninstall/launch`——运行时按需发现、安装能力，不用预装全部 150 个。
- **能力矩阵（capability matrix）**：`cli-hub matrix preflight/install --capability <id>`，按"要做什么"（如 `video-creation`）而非"要装哪个软件"选能力，装之前先做 gap-analysis。
- **Meta-skill 自动生成新 harness**：`cli-anything-plugin/`（含 `HARNESS.md`、`skill_generator.py`）教会 agent 一套 7 阶段方法论（分析→设计→实现→测试→打包→生成 SKILL.md→验证），能给没支持的软件**自己造新技能**。

**架构**：纯客户端 Python CLI 框架 + 技能库，没有 server 要跑。技能统一放在 `skills/` 目录，一个软件一个 `SKILL.md`（如 `skills/cli-anything-blender/SKILL.md`），可用 `npx skills add HKUDS/CLI-Anything --skill <name> -g -y` 单独装。程序化调用就是 shell 出去跑已装的 CLI（如 `cli-anything-blender --json scene new`），解析 JSON stdout——对任何 agent runtime 都极易接入。

**License**：Apache-2.0，完全可用/可嵌入/可再分发。

**成熟度**：4.47 万星，4187 fork，2026-06-25 仍在推送，近乎每日提交，有 arXiv 技术报告（2606.03854），CI 2461 个测试通过，文档已译中/日/德。非常成熟活跃，不是玩具项目。

**已有官方 Hermes 集成**：`hermes-skill/SKILL.md`（技能名 `cli-anything-hermes`），明确点名对接 `NousResearch/hermes-agent`，把方法论映射到 Hermes 自己的工具（`terminal`、`execute_code`、`delegate_task`、`read_file`/`write_file`、`patch`）。

**集成方式（按优先级）**：
1. 【工具接入，最先做】把 `cli-hub` 接成员工可调用的工具：员工遇到"人类需要 Blender/LibreOffice/Obsidian 自动化但我不会"时，`cli-hub search <任务>` → 装上 → `cli-anything-<软件> --json <命令>`。一次接入，立刻获得约 150 项能力，且随生态更新自动扩容。
2. 【技能包，直接装】把 `cli-hub-meta-skill` 装进对应员工的 `~/.hermes/skills/`，教会"发现→安装→preflight"的标准循环；如果想让员工自己造新 harness，再装 `hermes-skill`（`cli-anything-hermes`）。
3. 不是服务依赖——纯客户端生态，`pip install` 相应包即可，无需额外部署基础设施。

## 二、msitarzewski/agency-agents —— ⭐ 强推荐，人格素材库 + 已有 Hermes 转换器

**是什么**：250+ 个独立的 AI agent 人格定义文件（Markdown），按 20+ division 组织（工程/市场/销售/财务/安全/产品/游戏开发/GIS/学术等），配一套安装/转换工具链，能把同一份人格素材转成 Claude Code/Cursor/Codex/Gemini CLI/Copilot/Aider/Windsurf/Kimi/OpenCode/Osaurus **以及 Hermes** 各自的格式。还有配套桌面 GUI 安装器（agencyagents.app）。

**格式**：单文件 `.md`，YAML frontmatter（`name`/`description`/`tools`/`color`/`emoji`/`vibe`）+ "身份与记忆"部分（人格、沟通风格）+ "必须遵守的硬性规则"（约束/护栏）+ 核心能力 + 深度领域打法（表格/框架/日历/checklist，例如 CFO agent 附带完整年度规划日历和损益表结构）。**这个结构比单纯 system prompt 更接近 SOUL.md 的身份文件哲学**，比模板丰富、比结构化 JSON 简单。

**与 AgentPulse 员工编制的映射**：

| AgentPulse 角色 | 对应 agency-agents 文件 |
|---|---|
| 老板秘书 | `specialized/specialized-chief-of-staff.md`（近乎精确匹配："master coordinator...过滤噪音、掌控流程、路由决策"） |
| 内容员工 | `marketing/marketing-content-creator.md` + ~25 个平台专项 agent（含小红书/抖音/微信/B站/微博，中国市场覆盖意外地强） |
| 运营员工 | `specialized/operations-manager.md`、`project-management/*` |
| 销售客服 | `sales/*`（10 个）、`specialized/customer-service.md`、`specialized/sales-outreach.md` |
| 财务行政 | 整个 `finance/` division（记账/FP&A/税务/投研）+ `specialized/chief-financial-officer.md` |

**License**：MIT（`Copyright (c) 2025 AgentLand Contributors`），完全可用，无限制修改/再分发。

**成熟度**：2025-10 创建，2026-07-04 仍有推送，642+ 合并 PR，外部贡献者活跃。⚠️ star 数（127,107）/fork 数（20,637）对这个年龄和细分领域而言异常高，已用 GitHub 原始 API 核实数字真实（不是渲染错误），但可能是某次病毒式传播带来的，长期稳定性未知，实现前建议重新核实项目现状。

**已有官方 Hermes 集成**：`integrations/hermes/`（`scripts/convert.sh --tool hermes`），生成一个 `agency-agents-router` Hermes 插件，对 232 个 agent 做懒加载 search/inspect/load/delegate，避免把 232 个 agent 全部塞进 Hermes 的工具面。

**集成方式**：
1. 【人格素材，直接抽取】把"身份与记忆/沟通风格/硬性规则"部分直接搬进对应员工的 SOUL.md——这几节结构和 SOUL.md 的身份文件哲学高度吻合，几乎不用改造。
2. 【拆成 SKILL.md】"核心能力"和框架/checklist 部分（如 CFO 的年度规划日历、销售的 MEDDPICC 流程）更适合拆成 SKILL.md 的 procedure（原文件把身份和流程混在一起，需要人工拆分——不是简单复制粘贴）。
3. 【架构参考，非直接采用】`agency-agents-router` 的"懒加载暴露大型人格库"模式值得借鉴——即使 AgentPulse 最终自建 SOUL.md 生成管线，也可以参考它如何不占满 Hermes 的工具面。
4. ⚠️ 内容以英文为主，中国市场专项 agent 是"外挂"上去的，需要本地化改写——MIT 协议允许自由改。

## 三、anbeime/skill —— 🟡 谨慎使用，仅做"发现索引"，不整体采纳

> ⚠️ **2026-07-04 已拍板暂不集成**（见文首结论 4）。以下分析保留供以后需要单独引用某个子技能时参考，不代表当前推进计划的一部分。

**是什么**：一个 AI Agent 技能聚合站/商店（"技能商店"），Python 爬虫每 24 小时从上游 `VoltAgent/awesome-agent-skills` 拉取同步、发布到 Vercel 站点。243 个技能：182 个"官方"（纯元数据/链接，指向 Anthropic/Vercel/Cloudflare/Stripe 等上游）+ 61 个"本地"（仓库里真的 vendor 了内容）。

**格式**：抽查过的两个 SKILL.md 样本确实是 agentskills.io 风格（frontmatter + 任务目标/操作步骤），但字段命名有出入（`allowed-tools` 而非标准的 `triggers`，多了个非标准 `dependency` 块），且未逐一确认 61 个本地技能是否都有 `pitfalls`/`verification` 部分——这是引入前要补的缺口，不能假设都齐全。

**能力方向**：中文内容生产为主——TTS/数字人配音、PPT 生成（NanoBanana）、小红书/微信/抖音自动发布、合同法律审查、股票财务分析、arXiv 论文总结，以及 fork 进来的 Anthropic 官方 docx/xlsx/pdf/pptx 技能。61 个里只有 26 个"完全免费"，15 个强制要外部 API（智谱/GLM 等）。

**License 是硬伤**：README 徽章写 CC BY 4.0（正文又混着提 MIT），但**仓库根目录没有 LICENSE 文件**——只有零散 fork 进来的子技能各自带的 LICENSE，继承各自上游、协议不一致。整体聚合物的授权状态不清晰，整体引入有法律风险。

**成熟度**：3127 星，318 fork，2026-07-04 仍在推送，24 小时自动同步 CI；但 2026-02-02 才创建，年轻、可能是短期热度，长期稳定性存疑。

**集成方式（保守）**：
1. ❌ **不**整体作为 Hermes skill tap 采纳（License 不清 + 依赖未审 + schema 不一致，三个理由任一条都够拒绝整体引入）。
2. ✅ 只挑单个技能、逐一审计 license/依赖后单独 fork——最佳候选：仓库里 vendor 的 4 个 Anthropic 原生文档技能（`pptx`/`xlsx`/`pdf`/`docx`，上游 Apache/MIT，本来就是 SKILL.md 原生格式）；`paper-analysis-assistant`、`stock-analysis` 也可考虑（AgentPulse 未来可能需要研究/财务场景）。
3. 把"官方"182 条列表当成**发现索引**，不当可安装内容——真要用，去它们各自的上游仓库（或直接看 `VoltAgent/awesome-agent-skills`）fork，绕开这层聚合站的授权模糊问题。
4. 引入任何技能都要重新规范化 frontmatter（补 `triggers`，确认/补全 `pitfalls`/`verification`）。

## 汇总：可集成能力清单（供后续慢慢实现）

**(A) 工具接入 —— 让员工"现学现用"外部软件/能力**
- [ ] 接入 `cli-hub`（CLI-Anything）作为员工可调用工具，打通约 150 项软件自动化能力
- [ ] 评估是否需要给员工挂 `cli-anything-hermes` meta-skill，让员工自己给新软件造新 harness

**(B) 技能包（SKILL.md）—— 教会员工标准作业流程**
- [ ] 装 `cli-hub-meta-skill`（发现/安装/preflight 循环）
- [ ] 从 agency-agents 拆出各角色的"核心能力/框架/checklist"部分，转成对应员工的 SKILL.md（如 CFO 年度规划、销售 MEDDPICC 流程）
- ~~从 anbeime/skill 里逐一审计后单独 fork~~ —— 暂不推进（见文首结论 4），需要文档/研究类技能时再重新评估

**(C) 人格素材 —— SOUL.md 生成参考**
- [ ] 老板秘书 SOUL.md ← `agency-agents: specialized-chief-of-staff.md`
- [ ] 内容员工 SOUL.md ← `agency-agents: marketing-content-creator.md` + 中国市场专项 agent（需本地化）
- [ ] 运营员工 SOUL.md ← `agency-agents: operations-manager.md` / `project-management/*`
- [ ] 销售客服 SOUL.md ← `agency-agents: sales/*` + `customer-service.md` + `sales-outreach.md`
- [ ] 财务行政 SOUL.md ← `agency-agents: finance/*` + `chief-financial-officer.md`
- [ ] 参考（不直接搬）`agency-agents-router` 的懒加载模式，用于我们自己的大型人格库暴露方案

## 建议实现顺序

1. **CLI-Anything 的 `cli-hub` 工具接入**——ROI 最高、集成成本最低（对方已做好 Hermes 集成），一次接入立刻获得约 150 项能力。
2. **agency-agents 人格素材 → SOUL.md**——直接提升"招募员工"时生成的人格质量，老板秘书/财务/销售这几个角色现成度很高，能明显加速。
3. **agency-agents 的角色能力 → SKILL.md 拆分**——需要人工拆分身份/流程，工作量更大，放第二批。
4. ~~anbeime/skill 的逐一审计式引用~~——暂不推进（2026-07-04 拍板，见文首结论 4）。

## 风险和待验证项

- 三个仓库都在快速变化（调研当天三者都有近日活跃提交），**实现前建议重新核实其现状**（stars、维护状态、license 有无变化），尤其 agency-agents 异常的 star 数值得留意，不排除后续降温或仓库变动。
- anbeime/skill 的整体授权状态不清晰，任何引用都要先看清楚该子技能自己的 LICENSE，**不要整仓库拉取或做 git submodule**。
- CLI-Anything 的 150 个 harness 各自依赖对应软件已安装（如 Blender、GIMP 本体）——服务器端部署 Hermes 员工时，宿主机需要装上这些软件才能真正跑起来，不是纯 API 调用，需要评估服务器资源和安装成本。
- agency-agents 拆分 SOUL.md/SKILL.md 时容易把"身份"和"流程"搅在一起复制过去，导致 SOUL.md 臃肿——落地时要严格按 [ADR 0001](../decisions/0001-hermes-as-agent-runtime.md) 的"人格 vs 技能"分工来拆。

## 来源

- [github.com/HKUDS/CLI-Anything](https://github.com/HKUDS/CLI-Anything)（已克隆验证 README/LICENSE/skills/、hermes-skill/、cli-hub-meta-skill/）；技术报告 [arXiv:2606.03854](https://arxiv.org/abs/2606.03854)；官网 [clianything.cc](https://clianything.cc/)
- [github.com/msitarzewski/agency-agents](https://github.com/msitarzewski/agency-agents)（已克隆验证 README/LICENSE/`integrations/hermes/`/`marketing-content-creator.md`/`chief-financial-officer.md`/`specialized-chief-of-staff.md`）
- [github.com/anbeime/skill](https://github.com/anbeime/skill)（经 `gh api` 直接读取 README、根 `SKILL.md`、`skills/tts-voice-synthesis/SKILL.md`、完整文件树）
- 上游技能索引：[VoltAgent/awesome-agent-skills](https://github.com/VoltAgent/awesome-agent-skills)（anbeime/skill 的爬取来源，绕开聚合站授权问题时应直接看这里）

## 需要交给其他成员继续处理（若沿用 docs/workflow.md 的研发闭环）

- 工具接入方案细化：交给 `agentpulse-runtime-engineer`，把 `cli-hub` 的工具调用协议写进 `docs/runtime.md`（该文档目前尚未创建）。
- SOUL.md/SKILL.md 拆分与本地化：交给 `agentpulse-agent-architect`，把 agency-agents 的角色素材转成 AgentPulse 默认员工的实际人格文件，并处理中国市场本地化。
- 是否正式采用 CLI-Anything 作为标准工具：如果决定采用，交给项目所有者/`agentpulse-system-architect` 评估是否需要单独立一条 ADR（涉及服务器需装第三方软件，有部署成本，够格作为架构决策）。
