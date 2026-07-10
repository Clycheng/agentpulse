# services/api — 分层规则（嵌套 AGENTS.md）

> 补充根目录 [AGENTS.md](../../AGENTS.md) 的通用规范。本文件专门描述 `services/api` 的三层边界。  
> **修改本目录任何文件前先读本文件，再看 [EXECUTION-BOARD.md](../../docs/tech-design/EXECUTION-BOARD.md) 领任务。**

---

## 三层边界（不可越界）

```
api/routes/       ← 路由层：只做 HTTP 解析 + 调编排层 + 返回响应；绝不写业务逻辑
orchestration/    ← 编排层：业务逻辑（讨论/发言/brief 收敛）；只通过 runtime/ 接口调 LLM/Hermes
runtime/          ← 运行时层：对接 DeepSeek/Hermes HTTP，暴露统一接口给编排层
```

### 路由层禁止模式（写了 = 架构漂逸）

| 禁止 | 允许替代 |
|---|---|
| `for` 循环实现讨论轮次 | 调 `orchestration/discussion.py::run_discussion_round` |
| 路由内私有 `_llm_xxx` 函数做 LLM 发言选择 | 调 `orchestration/discussion.py::select_next_speaker` |
| 路由内 `_extract_mention_xxx` 解析 @ | 同上（已内置在 select_next_speaker） |
| 路由内直接 `import httpx` 调外部 API | 通过 `runtime/` 接口 |
| 路由内 `if discussion_status == ...` 判断讨论状态机 | 通过 `orchestration/` 状态函数 |

### 编排层禁止模式

| 禁止 | 允许替代 |
|---|---|
| `import httpx` 直连 Hermes / DeepSeek | 调 `runtime/hermes_client.py` 或现有临时执行层 |
| 直接写 `runs` / `run_steps` 表 | 通过 `runtime/runner.py::RunService` |

---

## 验收 checklist（每个 TD task 完工必过）

```bash
# 路由层无业务循环/私有 LLM 函数
grep -rn "for.*turn\|while.*round\|_llm_select\|_extract_mention" app/api/routes/

# 生产入口真正调到编排函数（不是死码）
grep -n "run_discussion_round\|select_next_speaker" app/api/routes/workspace.py

# 编排层无直接外部 HTTP
grep -rn "httpx\|requests\|hermes_client" app/orchestration/
```

三条全干净（第二条必须有输出）才能 commit。

---

## 讨论编排入口（TD-02-T5 已归位，2026-07-09）

群讨论的**唯一生产入口** = `orchestration/discussion.py::run_discussion_round`（async 事件流）。`send_message` / `send_message_stream` 都 `async for event in run_discussion_round(...)` 驱动它，只注入两个回调：

- `turn_executor(conn, agent_id)`：异步生成器，产出该 agent 这一轮的回复（流式 yield `chunk` 事件 + 最终 `message` 事件；非流式只产出 `message`），并负责持久化 + commit。
- `llm_complete(prompt) -> str`：主持人 LLM 的执行层薄封装（由 `make_speaker_selector()` 构造），只负责调 DeepSeek 返回原文；发言人选择的全部判定（@提及/JSON 解析/轮询降级）在编排层。

改动这三处前重读本文件的三层边界；`complete_agent_reply` 仍服务于非流式 `/messages`（其单测在 `test_workspace_flow.py`），不是死码。
