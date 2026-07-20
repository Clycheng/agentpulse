# TD-10：业务受控工具门（Business-Controlled Tool Gate）

- 关联：[ADR 0008](../decisions/0008-human-in-the-loop-approval-model.md)（§2/§6，本 TD 是分片⑥拆出的独立后续）、[TD-03-T4](TD-03-hermes-execution.md)（技术危险动作审批机制，本 TD 复用其审批基础设施）、[TD-07](TD-07-business-capability-catalog.md)（`capability_catalog.py` 里已经标了 `risk_gate=approval/prohibited_auto` 的业务能力，但目前只是静态标签，无运行时强制）、[TD-09](TD-09-channel-adapters.md)（渠道出站，本 TD 的 `send_email` 试点复用其 email 凭证模型）
- 执行会话：**是**（要真配 Hermes profile 的 MCP 连接、真跑一次"agent 调受控业务工具→挂起→老板批准/拒绝→继续"，ADR 0005 隔离规矩适用）。

## 背景与目标

ADR 0008 已经把"技术危险动作"（`rm`、部署、推代码……）的审批门做实：Hermes 自己识别命令危险性，触发 ACP `request_permission`，我们的 `approval_bridge` 接住。**但 Hermes 完全不认识"业务危险"**——从 Hermes 的角度看，"发一条微博"和"查一下天气"都只是调用了 `web`/`image_gen` 这类工具，没有任何内建的"这是在花钱/在对外发布"的语义。

`capability_catalog.py` 里已经给 `social_content`、`email_sending`、`ad_bidding`、`refund_processing`、`payroll_processing`、`payment_execution` 等条目标了 `risk_gate='approval'` 或 `'prohibited_auto'`（TD-07 早就写好了），**但这个标签目前只在供给时决定"要不要在 profile 上开这个 toolset"，跟运行时完全没有关系**——员工一旦被供给了 `social_content` 能力，运行时她想发就发，没有人拦她。ADR 0008 §6 说得很清楚："Hermes 永不 gate 这些 → 必须由我们建成『受控业务工具』"。这正是本 TD 要交付的东西。

**目标**：员工要执行一个业务危险动作时，动作本身在我们这层被拦下、判风险、复用现有的审批 UI（跟技术危险动作长得一模一样：允许一次/永远允许/拒绝），老板批准后才真的执行；拒绝或超时则不执行，并把结果如实告诉员工（她可以在对话里跟老板解释后续）。

**不做**（明确排除在本 TD 之外，避免范围膨胀）：
- 不做动态/按内容严重度的风险分级（比如"退款 <100 元自动、>100 元才审批"）——v1 的 `risk_gate` 仍是能力级静态标签，跟 TD-07 现有目录保持一致。动态策略层是 ADR 0008 §"决定 2"提到的方向，本 TD 只搭好"能拦下 + 能审批"的地基，动态判断留作独立后续（见文末"未来扩展"）。
- 不做每一种业务动作的真实外部集成（真连微博 API、真连 SendGrid）——v1 只落地 **一个试点工具**（`send_email`，理由见下）证明整条机制可用，其余业务能力先接上"拦截+审批"骨架，实际外部调用可以是诚实的"未配置"错误，而不是假装成功。

## 技术设计

### 为什么 Hermes 内建审批机制搭不上业务危险

技术危险审批的链路是：Hermes 自己的执行引擎判断"这条命令危险" → 通过 ACP JSON-RPC 调用**我们的 client**（`hermes_client.py` 里注册的 `request_permission` 回调）→ 我们的 `approval_bridge` 挂起等老板决定 → 把结果传回 Hermes 引擎 → Hermes 决定要不要真的执行这条命令。

业务危险动作不一样：员工调用的是一个**普通 MCP 工具**（对 Hermes 来说，"发微博"跟"查天气"没有本质区别，都是"调用一个外部工具、拿到返回值"）。Hermes 自己不会在工具执行前后插入任何"这个工具危险，要不要问问人类"的判断——**这层判断只能发生在工具的实现内部**，也就是说：**拦截点必须搬到我们自己实现、自己托管的 MCP 工具里**，而不是指望 Hermes 引擎帮我们拦。

好消息是：这样反而更简单——我们的 MCP 工具处理函数本身就是一段普通的 Python 异步代码，可以在"真正执行发送"之前，直接 `await approval_bridge.await_decision(approval_id)` 挂起，跟技术危险审批**复用同一个挂起原语**，只是触发挂起的调用点从"ACP 回调"换成了"我们自己 MCP 工具的 handler"。

### 整体架构

