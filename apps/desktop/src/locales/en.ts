const translations = {
  "nav": {
    "chat": "Messages",
    "staff": "Staff",
    "market": "Talent Market",
    "tasks": "Tasks",
    "ideas": "Ideas",
    "channels": "Channels",
    "lib": "Library",
    "themeSettings": "Theme settings",
    "light": "Light",
    "dark": "Dark",
    "system": "System",
    "logout": "Log out",
    "language": "Switch language"
  },
  "auth": {
    "heroTitle": "Turn your one-person company into an AI team.",
    "heroSubtitle": "Once your workspace is created, your secretary, org chart, talent market, and conversations all persist to PostgreSQL. V1 runs on a real DeepSeek conversation loop.",
    "feature1Title": "Organized agents",
    "feature1Desc": "Departments, employees, and role prompts all persist",
    "feature2Title": "Start from a message",
    "feature2Desc": "Starts in a DM with your secretary, then expand into group chats",
    "feature3Title": "Real model calls",
    "feature3Desc": "Replies are tagged with the actual provider and model",
    "registerEyebrow": "Get started",
    "loginEyebrow": "Welcome back",
    "registerTitle": "Create your AI company",
    "loginTitle": "Sign in to your workspace",
    "registerSubtitle": "There's no demo account — submitting creates a real local workspace.",
    "loginSubtitle": "Use your registered email and password to continue.",
    "tabRegister": "Register",
    "tabLogin": "Sign in",
    "email": "Email",
    "password": "Password",
    "passwordPlaceholder": "At least 6 characters",
    "displayName": "Your name",
    "displayNamePlaceholder": "e.g. Boss",
    "workspaceName": "Company / studio name",
    "workspaceNamePlaceholder": "e.g. My One-Person Company",
    "submitting": "Please wait...",
    "submitRegister": "Create & enter",
    "submitLogin": "Sign in",
    "loginFailed": "Sign-in failed",
    "emailRequired": "Please enter your email",
    "passwordMinLength": "Password must be at least 6 characters",
    "passwordRequired": "Please enter your password",
    "displayNameRequired": "Please tell us what to call you",
    "workspaceNameRequired": "Please enter a company / studio name"
  },
  "chat": {
    "inviteMembers": "Invite members",
    "relatedTasks": "Related tasks",
    "relatedTasksWithCount": "Related tasks {{count}}",
    "runTrace": "Run trace",
    "groupDiscussion": "Start group discussion",
    "viewStatus": "View status",
    "sendPlaceholderGroup": "Message #{{name}} — @mention to call on someone",
    "sendPlaceholderDm": "Message {{name}}",
    "noConversation": "No conversation yet",
    "noConversationHint": "A DM with your secretary is created automatically after signup.",
    "searchPlaceholder": "Search conversations, staff, tasks"
  },
  "runTrace": {
    "title": "Run Trace",
    "description": "Replay every run in this conversation in order — messages, tool calls, tool results, and approval requests all laid out.",
    "loading": "Loading…",
    "empty": "No runs yet in this conversation",
    "noSteps": "No steps recorded",
    "status": {
      "queued": "Queued",
      "running": "Running",
      "waiting_user": "Awaiting approval",
      "waiting_clarify": "Awaiting clarification",
      "completed": "Completed",
      "failed": "Failed"
    }
  },
  "staff": {
    "title": "Org Directory",
    "summary": "{{company}} · {{agentCount}} AI employees · {{deptCount}} departments · {{busyCount}} active",
    "createEmployee": "Add employee",
    "subLevel": "Open",
    "busyMembers": "{{count}} active",
    "waitingMembers": "{{count}} pending",
    "noSubDeptOrMember": "{{name}} has no sub-departments or members yet",
    "noDept": "No departments yet",
    "builtinSecretary": "Built-in secretary"
  },
  "common": {
    "cancel": "Cancel",
    "save": "Save",
    "confirm": "Confirm",
    "close": "Close",
    "loading": "Loading…"
  }
} as const;

export default translations;
