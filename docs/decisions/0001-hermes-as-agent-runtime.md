# 0001. 以 Hermes 为员工运行时基座

- 状态: 已接受
- 日期: 2026-07-03
- 决策者: 项目所有者

## 背景
AgentPulse 要让"AI 员工"真正具备专业能力、能调工具、有记忆、能自我进步——而不是给 LLM 套层公司皮。需要选一个 agent 运行时作基座。早期 [ROADMAP.md](../../ROADMAP.md) 倾向"多 CLI 适配(先 Codex，后 Claude/Kimi/Hermes)"。

## 决策
**以 [Hermes Agent](https://github.com/NousResearch/hermes-agent)(Nous Research 开源，MIT)为唯一员工运行时基座。** 每个 AI 员工 = 一个 Hermes `profile`(独立 HERMES_HOME：SOUL.md 人格 + Skills 技能 + Memory 记忆 + 可选模型)。
- **不**采用 Codex / Claude Code 这类"操作文件的工程师型" CLI 作基座。
- **不**自建 Agent 协议 / Runtime / 工具系统。

## 理由
- Hermes 原生具备本项目要的三大能力：**持久记忆 + 学习循环(自我进步)**、**技能系统(自然语言可定制专业性)**、**多平台 + 多实例 + 7×24 daemon**。
- 目标用户是普通人/一人公司(内容、运营、客服、销售…)，不是写代码——工程师型 CLI 不合适。
- 单基座让适配层从"养多个 CLI"简化为"对接一个 Hermes"。
- 可编程驱动已验证(HTTP Runs API / kanban / Python 库)，多实例编排是已发布能力。
- 详见 [../ARCHITECTURE.md](../ARCHITECTURE.md) §3。

## 后果
- 现有 `services/api` 直连 DeepSeek 的实现降级为**临时执行层**，后续由"后端调 Hermes profile"替换；但 workspace/task/审批/会话表保留作协作编排层骨架。
- 引入重依赖 Hermes(高速迭代中，部分多 agent 特性尚是 proposal)；多员工=多进程，吃资源。
- 后续：先做"本机 Hermes + 后端 HTTP Runs API 驱动"的地基验证。
