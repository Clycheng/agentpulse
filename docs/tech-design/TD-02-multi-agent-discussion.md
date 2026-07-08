# TD-02：多 agent 群讨论（照 AutoGen 骨架）

- 关联 ADR：[0002](../decisions/0002-self-built-group-discussion.md)（自研群讨论，照 AutoGen）、[0006](../decisions/0006-group-discussion-v1-first-slice.md)（第一片，本阶段在其上叠加）
- ⚠️ 执行会话要求：纯 `services/api` 逻辑，**暂不碰 Hermes**，在任意会话做都安全（写代码 + 单测不起 Hermes 进程）；若要端到端手测则同 TD-01（需 agentpulse 锚定会话起服务）。

## 🔴 2026-07-08 架构复核：实现已落地但发生真实漂移，未完成前不得视为"TD-02 已完成"

对照本设计 (`select_next_speaker`/`run_discussion_round`/`check_convergence` 应放在 `orchestration/discussion.py`，路由层只负责调用) 复核实际代码，发现结构性偏离：

1. **`run_discussion_round`（本设计的核心编排函数）在生产环境是死代码。** 它写在 `orchestration/discussion.py` 里，`orchestration/__init__.py` 导出，`api/routes/workspace.py` 也 `import` 了它——**但路由函数体内从未调用它**。唯一调用方是 `tests/test_discussion.py`。也就是说：**它的单测全过，给出"TD-02 已完成"的假象，但真实请求完全不经过它。**
2. **路由层里另起了两份重复的讨论循环**：`send_message`（非流式）和 `send_message_stream`（流式，**桌面端现在唯一在用的入口**）里各自手写了一遍"选发言人→组 prompt→拿回复→判断是否继续"的循环，逻辑基本同构但物理复制成两份。这直接违反 [ARCHITECTURE-DETAILED.md](ARCHITECTURE-DETAILED.md) §3.1 的边界层职责("**不写业务逻辑**")。
3. **发言人选择被另起了一套 `_llm_select_speaker`**（定义在 `workspace.py` 里，含自己的 `_extract_mention_simple`、自己的 transcript 加载），路由**先试 `_llm_select_speaker`，失败才 fallback 到本设计的 `select_next_speaker`**——优先级和本设计（① @提及 → ② 主持人 LLM → 降级轮询，单一入口）相反，等于多了一条平行路径。`build_speaker_selection_prompt`（prompt 构造）倒是复用了编排层的，没有重复，这块是对的。

**为什么这必须在 TD-03 之前修**：TD-03-T3 原计划"替换 `complete_agent_reply` 的执行部分"——但 `complete_agent_reply` 只被非流式 `send_message` 调用，前端已经**只走** `/messages/stream`（`_stream_agent_reply`）。如果 worker AI 照原计划做，会把 Hermes 接到一条用户实际走不到的死路径上，端到端手测时才会发现"接了 Hermes 但界面没变化"。

### TD-02-T5：路由归位——消除重复实现，编排逻辑收回 orchestration 层（新增，阻塞 TD-03-T2/T3）
- 改动点：`send_message` 和 `send_message_stream` 的讨论循环**统一改为调用 `orchestration/discussion.py::run_discussion_round`**（需要给它加流式变体或让路由包一层生成器）；删除路由层的 `_llm_select_speaker`/`_extract_mention_simple`，讨论中的发言人选择唯一入口收敛到 `select_next_speaker`；非流式 `send_message` 若已被前端弃用，评估是否降级为纯 API 兼容层或标记 deprecated（不要直接删，先确认无其他调用方/测试依赖）。
- 验收：
  1. **架构断言（必须）**：在 `tests/` 新增集成测试，mock `orchestration.discussion.run_discussion_round`，向 `/messages/stream` 发真 HTTP 请求，断言 mock 被调用（验证生产路径真正经过编排入口，而不是单测那种直接 import 调函数的假验收）。
  2. **禁止模式检查（必须）**：在 commit 前跑 `services/api/AGENTS.md` 里的三条 grep，结果必须干净。
  3. **单测保持全过**：现有 372 行 `test_discussion.py` 不退步。
  4. **workspace.py 不再有独立讨论循环/发言人选择**：grep 路由文件无 `_llm_select` / `_extract_mention_simple` 定义。
- 依赖：无（在现有代码基础上重构）。需 agentpulse 会话：否（重构+单测，手测验证同 TD-01）。
- 估算：1–1.5 天。
- **TD-03-T2/T3 在此任务完成前不得开工**（否则会把 Hermes 接到错误的代码路径上）；TD-03-T1（纯 schema）不受影响，可继续。

