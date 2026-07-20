# service-claw-cloud 调研：对 AgentPulse 的借鉴建议

> 调研对象是 UnitPulse（本机另一个真实项目，与 AgentPulse **零关联**，本次只读代码做架构借鉴，未触碰其任何文件/进程）旗下的 `service-claw-cloud`——物业播本调度器（`service-claw`，跑在一台本地 Mac 上，靠 Playwright + 登录态 Chrome 操作 Gmail/DocuSign/Zillow 等无 API 或 API 不够用的系统）的云端镜像服务。本文只做**已调研未拍板**的记录（同 [dust.md](dust.md) 的定位），不代表架构决策——采纳与否、何时采纳需另开 ADR。

## 范围和结论

`service-claw-cloud` 解决的是一个跟 AgentPulse 结构同源的问题：**"大脑/UI 在云上，真正动手的执行体在别处（甚至是另一台机器）"**。它的解法——命令队列（UI→云→本地"拉"而不是"推"）、心跳/机器注册表、Excel 工作簿式的三层数据模型（封面/清单行/事件流）、幂等同步——对我们当前"单进程内 `approval_bridge` 用 asyncio Future 挂起"的实现，以及未来 ADR 0003 描述的"服务端常驻 Hermes daemon + 桌面端分机部署"，有直接、可执行的参考价值。

核心结论：

1. **它今天就已经在过我们迟早要过的桥**：中国大陆平台（公众号/小红书/抖音后台）基本没有官方发布 API，TD-10 的 `publish_social_content` 真要落地，最终大概率也要靠一台挂着老板登录态浏览器的机器去点——跟这个项目"Mac 跑 Playwright，云端只管编排+UI+命令队列"是同一个拓扑。
2. 它的**命令队列 + 轮询 + 原子认领**（Postgres `FOR UPDATE SKIP LOCKED`）模式，是我们 `approval_bridge`（进程内 Future，文档自己承认"单进程 only"）将来要跨进程/跨机器时的现成范本，不用等到那天再发明。
3. 它的**心跳/机器注册表**（`claw_machines`：注册→心跳→online/stale/offline）戳破了一个我们现在的真问题——员工卡上的"在线待命"是写死的字符串，跟 `hermes profile list` 显示的真实 `stopped` 状态对不上。
4. 它的数据模型纪律（封面表缓存汇总数字、清单行原地 UPDATE 带 `waiting_on`、事件流只追加）里，有几个小到可以现在就抄的字段/习惯——不需要等大架构变动。

## 来源

本地只读代码调研，路径：`/Users/liuxiajiang/Desktop/unitpulse/service-claw-cloud/`（`README.md`、`app/main.py`、`app/api/{playbooks,admin_commands,internal_sync,machines}.py`、`app/db/models.py`、`deploy/MORNING_RUNBOOK.md`）。未执行、未修改、未启动该服务的任何进程。

## 架构：为什么拆成两半

README 第一句话就是理由："Playwright + Chrome 的登录态会话搬不上云"。于是变成：

```
   本地 Mac（service-claw）                 云端（service-claw-cloud）
   ─────────────────                       ──────────────────────────
   ┌─────────────────┐                     ┌──────────────────────┐
   │ PlaybookScheduler│ ──写──HTTPS───────►│ POST /internal/sync   │ → PG
   │ Playwright+Chrome│                     │ GET  /up-claw/...     │ ← UI
   │ 登录态会话       │ ◄──轮询──DB────────│ POST /admin/commands  │ ← UI
   └─────────────────┘                     └──────────────────────┘
```

- **云端只做**：状态镜像（PG）、UI 读接口、命令队列。
- **本地 Mac 只做**：真正的浏览器自动化 + 定期把状态同步回云端 + 轮询取新命令。
- **鉴权分两套**：内部同步/命令端点用共享 bearer token（`UP_CLAW_SYNC_TOKEN`，一台 Mac 一个 token）；UI 端点走 Google OAuth，限 `@unitpulse.ai`。

