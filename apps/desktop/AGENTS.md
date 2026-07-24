# AgentPulse Desktop — 开发规范

## 当前状态

`src/main.tsx` (~5400 行) 是单文件 React 原型，包含：
- 所有类型定义 (View/Agent/Task/Message 等)
- 所有工具函数 (avatarText/formatTime/authHeaders 等)
- 所有 UI 组件 (App/Sidebar/ChatView/StaffView 等，~50 个)

**这是原型阶段的有意选择**——快速迭代，不等架构定稿。

## 模块化路线（未来工作）

1. 抽取 `src/types.ts` — 所有 type/interface
2. 抽取 `src/utils.tsx` — 工具函数（avatarText, formatTime, authHeaders 等）
3. 抽取 `src/api.ts` — API 调用层（`apiRequest` 等）
4. 组件拆分到 `src/components/` — 每个 View 一个文件
5. 引入轻量路由或状态管理

## 当前约束

- 修改现有功能时，保持在同一文件内
- 新增功能 >100 行时，考虑抽成独立组件文件
- 不要为了"干净"而大规模重写——优先功能交付

## 打包分发（2026-07-15 起可用）

已接入 electron-builder（`package.json` 的 `build` 字段）。

```bash
npm run package:mac    # → release/AgentPulse-<version>-arm64.dmg + .zip
npm run package:win    # → release/*.exe (nsis 安装包)
npm run package:linux  # → release/*.AppImage
```

图标源文件在 `resources/`（`icon.icns`/`icon.ico`/`icon.png`，从
`apps/site/favicon.svg` 用 `rsvg-convert` + `iconutil`/Pillow 生成，
改 logo 后要重新生成这三个文件）。

**当前分发约定（ADR 0012）**：
1. 首发是未签名公开内测包。macOS Gatekeeper 和 Windows SmartScreen 会提示
   未知开发者，官网必须展示 SHA256 和安装说明；代码签名、公证和自动更新后置。
2. 开发模式默认连接 `http://127.0.0.1:8000/api`；打包后的生产版本固定连接
   `https://api.agentpulse.cc/api`，使用 `app://agentpulse` 协议加载资源，不允许
   环境变量把发布包指向任意 API。
3. JWT 只经 preload IPC 读写 Electron `safeStorage`，renderer 不使用
   `localStorage` 持久化登录态；主进程禁止非白名单导航、弹窗和 webview。
