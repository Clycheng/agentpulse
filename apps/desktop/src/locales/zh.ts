const translations = {
  "nav": {
    "chat": "消息",
    "staff": "员工",
    "market": "人才市场",
    "tasks": "任务",
    "ideas": "想法",
    "channels": "渠道",
    "lib": "资料库",
    "themeSettings": "主题设置",
    "light": "浅色",
    "dark": "深色",
    "system": "跟随系统",
    "logout": "退出登录",
    "language": "切换语言"
  },
  "auth": {
    "heroTitle": "把一人公司，搭成一支 AI 团队。",
    "heroSubtitle": "创建工作区后，小秘、组织架构、人才市场和会话数据都会写入 PostgreSQL。第一版先跑通真实 DeepSeek 对话闭环。",
    "feature1Title": "组织化智能体",
    "feature1Desc": "部门、员工、职责 Prompt 都能沉淀",
    "feature2Title": "从消息开始协作",
    "feature2Desc": "默认进入小秘私聊，后续拉群推进",
    "feature3Title": "真实模型调用",
    "feature3Desc": "回复会标记 provider 与 model",
    "registerEyebrow": "开始搭建",
    "loginEyebrow": "欢迎回来",
    "registerTitle": "创建你的 AI 公司",
    "loginTitle": "登录工作台",
    "registerSubtitle": "没有演示账号，提交后会创建你的真实本地工作区。",
    "loginSubtitle": "使用平台注册邮箱和密码继续进入工作台。",
    "tabRegister": "注册",
    "tabLogin": "登录",
    "email": "邮箱",
    "password": "密码",
    "passwordPlaceholder": "至少 6 位",
    "displayName": "你的称呼",
    "displayNamePlaceholder": "例如：老板",
    "workspaceName": "公司/工作室名称",
    "workspaceNamePlaceholder": "例如：我的一人公司",
    "submitting": "请稍候...",
    "submitRegister": "注册并进入",
    "submitLogin": "登录",
    "loginFailed": "登录失败",
    "emailRequired": "请填写邮箱",
    "passwordMinLength": "密码至少需要 6 位",
    "passwordRequired": "请填写密码",
    "displayNameRequired": "请填写你的称呼",
    "workspaceNameRequired": "请填写公司/工作室名称"
  },
  "chat": {
    "inviteMembers": "邀请员工",
    "relatedTasks": "关联任务",
    "relatedTasksWithCount": "关联任务 {{count}}",
    "runTrace": "运行轨迹",
    "groupDiscussion": "拉群讨论",
    "viewStatus": "查看状态",
    "sendPlaceholderGroup": "发消息给 # {{name}}，@员工 可点名",
    "sendPlaceholderDm": "发消息给 {{name}}",
    "noConversation": "暂无会话",
    "noConversationHint": "注册后系统会自动创建小秘私聊。",
    "searchPlaceholder": "搜索会话、员工、任务"
  },
  "runTrace": {
    "title": "运行轨迹",
    "description": "按时间顺序回放这个会话里每次运行的完整过程——消息、工具调用、工具结果、审批请求都摊开显示。",
    "loading": "加载中…",
    "empty": "这个会话还没有运行记录",
    "noSteps": "暂无步骤记录",
    "status": {
      "queued": "排队中",
      "running": "执行中",
      "waiting_user": "等待老板确认",
      "waiting_clarify": "等待澄清",
      "completed": "已完成",
      "failed": "失败"
    }
  },
  "staff": {
    "title": "组织内联系人",
    "summary": "{{company}} · {{agentCount}} 名 AI 员工 · {{deptCount}} 个部门 · {{busyCount}} 人执行中",
    "createEmployee": "创建员工",
    "subLevel": "下级",
    "busyMembers": "{{count}} 人执行中",
    "waitingMembers": "{{count}} 个待确认",
    "noSubDeptOrMember": "{{name}} 暂无下级部门或成员",
    "noDept": "暂无部门",
    "builtinSecretary": "内置秘书"
  },
  "common": {
    "cancel": "取消",
    "save": "保存",
    "confirm": "确认",
    "close": "关闭",
    "loading": "加载中…"
  }
} as const;

export default translations;
