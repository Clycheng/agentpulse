# TD-09：外部渠道接入（Channel Adapters）

- 关联 ADR：[0006](../decisions/0006-group-discussion-v1-first-slice.md)（会话/消息基础）
- 执行会话：**否**（纯 HTTP 路由 + 适配器代码，不碰 Hermes）。

## 产品目标

目前 AgentPulse 只能在 App 内主动发起对话。对于客服/运营场景，用户（客户/外部人员）通过**微信/邮件/网页表单**发来消息时，AI 员工应该能自动接收并处理——不需要老板手动转发。

核心设计原则：**渠道对 agent 透明**。agent 不知道也不需要知道消息来自哪个渠道，它只看到标准化的消息进入会话，像内部对话一样处理。

---

## 技术设计

### 整体架构

```
外部消息
  微信/WeCom webhook  ──┐
  邮件 (SMTP/webhook)  ──┤──▶ POST /webhooks/{channel}/{token}
  网页表单 / widget    ──┤           │
  通用 webhook        ──┘           ▼
                               ChannelRouter
                                    │
                    ┌───────────────┤───────────────┐
                    ▼               ▼               ▼
             找或建 conversation  标准化消息       dedup 检查
                    │               │               │
                    └───────────────┴───────────────┘
                                    │
                                    ▼
                        现有 send_message 流程（完全复用）
                                    │
                                    ▼
                    agent 处理 → 回复消息
                                    │
                                    ▼
                            ChannelReply
                    发回原始渠道（微信回复/发邮件/widget 推送）
```

### 数据模型（新增表 + 扩列，两 schema 都加）

**新增 `channel_configs` 表**：
| 列 | 类型 | 说明 |
|---|---|---|
| `id` | TEXT PK | `chan_xxx` |
| `workspace_id` | TEXT NOT NULL FK→workspaces CASCADE | |
| `channel_type` | TEXT NOT NULL CHECK IN (`wechat`,`email`,`web_widget`,`generic_webhook`) | |
| `name` | TEXT NOT NULL | 用户给这个渠道起的名字，如"官网客服入口" |
| `token` | TEXT NOT NULL UNIQUE | 随机生成，用于 webhook URL：`/webhooks/{type}/{token}` |
| `config_json` | TEXT NOT NULL DEFAULT `'{}'` | 渠道特定配置（见下方各渠道字段） |
| `target_agent_id` | TEXT FK→agents SET NULL 可空 | 该渠道消息默认分配给哪个员工（空=路由逻辑决定） |
| `target_conversation_id` | TEXT FK→conversations SET NULL 可空 | 固定群（如客服群），空=每个外部用户单独开会话 |
| `active` | BOOLEAN NOT NULL DEFAULT TRUE | |
| `created_at` | TEXT NOT NULL | |

**`conversations` 扩列**：
- `source_channel TEXT 可空`：哪个渠道来的（`wechat`/`email`/`web_widget`/`generic_webhook`/null）
- `external_conversation_id TEXT 可空`：外部会话标识（微信 openid/邮件 thread_id），同一外部用户的消息归入同一会话

**`messages` 扩列**：
- `external_message_id TEXT 可空`：外部消息唯一 ID，用于去重（同一条消息 webhook 可能重发）

### 各渠道 config_json 字段

**微信公众号/企业微信（wechat）**：
```json
{ "app_id": "...", "app_secret": "...", "token": "...", "encoding_aes_key": "..." }
```
消息验证：微信标准签名验证（sha1(token+timestamp+nonce)）。

**邮件（email）**：
```json
{ "provider": "sendgrid|mailgun|generic",
  "inbound_webhook_key": "...",
  "reply_from": "support@company.com",
  "api_key": "..." }
```
收信：支持 SendGrid/Mailgun 的 inbound parse webhook。
发信：通过邮件服务商 API 发回复（**不直连 SMTP**，安全）。

**网页 Widget（web_widget）**：
```json
{ "allowed_origins": ["https://company.com"] }
```
前端嵌入代码：`<script src="https://agentpulse.io/widget.js" data-token="{token}"></script>`。
WebSocket 或 SSE 双向通信，无需第三方依赖。

**通用 Webhook（generic_webhook）**：
```json
{ "secret": "...", "message_path": "$.message", "user_id_path": "$.user.id", "reply_url": "..." }
```
任何能发 POST JSON 的系统都可接入，用 JSONPath 提取消息体。

### ChannelRouter 核心逻辑（`services/api/app/channels/router.py`）

