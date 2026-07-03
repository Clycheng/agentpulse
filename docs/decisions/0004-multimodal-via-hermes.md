# 0004. 多模态经 Hermes 辅助模型处理（DeepSeek 作文本主模型）

- 状态: 已接受
- 日期: 2026-07-03
- 决策者: 项目所有者

## 背景
计划用 DeepSeek 作主模型，但 DeepSeek 是文本模型，读不了图片/音频/视频。员工需要能处理这些媒体。

## 决策
**主模型可用 DeepSeek(文本)，多模态交给 Hermes 的能力感知路由 + 辅助模型/工具处理**，把一切模态转成文本喂给主模型：
- 图片 → `vision_analyze`，配 `auxiliary.vision` 辅助视觉模型(如 `google/gemini-2.5-flash` 或本地 `qwen2.5-vl`)。
- 音频 → 内置 Whisper STT(`stt.provider: local` 可免费离线 / groq / openai / mistral)。
- 视频 → `video_analyze`；PDF → `web_extract`。
- 每个员工可用不同主/辅模型(profiles)。

## 理由
- Hermes 原生就是这么设计的(文本主模型时自动路由到辅助模型描述→注入文本)，不用我们造。
- DeepSeek V3 满足主模型硬要求(≥64k 上下文 + function-calling)。
- 详见 [../ARCHITECTURE.md](../ARCHITECTURE.md) §3.7 / §3.8。

## 后果
- 需要为辅助视觉/语音模型配置额外的 provider/key(或本地模型)，有额外调用成本。
- 扫描件 PDF 的 OCR 未确认 Hermes 原生支持，若需要可能要额外步骤。
