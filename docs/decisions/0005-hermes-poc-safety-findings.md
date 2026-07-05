# 0005. Hermes 地基验证发现：工作目录隔离是硬需求，讨论对齐门不能只靠人格指令

- 状态: 已接受
- 日期: 2026-07-05
- 决策者: 项目所有者 + 实测发现

## 背景

按 [ADR 0001](0001-hermes-as-agent-runtime.md) 和 AGENTS.md §4 的建议，做了第一次本机 Hermes 地基验证：pip 装 `hermes-agent`（隔离 venv + 独立 `HERMES_HOME`），建了两个员工 profile（`muobai`=内容主笔、`xiaomi`=老板秘书，各自写了不同 SOUL.md），并用纯 HTTP（curl，模拟后端）驱动。

验证中发生了一起真实事故：测试"小秘遇到背景模糊的任务会不会反问"时（故意问了一句模糊的"帮我搞一下下个月的推广"），Hermes **没有反问，而是编造了一个不存在的"房产中介行业"背景，自己生成了 10 个文件，并把它们真实写进了 `/Users/liuxiajiang/Desktop/unitpulse`（另一个真实项目 UnitPulse 的主仓库根目录，不是本次验证用的隔离沙盒）**。已确认这些文件此前从未存在于 git 历史（`??` 全新未跟踪），已全部删除，UnitPulse 仓库恢复干净；本次事故未波及任何 AgentPulse 相关目录。

## 发现一：Hermes 的 `terminal.working_dir` 默认是相对路径 `.`，不能信任

`hermes config show` 显示 `Terminal → Working dir: .`——这是相对路径，实际解析依赖**调用 Hermes 进程时的操作系统当前工作目录**，而不是一个声明式的、与调用环境无关的绝对路径。当后台/编程化方式驱动 Hermes（尤其是异步/后台执行）时，这个"环境当前目录"完全可能不是调用方以为的那个目录——本次事故就是因为如此，导致 agent 的文件写入工具在错误的真实项目目录里执行。

**这不是一次性失误，是这个默认配置在"后端编程化驱动 Hermes"场景下的固有风险。**

## 决策

1. **每次为员工 profile 启动 Hermes 进程（无论是 CLI 调用、`gateway run`，还是走 Runs API），必须显式设置 `terminal.working_dir` 为一个绝对路径的隔离工作目录**，格式建议 `<server_data_root>/runs/<run_id>/` 或 `<server_data_root>/profiles/<profile>/workdir/`，绝不依赖默认的相对路径 `.`。
2. 这条要求补充进 [docs/ARCHITECTURE.md](../ARCHITECTURE.md) 的 Execution Layer 一节（Multica 式"每次任务独立 workdir"的隔离原则，现在有了具体的、来自实测的失败案例作为佐证，不再只是理论上的最佳实践）。
3. 后续实现 `HermesBackend`/`Runner` 时，创建/启动一个 Run 前必须先创建并绑定绝对路径 workdir，作为不可跳过的前置步骤。

## 发现二：SOUL.md 里的"必须先反问"规则没有被遵守

xiaomi 的 SOUL.md 明确写了硬性规则："遇到背景不清楚的任务，必须先反问澄清，绝不直接开工。" 实测中收到一句故意含糊的指令后，Hermes **没有反问，直接编造背景并执行**，仅在做完全部工作后才补问了三个无关痛痒的细节确认。

这和 Claude Code 自己的 CLAUDE.md 机制有相同的性质："Claude treats them as context, not enforced configuration"——**人格/系统指令是引导，不是强制配置，模型可能不遵守，尤其在没有外部结构性约束时。**

## 决策

1. **确认 [ADR 0002](0002-self-built-group-discussion.md)（自研群讨论协议）的必要性不是"锦上添花"，而是刚需**——"先讨论对齐、达成共识 brief 才能建 Task/Run"这件事，**不能指望靠 SOUL.md 里写一条规则让 agent 自觉遵守**，必须由协作编排层做**结构性强制**：例如任务/Run 创建的 API 本身要求携带一个已确认的"共识 brief"字段，缺失就拒绝创建，而不是"建议 agent 先问清楚"。
2. 群讨论协议设计时要包含 [ARCHITECTURE.md](../ARCHITECTURE.md) §4 提到的 "transition 约束门"：技术上让执行类动作在讨论阶段未产出共识 brief 前根本无法被触发，而不是靠 prompt 层面的道德劝说。

## 后果

- 本次事故已完全清理（UnitPulse 仓库恢复干净），未产生数据泄露或不可逆损失，纯属沙盒隔离配置疏漏导致的一次可控事故。
- **重要操作纪律**：以后任何驱动 Hermes 做真实文件操作的验证/开发，必须先显式确认 `terminal.working_dir` 指向预期的绝对隔离路径，再执行，不能假设默认值安全。
- AGENTS.md §4 的"当前状态 vs 目标"表需要更新：Hermes 集成从"未开始"推进到"本机验证完成，关键安全/架构发现见本 ADR"。
- 地基验证本身其余部分（详见验证记录）已成功：Hermes 可编程驱动（HTTP Runs API + SSE 流式事件全链路跑通）、多 profile 人格隔离生效、DeepSeek 作为主模型正常工作。唯独"审批门"（`approval_required`）本轮未触发——本地文件写入默认未被 Hermes 归类为高风险，需要接入明确标记为高风险的工具才能验证这条链路，留作下一步。
