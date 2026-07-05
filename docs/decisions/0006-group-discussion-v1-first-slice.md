# 0006. 群讨论协议 v1 第一片：讨论态 + 共识 brief + Task 创建门（对齐用人工确认）

- 状态: 已接受（计划已获项目所有者认可，尚未实现）
- 日期: 2026-07-05
- 决策者: 项目所有者认可

## 背景

[ADR 0002](0002-self-built-group-discussion.md) 定了"自研群讨论协作层"的方向，[ADR 0005](0005-hermes-poc-safety-findings.md) 用实测证明"讨论对齐后才能开工"必须是编排层的结构性强制、不能靠 SOUL.md 自觉。但这两条都是原则，没落到"下一步具体写什么代码"。

2026-07-05 做了一次冷读测试（一个零上下文的 AI 只读本仓库判断能否继续），结论：产品愿景/架构方向/硬规矩都清楚，但**最近这一步的具体计划没写进仓库**，冷读者会因此照旧版"先实现 Runner/HermesBackend"去做，与本条计划岔开。本 ADR 就是把已认可的"第一片"计划落进仓库，消除这个歧义。

## 决策

**下一步先做群讨论协议的第一片，且这一片刻意不碰 Hermes**（在现有临时的 DeepSeek 直连执行层上就能把编排骨架跑通，以后换真 Hermes 时编排层设计不用重来）：

1. **会话/群聊引入"讨论态 → 已对齐"的状态机**。一件事进来先处于"讨论中"，不自动建任务。
2. **引入"共识 brief"数据对象**（目标 / 范围 / 约束 / 负责人等），作为讨论阶段的结构化产出。
3. **Task 创建 API 强制要求携带 consensus_brief，缺失即拒绝创建**——这是 ADR 0005 要的"结构性强制门"。**现有 `services/api/app/services/workspace.py` 里 `TASK_INTENT_PATTERNS` 正则 + `extract_task_intent`"发一句话就自动建任务"的逻辑要被移除/替换**——它正是"稀里糊涂开干"的反例。
4. **对齐判定 v1 = 人工确认，不做 LLM 自动判"讨论完了没"**：由秘书/负责员工整理出纪要，老板点"确认纪要 → 生成任务"才真正建 Task。更可靠，也避免过度设计。

**本片明确不做**（留给后续 slice）：多 agent 发言路由 / 轮流接力 / SelectorGroupChat 那套（[ADR 0002](0002-self-built-group-discussion.md) / ARCHITECTURE §4 的完整 AutoGen 骨架）；也不做真正接 Hermes 驱动执行。

## 理由

- 顺序符合 ROADMAP 的 Runtime 集成优先级（群讨论协议排在深度接 Hermes 之前）。
- 直接落地 ADR 0005 的教训（结构性门控），且这是纯后端逻辑/数据模型，不需要真跑 Hermes 就能建骨架。
- 不需要把工作挪到"cwd 锚定在 agentpulse 的会话"——本片全在 `services/api` 内改代码/schema，不起 Hermes 进程，不触发 [ADR 0005](0005-hermes-poc-safety-findings.md) 的隔离风险；等到真正接 Hermes 驱动那一步再遵循隔离规矩另开会话。

## 待解决（动手前须与项目所有者敲定，别猜）

冷读测试点出这几处目前只有"原则"没有"细节"，实现前需要确认，不要自行编造后当成既定：

1. **consensus_brief 的确切 schema**：字段有哪些（目标/范围/约束/成功标准/负责人…）、哪些必填、存 Postgres 的表结构。
2. **编排层放在代码哪里**：建议后端新模块（如 `services/api/app/orchestration/`），需确认，不要塞进 Hermes profile 或现有 service 里搅在一起。
3. **"已对齐"信号 v1 的确切形式**：本 ADR 定为"人工点确认"，需确认 UI/API 上具体是老板的哪个动作触发、由谁发起纪要。
4. **Task 与 Run 的关系**：是否每个 Task 必有 Run、Run 能否脱离 Task 存在（本片可能还不涉及 Run，但建 schema 时要想清楚）。
5. **Hermes 部署期多 profile 进程管理**：本片不涉及，留到接 Hermes 驱动那一步再定，此处仅记录它是已知的开放项。

## 后果

- 现有"正则自动建任务"逻辑将被移除/门控，`extract_task_intent` 相关测试与前端行为需同步调整。
- 完成本片后更新 AGENTS.md §4 的"当前状态"与"下一步"，避免下一个 AI 读到过期状态。
- 这一片跑通后，才在其上叠加"多 agent 发言路由"和"接 Hermes 真执行"两片。
