# apps/desktop — 设计系统 & 前端约定（嵌套 AGENTS.md）

> 补充根 [AGENTS.md](../../AGENTS.md)。改本目录 UI 前先读这份，别把设计系统改回"通用蓝色 SaaS 仪表盘"。

## 是什么
Electron + React + Vite 单文件原型：`src/main.tsx`（逻辑/视图）+ `src/styles.css`（全部样式，token 驱动）。5 个视图：消息(chat) / 员工(staff) / 人才市场(market) / 任务(tasks) / 资料库(lib)。

## 设计方向（2026-07-09 用 impeccable skill 重做）
**register = product**（设计服务于任务，对标 Linear / Raycast / Notion 的克制感）。定位：一人 AI 公司的「运营驾驶舱」。

- **要避开的 reflex**：通用浅色 + SaaS 蓝 + 满屏等大卡片 + 每段小号 tracked eyebrow。旧版正是这个，别改回去。
- **配色策略 = Restrained**：中性 ink 底 + **单一品牌强调色 = teal「脉搏」**（`--primary`，语义=员工 7×24 永远"在工作/活着"）。teal 只用于主操作、当前选中、focus ring、live 状态——**不做装饰**。
- **语义色与品牌色分离**：success 绿 / warning 琥珀 / danger 红，都与 teal 不同色相。
- **每个 agent 有自己的 hue**（`agents.hue`，见 main.tsx）：**chrome 克制、人物带色**——头像/在线点/提及用 per-agent hue，外壳只有 ink+teal。
- **双主题**：浅色 = 干净驾驶舱；深色(`[data-theme='dark']`) = 近黑 cockpit + 更亮 teal。两套都要保持精致。

## Token 契约（`styles.css` 顶部 `:root` + `[data-theme='dark']`）
改样式**优先用 token，别写死颜色**（旧代码残留过 `rgba(49,85,200,…)` 蓝，已清理）。
- 中性：`--app-bg / --surface / --surface-muted / --surface-subtle / --border / --border-soft / --text / --text-strong / --muted / --subtle`
- 品牌：`--primary / --primary-hover / --primary-strong / --primary-soft / --primary-soft-strong / --on-primary`
- 语义：`--danger(-soft) / --success(-soft) / --warning(-soft)`
- 高度：`--shadow-xs/sm/md/lg`（+ `--shadow-soft` 别名）；focus：`--ring`（teal）
- 圆角：`--radius-sm/​/-lg/-pill`；缓动：`--ease-out`
- 字体：Latin=Inter，CJK=Noto Sans SC（一套 sans，固定 rem 梯度，非流体）

## 规矩
- 每个交互元素要有 default/hover/focus(-visible ring)/active/disabled 全套（product register 要求）。
- 动效 150–250ms、`--ease-out`、只表达状态不装饰；`prefers-reduced-motion` 已全局兜底；`pulse-ring` 关键帧只给 live/working 指示器。
- 对比度：正文 ≥4.5:1；`--subtle` 已按 placeholder/timestamp 用途调到达标，别再调浅。
- 验证：`.claude/launch.json` 里 `desktop-renderer`（Vite 5174，纯前端）。要真数据需另起后端：`services/api` 用 `AGENTPULSE_DATABASE_URL=sqlite:///…` 起 uvicorn（SQLite 免 Docker）。改 CSS 走 Vite HMR，热更不用 reload。
</content>
