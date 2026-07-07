# TD-01：端到端手测并收尾群讨论第一片

- 关联 ADR：[0006](../decisions/0006-group-discussion-v1-first-slice.md)
- 前置状态：第一片已实现、单测 14 passed（commit `c2054bf`），但**未在跑起来的应用里端到端手测过**，且讨论态状态机（`discussion.py`）还没接到 brief 流程上。
- ⚠️ 执行会话要求：本阶段要起后端 + 桌面端，**必须在 cwd 锚定于 `/Users/liuxiajiang/Desktop/code/agentpulse` 的会话里做**（[ADR 0005](../decisions/0005-hermes-poc-safety-findings.md) 隔离规矩），不要在 UnitPulse worktree 会话里起服务。

## 技术设计

### 目标
把第一片从"单测通过"推进到"真实应用里跑得通、且状态一致"。不加新功能，只验证 + 补最后的接线漏洞。

### 范围
- **做**：端到端手测 brief 全流程；把讨论态状态机接到 brief 确认/拒绝上；修手测暴露的 bug。
- **不做**：多 agent 路由（TD-02）、Hermes（TD-03）、任何新数据模型。

### 现状缺口（已知，需在本阶段收口）
1. `discussion.py` 有 `discussing`/`aligned` 两态和 get/set 函数，但 `brief.py` 的 confirm/reject **没有调用 `set_discussion_status`**——即 brief 确认后会话讨论态不会变成 `aligned`。需接线：brief `confirmed` → 关联会话置 `aligned`；若之后又有新讨论/新 brief 草稿 → 回到 `discussing`。
2. `POST /api/tasks` 门控依赖 confirmed brief，但**"从 brief 一键生成 Task"的实际入口**（老板点"确认并创建任务"后，前端到底调了什么、传没传 `consensus_brief_id`）需端到端确认串通。
3. 前端 `BRIEF_CARD:` 卡片的渲染/按钮回调，需在真实数据下确认（confirm 调 `/api/briefs/{id}/confirm`、reject 调 reject，且确认后卡片状态更新）。

### 端到端手测脚本（验收基准）
在 agentpulse 锚定会话里：起 Postgres（docker compose）+ 后端（uvicorn）+ 桌面端 renderer（vite），注册账号后：
1. 给小秘发一句模糊目标 → 断言：**不再自动建任务**（旧正则已删），会话处于 `discussing`。
2. 造/发一条 brief 草稿（走 `POST /api/briefs`）→ 断言：群聊出现「共识纪要（待确认）」卡片。
3. 点「不对，继续讨论」→ 断言：brief `rejected`，会话仍 `discussing`，无任务产生。
4. 再确认一个 brief（`confirm`）→ 断言：brief `confirmed`、会话 `aligned`、可据此建任务、群聊出现"已创建任务"系统消息、任务中心出现该任务。
5. 尝试绕过 brief 直接 `POST /api/tasks`（无 `consensus_brief_id`、无 `parent_task_id`）→ 断言：被门控拒绝（400）。
（每步截图或记录响应，作为"验证过"的证据，遵循 AGENTS.md §5"声明完成前先验证"。）

## Tech-Tasks

### TD-01-T1：接线讨论态状态机到 brief 生命周期
- 改动点：`orchestration/brief.py` 的 confirm/reject 里调用 `discussion.set_discussion_status`；新建 brief 草稿或 reject 后回到 `discussing`，confirm 后置 `aligned`。
- 验收：单测覆盖"confirm→会话 aligned""reject→会话仍 discussing"；`bootstrap`/会话查询能返回 `discussion_status`。
- 依赖：无（纯 `services/api`）。
- 需 agentpulse 会话：否（可在任意会话写代码 + 跑单测）。
- 估算：0.5 天。

### TD-01-T2：端到端手测 + 修 bug
- 改动点：按上面"端到端手测脚本"实跑，修暴露的接线/前端回调/字段缺失问题。
- 验收：脚本 5 步全部通过，留截图/响应记录。
- 依赖：TD-01-T1。
- 需 agentpulse 会话：**是**（起后端 + 桌面端）。
- 估算：0.5–1 天。

### TD-01-T3：补前端 brief 卡片的边界
- 改动点：卡片在 `confirmed`/`rejected` 后的态（不能重复确认）；多个待确认 brief 并存时的展示；brief 里可选字段（scope/constraints/负责人）缺失时的降级展示。
- 验收：手测覆盖上述边界，无报错、无重复提交。
- 依赖：TD-01-T2（以手测发现为准，可能合并进 T2）。
- 需 agentpulse 会话：是。
- 估算：0.5 天。

## Definition of Done
- 上述验收全过，AGENTS.md §4 的"⚠️ 尚未端到端手测"标记可去掉。
- 更新 CHANGELOG。
