# Changelog

本文件记录 AgentPulse 值得留痕的改动。**每次做完实质工作请在顶部追加一条**（见 [AGENTS.md](AGENTS.md) §5）。
架构/方向级决策另记在 [docs/decisions/](docs/decisions/)。格式参考 [Keep a Changelog](https://keepachangelog.com/)。

## [Unreleased]

### 2026-07-10（TD-07-T2 API 半：按职位招人的后端契约）
- **feat(api)**: 为"按职位一键招人"提供后端契约（前端"按职位选"UI 待做）。
  - `GET /api/role-bundles`（`routes/catalog.py`，认证）：列出 12 个预配角色及其 `capability_keys` 与 `resolved`（合并后的 toolsets/mcp/creds/risk_gate），供创建员工弹窗渲染选项。
  - `POST /api/agents` 的 `role_spec` 新增可选 `role_bundle_key`：有值时经 `get_role_bundle` 展开并"bundle 优先去重"并入 `capability_keys`（可与手动勾选叠加）；未知角色 → 400。
  - 测试：新增 `test_role_bundles_api.py` 5 例（列角色 + 认证要求、按角色建员工能力自动填齐、bundle 与显式 key 合并、未知角色 400）。全套 **199 测试通过**（+5）。

### 2026-07-10（TD-07-T1：业务岗位能力目录扩展）
- **feat(api)**: 让"用一句话招人"覆盖业务岗，不只是技术岗。
  - `orchestration/capability_catalog.py` 在技术岗种子外补齐 **7 大类 31 个业务能力**：客服（customer_service/ticket_management/refund_processing/customer_data_lookup）、内容运营（content_writing/image_creation/email_drafting/email_sending/seo_content/ad_analysis/ad_bidding）、数据（data_query/data_analysis/report_generation/web_scraping）、HR、法务、财务（含 `payment_execution` = `prohibited_auto`，花钱不可逆永不自动）、项目管理。
  - 新增 `ROLE_BUNDLES`（12 个预配角色：客服专员/数据分析师/HR 专员…→ 能力清单）+ `get_role_bundle(name)`/`list_role_bundles()` 访问器；供 TD-07-T2"按职位一键招人"用。
  - 对齐修正：种子里 `social_content` 的 toolsets 由代码侧 `[web,vision]` 补成与 DATA-MODEL §6.3 真相源一致的 `[web,vision,image_gen]`（此前 TD-05 代码与真相源不一致）。
  - 测试：`test_capability_catalog.py` 扩到 33 例——把"CATALOG 恰好 8 个种子键"的断言改为"种子键 ⊆ CATALOG"，新增业务条目合法性（description/risk_gate 合法、有 MCP 必声明凭证）、`ROLE_BUNDLES` 全部 key 都在 catalog、每个角色能 resolve_bundle 不报错、未知角色报错。全套 **194 测试通过**（+10）。DATA-MODEL §6.3 同步。

### 2026-07-10（TD-09-T2：渠道管理 API + 公开 Webhook 端点）
- **feat(api)**: 把 TD-09-T1 的 channel router 接成一条可 curl 验证的完整入站链路。
  - `app/services/channels.py`：渠道 CRUD（create 生成 `token` + 返回 `webhook_url`、list、get+stats、patch、软删 active=0）、`channel_stats`（今日入站数 / 活跃外部用户数）、`verify_signature`（URL token 为主凭证；config 里配了 `secret` 则额外校验 `X-Signature` = HMAC-SHA256(raw_body)）。
  - `app/api/routes/channels.py`：`/api/channels` 认证 CRUD（含 target_agent/target_conversation 归属校验）。
  - `app/api/routes/webhooks.py`：**公开** `POST /webhooks/{channel_type}/{token}`（不挂 /api、无 JWT）——按 token+type 查 active 渠道 → 验签 → 解析 JSON → `route_inbound` → 若渠道 pin 了 target_agent，经现有 `complete_agent_reply` **尽力触发一次回复**（执行层报错则吞掉、仍返回 200，消息已落库）。
  - 新增 email 适配器（SendGrid/Mailgun inbound-parse 风格，按 from/text 归一化）；注册表现覆盖 generic_webhook + email；微信(XML+加密)/widget 留 TD-09-T3。
  - 测试：新增 `test_channels_api.py` 8 例（CRUD + 未知 target 拒绝、webhook 入站落库、去重、stats、未知/停用 token→404、缺/对 HMAC 签名→401/200、不支持渠道类型→400、mock LLM 下 target_agent 触发 agent 回复）。全套 **184 测试通过**（+8）。DATA-MODEL §9.2/9.3 标记已实现。

### 2026-07-10（TD-09-T1：外部渠道数据模型 + Router 核心）
- **feat(api)**: 外部渠道接入地基——外部消息(微信/邮件/网页/通用 webhook)进来后归一化成标准消息、进入普通会话流，**agent 完全不感知渠道**（纯数据 + Router，不接 webhook 端点/不碰 Hermes）。
  - schema（双 schema + `ensure_column`）：新增 `channel_configs`（channel_type CHECK、token UNIQUE、config_json、target_agent_id/target_conversation_id、active 存 INTEGER 0/1）；`conversations` 加 `source_channel`/`external_conversation_id`；`messages` 加 `external_message_id`（webhook 重发去重）。
  - `app/channels/`：`adapters/`(base `ChannelMessage` + `generic` 适配器按可配置点路径 `message_path`/`user_id_path`/`message_id_path` 提取 + 注册表 `get_adapter`)；`router.py` 的 `route_inbound`(归一化→找/建会话→去重→落 `sender_type='user'` 消息)、`find_or_create_conversation`(pin 固定群 / 按 `(source_channel, external_user_id)` 归线程)、`message_already_processed`。留 TD-09-T2 触发 agent 回复的接缝。
  - 测试：新增 `test_channels.py` 6 例（建会话+消息+外部字段、按 external_message_id 去重、同一外部用户归一会话且不同用户分开、pin 固定群路由、无 message_id 不去重、自定义嵌套路径 + 缺内容报错）。全套 **176 测试通过**（+6）。DATA-MODEL §9.1 标记已实现。

### 2026-07-10（TD-08-T1：Idea 中心数据模型 + API）
- **feat(api)**: 落地北极星 §1.5「没有 idle 员工 → idea 中心」的后端地基（纯数据 + API，不接 Hermes）。
  - schema（双 schema + `ensure_column` 迁移）：新增 `ideas` 表（category/status 带 CHECK 约束，`converted_brief_id` 追溯转化）；`agent_specs` 加 `last_idle_think_at`/`idle_think_interval_hours`/`idle_thinking_enabled`；`conversations` 加 `idea_id`（追溯从哪个 idea 转来的会话）。
  - `app/services/ideas.py`：create/get/list（按 new 优先 + status/agent/category 过滤）/review（accept→accepted、dismiss→dismissed）/convert（建 group 会话 + 拉入 source agent + 首条系统消息=idea 内容 + 回链 `conversations.idea_id` + idea→converted）/set_idle_thinking。
  - `app/api/routes/ideas.py`（注册进 main）：`GET/POST /api/ideas`、`GET /api/ideas/{id}`、`POST /api/ideas/{id}/review`、`POST /api/ideas/{id}/convert`、`PATCH /api/agents/{id}/idle-thinking`；业务逻辑在 service 层，路由只做 HTTP。
  - 两处实现偏差（已回填 DATA-MODEL §8）：`idle_thinking_enabled` 两方言统一存 `INTEGER 0/1`（迁移用单一定义字符串），API 序列化为 bool；idle-thinking 接口返回精简的 `IdleThinkingSettings` 而非 `AgentSpecOut`（无 spec 的员工返回 404）。
  - 测试：新增 `test_ideas.py` 8 例（CRUD、new 优先与过滤、review、convert 建会话并直查 DB 断言 `idea_id` 回链、重复 convert 拒绝、schema 422、DB CHECK 约束、idle-thinking 更新与无 spec 404）。全套 **170 测试通过**（+8）。DATA-MODEL §8.1 标记已实现。

### 2026-07-09（前端重做：桌面端设计系统升级）
- **feat(desktop)**: 用 impeccable 前端 skill 重做桌面端 UI（`apps/desktop/src/styles.css`，纯样式层，不动 `main.tsx` 逻辑/结构，功能不受影响）。
  - **方向**：从"通用浅色 + SaaS 蓝 + 扁平卡片"升级为「一人 AI 公司运营驾驶舱」。register=product（对标 Linear/Raycast 的克制）。配色策略 Restrained：中性 ink 底 + **单一品牌色 teal「脉搏」**（语义=员工 7×24 在工作），teal 只用于主操作/选中/focus/live 状态；success/warning/danger 与品牌色分色相；保留并沿用 per-agent `hue`（外壳克制、人物带色）。
  - **Token 层重写**：`:root`（浅色）+ `[data-theme='dark']`（近黑 cockpit + 更亮 teal）全套 token——中性梯度、品牌 teal 家族（含 `--on-primary`/`--primary-strong`）、语义色带 soft 变体、4 级 `--shadow-*` 高度、teal `--ring`、圆角(含 pill)、`--ease-out`；字体 Latin=Inter + CJK=Noto Sans SC。
  - **组件精修**：全局 `:focus-visible` teal ring + 交互过渡 + `prefers-reduced-motion` 兜底 + `pulse-ring` 关键帧（仅 live 指示器）；按钮/小按钮补齐 hover/active/disabled 全套状态与阴影；侧栏品牌 mark 改 teal 渐变芯片、active 导航加 teal 指示条；search-box 变真输入(border+focus ring)、composer focus ring + send 全状态、卡片加 xs 阴影、pill 圆角、清理残留写死蓝（auth 渐变/focus 改 teal token）。
  - **对比度**：按 skill 要求把 `--subtle`（placeholder/timestamp）在两套主题都调到达标。
  - 浏览器预览验证：消息/人才市场/任务/员工四视图 + 浅色&深色两主题均已截图确认级联正确、无 console 报错。新增 `apps/desktop/AGENTS.md` 固化设计系统，防后续 AI 改回通用蓝。

### 2026-07-09（TD-03-T1：Run/RunStep 数据模型）
- **feat(api)**: 为接 Hermes 执行铺好数据地基（纯 schema + 生命周期，不起 Hermes）。
  - `database.py` 两套 schema（SQLite + Postgres）+ `ensure_column` 迁移：`runs` 扩 `task_id`/`hermes_profile_id`/`hermes_run_id`/`workdir`（新列暂可空，NOT NULL 与"每个 Run 必属 Task"由 TD-03-T3 的 RunService 在应用层强制）；新增 `run_steps` 表（映射 Hermes SSE 事件：message/thinking/tool_call/tool_result/approval_required/status/final）；`approvals` 加 `run_id`（批准后据此恢复对应 Run）+ `type`（high_risk/clarification/capability_upgrade，行为在 T4）；`agents` 加 `hermes_gateway_port`（一员工一 gateway 一端口）。引用 `runs` 的 FK 列走 `ensure_column`（在 runs 建表之后加），规避 Postgres 前向引用报错。
  - 新增 `app/runtime/runs.py`：Run 生命周期状态机（`queued → running → waiting_user|waiting_clarify → completed|failed`，非法转移抛 `RunStateError`，终态 stamp `completed_at`）+ `create_run`/`transition_run`/`append_run_step`/`list_run_steps`（支持 `after_step_id` 增量拉取，对接 TD-03 前端轮询契约）。
  - 测试：新增 `test_run_lifecycle.py` 13 例——状态机合法/非法转移、终态无出边、失败记 error、run_steps 追加+增量列出、以及对真实 `init_db()` 跑迁移并断言新列/新表存在且幂等。全套 **162 测试通过**（+13）。
  - DATA-MODEL §5.1/§5.2 标记为已实现；解锁 TD-03-T2（HermesBackend，需 agentpulse 会话起 Hermes）。

### 2026-07-09（TD-02-T5：路由归位，修复架构漂移）
- **fix(api+orchestration)**: 消除 2026-07-08 复核发现的结构性漂移，把群讨论编排真正收回编排层。
  - `orchestration/discussion.py::run_discussion_round` 从"只被单测调用的死码 + 同步 dict 返回"**重写为 async 事件流**（yield `speaker`/`chunk`/`message`/`error`/`end` 事件），成为群讨论的**唯一生产入口**。`send_message`（非流式）和 `send_message_stream`（流式）都改为 `async for event in run_discussion_round(...)` 驱动它——路由层只注入 `turn_executor`（如何执行一轮 agent 回复 + 持久化）和 `llm_complete`（主持人 LLM 执行层薄封装，由新的 `make_speaker_selector()` 构造），再把事件翻译成各自传输格式（SSE 帧 / 累积列表）。
  - 发言人选择逻辑（@提及 → 主持人 LLM → 轮询降级）全部收敛到编排层：新增 `resolve_next_speaker`（端到端解析，内部经注入的 `llm_complete` 调 LLM），路由层的 `_llm_select_speaker`/`_extract_mention_simple` **删除**；`_build_discussion_context` 迁移为编排层 `build_discussion_context`。
  - 编排层保持零外部 HTTP：LLM 调用一律经注入回调，`app/orchestration/` 内无 `httpx`/`requests`/`hermes_client`。
  - 测试：`test_discussion.py` 按新 async 契约重写 `TestRunDiscussionRound`，新增 `TestResolveNextSpeaker`/`TestParseSpeakerJson`/`TestBuildDiscussionContext`（覆盖从路由迁入的 LLM 选人逻辑）；`test_workspace_flow.py` 新增 `test_stream_group_discussion_routes_through_orchestration`——mock `run_discussion_round`，向 `/messages/stream` 发真 HTTP 请求断言生产路径确实经过编排入口（不是单测直调函数的假验收）。全套 **149 测试通过**（较基线 137 +12）。
  - 三条禁止模式 grep 全干净（路由无业务循环/私有 LLM 选人、生产入口真调 run_discussion_round、编排无直连 HTTP）。
  - Verified: run_discussion_round called via production path POST /api/conversations/{id}/messages/stream（及 /messages）；解锁 TD-03-T2/T3。

### 2026-07-08（架构复核：发现真实漂移）
- **docs(architecture-audit)**: 用户直接质问"AI 干的活方向有没有飘"，做了一次彻底代码复核（不只是接口签名，而是追调用链），确认**是，且是结构性漂移，需要纠正**：
  - `orchestration/discussion.py::run_discussion_round`(TD-02 设计的核心编排入口)在生产环境是**死代码**——只被单测调用，`api/routes/workspace.py` 的 `send_message`/`send_message_stream` 从未真正调用它。372 行单测全过，但只测了一个生产请求走不到的函数，给出"TD-02 已完成"的假象。
  - 路由层里独立写了**两份重复的讨论循环**(非流式/流式各一份)，外加一套单独的 `_llm_select_speaker`+`_extract_mention_simple`(跟编排层的 `select_next_speaker` 功能重叠、优先级还反过来)，直接违反 ARCHITECTURE-DETAILED.md §3.1 的边界层职责("不写业务逻辑")。
  - 风险点：TD-03-T3 原计划替换 `complete_agent_reply` 的执行部分，但该函数只被前端已弃用的非流式 `/messages` 调用；前端现在只走 `/messages/stream`(`_stream_agent_reply`)。若不纠正直接做 TD-03，会把 Hermes 接到用户实际走不到的死路径。
  - **纠正**：新增 [TD-02-T5](docs/tech-design/TD-02-multi-agent-discussion.md#td-02-t5)（路由归位：重复实现收回 orchestration 层，唯一化发言人选择入口），列为看板最高优先级，**TD-03-T2 及以后新增依赖 TD-02-T5**（TD-03-T1 纯 schema 不受影响）。TD-03 设计文档同步更正真实执行入口。看板"已完成"表补注该风险，避免误读为"TD-02 已可靠交付"。
  - 未直接修改代码（分工：本侧只出设计/纠正，实现交给 worker AI）。

### 2026-07-08（架构侧收尾）
- **docs(backfill)**: 完成验证报告(`19c209b`)遗留的回填义务——V1–V7 实测事实写入 DATA-MODEL §5.3(Runs API 真实请求体/Tirith 审批配置/一 profile 一 gateway 一端口/MCP·skills·profile 打包命令/25 个 toolset 真名)；§6.3 catalog 种子改用真名(`file` 不是 `files`)；TD-03 开放问题全关(含 **workdir 架构决策**：Runs API 无 per-run cwd → profile 级绝对 work root + 每 Run 子目录约定，硬边界在员工 work root)；TD-04-T6/TD-05/ARCHITECTURE/agent-model 的〔待核〕全部替换为实测事实。
- **docs(board)**: 重建执行看板——修复指向不存在文件的坏链接、错乱编号；"待提交"条目全部换成真实 commit 号(TD-02=`b61005e`、TD-04-T3=`f55d0b1`、T4=`81af20d` 等)；新队列=端到端手测 / TD-03-T1 / TD-04-T6(已解锁)。维护规则加两条：链接必须指向真实文件、完成必须带 commit 号。
- **chore(cleanup)**: 删除验证会话遗留的 `~/.local/bin/vtest3` wrapper(报告自标的污染)；UnitPulse 干净检查通过；全量测试 137 passed 复核通过。

### 2026-07-08（四）
- **docs(readme)**: README 全面重写——修掉 ADR 0001 之前的过时内容(旧 mermaid 里的 Local Runtime/Tool Broker/多 LLM Provider、Roadmap Phase 3 的 provider adapters、"Agent runtime: Planned" 状态)，对齐当前架构(自研编排层 + Hermes 每员工一 profile)与真实进度(群讨论第一片✅、Hermes PoC✅)。SEO/GEO 优化：双语定义句前置 + 英文 Overview、徽章、三方对比表(vs 聊天机器人 vs 自动化平台)、FAQ 问答区(6 问，LLM 引用友好)、关键词/Topics 区、按读者分流的文档导航表、精简 Quick Start。

### 2026-07-08（三）
- **docs(tech-design)**: 新增 [EXECUTION-BOARD.md](docs/tech-design/EXECUTION-BOARD.md)——唯一任务状态源，让任何 AI 冷启动读仓库即知"下一步做什么"(现在就做队列/依赖阻塞表/已完成表/认领锁规则：开工第一动作=改看板为进行中并 push)，不再需要人类口头派单。AGENTS.md §4"下一步"改为第一跳指看板；执行协议第 2/5 条改为"领任务/完成都在看板标状态"(TD 文件不标，防两处漂移)。

### 2026-07-08（二）
- **docs(tech-design)**: 分工定版——本侧只产设计文档，实现由 worker AI 执行。为此补齐三块：① [HERMES-VERIFICATION-PLAYBOOK](docs/tech-design/HERMES-VERIFICATION-PLAYBOOK.md)(把清〔待核〕变成可执行剧本 V1–V7：toolsets 真名/MCP 语法/技能安装/单网关多 profile/审批触发/打包分发/workdir 语义，含硬性安全前置与回填清单)；② TD-03 加深到字段级(SSE事件→run_steps 映射表、RunService 签名、v1 前端轮询决策、**发现并补上 `approvals.run_id` schema 缺口**——没它批准后找不到该恢复哪个 Run，已进 DATA-MODEL §5.1)；③ TD-02 加深到字段级(send_message 接线点、配置常量、发言人选择严格 JSON 契约+降级、收敛判定契约、prompt 约束、防刷屏)。README 新增 V 线(建议最先执行)与"Worker AI 执行协议"6 条。

### 2026-07-08
- **docs(tech-design)**: 新增 [TD-05](docs/tech-design/TD-05-capability-catalog.md)(能力映射表：代码常量模块+resolve_bundle 合并规则+risk_gate 只升不降+domain_register 永远 prohibited_auto) 与 [TD-04](docs/tech-design/TD-04-agent-provisioning.md)(Agent 供给完整详细设计：v1 入口=创建员工表单而非聊天以解耦 TD-02；供给分逻辑/物理两段，`ProfileProvisioner` 接口把接缝正好切在〔待核〕Hermes 边界上，RecordOnly 实现让 T1–T5 全部可先做可测；role_spec LLM 起草+代码硬校验；SOUL 生成；凭证不落库直写 profile .env；供给状态机+幂等重试；6 个 task 中仅 T6 需 agentpulse 锚定会话)。阶段表新增 D 线(与 B/C 可并行)。

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