对 AgentPulse 最直接的映照：TD-10 的业务受控工具，只要涉及"国内平台没有官方发布 API"，最终执行体就不可能是纯 HTTP 调用，而是需要一台真机上的登录态浏览器/`computer_use`。到那天，AgentPulse 的形状会变成跟这个项目一样——服务端（编排/审批/DB）在云上，执行体在别处。**这一条已经写进 [TD-10 的"未来扩展"](tech-design/TD-10-business-tool-gate.md)。**

## 命令队列模式：UI→云→本地"拉"而不是"推"

UI 从不直接碰本地 Mac——它把命令写进 `playbook_admin_commands` 表（`status='pending'`），本地 Mac **轮询认领**：

```sql
WITH eligible AS (
    SELECT id FROM playbook_admin_commands
    WHERE status = 'pending'
    ORDER BY requested_at
    FOR UPDATE SKIP LOCKED
    LIMIT :n
)
UPDATE playbook_admin_commands c
SET status='running', claimed_at=:now, claimed_by=:machine_id
FROM eligible WHERE c.id = eligible.id
RETURNING ...;
```

`FOR UPDATE SKIP LOCKED` 让多台机器并发轮询同一个队列时，不会互相等锁、也不会双认领同一条命令——这是"轮询认领"模式能安全水平扩展的关键写法，值得记住。做完之后 `POST /internal/admin-commands/{id}/complete` 回写结果。

**对我们的映射**：`approval_bridge.py` 现在是**进程内 asyncio Future**，docstring 自己写明"Single uvicorn process only"。这在 ADR 0003 描述的"服务端常驻 Hermes daemon + 桌面端分机部署"真正落地之前够用，但那天到了，挂起/唤醒必须从"进程内 Future"换成"DB 队列 + 轮询 + 原子认领"这套模式——不需要现在动手，但应该现在就写进 `ARCHITECTURE-DETAILED.md` 的横切关注点，防止将来有人试图把一个 asyncio Future 跨进程/跨机器传递（那是传不过去的）。

顺带：它的 `command_type` 词汇表很成熟——`pause / resume / restart_matter / skip_matter / override_resource / revert_version`。AgentPulse 老板对员工/任务的控制面目前只有"批准/拒绝"，**暂停/跳过/重跑某个任务**是自然的下一批控制原语，可以先记在这里，不急着做。

## 心跳 + 机器注册表：我们的"在线待命"目前是假的

`claw_machines` 表：注册 → 每 60s 心跳 → `online/stale/offline` 生命周期，UI 上能看到每台机器的真实健康度。

对照 AgentPulse：员工卡上的"在线待命"（`status_label`）是**写死的字符串**（见 `apps/desktop/src/main.tsx` 的 agent 序列化），跟 `hermes profile list` 显示的真实进程状态（现在这台机器上所有 profile 都是 `stopped`——Hermes 只在真正跑一次 ACP 会话时才起子进程，闲时压根没有常驻进程）完全对不上。等我们做 7×24（daemon + cron，ADR 0003）时，一张 `agent_runtime_status`（`hermes_profile`、`last_heartbeat_at`、`status`）小表 + 员工卡读真实状态，是低成本高诚实度的改进——不需要等 daemon 全部做完，`hermes profile list` 这个命令本身现在就能定期跑一下、比对返回结果，先把"在线待命"改成"闲置"更誠實。

## 数据模型的"Excel 工作簿"隐喻

三张表分工纪律很清楚：

- **`playbook_runs`**（封面）：挂**缓存的汇总数字**（`onboarding_resolved`/`onboarding_total`、`anomaly_count_24h`）——列表页不用 JOIN 就能渲染。
- **`playbook_matter_state`**（清单行）：原地 UPDATE，有个很小但很妙的字段 **`waiting_on`**（这一行正在等谁/等什么，纯文本）。
- **`playbook_activity`**（事件流）：只追加、永不改删，`event_type` 枚举里有 `anomaly_fired` 和 `admin_action_taken`——老板的手动操作跟系统事件在**同一条时间线**里。

对 AgentPulse 可以现在就抄的三个小东西（已登记到 EXECUTION-BOARD，见下）：

