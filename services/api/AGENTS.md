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

## 当前已知死码（待 TD-02-T5 清理）

- `workspace.py::complete_agent_reply`：非流式 `/messages`，前端只走 `/messages/stream`，此函数是死路径。
- `workspace.py::_llm_select_speaker` + `_extract_mention_simple`：路由层的重复发言人选择，等 TD-02-T5 删。
- `workspace.py` send_message / send_message_stream 里各自内联的讨论循环：TD-02-T5 替换为调 `run_discussion_round`。

详见 [TD-02 🔴漂逸说明](../../docs/tech-design/TD-02-multi-agent-discussion.md)。
