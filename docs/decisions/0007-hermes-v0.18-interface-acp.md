# 0007. Hermes v0.18 集成接口：REST /v1/runs 已不存在 → 用 ACP（stdio）驱动；供给用 CLI

- 状态: 已接受并部分实现（2026-07-10；本机实测 Hermes v0.18.2；`LocalHermesProvisioner` 已实现并过 e2e）
- 日期: 2026-07-10
- 决策者: 项目所有者授权接入 Hermes（提供 DeepSeek key，要求自装 + 集成）
- supersedes: [DATA-MODEL §5.3](../tech-design/DATA-MODEL-AND-API.md) 与 [TD-03 §5.3](../tech-design/TD-03-hermes-execution.md) 中"REST `POST /v1/runs` + SSE `GET /v1/runs/{id}/events`"的接口假设；相关 [验证报告 2026-07-07](../research/hermes-verification-2026-07-07.md) 的 API 形状部分作废。

## 背景

TD-03 / DATA-MODEL §5.3 的 `HermesBackend` 设计建立在 2026-07-07 验证报告的结论上：起 `hermes gateway`（:8642，OpenAI 兼容），异步 REST Runs API（`POST /v1/runs` → SSE `/v1/runs/{id}/events` → `/approval` → `/stop`），一员工一 gateway 一端口（`agents.hermes_gateway_port`）。

2026-07-10 项目所有者给了真实 DeepSeek key、要求真正安装并集成 Hermes。本机已装 **Hermes Agent v0.18.2（2026.7.7.2）**。对照实测，上述接口假设**已经过时**：

- `hermes gateway` 在 v0.18.2 里是**消息平台网关**（Telegram/Discord/WhatsApp/Weixin…），**不再暴露 OpenAI 兼容的 REST Runs API**。
- 机器级编程接口是两条：`hermes serve`（JSON-RPC / WebSocket，:9119，桌面/远程客户端用）与 `hermes acp`（**Agent Client Protocol**，stdio JSON-RPC，给编辑器/程序化集成用）。`hermes acp --check` = OK。
- 一次性执行走 `hermes [--profile X] -z "<prompt>"`（**已实测：配好 DeepSeek 的 isolated profile 一次性返回 "OK"，key 有效**）。

即：REST `/v1/runs` 这条路**没有了**。继续照旧设计写 `HermesBackend` 会接到一个不存在的接口上。

## 决策

1. **执行传输层改用 ACP（`hermes acp`，stdio JSON-RPC）**作为 `HermesBackend` 与员工运行时的对接协议（取代 REST Runs API）。ACP 原生具备：`session/new`、`session/prompt`、流式 `session/update`（消息增量 / 工具调用 / 权限请求）——正好映射我们的 `AgentEvent`/`run_steps` 与**审批**（ACP 的 permission request = 我们的 approval）。一员工一 profile；每次 Run 起一个 `hermes --profile <p> acp` 子进程（stdio），**不再需要每员工一个 HTTP 端口**。
2. **`agents.hermes_gateway_port` 作废**（ACP 走 stdio 无端口）。列暂不删（避免迁移噪音），但 provisioner 不再写它；后续清理另开小改动。
3. **供给（provisioning）用 `hermes` CLI**，已落地 [`LocalHermesProvisioner`](../../services/api/app/runtime/profile_provisioner.py)（TD-04-T6），实测命令：`profile create <n> --no-alias --no-skills` → `--profile <n> config set model deepseek/deepseek-v4-flash` → `config set terminal.working_dir <ABS>` → `tools enable <...>` → `skills install <id> --yes` → 凭证追加进 `<profile>/.env`。
4. **workdir 铁律（ADR 0005）在代码里强制**：`LocalHermesProvisioner(work_root=...)` 要求绝对路径，否则构造即抛错；每 profile 的 `terminal.working_dir` = `<work_root>/<profile>/work`。
5. DeepSeek provider 实测：id `deepseek`，key 环境变量 `DEEPSEEK_API_KEY`，base `https://api.deepseek.com/v1`，模型 `deepseek/deepseek-v4-flash`|`-pro`。key 存 profile 的 `.env`（gitignore）与后端 `services/api/.env`（gitignore），**绝不入库/入日志/入 commit**。

## 理由

- ACP 是**面向程序化 agent 控制的标准协议**，v0.18.2 一等支持且 `--check` 通过；它的流式更新 + 权限请求语义与本项目的"分步可见 + 高风险拍板"需求天然契合，比自己解析某个私有 REST 更稳、更不容易随版本漂。
- 一员工一 profile + 每 Run 一个 acp 子进程，比"常驻 gateway + 端口分配 + 心跳"简单得多，隔离也更干净；符合 [ADR 0001](0001-hermes-as-agent-runtime.md) 复用 Hermes 原生能力的方向。
- CLI 供给已**实测可复现**（不是纸面），把它固化成代码是最低风险的第一步。

## 后果

- **好处**：`LocalHermesProvisioner` 现在能真建员工 profile（TD-04-T6 完成，e2e 过）；key 验证通过，"套壳→真运行时"的地基通了。
- **代价 / 待办**：
  - `HermesBackend`（TD-03-T2）要照 **ACP** 重写，不是 REST。需要一个 Python ACP 客户端（起子进程、stdio JSON-RPC、把 `session/update` 映射成 `AgentEvent`→`run_steps`，把 permission request 映射成 approvals）。
  - `RunService`（TD-03-T3）据此消费事件、写 `run_steps`、审批挂起/续跑。
  - DATA-MODEL §5.3 / TD-03 §5.3 要按本 ADR 重写接口段（本 ADR 为准）。
  - `agents.hermes_gateway_port` 列后续清理。
- **风险**：ACP 客户端实现 + 审批映射需在 agentpulse 锚定会话里端到端实测（真起子进程、真调 DeepSeek）后才能宣布 TD-03-T2/T3 完成——延续本项目"单测过≠真做完"的纪律。
