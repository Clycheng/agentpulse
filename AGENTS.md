# AGENTS.md — 接手本项目的 AI / 开发者必读

> **动手前先读完本文件。** 它定义 AgentPulse 的产品方向、已拍板的架构决策、以及开发规范。
> 本文件是唯一的"北极星"。**任何偏离本文件方向的改动，动手前必须先跟项目所有者确认。**
> 如果你是被"甩"了这个仓库、没有对话上下文的 AI：读完 `AGENTS.md` → `docs/ARCHITECTURE.md` → `docs/decisions/` 就能完整对齐，直接开工。

---

## 0. 这是什么项目

**AgentPulse** = 面向一人公司 / 自媒体的「AI 公司工作台」。把"一个人经营公司"重组成：公司 → 招 AI 员工 → 交代目标 → 拆解任务 → 多员工协作 → 展示进度产出 → 高风险动作等用户拍板。产品愿景见 [README.md](README.md)。

Monorepo：`apps/`(web/desktop/admin，desktop 是主原型 Electron+React)、`services/api`(FastAPI + PostgreSQL)。

---

## 1. 北极星（产品方向 · 不可跑偏）

1. **用户是老板，不是系统管理员**：不把 prompt / schema / workflow DAG 丢给普通用户。
2. **协作模式 = 先拉群讨论，再分工执行**：要干一件事，先拉相关员工进群，**把背景/目标/分工讨论明白**，达成共识后才开工。**Agent 要像人——背景不清楚必须在群里发问，绝不允许被分配了就稀里糊涂开干。**
3. **自然语言捏 agent**：用户用一句话描述角色，系统生成不同技能 / 能力的 AI 员工。
4. **每个 agent 自我学习、持续进步**：在工作中沉淀技能、积累记忆，越用越懂这家公司。
5. **没有 idle 员工**：员工空闲时也在想业务、攒 idea(投到独立的「idea 中心」，区别于任务中心)、学技能。**7×24 不间断工作。**
6. **群聊 + 私聊都要支持**：同一套会话引擎，参与者=2 就是私聊。

---

## 2. 架构决策（已拍板 · 改动前须新增 ADR）

详细论证与调研出处见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)，原子决策见 [docs/decisions/](docs/decisions/)。

### 分层
```
产品层 (AgentPulse)     公司/部门/员工卡 · 自然语言捏 agent · 技能市场 · idea中心 · 看板
协作编排层 (自研·核心)   群讨论协议：共享 transcript + 发言路由 + 对齐门 + 人类拍板 + 终止条件
   照 AutoGen 骨架       讨论达成 → 产出"共识 brief" → 才建 Task/Run · Task/Run/RunStep/Approval
运行时层 (Hermes)        每员工 = 1 个 Hermes profile(SOUL人格 + Skills技能 + Memory记忆 + 可选模型)
                        自我学习 = 技能沉淀 + 记忆(Hermes 原生) · 7×24 = daemon+cron(我们编排)
执行/部署层             后端服务器常驻 Hermes daemon(Docker/systemd)；后端/官网/后台/客户端分处不同机器互联
```

### 一句话
> **AgentPulse 自研「公司协作大脑」(拉群 → 讨论对齐 → 分工 → 拍板 → 追踪)；Hermes 提供「每个员工的专业能力 + 记忆 + 自我进步」；两者靠 HTTP(Runs API) / kanban 对接。**

