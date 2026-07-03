# CLAUDE.md

**先读 [AGENTS.md](AGENTS.md)** —— 它是本项目给所有 AI / 开发者的第一份文件，定义产品方向、架构决策和开发规范。本项目所有约定都以 AGENTS.md 为准。

关键提醒（详见 AGENTS.md）：
- 本仓库是 **Clycheng 的私有仓库**，提交署名必须是 `Clycheng <30332511+Clycheng@users.noreply.github.com>`，**绝不能用其他 git 身份**。在 `main` 上开发，commit message 用英文。
- 基座是 **Hermes Agent**（不接 Codex/Claude CLI）；协作编排层（群讨论协议）自研。
- 做完任何实质工作要**记录**：架构决策进 `docs/decisions/`，改动进 `CHANGELOG.md`，并同步过时文档。
