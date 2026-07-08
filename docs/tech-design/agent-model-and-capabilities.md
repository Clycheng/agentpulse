# Agent 模型与能力体系（一个 agent 到底怎么"有本事")

> 回答"每个 agent 怎么获得多种专业能力、小秘书凭什么特殊、一句话怎么变成定制 agent、24×7 怎么像真员工"。
> **可信度标注**：`〔实测〕`= 本机亲手验证过；`〔研究〕`= 本会话调研得出(见 [ARCHITECTURE.md §5](../ARCHITECTURE.md) 出处)；`〔待核〕`= 推断，编码前须对 Hermes 文档/实测确认，别当既定事实；`〔常识〕`= 稳定的行业事实(MCP 生态、各类 API)。

---

## 0. 一句话心智模型：agent = 一个底座 + 四层叠加

**每个 AI 员工 = 一个 Hermes profile〔实测〕。空 profile 就是"基础 agent"。往上叠四样，就成了某个工种：**

| 层 | 是什么 | 决定 | 载体 |
|---|---|---|---|
| 人格 SOUL.md | 他是谁 | 角色/口吻/边界/"背景不清先问" | `profiles/<name>/SOUL.md`〔实测〕 |
| 技能 Skills | 他会怎么做（KNOW-HOW，流程知识） | "做 SEO 审计的步骤""发 PR 的规范" | `profiles/<name>/skills/*/SKILL.md`〔研究〕 |
| 工具/MCP | 他能实际动手做什么（POWER，执行力） | 跑 shell、调 GitHub、部署 | config.yaml 的 toolsets + `mcpServers`〔实测起过gateway/tools；per-profile MCP 语法待核〕 |
| 凭证 | 钥匙 | 每个外部服务的 token | `profiles/<name>/.env`〔实测〕 |
| 模型 | 脑子 | 推理/工具调用能力 | config.yaml `model`〔实测 deepseek-v4-flash〕 |

