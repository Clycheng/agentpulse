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
