# 0002. 自研群讨论协作层（照 AutoGen 骨架）

- 状态: 已接受
- 日期: 2026-07-03
- 决策者: 项目所有者

## 背景
产品核心协作模式是「先拉群把事讨论明白 → 再分工执行」，agent 要像人一样在背景不清时发问，不许被分配了就稀里糊涂开干。需要决定这套多员工讨论从哪来。

## 决策
**群讨论/协作编排层自研**，骨架照 **AutoGen** 的成熟设计。**群聊和私聊用同一套引擎**(参与者=2 即私聊)。执行运行时仍是 Hermes(见 [0001](0001-hermes-as-agent-runtime.md))；基建模式参照 Multica。

必备零件(照 AutoGen 验证)：单一共享 transcript、可插拔发言选择、transition 约束门(没对齐前执行 agent 不许发言)、human 作为参与者 + 等待输入事件、可组合终止条件(区分"已对齐"vs"回合上限")、显式 handoff、有状态可恢复 run、两阶段(讨论产出「共识 brief」→ seed 执行)。参照 Magentic-One 的 Task Ledger→Progress Ledger。

## 理由
- **Hermes 不做多 agent 围坐讨论**(它是单 agent + 记忆)。
- **Multica 的"协作"只是 leader 派活(delegation)，不是讨论**——不满足"先讨论明白"的诉求。
- AutoGen 已把群讨论需要的所有原语验证清楚，直接借鉴骨架比从零摸索稳。
- 详见 [../ARCHITECTURE.md](../ARCHITECTURE.md) §4。

## 后果
- 这是 AgentPulse 最主要的自研工作量。
- 讨论阶段必须产出结构化「共识 brief」对象，用它驱动 Task/Run，而非只靠原始聊天记录。
- 需要防止两个易漏点：① transition 约束(防止讨论没完就开干)；② 独立的"已对齐"终止信号(区别于回合上限)。
