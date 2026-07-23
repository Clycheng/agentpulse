# 0011. 受控业务动作与密钥托管

- 状态: 已接受
- 日期: 2026-07-23
- 决策者: 项目所有者

## 背景

Hermes 的 ACP 审批只能识别终端、文件等技术危险动作，不能判断发邮件、发布内容、退款或付款等业务风险。TD-11 已建立按 Run 动态注入的公司内部 MCP 工具，但该端点只允许任务负责人读写当前计划，不能安全复用于聊天和外部业务动作。旧 TD-10 还假设业务密钥写入 Hermes profile、审批依赖进程内 Future、邮件已有出站 provider；这些前提均与当前代码不符，而且把 API key 交给 Hermes 会允许员工绕过审批直接调用外部服务。

## 决策

1. `/mcp/company-tools` 继续只服务任务计划；新增 `/mcp/business-tools`，使用独立 token 类型和鉴权边界，同时支持聊天 Run 与任务 Run。RunService 在数据库 Run 已存在后按员工已启用能力动态注入该端点。
2. 业务 provider 密钥由 AgentPulse 加密存储，绝不写入 Hermes profile。密钥用现有非默认 `auth_secret_key` 派生的版本化 Fernet key 加密，API 只返回是否已配置。
3. 每次业务调用先落 `business_actions`，审批、执行租约、attempt、外部 id 和结果都以数据库为真相源。审批 API 只记录决定；BusinessActionWorker 负责真实外部调用和重试。
4. `risk_gate=approval` 在没有长期策略时每次询问；“永远允许”只创建“workspace + agent + tool”策略且可撤销。`prohibited_auto` 永远只允许单次批准。
5. provider 请求必须使用稳定幂等键。应用永久保存成功结果；provider 的短期幂等窗口只覆盖崩溃、超时和租约回收期间的安全重试。
6. 首个真实 provider 是 Resend 纯文本邮件。社媒发布、退款、广告出价、薪酬和付款只注册受控工具与未配置状态，不伪造成功。

## 理由

- 独立 MCP audience 防止普通聊天 Run 获得修改任务计划的公司内部工具，同时允许同一业务审批机制覆盖聊天和自动任务。
- 密钥留在受控服务端，Hermes 只能表达业务意图，无法绕过权限、审批和审计。
- 数据库动作队列可在服务重启后恢复，并能把“外部服务已执行但响应丢失”的重复调用风险收敛到 provider 幂等键。
- 员工级长期策略符合能力和责任归属；付款类不可逆动作不能因一次批准永久放行。

## 后果

- API 进程新增 BusinessActionWorker 和第二个 FastMCP 应用；部署时两个 MCP URL都必须能被 Hermes 子进程访问。
- `auth_secret_key` 轮换后已保存的业务凭证需要重新录入；密钥值不得写日志、RunStep、审批 payload 或 API 响应。
- Resend 真机验证需要老板在桌面应用录入 API key 和发件人配置；没有凭证时测试必须跳过真实外网调用，不能伪造成功。
- TD-09 仍负责渠道出站回复和真实社媒适配；本决策不改变 TD-11 的内容包交付合同。