**这版架构已经推翻并纠正了一次自己的初稿**：一开始设想的是"供给时把 MCP 连接写进员工 profile 的 `config.yaml`"，读了 `hermes_client.py`（我们自己已有的代码！）和 Hermes 的 ACP 测试套件（`tests/acp/test_mcp_e2e.py`）后发现根本不用这么麻烦——`HermesBackend` 起会话时已经在调 `conn.new_session(cwd=ctx.workdir, mcp_servers=[])`（[hermes_client.py:248](../../services/api/app/runtime/hermes_client.py:248)），**这个空列表就是留给 MCP 服务器配置的**，而 ACP 协议本身就支持"每次开会话时动态传 MCP 服务器列表"（`acp.schema.McpServerHttp(name, url, headers=[HttpHeader(name, value)])`，已验证是 `agent-client-protocol==0.9.0` 这个既有依赖包自带的真实类型，不是臆测）。这比"供给时写死进 profile 文件"好得多：

- 不用碰 profile 的 `config.yaml`/`.env`，不用担心 Hermes CLI 交互式命令、YAML 格式细节。
- **鉴权 token 可以按次生成、直接绑定这一次 run**——签一个包含 `run_id`/`agent_id`/`workspace_id`/`conversation_id` 的短期 token（复用已有的 `python-jose`，跟 `app/core/security.py` 签发登录 token 是同一套机制），当 `Authorization: Bearer <token>` 头传给 MCP 服务。这样**"定位 run_id"这个问题直接被设计消解掉了**，不需要任何"猜当前活跃 run"的启发式——MCP 服务收到请求，验完签名直接从 token 里解出 run_id，一步到位、无歧义。
- 只有这个 agent 当前这条 run 真的需要用到业务受控工具时才会带上 MCP 服务器列表（由 `runner.py` 在起 run 前查一下这个员工的 `agent_capabilities` 里有没有任何一条 `business_tool` 非空且状态 `enabled`），没有相关能力的员工的会话完全不受影响。

```
runner.py::stream_agent_run 起 run 前
  → 查这个 agent 的 agent_capabilities，收集有 business_tool 字段且 enabled 的能力
  → 有的话：签一个绑定 (run_id, agent_id, workspace_id, conversation_id) 的短期 token
           塞进 RunContext.mcp_servers = [{"name": "agentpulse-business",
                                            "url": "{base_url}/mcp/business-tools",
                                            "token": token}]
                                    │
HermesBackend.run(ctx) 起 ACP 会话时：
  conn.new_session(cwd=ctx.workdir,
                    mcp_servers=[McpServerHttp(name=..., url=...,
                                  headers=[HttpHeader("Authorization", f"Bearer {token}")])
                                 for ... in ctx.mcp_servers])
                                    │
                agent 在推理里决定"发这条社媒内容" / "发这封邮件"
                                    │
                       调用 MCP 工具 publish_social_content(...)
                                    │
                                    ▼
                 我们的 MCP 服务（挂在 services/api 同一个 FastAPI 进程里）
                        POST /mcp/business-tools （streamable-HTTP MCP transport）
                                    │
                 1. 验 token 签名 + 过期时间，解出 run_id/agent_id/workspace_id/conversation_id
                 2. 查 capability_catalog 该工具对应能力的 risk_gate
                 3. risk_gate == 'auto'      → 直接执行，返回结果
                    risk_gate == 'approval'  → 挂起（见下）
                    risk_gate == 'prohibited_auto' → 挂起，且永不因超时之外的
                                                      理由自动放行
                                    │
                       （挂起分支）写 approvals 行(type='business_tool', run_id=解出的值)
                       + 在该员工当前对话里插一条 APPROVAL_CARD 系统消息
                       （前端 ApprovalCard 复用，新渲染分支）
                                    │
                    await approval_bridge.await_decision(approval_id)
                     （复用 TD-03-T4 的挂起原语，同一个 50s 超时收敛）
                                    │
                老板在聊天里点 允许一次/永远允许/拒绝 → 同一个
                POST /api/approvals/{id}/resolve 端点（扩展识别 business_tool 类型）
                                    │
              approved → 真的执行动作（调外部 API）→ 把结果文本
              denied/expired → 不执行，返回"已被老板拒绝/超时未处理"的说明文本
                                    │
                       MCP 工具返回这段结果文本给 Hermes
                       agent 在对话里正常反馈（"已发布"/"老板拒绝了，我先搁置"）
```

**关键点**：这条挂起链路完全绕开了 `stream_agent_run` 的 AgentEvent 循环——从 RunService 的角度看，这只是这一个工具调用花了比较久的时间，ACP 会话本身没有中断。approvals 卡片能出现在聊天界面，靠的是 MCP 工具 handler 直接往 `messages`/`approvals` 表写系统消息 + 审批行，跟前端已有的"轮询/刷新拿到新消息"机制天然兼容，不需要新的推送通道。