## 技术设计

### 目标
把"讨论"从第一片的**单发**（一个员工发一条 brief 草稿）升级为**多员工真正在群里接力讨论、澄清背景、再收敛出 brief**——这是产品灵魂"先拉群讨论明白"。仍不接 Hermes，执行层保持临时的直连 DeepSeek。

### 范围
- **做**：群聊里多员工按序发言、发言人选择、澄清式提问（背景不清先问老板/同事）、轮次上限、由谁在何时收敛出 brief 草稿、老板可中途插话。
- **不做**：真·Hermes 执行（TD-03）；跨会话记忆/技能学习（Hermes 原生，后续）；复杂 DAG。

### 借鉴 AutoGen 的最小要件（见 [ARCHITECTURE.md](../ARCHITECTURE.md) §4，都是"自研但照它证明过的骨架"）
1. **单一共享 transcript**：群会话的消息序列就是共享上下文，每轮把当前 transcript 喂给被选中的发言员工。已有 `messages` 表即是。
2. **发言人选择（可插拔）**：v1 先做两种——(a) 老板 `@某员工` → 指定该员工；(b) 群里无 @ → 一个"主持人"角色（默认小秘）用 LLM 从群成员里选下一个该发言的人（基于各 agent 的 role/description）。预留 `selector` 接口，后续可加轮询/自定义。
3. **transition 约束门**：讨论阶段（`discussing`）**只允许"讨论类"发言，不允许执行类动作**——本阶段执行类动作本就还没有（TD-03 才有），但要把这个约束点显式建模，为 TD-03 铺路：发言产出只能是"消息/提问/brief 草稿"，不能是"建任务/调工具"。
4. **澄清式提问**：员工 prompt 里加规则"背景不清先在群里问，不要臆测"；但按 [ADR 0005](../decisions/0005-hermes-poc-safety-findings.md) 教训，**这只是引导不是保障**——真正的保障是"没 confirmed brief 就建不了任务"的门控（第一片已有）。本阶段不需要额外强制，但要在设计里写明"提问是软引导、门控是硬保障"，避免后人误以为提问行为可靠。
5. **可组合终止条件**：讨论何时"该收敛出 brief 了"——v1 用**主持人判断 + 轮次上限双保险**：主持人每轮判断"背景是否已够拆解任务"，够了就发 brief 草稿；同时设每次讨论最多 N 轮（防止无限对话，AutoGen 的 max_round），到顶也强制让主持人产出一版 brief 草稿交老板定夺。
6. **人类中途插话**：老板随时可在群里发言（相当于 UserProxyAgent），会进入 transcript 影响后续发言人；老板发言优先级最高。

### 数据/模块设计
- 复用现有 `messages`（transcript）、`conversations.discussion_status`、`consensus_briefs`。
- 新增 `orchestration/discussion.py` 里的**发言编排**逻辑（现有该文件只有状态机，扩成含"选下一个发言人 + 跑一轮多员工讨论"）：
  - `select_next_speaker(conn, conversation_id, agents, last_message) -> agent_id | None`
  - `run_discussion_round(...)`：选人 → 组 prompt（含 transcript + 该员工 role/SOUL 概要 + "讨论阶段只讨论不执行"约束）→ 调临时执行层（现有 `complete_agent_reply` 那套）→ 写回消息 → 判断是否收敛。
- **执行层暂不变**：仍走 `complete_agent_reply` → DeepSeek。多 agent 只是"多次调用不同人格的临时执行层"，等 TD-03 再把这层换成 Hermes。
- 群成员发言不能无限互相刷屏：加"连续 agent 发言不超过 M 条就必须停下等老板"或"每轮上限 N"。

### 字段级细化（worker AI 直接照此实现）

**接线点**：`workspace.py::send_message`——群聊(kind='group')且 `discussion_status='discussing'` 时，把现有"逐个 reply agents 调 `complete_agent_reply`"替换为一次 `run_discussion_round(...)`；DM(kind='dm')保持现状不动。

**配置常量**（`orchestration/discussion.py` 顶部，可被 `core/config.py` 环境变量覆盖）：
```python
MAX_AGENT_TURNS_PER_ROUND = 4      # 一条老板消息最多触发几条 agent 发言
TRANSCRIPT_WINDOW = 30             # 组 prompt 用最近 N 条消息
MODERATOR_IS_DEFAULT_SECRETARY = True  # v1 主持人固定=小秘(source='secretary' 的 agent)
```

