# 执行看板（唯一任务状态源 · AI 冷启动从这里知道"下一步干什么"）

> **任何 worker AI 开工流程**：读完 [README.md](README.md) 的"Worker AI 执行协议" → 在本文件挑「现在就做」里最靠前、且会话类型匹配的任务 → **开工第一个动作 = 把该任务状态改成 `🔵 进行中` 并 commit+push 本文件**（防止多 AI 撞车）→ 做完按协议验收/回填 → 状态改 `✅ 完成(commit)` 再 push。
> 任务状态**只在本文件标**（TD 文件里只有设计和验收标准，不标状态），避免两处漂移。

## 现在就做（无阻塞，按此顺序领）

| 序 | 任务 | 一句话 | 会话要求 | 状态 |
|---|---|---|---|---|
| 9 | [TD-01-T2/T3](TD-01-group-discussion-v1.md) | 端到端手测群讨论第一片 | **agentpulse** | ⚪ 待领 |
| 10 | [TD-04-T6](TD-04-agent-provisioning.md) | LocalHermesProvisioner 真实现 | **agentpulse** | ⚪ 待领 |

注：1 与 2–6 **可由不同 AI 并行**；2–6 之间按序（5 依赖 4，6 无依赖可与 4/5 并行）。

## 有依赖，等前置完成后做

| 任务 | 等什么 | 会话要求 |
|---|---|---|
| TD-02 全部(多 agent 讨论) | TD-01-T1(讨论态接线) | 任意(手测除外) |
| TD-03 全部(接 Hermes 执行) | PLAYBOOK V4/V5/V7 回填；T1 可先行 | T2 起 **agentpulse** |

## 已完成

| 任务 | commit |
|---|---|
| TD-04-T5(API+前端最小闭环) | 待提交 |
| TD-04-T4(供给编排+状态机) | 待提交 |
| TD-04-T3(role_spec 起草+SOUL 生成) | 待提交 |
| TD-04-T2(ProfileProvisioner+RecordOnly) | `0ed930d` |
| TD-04-T1(agent_specs/capabilities 建表+DTO) | `cd52af8` |
| TD-05-T1(capability_catalog) | `dd595de` |
| TD-01-T1b(TaskOut consensus_brief_id) | `0c745b0` |
| TD-01-T1(讨论态接线) | `a9b2b06` |
| PLAYBOOK V1–V7(验证报告) | `19c209b` |
| 群讨论第一片(ADR 0006 实现) | `c2054bf` |
| 全部设计文档(架构/DATA-MODEL/TD-01~05/剧本/本看板) | 见 CHANGELOG 2026-07-03~08 |

## 维护规则
- 领任务/完成任务的 AI **必须**更新本文件并 push（这就是认领锁）。
- 新增 TD/task 时同步登记到上面两张表。
- 状态含义：⚪ 待领 / 🔵 进行中(注明领取方+日期) / ✅ 完成(注明 commit) / ⛔ 阻塞(注明等什么)。