```python
async def route_inbound(channel_config: Row, raw_payload: dict) -> None:
    msg = adapter.normalize(channel_config, raw_payload)
    # → ChannelMessage(external_user_id, content, external_message_id, timestamp)

    # dedup
    if await message_already_processed(conn, channel_config.id, msg.external_message_id):
        return

    # 找或建 conversation
    conv = await find_or_create_conversation(conn, channel_config, msg.external_user_id)
    # 规则：
    #   target_conversation_id 有值 → 用固定群（适合客服总群）
    #   否则按 (channel_config_id, external_user_id) 查找现有会话，没有则建新 DM/群
    #   会话 source_channel = channel_type, external_conversation_id = external_user_id

    # 写消息（sender_type='user', sender_id=external_user_id）
    message = await create_message(conn, conversation_id=conv.id, content=msg.content, ...)

    # 复用现有 send_message 触发 agent 处理
    await trigger_agent_response(conn, conv.id, message.id)
    # agent 回复后，ChannelReply 把结果发回原渠道
```

### ChannelReply（回复发回原渠道）

agent 回复写入 messages 表后，`ChannelReply` 检查 `conversation.source_channel` 决定如何回复：

| 渠道 | 回复方式 |
|---|---|
| `wechat` | 调微信 API 发消息到 openid |
| `email` | 调邮件服务商 API 发回复邮件（回复同一 thread） |
| `web_widget` | 通过 WebSocket/SSE 推送到 widget |
| `generic_webhook` | POST 到 `config_json.reply_url` |
| null（内部） | 不处理，前端轮询自取 |

---

## API 契约

| 接口 | 方法 | 说明 |
|---|---|---|
| `GET /api/channels` | GET | 列出工作区所有渠道配置 |
| `POST /api/channels` | POST | 创建渠道（返回 webhook URL） |
| `GET /api/channels/{id}` | GET | 渠道详情 + 统计（今日消息数/活跃外部用户数） |
| `PATCH /api/channels/{id}` | PATCH | 更新配置/active 状态 |
| `DELETE /api/channels/{id}` | DELETE | 删除渠道（软删，active=false） |
| `POST /webhooks/{channel_type}/{token}` | POST | **公开端点**，各渠道 webhook 接收（无需认证，用 token + 签名验证） |
| `GET /widget.js` | GET | 网页 widget JS 文件（CDN 分发，按 token 初始化） |

---

## Tech-Tasks

### TD-09-T1：数据模型 + 基础 Router
- 改动点：`channel_configs` 建表；`conversations/messages` 扩列（双 schema）；`channels/router.py` 实现 `route_inbound` + dedup + find_or_create_conversation；`channels/adapters/` 目录（各渠道归一化）。
- 验收：单测——相同 external_message_id 第二次调用不建重复消息；target_conversation_id 有值时路由到固定群；无值时按 external_user_id 找到已有会话。
- 依赖：无（基于已有 conversations/messages 表）。需 agentpulse 会话：否。估算：1.5 天。

### TD-09-T2：渠道管理 API + Webhook 端点
- 改动点：`channels/webhook_handler.py`（`/webhooks/{type}/{token}`，验签 + 调 router）；`channels/` 的 CRUD API；各渠道 adapter（微信/邮件/generic 各一个文件）。
- 验收：用 curl 或 ngrok 向 `/webhooks/generic_webhook/{token}` POST 一条消息 → messages 表有记录 → agent 产生回复。
- 依赖：TD-09-T1。需 agentpulse 会话：否（端到端测试需真实 agent，但 adapter 逻辑可 mock）。估算：2 天。

### TD-09-T3：ChannelReply + 网页 Widget
- 改动点：`channels/reply.py`（agent 回复后按 source_channel 回发）；网页 widget JS + SSE 端点；桌面端渠道管理页面（创建/查看渠道、复制 webhook URL / widget 嵌入代码）。
- 验收：端到端——网页 widget 发消息 → agent 回复 → widget 里实时显示回复。微信/邮件验证在真实账号下做。
- 依赖：TD-09-T2。需 agentpulse 会话：否。估算：2 天。

## Definition of Done
- 工作区能创建多个渠道（邮件/微信/网页/通用 webhook）。
- 外部消息进入 → agent 自动处理 → 回复发回原渠道，全程无需老板转发。
- 同一外部用户的多条消息自动归入同一会话（线程连续）。
- agent 层完全不感知渠道类型，零代码改动。
