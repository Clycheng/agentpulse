# TD-12: 零成本云端部署与桌面分发闭环

- 关联: [ADR 0012](../decisions/0012-cloud-hosted-desktop-distribution.md)、[ADR 0007](../decisions/0007-hermes-v0.18-interface-acp.md)、[TD-11](TD-11-autonomous-content-execution.md)
- 执行会话: **agentpulse**（需要真实 Hermes、Docker、桌面打包和线上服务验收）

## 目标与边界

打通 `agentpulse.cc` 官网下载、桌面安装、注册登录、workspace 级 DeepSeek BYOK、默认四人团队供给和云端 Hermes 执行。首版使用 Vercel、Oracle Always Free、Supabase Free 和独立 GitHub Releases 仓库，固定平台月费为零。

首版只发布未签名的 macOS Apple Silicon 与 Windows x64 内测包；明确展示系统安全提示，不实现代码签名、公证、自动更新、邮箱验证、找回密码、多节点调度或生产 SLA。

## 技术设计

### 云端拓扑

Oracle ARM64 单节点以 Docker Compose 运行 Caddy 与一个 AgentPulse API/Hermes 容器。Caddy 为 `api.agentpulse.cc` 提供 HTTPS；Hermes profiles 与 Run workdir 挂载到持久卷。Supabase 只提供 PostgreSQL，现有 AgentPulse JWT 认证保持不变。

API 镜像固定 Python 3.11、AgentPulse lockfile 与 Hermes v0.18.2 源码提交。生产只允许一个 API 副本；健康检查失败自动重启。部署脚本按镜像 digest 更新，ready 检查失败恢复上一 digest。数据库每日 `pg_dump`，本地加密保留七天。

### Workspace BYOK

`workspace_model_credentials` 以 workspace/provider 唯一，保存版本化 Fernet 密文、模型、验证状态和时间。注册只创建工作区、四名员工与内容经营群；没有模型 Key 时 profile 状态为等待凭证，不启动 Run。

`PUT /api/settings/model-provider` 只接受 DeepSeek 和服务端白名单模型。Key 经 provider 验证后加密保存，并幂等供给 workspace 的员工。Hermes ACP 子进程按 Run 注入解密后的 `DEEPSEEK_API_KEY`；Key 不写 profile、RunStep、日志或 API 响应。撤销 Key 后阻止新 Run，保留员工记忆和历史数据。

### 认证与桌面边界

公开注册最多 100 个用户。单节点内实现可信代理后的 IP 限流：注册每小时 5 次，登录每 10 分钟 10 次。达到上限返回稳定错误码，桌面显示内测名额已满。

生产 Electron 使用 `app://agentpulse` 自定义安全协议加载静态资源，固定 API 为 `https://api.agentpulse.cc/api`。主进程限制导航和新窗口；JWT 通过 preload IPC 交给 Electron `safeStorage`，renderer 不持久保存 token。

### 发布与官网

源码仓与发布仓分离。`Clycheng/agentpulse-releases` 只保存 DMG/ZIP/EXE、SHA256 和 `latest.json`。发布 workflow 在 `v*` 标签校验版本、跑测试并构建 macOS arm64 与 Windows x64，使用固定资产名上传；不启用未签名自动更新。

Vercel 以 `agentpulse.cc` 为主域，`www` 重定向到 apex。官网按平台推荐下载并始终展示其他平台、版本、校验值和未签名安装步骤；接入无 Cookie 的 Vercel Web Analytics 与下载事件。

## Tech-Tasks

### TD-12-T1: 生产 API 与 workspace BYOK

实现双数据库 schema、加密凭证 API、DeepSeek 验证、Hermes 每 Run 环境注入、注册上限/限流和 live/ready 健康检查。

验收: 明文不落库/profile/log/API；跨 workspace 隔离；错误、撤销、重新供给和限流都有测试。

### TD-12-T2: 桌面生产安全与设置

实现 `app://` 协议、生产 API 构建保护、safeStorage 会话桥和 DeepSeek onboarding/settings UI。

验收: 注册后可配置 Key 并看到四人供给状态；renderer 无持久 token；desktop lint/build 通过。

### TD-12-T3: 容器、云端部署与发布流水线

实现 ARM64 Dockerfile、Compose/Caddy、备份/部署回滚脚本、GitHub Actions 和 release manifest。

验收: ARM64 镜像可启动，重启后 profile/任务恢复；tag 产生 macOS/Windows 资产和可验证 SHA256。

### TD-12-T4: 官网下载、域名与线上验收

实现下载页、安装说明、Analytics 事件并修复 apex/www/API DNS。完成真实下载、安装、注册、BYOK、讨论、launch、重启恢复和内容包交付。

验收: DNS/HTTPS、下载、分析事件和完整桌面流程有真实证据；无法自动完成的账号验证明确记录。

