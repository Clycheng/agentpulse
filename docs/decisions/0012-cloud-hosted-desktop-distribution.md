# 0012. 云端托管的薄桌面客户端与 BYOK 分发

- 状态: 已接受
- 日期: 2026-07-23
- 决策者: 项目所有者

## 背景

AgentPulse 已具备讨论、持久任务接力、Hermes 执行和受控业务动作，但 Electron 仍默认连接本机 API，模型 Key 是服务器全局配置，也没有可复现的生产镜像、安装包发布或官网下载链路。用户需要下载安装后登录并使用自己的模型 Key，而不是在本机安装 Python、PostgreSQL 和 Hermes。

首轮公开内测要求固定平台月费为零，并接受免费层容量、无 SLA 和未签名安装提示。

## 决策

1. Electron 保持薄客户端；AgentPulse API、调度 worker 与 Hermes profiles 运行在一个持久化云端单节点，不把运行时打入安装包。
2. Oracle Always Free 承载 ARM64 API/Hermes，Supabase Free 承载 PostgreSQL，Vercel 承载官网，独立公开 GitHub Releases 仓库存放安装包。源码仓可见性不在本决策中改变。
3. 模型费用由 workspace 所有者承担。DeepSeek Key 由 AgentPulse 加密托管，只在对应 workspace 的 Hermes ACP 子进程环境中短暂注入，不写入 profile。
4. 首发 macOS Apple Silicon 与 Windows x64 未签名内测包。官网必须解释安装警告并提供 SHA256；签名、公证和自动更新后置。
5. 单节点是首版硬边界。生产只运行一个 API 副本；数据库仍是业务状态真相源，Hermes profile/记忆/workdir 使用节点持久卷。

## 理由

- 薄客户端让用户关机后员工仍能执行，也避免要求普通用户维护运行时和数据库。
- BYOK 把推理费用和密钥所有权留给用户，符合零固定成本约束；按 Run 注入比把 Key 写进 profile 更容易保证租户隔离。
- 免费云资源足以验证小规模内测，但不足以承诺高可用。明确单节点比伪装成集群更诚实，也与当前本地 profile 文件模型一致。
- 独立发布仓可以公开分发二进制而不耦合源码仓可见性。

## 后果

- Oracle 注册、容量和银行卡验证是外部人工依赖；无法获得实例时可临时用受控隧道接入本机，域名和客户端契约不变。
- Supabase Free 没有生产 SLA/免费自动备份，必须增加应用侧备份并接受闲置暂停风险。
- `auth_secret_key` 同时保护 JWT 和凭证派生密钥，生产部署必须持久备份，轮换前需实现显式重加密。
- 多节点扩容前必须先把 Hermes profile/记忆迁移到共享或可复制存储，并重新审计跨进程审批与租约行为。