### MCP 服务实现

- 挂在 `services/api` 同一个 FastAPI 进程下的新路由 `app/api/routes/mcp_business_tools.py`，用官方 `mcp` Python SDK（新依赖，`requirements.txt` 加 `mcp`）实现 **streamable-HTTP transport**。
- 每个 MCP 工具 = 一个 `capability_catalog.CapabilityDef` 里新增字段 `business_tool: str | None = None`（默认 `None`，向后兼容），只有需要业务级拦截的条目才填（`email_sending` → `send_email`、`social_content` → `publish_social_content`、`refund_processing` → `process_refund`、`ad_bidding` → `update_ad_bid`、`payroll_processing` → `submit_payroll`、`payment_execution` → `execute_payment`）。工具的入参 schema 就用 `CapabilityDef` 已有的 `description` 做人类可读描述，参数字段按各业务动作各自定义（`send_email(to, subject, body)` 等）。
- **每次开会话动态传 MCP 服务器，不碰 profile 供给**（已核对真实源码，纠正了两版设想——先是以为要调 `hermes mcp add`，读了 `hermes_cli/mcp_config.py` 发现那条 CLI 命令重度交互、非交互调用会卡死在等 TTY 输入；后来发现根本不用碰 profile 文件，ACP 协议本身就支持每次 `new_session()` 动态传 `mcpServers`，`hermes_client.py:248` 已经预留了这个空列表）：
  1. `RunContext` 加一个字段 `mcp_servers: list[dict] = field(default_factory=list)`（纯 dict，不在 dataclass 里直接引入 `acp.schema` 类型，转换放在调用 `new_session` 那一行）。
  2. `runner.py::stream_agent_run` 起 run 前，查这个 agent 的 `agent_capabilities`（`status='enabled' AND capability_key IN (...有 business_tool 的 key...)`），非空则签一个短期 token（`python-jose`，payload 是 `{run_id, agent_id, workspace_id, conversation_id, exp}`，过期时间设成略长于 run 的 `timeout`），填进 `ctx.mcp_servers`。
  3. `hermes_client.py` 的 `new_session` 调用把 `ctx.mcp_servers` 的每个 dict 转成 `McpServerHttp(name=..., url=..., headers=[HttpHeader(name="Authorization", value=f"Bearer {token}")])`。
  - **尚未验证**（T1 验收里必须真机确认的第一件事）：Hermes 收到这个动态 MCP 服务器列表后，真的会去连并把工具喂给模型推理——`test_mcp_e2e.py` 验证的是 ACP server 这一层的注册逻辑，不是端到端"模型真的选择调用了这个工具"。如果真机测试发现模型不认这些工具/连接失败，以真机结果为准回填本文档。

### 数据模型（双 schema 都要改）

- `approvals.type` 的 CHECK 约束新增一个允许值：`CHECK(type IN ('high_risk','clarification','capability_upgrade','business_tool'))`。
- `approvals.payload_json` 对 `business_tool` 类型存 `{"tool": "send_email", "capability_key": "email_sending", "args": {...人类可读参数预览...}}`，供前端 `ApprovalCard` 渲染动作详情（比如"给 xxx@example.com 发邮件，主题：xxx"）。
- `capability_catalog.CapabilityDef` 加一个字段：
  ```python
  @dataclass(frozen=True)
  class CapabilityDef:
      ...
      business_tool: str | None = None  # 对应本 TD 的 MCP 工具名；None=不需要业务级拦截
  ```
  只需要改这一个文件（`orchestration/capability_catalog.py`），无新表。
- 不新建鉴权/映射表——复用 `agent_specs.hermes_profile` 反查（见上）。

### 审批 UI 复用

- 前端 `ApprovalCard`（`apps/desktop/src/main.tsx`）现有的 `category` 判断（`clarification`/`capability_upgrade`/其余当高风险）改成显式的 `switch`，新增 `business_tool` 分支：图标用 `send`/`publish`，标题读 `payload.tool` 对应的人类可读名字（如"发送邮件""发布社媒内容"），正文展示 `payload.args` 里的关键字段（收件人/主题/发布平台/金额——按 `tool` 类型各自定义一个精简展示函数，不要把整个 JSON 甩给老板看）。按钮沿用已有的"允许一次/永远允许/拒绝"三态，走同一个 `/api/approvals/{id}/resolve`（`resolve_approval` 里 `approval["type"] in (...)` 的判断加上 `'business_tool'`，唤醒逻辑与 `high_risk` 完全一致，不需要 `capability_upgrade` 那种"批准时先装能力"的特殊分支）。

