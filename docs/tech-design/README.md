# Tech-Design（技术设计 + 任务拆解）

本目录把已拍板的方向（[docs/decisions/](../decisions/) 的 ADR）落成**可执行的技术设计**和**可分配、可验收的 tech-task**。

- **ADR（`docs/decisions/`）** 回答"为什么这么决定"（方向/取舍，改动前须新开 ADR）。
- **Tech-Design（本目录）** 回答"具体怎么实现"：数据模型、API 契约、模块边界、时序流程，以及拆成哪些 task。
- 一个 tech-design 文件（`TD-NN-<slug>.md`）= 一个可独立推进的**阶段**，内含两段：`## 技术设计` + `## Tech-Tasks`（编号 `TD-NN-Tk`，各带验收标准/依赖/是否需 agentpulse 会话）。

## 当前目标弧（从"第一片已完成"到"第一个真正可用的垂直闭环")

> 老板抛目标 → 员工群里讨论澄清 → 对齐出共识 brief → 门控建任务 → **真·Hermes 员工执行** → 结果/审批回到聊天 → 老板看到

第一片（讨论态 + brief + Task 创建门控，[ADR 0006](../decisions/0006-group-discussion-v1-first-slice.md)）**已实现并通过单测**（commit `c2054bf`）。剩下三个阶段：

| 阶段 | 文件 | 一句话 | 是否需 agentpulse 锚定会话 | 规模 |
|---|---|---|---|---|
| A | [TD-01](TD-01-verify-and-harden-slice-1.md) | 端到端手测并收尾第一片（含讨论态接线） | 是（要起后端+桌面端） | 小 |
| B | [TD-02](TD-02-multi-agent-discussion.md) | 多 agent 真正在群里接力讨论（照 AutoGen 骨架） | 否（纯 `services/api` 逻辑，暂不碰 Hermes） | 中大 |
| C | [TD-03](TD-03-hermes-execution.md) | 执行层从"直连 DeepSeek"换成"调 Hermes profile"(Run/RunStep + HermesBackend) | **是**（会真起 Hermes 进程，[ADR 0005](../decisions/0005-hermes-poc-safety-findings.md) 隔离规矩） | 大 |

**推荐顺序 A → B → C**：A 先确认前一片没白做（便宜、低风险）；B 是产品灵魂"先讨论"、且在任何会话做都安全；C 价值最大但工程量最大、且必须另开 agentpulse 锚定会话。B/C 的先后可调，但 A 应最先。

## 与旧文档的关系

- [docs/backlog.md](../backlog.md) / [docs/workflow.md](../workflow.md) 是 Hermes 转向**之前**的 Epic/Story 拆解（还在讲多 CLI "本地 runtime"），其**流程方法论**（Research→PRD→Architecture→Backlog→Build→QA）仍可参考，但**具体任务清单已过时**，以本目录为准。
