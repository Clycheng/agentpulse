# 闭环走查：一个目标从群讨论到执行再回到老板（锚文档）

> 先读这份，再看 TD-01/02/03 和 [DATA-MODEL-AND-API.md](DATA-MODEL-AND-API.md)。它用一个具体场景把完整闭环走一遍，让你先知道"跑通到底是什么"，任务清单挂在它下面。
> 标注：`【已实现】`现在真能跑 / `【TD-02】`多 agent 讨论 / `【TD-03】`接 Hermes。

## 场景
老板阿磊经营小红书内容号。员工：`小秘`(主持人 agent)、`墨白`(内容主笔 agent)。群会话 `conv_01`「内容策划组」。

## 闭环 8 步（带真实数据 / 跑哪段代码）

**① 老板抛目标 【已实现】**
阿磊发「帮我搞下周小红书的内容」→ `POST /api/conversations/conv_01/messages {"content":"..."}` → `send_message()` 存消息，会话 `discussion_status='discussing'`。现在它会调 `complete_agent_reply()`→DeepSeek 回一条；**不再自动建任务**（正则已删）。

**② 员工群里讨论澄清 【TD-02，现在缺】**
`select_next_speaker()`→小秘先说：「先对齐：主题?篇数?配合活动?」阿磊答「减脂餐/3篇/周三直播预热」→ 小秘 `@墨白`，墨白追问人群 → 阿磊「普通上班族」。到轮次上限或主持人判断"够了"停。靠 `run_discussion_round()`（[DATA-MODEL §4](DATA-MODEL-AND-API.md)）。

**③ 收敛共识 brief 【通道已实现 / 自动收敛属 TD-02】**
小秘 `POST /api/briefs`（契约见 [DATA-MODEL §2.1](DATA-MODEL-AND-API.md)）：
```json
{"discussion_conversation_id":"conv_01",
 "goal":"为小红书号策划下周3篇减脂餐内容,给周三食谱直播预热",
 "scope":"3篇图文,面向想减肥的普通上班族;直播预热是重点",
 "constraints":"周三前至少发1篇预热;不虚构营养数据",
 "success_criteria":"3篇选题+结构定稿,老板确认",
 "owner_agent_id":"agent_mobai","created_by_agent_id":"agent_xiaomi"}
```
→ `consensus_briefs` 建行 `status='draft'` 返回 `brief_77` → 群里插 `BRIEF_CARD:{...}` 系统消息 → 前端渲染「共识纪要(待确认)」卡片。

**④ 老板拍板 【已实现，状态机接线待补】**
点「确认并创建任务」→ `POST /api/briefs/brief_77/confirm` → `status='confirmed'`。⚠️ 应同步把 `conv_01` 置 `aligned` 但现在没做（[DATA-MODEL §3 G3](DATA-MODEL-AND-API.md) / TD-01-T1）。

**⑤ 门控建任务 【已实现，全项目最硬的一块】**
`POST /api/tasks {"title":"写3篇减脂餐文案","consensus_brief_id":"brief_77",...}` → `create_task()` 首步 `validate_task_creation_gate()`：`brief_77` 存在且 confirmed → 放行建任务，群里「已创建任务：…」。**跳过 brief 直接建 → 400**（结构性强制，[DATA-MODEL §2.5](DATA-MODEL-AND-API.md)）。

**⑥ 员工真·执行 【TD-03，现在是假的】**
现在任务建好没人真干。目标：建任务→`RunService` 建 `runs(queued)`→**mkdir 绝对路径 workdir**→`HermesBackend.run()`：`POST :8642/v1/runs`→SSE `message.delta…run.completed`，每事件写 `run_steps`+推前端。墨白 `SOUL.md` 让产出带主笔调性。契约见 [DATA-MODEL §5](DATA-MODEL-AND-API.md)。

**⑦ 高风险审批 【TD-03】**
墨白要"直接发布"→ Hermes 抛 `approval_required`→建 Approval、Run→`waiting_user`→**复用已有内联审批卡片**弹群里→阿磊「确认通过」→`POST /v1/runs/{id}/approval` 续跑。

**⑧ 结果回聊天 【TD-03】**
Hermes `final`→墨白3篇文案写回群消息 + 任务进度→完成。→ 有新目标再从①开始。**闭环合上。**

## 现在能跑通的 vs 缺的
- ✅ **③→④→⑤**（讨论对齐→拍板→受控建任务）真能跑，是第一片。
- ⚠️ ④ 状态机接线断的 → TD-01。
- ❌ ② 真讨论 → TD-02；❌ ⑥⑦⑧ 真执行+审批+回写 → TD-03（"像不像真 AI 公司"的分水岭）。

**一句话**：现在通的是中段"对齐→建任务"，缺前段"真讨论"和后段"真干活"。TD-02 补前、TD-03 补后，合起来才是完整闭环。
