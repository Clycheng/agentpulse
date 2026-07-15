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

**上线前必须处理的两件事**：
1. **签名/公证**：现在 `mac.identity` 强制设为 `null`（跳过签名），
   打出来的是未签名 App——本地测试没问题，但如果要给别人下载安装，
   macOS Gatekeeper 会直接拦截，需要 Apple Developer ID 证书 + 公证
   （`electron-builder` 原生支持，配好 `APPLE_ID`/`APPLE_APP_SPECIFIC_PASSWORD`
   等环境变量即可，去掉 `identity: null`）。Windows 同理需要代码签名证书，
   否则 SmartScreen 会报"未知发布者"警告。
2. **生产 API 地址**：桌面端默认连 `http://127.0.0.1:8000/api`
   （见 `src/main.tsx` 的 `apiBaseUrl`），构建产物前必须设置
   `VITE_AGENTPULSE_API_URL` 环境变量指向真实部署的后端域名，
   否则打包出去的客户端谁也连不上。
