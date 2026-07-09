# 执行看板（唯一任务状态源 · AI 冷启动从这里知道"下一步干什么"）

> **任何 worker AI 开工流程**：读完 [README.md](README.md) 的"Worker AI 执行协议" → 在本文件挑「现在就做」里最靠前、且会话类型匹配的任务 → **开工第一个动作 = 把该任务状态改成 `🔵 进行中` 并 commit+push 本文件**（防止多 AI 撞车）→ 做完按协议验收/回填 → 状态改 `✅ 完成(commit)` 再 push。
> 任务状态**只在本文件标**（TD 文件里只有设计和验收标准，不标状态），避免两处漂移。

## ✅ 架构漂移已修复（2026-07-09）——TD-02-T5 完成，TD-03-T2/T3 解锁

`orchestration/discussion.py::run_discussion_round` 曾是死码（生产路由手写重复讨论循环 + `_llm_select_speaker`）。TD-02-T5 已把 `send_message`/`send_message_stream` 的讨论循环统一收回到 `run_discussion_round`（重写为 async 事件流），发言人选择唯一入口收敛到 `resolve_next_speaker`/`select_next_speaker`，路由层只注入"如何执行一轮 turn"和"如何调主持人 LLM"。三条禁止模式 grep 全干净，新增生产路径断言测试。**TD-03-T2 及以后现可开工。**

## 现在就做（按此顺序领）

| 序 | 任务 | 一句话 | 会话要求 | 状态 |
|---|---|---|---|---|
| 1 | [TD-03-T1](TD-03-hermes-execution.md) | runs 扩列 + run_steps 新表 + approvals.run_id(⚠️双 schema) | 任意 | ⚪ 待领 |
| 2 | [TD-04-T6](TD-04-agent-provisioning.md) | LocalHermesProvisioner 真实现(语法已实测解锁，注意 import 写 wrapper 要清理) | **agentpulse** | ⚪ 待领 |
| 3 | [TD-01-T2/T3](TD-01-verify-and-harden-slice-1.md) | 端到端手测：brief 全流程 + 多 agent 讨论流(起后端+桌面端真跑一遍；TD-02-T5 已重构完，现在测的就是最终路径) | **agentpulse** | ⚪ 待领 |

## 有依赖，等前置完成后做

| 任务 | 等什么 | 会话要求 |
|---|---|---|
| [TD-03-T2](TD-03-hermes-execution.md)(HermesBackend) | TD-03-T1（TD-02-T5 已完成✅） | **agentpulse** |
| TD-03-T3(RunService+替换执行层) | TD-03-T2 | **agentpulse** |
| TD-03-T4(Tirith 审批 + clarification_required) | TD-03-T3 | **agentpulse** |
| TD-03-T5(员工↔profile 生命周期) | TD-03-T2；可与 TD-04-T6 合并做 | **agentpulse** |
| [TD-06-T1](TD-06-agent-self-evolution.md)(技能自动沉淀) | TD-03-T3 + TD-04-T6 | **agentpulse** |
| [TD-06-T2](TD-06-agent-self-evolution.md)(主动能力升级申请) | TD-03-T4 + TD-04-T6 | **agentpulse** |
| TD-06-T3(SOUL 模板注入 + 成长轨迹 UI) | TD-06-T1 + TD-06-T2 | 否（前端）/ agentpulse（验 SOUL） |
| [TD-07-T1](TD-07-business-capability-catalog.md)(业务能力目录扩展) | TD-05-T1（已完成） | 否 |
| TD-07-T2(角色 Bundle + UI) | TD-07-T1 + TD-04-T5 | 否 |
| [TD-08-T1](TD-08-idea-center.md)(ideas 表 + API) | 无 | 否 |
| TD-08-T2(IdleThinkService + cron) | TD-03-T2 + TD-04-T6 | **agentpulse** |
| TD-08-T3(Idea 中心前端) | TD-08-T1 + TD-08-T2 | 否 |
| [TD-09-T1](TD-09-channel-adapters.md)(channel_configs 表 + Router) | 无 | 否 |
| TD-09-T2(Webhook 端点 + 渠道 API) | TD-09-T1 | 否 |
| TD-09-T3(ChannelReply + 网页 Widget) | TD-09-T2 | 否 |

## 已完成

| 任务 | commit | 备注 |
|---|---|---|
| TD-02-T5(路由归位)：send_message/stream 讨论循环统一收回 run_discussion_round(改为 async 事件流)，删除路由层 `_llm_select_speaker`/`_extract_mention_simple`/`_build_discussion_context`，发言人选择收敛到 `resolve_next_speaker`；+8 编排单测 +1 生产路径断言测试 | 2026-07-09(见 CHANGELOG) | 三条 grep 全干净；149 测试全过；解锁 TD-03-T2/T3 |
| 架构复核：发现 TD-02 路由层重复实现漂移，新增 TD-02-T5 阻塞项 | 2026-07-08(见 CHANGELOG) | 纯发现+文档纠正，代码未改 |
| 验证事实回填 DATA-MODEL/TD-03/04/05/ARCHITECTURE + workdir 架构决策 + 看板重建 | 2026-07-08(见 CHANGELOG) | |
| TD-02 T1–T4(多 agent 讨论编排+372 行测试) + SSE 流式 | `b61005e` | ⚠️ 编排函数本身正确，但**未被路由实际调用**——见上方漂移说明，需 TD-02-T5 完成整合 |
| 一键启动脚本 `npm run dev` | `4ec9e96` |
| SQLite 20 个失败测试修复 | `141592f` |
| TD-04-T5(API+前端最小闭环) | `c4d1e3e` |
| TD-04-T4(供给编排+状态机) | `81af20d` |
| TD-04-T3(role_spec 起草+SOUL 生成) | `f55d0b1` |
| TD-04-T2(ProfileProvisioner+RecordOnly) | `0ed930d` |
| TD-04-T1(agent_specs/capabilities 建表+DTO) | `cd52af8` |
| TD-05-T1(capability_catalog) | `dd595de` |
| TD-01-T1b(TaskOut consensus_brief_id) | `0c745b0` |
| TD-01-T1(讨论态接线) | `a9b2b06` |
| PLAYBOOK V1–V7 验证报告 | `19c209b` |
| 群讨论第一片(ADR 0006 实现) | `c2054bf` |
| 全部设计文档(架构/DATA-MODEL/TD-01~05/剧本/本看板) | 见 CHANGELOG 2026-07-03~08 |

## 维护规则
- 领任务/完成任务的 AI **必须**更新本文件并 push（这就是认领锁）。
- 新增 TD/task 时同步登记到上面两张表。
- **链接必须指向真实存在的文件**；完成状态必须带真实 commit 号，不写"待提交"。
- 状态含义：⚪ 待领 / 🔵 进行中(注明领取方+日期) / ✅ 完成(注明 commit) / ⛔ 阻塞(注明等什么)。