**发言人选择**（`select_next_speaker`）：① 最后一条老板消息有 `@员工` → 直接选它（复用 send_message 现有 mention 解析）；② 否则主持人 LLM 选：prompt 输入=transcript 窗口 + 各群成员 `{name, role, description}`，**强制输出严格 JSON** `{"next_speaker": "<agent_id>|NONE", "reason": "..."}`，解析失败/非法 id → 降级为轮询下一个未发言成员；返回 `None`=该停下等人。

**收敛判定**（`check_convergence(conn, conversation_id) -> dict`〔新增〕）：主持人 LLM，输入=transcript 窗口，输出严格 JSON `{"converged": bool, "missing": ["还缺什么背景", ...]}`；`converged=true` → 主持人再走一次 LLM 起草 brief 字段并**服务内直调** `orchestration.brief.create_brief(...)`（不绕 HTTP）；到 `MAX_AGENT_TURNS_PER_ROUND` 上限仍未收敛 → 也强制起草一版（`missing` 写进 brief 的 `constraints` 或说明），交老板定夺。

**每条 agent 发言的 prompt 组装**（复用现有 `complete_agent_reply` 的上下文机制，追加两段系统约束）：
- "当前处于**讨论阶段**：只允许讨论/提问/补充背景，不允许宣称已执行任何动作"（transition 约束的 prompt 侧；硬保障仍是 gate）。
- "你是 <name>（<role>）,发言保持角色视角,不重复别人已说的"。

**防刷屏**：`run_discussion_round` 内部计数,连续 agent 发言达 `MAX_AGENT_TURNS_PER_ROUND` 即停;下一条老板消息才开启新一轮。

### 开放问题（实现前定，别猜）
1. 主持人角色固定是"小秘"，还是每个群可配？v1 建议固定小秘，可后续放开。
2. 发言人选择用 LLM 判断，成本/延迟可接受吗？还是先用更简单规则（轮询群成员一圈）？建议 v1 先 LLM 选、但带轮次上限兜底。
3. "背景够不够拆任务"由主持人 LLM 判断的准确性——需在手测里观察，必要时把判断标准写进主持人 prompt。

## Tech-Tasks

### TD-02-T1：发言人选择器
- 改动点：`orchestration/discussion.py` 加 `select_next_speaker`（@ 优先；否则主持人 LLM 选）。
- 验收：单测——群里 @某员工时选中该员工；无 @ 时返回一个合法群成员或"该停了"。
- 依赖：TD-01 完成（讨论态接线好）。
- 需 agentpulse 会话：否。
- 估算：1 天。

### TD-02-T2：单轮多员工讨论编排
- 改动点：`run_discussion_round`——选人→组 prompt（带 transcript + 讨论态约束）→ 调现有临时执行层→写回消息；连续 agent 发言数/轮次上限。
- 验收：单测——一条老板消息触发若干员工按序发言、到上限即停；执行层仍是 DeepSeek 直连（不引入 Hermes）。
- 依赖：TD-02-T1。
- 需 agentpulse 会话：否（单测）。
- 估算：1.5–2 天。

### TD-02-T3：主持人收敛出 brief 草稿
- 改动点：主持人每轮判断"背景够了没"，够了 → 生成 `POST /api/briefs` 草稿（复用第一片的 brief 通道）；到轮次上限也强制产出一版。
- 验收：单测 + 手测——讨论若干轮后群里出现 brief 草稿卡片，老板可确认走通到建任务（衔接第一片全流程）。
- 依赖：TD-02-T2、TD-01。
- 需 agentpulse 会话：手测部分是。
- 估算：1.5 天。

### TD-02-T4：老板中途插话 + transition 约束显式建模
- 改动点：老板发言进入 transcript 并影响下一发言人；把"讨论阶段只产出讨论/提问/brief 草稿、不产出执行动作"建成显式检查点（为 TD-03 铺路）。
- 验收：单测——老板插话后编排响应；讨论态下无法触发任何执行类动作。
- 依赖：TD-02-T2。
- 需 agentpulse 会话：否。
- 估算：1 天。

## Definition of Done
- 群里多员工能就一个模糊目标接力讨论、澄清、收敛出 brief，老板能中途插话，最终衔接第一片走到建任务。
- 全程执行层仍是临时 DeepSeek 直连（不引入 Hermes）。
- 更新 AGENTS.md §4 + CHANGELOG + 本文件状态。