### 风险分类的 v1 范围

`risk_gate` 保持 TD-07 里已经定的能力级静态标签（`auto`/`approval`/`prohibited_auto`），本 TD 不引入按内容/金额的动态判断——那是 ADR 0008 §"决定 2"提到的policy 层，属于本 TD 交付之后的独立迭代（见"未来扩展"）。这个取舍是为了让 v1 聚焦在"机制通不通"，不要一开始就绑一个还没设计的风险判定引擎。

## API 契约

| 接口 | 方法 | 说明 |
|---|---|---|
| `POST /mcp/business-tools` | POST | MCP streamable-HTTP 端点，Hermes profile 通过 `hermes mcp add` 连接；请求头带 per-profile token |
| `GET /api/business-tools` | GET | 列出目录里带 `business_tool` 字段的能力条目（工具名+描述+risk_gate），供前端/文档参考，不是运行时必需 |
| `POST /api/approvals/{id}/resolve` | POST | **复用现有端点**，`resolve_approval` 加 `business_tool` 分支（唤醒逻辑同 `high_risk`） |

## Tech-Tasks

### TD-10-T1：MCP 服务地基 + `send_email` 试点工具全链路
- 改动点：`app/api/routes/mcp_business_tools.py`（新，`mcp` SDK streamable-HTTP）；`capability_catalog.py` 加 `business_tool` 字段 + 给 `email_sending` 填 `send_email`；`approvals` 双 schema CHECK 加 `business_tool`；`LocalHermesProvisioner.configure` 供给时按能力目录决定要不要 `hermes mcp add`；`resolve_approval` 加 `business_tool` 分支；MCP 工具 handler 里的 run_id 定位启发式。`send_email` 的真实发信复用 TD-09 email 适配器的 provider 调用方式（SendGrid/Mailgun，走 `email_sending` 能力已声明的 `EMAIL_API_KEY` 凭证）。
- 验收：`HERMES_E2E=1` 真机测试——员工有 `email_sending` 能力（真 profile 真挂上 MCP）→ 提示她发一封邮件 → 聊天里真的弹出业务审批卡 → 拒绝一次（不发信，agent 收到"已拒绝"文本并在对话里说明）→ 再触发一次批准（真的调外部 provider API 或至少真的打到 provider 的 sandbox/测试端点）。常开单测覆盖 risk_gate 分支（auto 直接过 / approval 走挂起 / 超时到 expired）不需要真 Hermes。
- 依赖：无（复用 approval_bridge/approvals 表已有基础设施）。需 agentpulse 会话：是。估算：3 天。

### TD-10-T2：推广到其余业务能力 + 前端卡片渲染
- 改动点：`social_content`→`publish_social_content`、`refund_processing`→`process_refund`、`ad_bidding`→`update_ad_bid`、`payroll_processing`→`submit_payroll`、`payment_execution`→`execute_payment` 五个能力补 `business_tool` 字段 + 各自的 MCP 工具实现（真实外部集成未配置时返回诚实的"该渠道未配置"错误，不假装成功）；`ApprovalCard` 加 `business_tool` 的按工具类型精简展示。
- 验收：每个工具至少一条单测（risk_gate 分支 + payload 展示字段正确）；前端 tsc 通过 + 浏览器实测至少一种非 email 工具的卡片渲染正常。
- 依赖：TD-10-T1。需 agentpulse 会话：否（前端 + 非真实外部集成部分）。估算：2 天。

## Definition of Done
- 员工被授予任何一个带 `risk_gate=approval/prohibited_auto` 的业务能力后，运行时**真的会在执行前停下**——不再是只在供给时起作用的静态标签。
- 老板在同一套审批 UI（允许一次/永远允许/拒绝）里处理业务危险动作，跟处理技术危险动作体验一致。
- 拒绝/超时不执行，agent 能在对话里如实说明"被拒绝了/超时了"，而不是卡死或裸执行。
- RunTrace/审批历史里能看到这些业务动作的审批记录（`approvals.type='business_tool'`）。

## 未来扩展（明确排除在本 TD 之外，留给后续独立 TD/ADR）
- 动态风险分级：同一工具按参数（金额、收件人、发布平台）区别对待，而不是能力级一刀切。
- "永远允许"规则的精细化（目前是能力级的全局放行，业务场景可能需要"这个金额以下永远允许，以上还是要问"）。
- 更多真实外部集成（更多社媒平台、更多支付网关、更多财务系统）。
