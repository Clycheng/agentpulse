# Changelog

本文件记录 AgentPulse 值得留痕的改动。**每次做完实质工作请在顶部追加一条**（见 [AGENTS.md](AGENTS.md) §5）。
架构/方向级决策另记在 [docs/decisions/](docs/decisions/)。格式参考 [Keep a Changelog](https://keepachangelog.com/)。

## [Unreleased]

### 2026-07-03
- **docs**: 对齐 AGENTS.md 开放标准 / Claude Code 官方实践——`CLAUDE.md` 改用 `@AGENTS.md` import(会话开头自动加载)；AGENTS.md 补充"文档随项目生长"约定(嵌套 AGENTS.md 就近生效 + `.claude/rules` 路径域 + skills)。
- **docs**: 新增项目基准文档，供后续 AI/开发者接手即对齐、防跑偏：
  - `AGENTS.md`（北极星 + 架构决策 + 开发规范 + 文档索引）、`CLAUDE.md`（指向 AGENTS.md）
  - `docs/ARCHITECTURE.md`（详细架构 + 调研结论 + 出处）
  - `docs/decisions/` ADR：0001 Hermes 为基座、0002 自研群讨论、0003 服务端7×24+idea中心、0004 多模态经 Hermes
  - 本 `CHANGELOG.md`
- **决策**：确定技术路线 = Hermes 为员工运行时基座 + 自研群讨论协作层(照 AutoGen) + 服务端 7×24 + idea 中心。详见 ADR 0001–0004。
- **feat(desktop)**: 聊天内联审批卡片——审批请求直接出现在对应会话，老板可当场批准/驳回（`apps/desktop`）。
- **feat(desktop)**: 聊天头部关联任务栏——会话正在驱动的任务以可点击 chip 展示（等级+状态），点击开任务详情。

<!-- 追加新条目到此区块顶部；发版时归档为带版本号的小节 -->