**最关键的区分(直接回答"一个工种 N 个技能怎么连"）：**
- **技能(SKILL) = 教他"怎么做"**，是流程/知识，本身不产生执行力。
- **工具/MCP = 给他"能做"的权力**，是真正能跑 shell、调 API 的东西。
- 有工具没技能 = 会乱来；有技能没工具 = 纸上谈兵。
- **一个"工种" = 一批技能 + 一批工具/MCP 授权 + 对应凭证，打包进一个 profile。** 比如"前端工程师"= {写码/测试/发 PR/部署 的技能} + {terminal 工具 + GitHub MCP + 部署 CLI} + {GitHub token + 部署平台 token}。

---

## 1. 小秘书凭什么特殊（Q1）

**它不是"更强的 agent"，底座和别人完全一样。区别只在两处：人格 + 工具面。**

- **人格**：它的 SOUL.md 是"老板秘书/参谋长"——职责是澄清、拆解、路由、汇报、提醒拍板，**不是自己去干专业活**。(可从 agency-agents 的 `chief-of-staff` 人格改造，见 [skill-source-repos.md](../research/skill-source-repos.md)。)
- **工具面**：它挂的是**编排类**能力(`delegate_task` / `hermes kanban` 的 decompose+route〔研究〕)，**不挂执行类工具**(不给它部署/域名权限)。它协调别人干，自己不下场。
- **在 AgentPulse 里它还兼三个系统角色**：① 群讨论的**主持人**(TD-02，选发言人、收敛 brief)；② 把"我要个前端工程师"这种话**变成一个新 agent** 的发起者(见 §3)；③ 对齐后**把任务路由**给专业员工。

→ **根本区别 = 职责范围(scoping) + 人格，不是不同的底座。** 任何 agent 理论上都能被配成秘书,只是我们只给秘书编排工具、不给执行工具。

---

## 2. agent 怎么创建、有没有基础 agent（Q2）

- **有基础 agent**：`hermes profile create <name>`〔实测〕生成一个空 profile（默认 SOUL、0 技能、最小工具）。这就是"基础 agent"。
- **造一个员工 = 在基础 profile 上做 5 件事**：写 SOUL.md → 装技能包 → 开 toolsets → 配 MCP 服务器 → 设模型 + 放凭证。
- **可复用的工种模板**：把一个工种打包成"profile 发行版 / 技能 tap(GitHub 仓库)"，`hermes profile install <git-url>`〔待核，profile install 机制存在但确切用法要确认〕。**AgentPulse 的"人才市场" = 一堆这种工种模板的目录**，招人=选模板装成 profile。

---

## 3. 一句话 → 自动生成定制 agent：数据流转（Q3 + Q4 的定制部分）

用户对小秘书说「我要个前端工程师」，系统内部流转：

```
① 用户 NL 需求  ──→  小秘书(LLM)解析成"角色规格 role_spec"(结构化)
② role_spec  ──→  能力映射表(§5) 翻译成具体 bundle
③ bundle  ──→  provision: 建 profile + 写 SOUL.md + 装技能 + 配 tools/MCP + 列出要用户提供的凭证
④ 缺凭证的能力  ──→  挂起，向用户索要(GitHub token 等)；花钱/不可逆的能力标为"需审批"
⑤ profile 就绪  ──→  员工出现在组织架构，idle→可用
```

**role_spec 数据结构〔待定，本项目要设计的新对象〕**：
```json
{ "role_name": "前端工程师",
  "responsibilities": ["实现页面","写测试","发 PR","部署预览环境"],
  "needed_skills": ["frontend-build","testing","git-pr-flow","deploy-preview"],
  "needed_toolsets": ["terminal","files","web"],
  "needed_mcp": ["github"],
  "needed_credentials": ["GITHUB_TOKEN","VERCEL_TOKEN"],
  "risk_gates": {"deploy_prod":"approval","domain_purchase":"prohibited-auto"} }
```
- **②的能力映射表是本项目的核心资产**(§5)：把"职责词"→"具体技能 + 工具/MCP + 凭证 + 风险等级"。小秘书 LLM 出草稿，映射表做兜底和安全约束。
- **SOUL.md 自动生成**：LLM 按 role+responsibilities 起草人格〔研究：SOUL.md 就是 markdown，可生成〕，可参考 agency-agents 现成人格。
- **凭证绝不自动伪造**：需要用户在密码管理器/设置里提供(部分如支付/域名购买按安全规则**禁止 agent 自动输入**)。
- 落库：复用现有 `agents` 表 + 新增 `role_spec`/能力授权关联表〔本项目要建，字段回填 [DATA-MODEL-AND-API.md](DATA-MODEL-AND-API.md)〕。

---

## 4. 前端工程师能做到什么程度：能力逐条落地（Q4 核心）

"一个工种 = N 个技能"，每个能力 = **技能(教流程) + 工具/MCP(给权力) + 凭证 + 风险门**。逐条给方案和现成度：

| 能力 | 靠什么执行(POWER) | 现成度 | 凭证 | 风险门 |
|---|---|---|---|---|
| 写代码/改文件 | terminal + files 工具〔实测 Hermes 有 write_file/terminal〕 | ✅ 原生 | — | 低(workdir 隔离) |
| 跑测试 | terminal 跑 `pytest`/`jest`〔实测能跑 shell〕 | ✅ 原生 | — | 低 |
| 推代码/发 PR | `git` via terminal，或 **GitHub 官方 MCP server**〔常识：github-mcp-server 存在，能管 PR/issue/actions〕 | ✅ 有现成 | GitHub PAT/OAuth | 中(写远端→建议审批) |
| 部署服务 | Vercel/Netlify/Cloudflare/Fly CLI(shell)，Cloudflare 有 MCP〔常识〕 | ✅ CLI 现成 | 平台 token | **高**：预览随意、**生产要审批** |
| 注册域名 | 注册商 API(Cloudflare Registrar/Namecheap/Porkbun)〔常识：API 存在，MCP 少〕 | 🟡 API 有、多数无 MCP，得包成工具 | 注册商 API key + **付费方式** | **禁止自动**：花钱+不可逆→**必须人来**(按安全规则属购买类) |
| SEO | Lighthouse CLI(审计)、Google Search Console API、关键词(Ahrefs/Semrush 付费 API)〔常识〕 | 🟡 审计✅、数据需 API key | 各 API key | 低-中 |
| 自我测试/CI | terminal + GitHub Actions(经 GitHub MCP)〔常识〕 | ✅ | GitHub token | 低 |
| 维稳/监控/安全 | 需接监控/云平台工具，尚无一键方案 | 🔴 后置，需逐个接 | 视平台 | 高 |

**所以前端工程师 agent 能做到:自己写代码 → 跑测试 → 提交推送 → 开 PR → 部署到预览环境;到"生产部署 / 买域名 / 花钱"这些一步,停下来弹审批卡片等你拍板。** 这不是能力不足,是**故意的安全门**(产品灵魂"高风险动作等老板拍板" + 安全规则)。技术上"全自动买域名+上生产"接得通,但**我们主动不让它无人值守做这些**。
- 缺凭证的能力 → 索要凭证前做不了;
- 闭源平台无 API 的动作 → 做不了(见 §5 小红书)。

---

## 5. 小红书运营 agent + 诚实的边界（Q5）

- **人格**:运营(可基于 agency-agents 的中国市场营销人格)。**技能**:选题/文案/发布节奏/数据复盘(流程知识,可 `/learn` 或从技能 tap 装)。
- **能干的**:写文案✅(原生 LLM+技能)、配图/短视频✅(Hermes 多模态 image_generate/vision〔研究〕)、排期建议✅、复盘分析✅。
- **⚠️ 真正发到小红书**:**小红书/抖音/微信基本没有开放的发布 API**〔常识〕。只有两条路,都得跟你说清:
  1. **半自动(推荐)**:agent 把内容+排期做好 → **人来点发布**(或半手动)。
  2. **非官方自动化**(浏览器自动化 / 三方 CLI,如本机 `~/.local/bin/xhs) → **违反平台 ToS、脆弱易封**,要你明确接受风险才做。
- **结论**:小红书运营 agent 能做到"**内容生产+排期+复盘全自动,发布环节人工或高风险自动化二选一**"。这是平台现实,不是我们能力不足。

---

## 6. 24×7 像真员工能到什么程度

- **机制**〔研究/实测〕:`hermes gateway` 常驻(服务器,不关机) + `cron`(定时主动干活,无需每次人喊) + `/goal`(长期目标跨轮) + webhooks(事件触发)。
- **做得到**:运营 agent 每早 cron:"复盘昨天数据 → 产出今天3条选题 → 投到 idea 中心";工程师 agent 定时:"跑一遍测试/依赖安全扫描,有问题开 issue"。**这就是"像真员工一样上班"的形态。**
- **诚实边界**(ADR 0003/0005):这是**编排出来的勤奋,不是自发意识**;它的"成长"是技能+记忆积累,**不是模型变聪明**;发布/花钱/不可逆动作**永远等你拍板**。

---

## 7. 技能/能力从哪来(不用全自研)

| 来源 | 给什么 | 现成度 |
|---|---|---|
| Hermes 内置 toolsets | terminal/files/web/browser/多模态〔实测/研究〕 | ✅ |
| **MCP 生态** | 外部服务(GitHub/云/数据库…),有注册表可发现安装(modelcontextprotocol/servers、Smithery、mcp.so、PulseMCP)〔常识〕 | ✅ 大量现成 |
| **cli-anything**(~150 桌面软件包成 CLI+技能,已自带 Hermes 集成)〔研究〕 | Blender/PPT/PDF/Obsidian… | ✅ 见 [skill-source-repos.md](../research/skill-source-repos.md) |
| **agency-agents**(250+ 人格) | 各工种 SOUL.md 素材 | ✅ 同上 |
| 技能 tap / `/learn` | 自动/半自动生成缺的 SKILL.md〔研究〕 | ✅ |

**结论:能力主要靠"组装现成积木"(内置工具 + MCP + cli-anything + 技能 tap),自研的是"怎么把它们按工种打包 + 安全门 + 编排",不是从零造工具。**

---

## ✅ 待核清单已全部关闭(2026-07-08)
1–4 已由 [验证报告](../research/hermes-verification-2026-07-07.md) 实测钉死(MCP 语法 / profile export·import·install / Tirith 四级审批 / 一 profile 一 gateway 一端口)，事实统一回填在 [DATA-MODEL §5.3](DATA-MODEL-AND-API.md)；5 的 role_spec 表结构已定稿于 [DATA-MODEL §6](DATA-MODEL-AND-API.md)。