1. **`waiting_on`**：我们挂起审批的 run，任务卡/员工卡应该直接显示"等老板拍板"这类文本，而不是要点进运行轨迹才知道卡在哪。
2. **异常聚合是一等公民**：我们员工失败目前只是 `runs.error` 里一条静默字符串，没有任何面向老板的"过去 24h 有 N 个异常"聚合视图。北极星"老板看到进度产出"，异常聚合恰恰是最该被看到的那类信号。
3. **审批事件并入同一条时间线**：老板的每次批准/拒绝/授权（`approvals` 表）目前和 `run_steps` 是两个独立的世界，回看一个 run 发生了什么时体验割裂。

## 幂等同步纪律

本地→云端所有写接口按**自然键 UPSERT**，重试安全；`playbook_activity` 还专门开了 `/batch` 端点给"断网后补追积压"用。等 AgentPulse 的 Hermes 执行侧和 API 侧真正分机部署、要处理网络抖动时，run_steps 回传直接照抄这套（natural-key upsert + batch 补追）即可，不用重新设计。

## 两个小而好的工程习惯

- **启动冒烟检查**：`app/main.py` 的 `lifespan` 里直接 `SELECT count(*) FROM playbook_runs`，生产环境连不上 DB 就直接拒绝启动（fail loud）。对照我们：`AGENTPULSE_HERMES_PROVISIONING=true` 但 `hermes` 二进制不存在/版本不对时，现在是**运行时才炸**（第一次有人发消息触发供给才发现）——启动时就该检查一次，已登记到 EXECUTION-BOARD 并实现（见下）。
- **`MORNING_RUNBOOK.md`**：每一步部署操作都配一条可执行的验证命令。跟我们自己的 [HERMES-VERIFICATION-PLAYBOOK.md](tech-design/HERMES-VERIFICATION-PLAYBOOK.md) 是同一种精神，互相印证这套"操作步骤旁边永远跟一条验证命令"的写法是对的，值得在其他 runbook 类文档里延续。

## 一个反向对照（同样重要，别照抄）

`service-claw` 是**编译出来的确定性播本**（matter 带 `when_grammar` 时间语法、`pattern` 分 one_shot/periodic），跟 AgentPulse"LLM agent 自主讨论决定做什么"是光谱的两端——**不要**把它的确定性播本模型整体搬过来，那违背 AGENTS.md 北极星"agent 自我学习、自主协作"的定位。

但它的 `pattern` 分类提醒了一件事：AgentPulse 的任务目前**全是 one-shot**（讨论→brief→建任务→执行→归档），而"运营类工作"（每周发内容、每天看数据、定期复盘）本质是 periodic matter——这正是 idea 中心 + cron（ADR 0003）那条线该长成的样子，不是本次调研的新发现，只是一个印证。

## 已实现的短期可做项

以下三条不需要架构级决策，同一轮里直接实现了（不停留在"已登记待做"），见 [EXECUTION-BOARD.md](tech-design/EXECUTION-BOARD.md) 和 CHANGELOG：

1. **启动冒烟检查**（`hermes_provisioning=true` 时校验 `hermes` 二进制存在，否则 fail loud 拒绝启动）——`app/main.py::_check_hermes_binary_if_provisioning_enabled`。
2. **`waiting_on` 字段**——`RunOut.waiting_on`：run 处于 `waiting_user`/`waiting_clarify` 时，查同一 run 上 pending 的 `approvals` 行，拼一句"等老板批准：{描述}"/"等老板回答：{描述}"，运行轨迹卡片直接显示，不用点进 steps 才知道卡在哪。
3. **24h 异常聚合**——`count_anomalies_24h`：过去 24 小时内 `status='failed'` 的 run + `status='expired'` 的审批计数（刻意不算 `rejected`——那是老板自己的决定，不是"出了问题"），挂在 `/me/bootstrap` 的 `anomaly_count_24h`，桌面端顶部 logo 上一个红色小红点 + hover 提示。

心跳/机器注册表、命令队列跨进程改造、`command_type` 控制原语扩展，属于更大的架构变动（依赖 ADR 0003 的 daemon 化落地），本次只记录方向，不拆 TD。
