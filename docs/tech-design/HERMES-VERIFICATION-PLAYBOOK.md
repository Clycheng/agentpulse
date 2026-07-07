# Hermes 验证剧本（worker AI 执行版）

> 目的：把散布在各 TD 里的〔待核〕项**一次实测钉死**，并回填权威文档。执行者照本剧本逐项做即可；每项都写明"怎么测 / 记什么 / 回填到哪"。
> 产出不是代码，是**被验证的事实**——回填后 TD-03 / TD-04-T6 / TD-05 才没有猜测成分。

## 0. 硬性安全前置（一条都不能省）

1. **必须在 cwd 锚定于 `/Users/liuxiajiang/Desktop/code/agentpulse` 的会话执行**；绝不在 UnitPulse 仓库/worktree 内起任何进程（AGENTS.md §5、[ADR 0005](../decisions/0005-hermes-poc-safety-findings.md)——上次就是这么把文件写进无关项目的）。
2. 全程使用**隔离环境**：独立 venv + 独立 `HERMES_HOME`（绝对路径，如 `<repo>/.hermes-verify/home`，已在 `.gitignore` 的位置或临时目录），不碰机器上已有的 `~/.hermes`（那是用户个人环境，无关本项目）。
3. `hermes profile create` 一律带 **`--no-alias`**（否则会写 wrapper 到 `~/.local/bin` 污染全局——实测踩过）。
4. 任何跑 agent 的测试前，显式 `config set terminal.working_dir <绝对路径>`；测试后检查该目录外无落盘。
5. 结束时：杀干净所有 hermes 进程；`git -C /Users/liuxiajiang/Desktop/unitpulse status --porcelain` 确认 UnitPulse 干净（标准收尾）。

## 1. 环境搭建（已验证可行的做法，照抄）

```bash
cd /Users/liuxiajiang/Desktop/code/agentpulse && mkdir -p .hermes-verify && cd .hermes-verify
python3 -m venv .venv && source .venv/bin/activate
pip install -q hermes-agent                       # 实测 v0.18.0 可用
export HERMES_HOME="$PWD/home" && mkdir -p "$HERMES_HOME"
echo "DEEPSEEK_API_KEY=<从环境取>" > "$HERMES_HOME/.env"
hermes profile create vtest --no-alias
hermes -p vtest config set model deepseek/deepseek-v4-flash   # ⚠️ 不是 deepseek-chat（实测）
hermes -p vtest -z "回复:OK"                                   # 冒烟：应回 OK
```

## 2. 验证项清单（逐项：怎么测 → 记什么 → 回填哪）

### V1 toolsets 真名清单
- 测：`hermes -p vtest tools list`（及 `tools --summary`）。
- 记：全部 toolset 名 + 默认开/关状态；`tools enable/disable <name>` 的确切用法。
- 回填：[TD-05](TD-05-capability-catalog.md) catalog 里的 `toolsets` 占位换真名；[DATA-MODEL §6.3](DATA-MODEL-AND-API.md) 同步。

### V2 per-profile MCP 配置语法（TD-04-T6 关键）
- 测：查 `hermes mcp --help` / `config.yaml` 注释 / 官方 docs；给 vtest 配一个最简 MCP server（如官方 filesystem/github mcp），确认 config 写法与生效方式（重启 gateway 是否必需）。
- 记：确切 config 键路径与 JSON/YAML 形状；凭证如何供给（.env 键名约定？）。
- 回填：DATA-MODEL §5.3/§6；[TD-04](TD-04-agent-provisioning.md) `configure()` 实现说明。

### V3 技能安装机制（TD-04 `install_skills`）
- 测：`hermes skills --help`；从一个 tap 装一个技能（如 `hermes skills tap add HKUDS/CLI-Anything` 或本地目录方式）；确认落盘位置 `profiles/vtest/skills/`。
- 记：编程化安装的确切命令；`/learn` 能否非交互触发（`-z "/learn <url>"` 试一次）。
- 回填：TD-04-T6；[agent-model-and-capabilities.md](agent-model-and-capabilities.md) §7。

### V4 单网关多 profile？（TD-03 部署模型关键）
- 测：再建 `vtest2 --no-alias`；起 vtest 的 gateway（`API_SERVER_ENABLED=true API_SERVER_PORT=8642`）后，检查 `/v1/*` 能否指定 profile（看 docs/`gateway list`）；不行则起第二个 gateway 换端口验证双进程并存。
- 记：结论=单网关多 profile ✅/❌；多进程时端口分配与资源占用（RSS）。
- 回填：TD-03 §开放问题1/2；[ARCHITECTURE-DETAILED](ARCHITECTURE-DETAILED.md) §2 拓扑表。

### V5 per-tool 风险/审批配置（TD-03-T4 关键）
- 测：查 `config.yaml` 里 approval/tool 权限相关键（及 issue #476 是否已合入该版本）；找一个能触发 `approval_required` 的配置或工具（写文件默认不触发——实测）；经 Runs API 触发一次，走 `POST /v1/runs/{id}/approval` 放行与拒绝各一次。
- 记：触发条件的确切配置；approval 请求/响应体形状；拒绝后 agent 行为。
- 回填：DATA-MODEL §5.4；TD-03-T4 验收细节。

### V6 profile 打包/分发（人才市场模板机制）
- 测：`hermes profile export/import/install --help`；export vtest 再 import 成 vtest3，确认 SOUL/skills/config 是否随包。
- 记：包格式与命令；`profile install <git-url>` 是否可用。
- 回填：TD-04 §决策 B、agent-model §2。

### V7 workdir 每 Run 隔离的可行做法（ADR 0005 落地方式）
- 测：`config set terminal.working_dir <abs>` 是 profile 级还是可按 run 覆盖？查 Runs API 请求体有无 cwd/workdir 参数。
- 记：结论——若只能 profile 级，TD-03 的"每 Run 独立 workdir"需改为"每 Run 前改写 profile config 或复用 profile 级目录+子目录约定"，把选定方案写清。
- 回填：TD-03 §技术设计、DATA-MODEL §5.1 `runs.workdir` 语义。

## 3. 交付物
1. `docs/research/hermes-verification-YYYY-MM-DD.md`：每项 V1–V7 的命令、原始输出要点、结论（✅/❌/部分）。
2. 上述"回填哪"全部落实（DATA-MODEL/TD-03/TD-04/TD-05/ARCHITECTURE 里的〔待核〕标记替换为实测事实，并在 CHANGELOG 记一条）。
3. 清理：进程杀净、`.hermes-verify` 可留作后续验证复用（确认在 .gitignore 内）、UnitPulse 干净检查通过。
