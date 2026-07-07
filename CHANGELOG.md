# Changelog

本文件记录 AgentPulse 值得留痕的改动。**每次做完实质工作请在顶部追加一条**（见 [AGENTS.md](AGENTS.md) §5）。
架构/方向级决策另记在 [docs/decisions/](docs/decisions/)。格式参考 [Keep a Changelog](https://keepachangelog.com/)。

## [Unreleased]

### 2026-07-07（深夜）
- **docs(tech-design)**: 新增 [ARCHITECTURE-DETAILED.md](docs/tech-design/ARCHITECTURE-DETAILED.md)——实现级系统架构脊梁：组件全景(对齐真实模块树)/运行时拓扑与部署/分层职责+接口/完整数据模型/三条核心时序(NL→agent 供给、讨论→任务、任务→Hermes 执行)/横切关注点(鉴权/凭证/审批/隔离/错误/双schema/流式/幂等)/Hermes 边界契约(调用面+假设+待核清单)/分期与组件深化索引(TD-04 供给、TD-05 catalog 待建)。
- **docs(tech-design)**: [DATA-MODEL-AND-API.md](docs/tech-design/DATA-MODEL-AND-API.md) 新增 §6"Agent 供给"权威 schema——`agent_specs`/`agent_capabilities` 两张新表(精确列/约束/状态机)、capability_catalog 种子(8 个 capability_key→bundle+risk_gate)、4 个新增 API 契约(POST /api/agents 扩 role_spec、credentials、provision、spec)；架构文档 §4.1 改为引用此节，杜绝两处漂移(G1 教训)。

### 2026-07-07（夜）
- **docs(tech-design)**: 新增 [agent-model-and-capabilities.md](docs/tech-design/agent-model-and-capabilities.md)，回答"系统怎么实现"的核心架构问题：agent = 基础 profile + 人格(SOUL.md) + 技能(教流程) + 工具/MCP(给执行力) + 凭证 + 模型；小秘书=编排角色(职责+工具面不同，非更强底座)；一句话→role_spec→自动 provision 出定制 agent 的数据流；前端工程师/小红书运营两个工种的能力逐条落地(每能力=技能+工具/MCP+凭证+风险审批门+现成开源程度)，含诚实边界(域名/生产部署/花钱须人工；小红书无开放发布 API)；能力主要靠组装现成积木(内置工具+MCP 生态+cli-anything+技能 tap)。文末列"待核清单"(per-profile MCP 语法、profile install、per-tool 风险配置等，编码前须对 Hermes 实测确认)。附注：本轮两路联网研究因环境 web 工具连续 600s 超时失败，本文档基于本会话早前成功研究 + 本机实测 Hermes 一手材料写成，推断处均标注可信度。

### 2026-07-07（傍晚）
- **docs(tech-design)**: 把 tech-design 拉到"任何人/AI 拿到即可开工"的标准。新增 [DATA-MODEL-AND-API.md](docs/tech-design/DATA-MODEL-AND-API.md)(唯一真相源：所有表/字段/类型/约束/接口/错误码精确规格，含 TD-02/TD-03 的目标 schema) 和 [the-loop.md](docs/tech-design/the-loop.md)(闭环走查锚文档，带真实数据)。核对实现代码发现并记录 4 处不对齐(G1–G5)：DB `participant_agent_ids_json` vs API `participant_agent_ids`(ADR 0006 写错，已加勘误)；`TaskOut` 缺 `consensus_brief_id`(加 TD-01-T1b 修)；`discussion_status` 未接线(TD-01-T1)；`database.py` 双 schema(init_postgres/init_sqlite)须两处同步改的硬约束。README/AGENTS.md 已指向这两份新文档。

### 2026-07-07（下午）
- **docs(tech-design)**: 新增 `docs/tech-design/` 目录，把"从第一片已完成 → 第一个真正可用的垂直闭环"的剩余工作拆成技术设计 + tech-task：[TD-01](docs/tech-design/TD-01-verify-and-harden-slice-1.md)(端到端手测并收尾第一片)、[TD-02](docs/tech-design/TD-02-multi-agent-discussion.md)(多 agent 群讨论，照 AutoGen 骨架)、[TD-03](docs/tech-design/TD-03-hermes-execution.md)(执行层换真·Hermes：Run/RunStep + HermesBackend + workdir 隔离 + 审批闭环)。每个 TD 含技术设计 + 编号 tech-task(带验收标准/依赖/是否需 agentpulse 锚定会话)。推荐顺序 A→B→C。AGENTS.md §4"下一步"与文档索引已指向这些。

### 2026-07-07
- **feat(orchestration)**: 实现 [ADR 0006](docs/decisions/0006-group-discussion-v1-first-slice.md) 群讨论协议第一片(commit `c2054bf`)：新增 `consensus_briefs` 表 + `tasks.consensus_brief_id` + `conversations.discussion_status`；新建 `orchestration/`(discussion/brief/gate)模块；`/api/briefs` 路由(create/confirm/reject/get)；**从 `send_message` 移除正则自动建任务**，Task 创建改为必须携带 confirmed brief 的门控(`gate.py`)；前端渲染共识纪要卡片(BRIEF_CARD 前缀)+ 确认/继续讨论按钮。14 tests 通过。
- **docs**: 同步文档到实际状态(上一条实现提交遗漏了此步)——`AGENTS.md` §4 从"群讨论 ❌ 未实现"更新为"🟢 第一片已实现(仅单测,未端到端手测)"并重列下一步三选项；ADR 0006 状态行标注已实现。另经实测复核 `services/api` 测试确为 14 passed、UnitPulse 仓库未被本次实现污染。

### 2026-07-05（下午）
- **docs**: 做了一次"冷读 handoff 测试"（一个零上下文 AI 只读仓库判断能否继续），结论：大方向/架构/硬规矩都接得住，但"最近这一步的具体计划"没写进仓库、且 AGENTS.md §4 旧"下一步"与实际商定计划不一致。据此新增 [ADR 0006](docs/decisions/0006-group-discussion-v1-first-slice.md) 把已认可的"群讨论协议第一片"计划（讨论态 + 共识 brief + Task 创建门、对齐用人工确认、本片不碰 Hermes）落进仓库，并附"待与所有者敲定"清单（consensus_brief schema、编排模块位置、对齐信号形式等）；同步更新 AGENTS.md §4"下一步"指向 ADR 0006，消除歧义。

### 2026-07-05
- **docs**: 完成 Hermes 本机地基验证——pip 装 `hermes-agent`、建多个 profile、用 DeepSeek 作主模型、HTTP Runs API + SSE 流式事件全链路跑通，多 profile 人格隔离验证成立。同时发现两个必须处理的坑并记为 [ADR 0005](docs/decisions/0005-hermes-poc-safety-findings.md)：① `terminal.working_dir` 默认相对路径不可信任，必须显式绝对路径隔离（验证中曾误写文件到无关的真实项目仓库，已确认全部为全新文件并清理干净，未造成数据丢失）；② SOUL.md 硬性规则不保证被遵守，印证 ADR 0002 的讨论对齐门必须由编排层结构性强制。已同步更新 `docs/ARCHITECTURE.md` §3.10 和 `AGENTS.md` §4。

### 2026-07-04
- **docs(research)**: 新增 `docs/research/skill-source-repos.md`——调研 `HKUDS/CLI-Anything`、`msitarzewski/agency-agents`、`anbeime/skill` 三个仓库能否为 Hermes 员工补技能。结论：前两个已自带官方 Hermes 集成，可分别作"工具接入"(约150项软件自动化)和"人格/技能素材"(250+ agent 人格，映射到默认员工编制)；第三个授权状态不清晰，仅作发现索引、逐一审计后引用。已列出可实现清单和建议顺序，尚未拍板/实现。
- **docs**: 补全 AGENTS.md 文档索引——之前遗漏了已存在的 `docs/prd.md`/`docs/backlog.md`/`docs/workflow.md`/`docs/research/`；并消除 `docs/ARCHITECTURE.md`(本次新增) 与 `docs/workflow.md`/`docs/backlog.md` 里提到的 Architecture 阶段产出物 `docs/architecture.md`(旧规划，从未创建) 之间的命名歧义——明确两者是同一份文档。

### 2026-07-03
- **docs**: 消除 `ROADMAP.md` 与 ADR 0001–0004 的技术歧义——不再只加警告，直接改写「Agent 底层设计」一节里所有假设"多 CLI 适配 / Codex 优先 / 本机检测多运行时"的内容(Multica 结论、Runtime 取舍表、建议架构、本机 Daemon、Runtime 优先级、后端模块目录、Day 15–19 计划)，改为与"Hermes 为唯一基座"一致的正确版本；产品愿景/MVP 边界/执行节奏方法论保留不变。
- **docs**: 对齐 AGENTS.md 开放标准 / Claude Code 官方实践——`CLAUDE.md` 改用 `@AGENTS.md` import(会话开头自动加载)；AGENTS.md 补充"文档随项目生长"约定(嵌套 AGENTS.md 就近生效 + `.claude/rules` 路径域 + skills)。
- **docs**: 新增项目基准文档，供后续 AI/开发者接手即对齐、防跑偏：
  - `AGENTS.md`（北极星 + 架构决策 + 开发规范 + 文档索引）、`CLAUDE.md`（指向 AGENTS.md）
  - `docs/ARCHITECTURE.md`（详细架构 + 调研结论 + 出处）
  - `docs/decisions/` ADR：0001 Hermes 为基座、0002 自研群讨论、0003 服务端7×24+idea中心、0004 多模态经 Hermes
  - 本 `CHANGELOG.md`
- **决策**：确定技术路线 = Hermes 为员工运行时基座 + 自研群讨论协作层(照 AutoGen) + 服务端 7×24 + idea 中心。详见 ADR 0001–0004。
- **feat(desktop)**: 聊天内联审批卡片——审批请求直接出现在对应会话，老板可当场批准/驳回（`apps/desktop`）。
- **feat(desktop)**: 聊天头部关联任务栏——会话正在驱动的任务以可点击 chip 展示（等级+状态），点击开任务详情。

<!-- 追加新条目到此区块顶部；发版时归档为带版本号的小节 -->