### 复用什么
- **员工运行时 = [Hermes Agent](https://github.com/NousResearch/hermes-agent)**(Nous Research 开源，MIT)。人格(SOUL.md)、技能(SKILL.md)、记忆、多模态、7×24 daemon、多实例(profiles)、编排(kanban)都用它的原生能力。
- 基建模式参照 **Multica**(Server/Daemon/adapter/pull队列+心跳+隔离workdir)。

### 明确不做（DON'T — 防止后续 AI 跑偏）
- ❌ **不**以 Codex / Claude Code 这类"操作文件的工程师型" CLI 为基座。基座只用 Hermes。
- ❌ **不**自建 Agent 协议 / Runtime / 工具系统(用 Hermes 的)。
- ❌ **不**把现在 `services/api` 里"直连 DeepSeek 回一段话"那套当成目标形态——**那只是临时执行层**，最终由"后端调 Hermes profile"替换。
- ⚠️ [ROADMAP.md](ROADMAP.md) 是早期文档，其中"多 CLI 适配 / 先 Codex 后 Claude"等 Runtime 取舍**已被本决策取代**，勿照搬；产品愿景和数据模型草案部分仍有效。

---

## 3. 关键已验证事实（已深度调研，勿重复造轮子）

- **驱动 Hermes**：起 `hermes gateway`(:8642，OpenAI 兼容)。长任务用**异步 Runs API**(`POST /v1/runs` → SSE `GET /v1/runs/{id}/events` → `POST .../approval` 解审批 → `/stop`)——完美对接"创建Run→流式→拍板→写回"。简单对话 `/v1/chat/completions`；定时 Jobs API；也可 Python 库 `from run_agent import AIAgent`。
- **多实例**：`profiles`(每员工独立 HERMES_HOME：人格/技能/记忆/密钥/模型隔离) + `hermes kanban`(orchestrator profile 派任务给 N 个 worker profile 独立进程)。已发布能力。
- **7×24 / 无 idle**：daemon + cron(60s tick 主动跑) + webhooks + `/goal` 原生；但"空闲自发想 idea"**不原生**(学习是每轮对话后触发) → **idea 中心 = 用 cron 编排"空闲即思考/学技能"**。
- **多模态**：DeepSeek 是文本模型也没关系——图片走 `vision_analyze`(配 `auxiliary.vision` 辅助视觉模型)、音频走内置 Whisper STT(可本地免费)、视频 `video_analyze`、PDF `web_extract`。Hermes 把一切模态转成文本喂给主模型。
- **模型要求**：主模型需 ≥64k 上下文 + 会 function-calling。DeepSeek V3 达标，可作默认主模型。
- **群讨论参照**：AutoGen 提供全部原语(共享 transcript、发言选择、transition 约束门、human-in-loop、可组合终止、Magentic-One 的 Task Ledger→Progress Ledger = "先讨论明白再开干"范本)。Multica 的"协作"只是 leader 派活(delegation)不是讨论，别照它做讨论层。

---

## 4. 当前状态 vs 目标

| 模块 | 现状 | 目标 |
|---|---|---|
| `services/api` | 直连 DeepSeek 回消息 + 正则建任务 + 任务记账(**套皮聊天，非真 agent**) | 协作编排层 + 调 Hermes profile 执行 |
| `apps/desktop` | 单文件原型(聊天/员工/任务/审批 UI，已接后端) | 保留，渐进接入群讨论 + Hermes |
| 群讨论协议 | ❌ 未实现 | 自研(照 AutoGen) |
| Hermes 集成 | ❌ 未开始 | 员工运行时 |

**建议的第一步(地基验证)**：本机装 Hermes → 建 2 个 profile → 从后端用 HTTP Runs API 跑通「后端 → Hermes → 流式事件 → 审批 → 写回」。这条链路通了，整个路线才算落地。

---

## 5. 开发规范（必须遵守）

### Git 身份 —— ⚠️ 最容易出错，务必看清
- 本仓库是 **Clycheng 的私有仓库**(`git@github.com:Clycheng/agentpulse.git`)。
- 提交署名**必须**是 `Clycheng <30332511+Clycheng@users.noreply.github.com>`(已配在本仓库 local git config)。**绝不能用其他身份(尤其 unitpulse / UP 的邮箱)提交**——本机存在多套 git 身份，别串。
- 在 `main` 分支上开发(项目所有者指定)。
- commit message 用**英文**、祈使句(与现有历史一致)。

### 动手前
- 读 `AGENTS.md` + `docs/ARCHITECTURE.md` + `docs/decisions/`。
- 任何偏离 §1/§2 方向的想法，**先跟项目所有者确认再动手**。

### 做完后必须记录（重要 —— 让下一个 AI 也不跑偏）
1. **架构/方向级决策** → 在 `docs/decisions/` 新增一条 ADR(见该目录 README 的格式)。
2. **值得记的改动**(新功能、重构、依赖变化) → 更新 `CHANGELOG.md`。
3. **相关文档过时了** → 同步更新(尤其本文件 §2/§3/§4)。
4. **声明"完成"前先验证**：跑起来看真实行为(build/测试/截图)，别空口说做完了。

### 文档如何随项目生长（对齐 AGENTS.md / Claude Code 官方实践）
- **本文件保持精简可扫(目标 <200 行)**，是"入口 + 规则 + 索引"；厚重内容放 `docs/`。
- **子项目专属规范** → 在该目录放**嵌套 `AGENTS.md`**(agents 就近读取，最近的生效)，如 `apps/desktop/AGENTS.md`、`services/api/AGENTS.md`、未来的 Hermes 集成目录。
- **按文件类型/路径的专项规则** → 放 `.claude/rules/*.md`，可加 `paths:` frontmatter 只在动相关文件时加载(注：`.claude/` 已 gitignore，需要团队共享的规则要调整忽略策略)。
- **可复用的多步流程** → 做成 skill 按需加载，而不是塞进本文件。
- 目的：靠"就近嵌套 + 路径域规则 + skills"控制上下文，别把根 AGENTS.md 堆大。

---

## 6. 文档索引

| 文件 | 内容 |
|---|---|
| [README.md](README.md) | 产品愿景(高层，稳定) |
| [AGENTS.md](AGENTS.md) | **本文件**：方向 + 架构 + 规范(接手第一读) |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 详细架构 + 调研结论 + 出处。**这就是 `docs/workflow.md`/`docs/backlog.md` 里 Architecture 阶段要产出的那份文档**——两边指的是同一份，只是大小写不同(历史遗留)，不要另建 `docs/architecture.md` |
| [docs/decisions/](docs/decisions/) | 架构决策记录(ADR)，含决策约定 |
| [docs/research/](docs/research/) | 竞品/开源项目调研(如 `dust.md`、`skill-source-repos.md`)，**已调研但未拍板**——区别于 `docs/decisions/`(已拍板) |
| [docs/prd.md](docs/prd.md) | MVP 产品需求文档：范围、用户故事、非目标 |
| [docs/backlog.md](docs/backlog.md) | Epic/Story/Task 拆分、验收标准、依赖图、assignee 建议 |
| [docs/workflow.md](docs/workflow.md) | 项目自己的研发闭环流程(Research→PRD→Architecture→Backlog→Build→QA→Retrospective)，含 `agentpulse-*` 角色分工 |
| [CHANGELOG.md](CHANGELOG.md) | 变更记录 |
| [ROADMAP.md](ROADMAP.md) | 早期路线(部分已被 §2 取代，见警告) |
