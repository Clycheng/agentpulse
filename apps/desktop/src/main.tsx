import { StrictMode, useEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode, RefObject } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';

type View = 'chat' | 'staff' | 'market' | 'tasks' | 'lib';
type ThemeMode = 'system' | 'light' | 'dark';
type EffectiveTheme = 'light' | 'dark';
type AgentStatus = 'busy' | 'wait' | 'stuck' | 'idle';
type TaskStatus = '待认领' | '进行中' | '待确认' | '阻塞' | '已完成';
type Priority = 'P0' | 'P1' | 'P2';
type LibraryTab = 'docs' | 'skills' | 'mcp';

type User = {
  id: string;
  email: string;
  display_name: string;
};

type Workspace = {
  id: string;
  name: string;
  onboarding_completed: boolean;
};

type Department = {
  id: string;
  name: string;
  sort_order: number;
};

type Agent = {
  id: string;
  name: string;
  role: string;
  description: string;
  dept: string;
  departmentId: string;
  hue: number;
  glyph: string;
  statusKind: AgentStatus;
  statusLabel: string;
  joined: string;
  prompt: string;
  skills: string[];
  mcps: string[];
  experiences: AgentExperience[];
};

type Chat =
  | {
      id: string;
      kind: 'dm';
      agentId: string;
      unread: number;
      time: string;
    }
  | {
      id: string;
      kind: 'group';
      name: string;
      memberIds: string[];
      unread: number;
      time: string;
    };

type Message = {
  id: string;
  from: string;
  type: 'system' | 'text';
  time: string;
  text: string;
  provider?: string;
  model?: string;
};

type Task = {
  id: string;
  title: string;
  description: string;
  pr: Priority;
  owner: string;
  status: TaskStatus;
  progress: number;
  src: string;
  srcLabel: string;
  dueDate?: string | null;
  parentTaskId?: string | null;
  createdAt: string;
  updatedAt: string;
  events: TaskEvent[];
  outputs: TaskOutput[];
  approvals: Approval[];
};

type TaskEvent = {
  id: string;
  taskId: string;
  conversationId: string | null;
  agentId: string | null;
  kind: string;
  title: string;
  content: string;
  time: string;
};

type TaskOutput = {
  id: string;
  taskId: string;
  conversationId: string | null;
  agentId: string | null;
  title: string;
  outputType: string;
  content: string;
  time: string;
};

type Approval = {
  id: string;
  taskId: string | null;
  conversationId: string | null;
  agentId: string | null;
  title: string;
  description: string;
  status: 'pending' | 'approved' | 'rejected' | string;
  riskLevel: string;
  resolvedBy: string;
  resolvedAt: string | null;
  time: string;
};

type AgentExperience = {
  id: string;
  agentId: string;
  taskId: string | null;
  outcome: 'success' | 'lesson' | string;
  summary: string;
  lessons: string;
  time: string;
};

type HireTemplate = {
  id: string;
  name: string;
  categoryId: string;
  category: string;
  dept: string;
  desc: string;
  prompt: string;
  skills: string[];
  mcps: string[];
  publisher: string;
  version: string;
  status: string;
};

type TalentCategory = {
  id: string;
  name: string;
  description: string;
  sortOrder: number;
};

type ToastState = {
  visible: boolean;
  message: string;
};

type ApiBootstrap = {
  workspace: Workspace;
  departments: Department[];
  agents: Array<{
    id: string;
    name: string;
    role: string;
    description: string;
    department_id: string;
    prompt: string;
    hue: number;
    glyph: string;
    status_kind: string;
    status_label: string;
    joined: string;
    skills: string[];
    mcps: string[];
  }>;
  conversations: Array<{
    id: string;
    kind: 'dm' | 'group';
    name: string;
    agent_id: string | null;
    member_ids: string[];
    unread: number;
    updated_at: string;
  }>;
  messages_by_conversation: Record<
    string,
    Array<{
      id: string;
      sender_type: 'user' | 'agent' | 'system';
      sender_id: string;
      content: string;
      created_at: string;
      provider?: string | null;
      model?: string | null;
    }>
  >;
  tasks: Array<{
    id: string;
    title: string;
    description: string;
    priority: string;
    owner_agent_id: string | null;
    status: string;
    progress: number;
    conversation_id: string | null;
    due_date?: string | null;
    parent_task_id?: string | null;
    created_at: string;
    updated_at: string;
  }>;
  task_events_by_task: Record<
    string,
    Array<{
      id: string;
      task_id: string;
      conversation_id: string | null;
      agent_id: string | null;
      kind: string;
      title: string;
      content: string;
      created_at: string;
    }>
  >;
  task_outputs_by_task: Record<
    string,
    Array<{
      id: string;
      task_id: string;
      conversation_id: string | null;
      agent_id: string | null;
      title: string;
      output_type: string;
      content: string;
      created_at: string;
    }>
  >;
  approvals_by_task: Record<
    string,
    Array<{
      id: string;
      task_id: string | null;
      conversation_id: string | null;
      agent_id: string | null;
      title: string;
      description: string;
      status: string;
      risk_level: string;
      resolved_by: string;
      resolved_at: string | null;
      created_at: string;
    }>
  >;
  agent_experiences_by_agent: Record<
    string,
    Array<{
      id: string;
      agent_id: string;
      task_id: string | null;
      outcome: string;
      summary: string;
      lessons: string;
      created_at: string;
    }>
  >;
  agent_templates: Array<{
    id: string;
    name: string;
    category_id: string;
    category: string;
    department: string;
    description: string;
    prompt: string;
    skills: string[];
    mcps: string[];
    publisher?: string;
    version?: string;
    status?: string;
  }>;
  agent_template_categories: Array<{
    id: string;
    name: string;
    description: string;
    sort_order: number;
  }>;
};

const themeOptions: Array<{
  mode: ThemeMode;
  icon: string;
  label: string;
}> = [
  { mode: 'light', icon: 'light_mode', label: '浅色' },
  { mode: 'dark', icon: 'dark_mode', label: '深色' },
  { mode: 'system', icon: 'computer', label: '跟随系统' },
];

const apiBaseUrl =
  import.meta.env.VITE_AGENTPULSE_API_URL ?? 'http://127.0.0.1:8000/api';
const tokenStorageKey = 'agentpulse_access_token';
const userStorageKey = 'agentpulse_user';

let messageCounter = 1;
const tempMessageId = () => `temp_${messageCounter++}`;

const materialIcon = (name: string, className?: string) => (
  <span
    aria-hidden="true"
    className={className ? `material-symbol ${className}` : 'material-symbol'}
  >
    {name}
  </span>
);

const avatarColor = (agent: Agent) => `oklch(0.55 0.11 ${agent.hue})`;

function avatarText(name: string) {
  const normalized = name.trim();
  if (!normalized) return '?';
  return Array.from(normalized).slice(0, 2).join('');
}

function getInitialThemeMode(): ThemeMode {
  const stored = localStorage.getItem('agentpulse_theme_mode');
  return stored === 'light' || stored === 'dark' || stored === 'system'
    ? stored
    : 'light';
}

function getSystemTheme(): EffectiveTheme {
  return window.matchMedia('(prefers-color-scheme: dark)').matches
    ? 'dark'
    : 'light';
}

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function getMentionContext(value: string, cursor: number) {
  if (cursor < 0) return null;
  const beforeCursor = value.slice(0, cursor);
  const match = /(^|\s)@([^\s@]*)$/.exec(beforeCursor);
  if (!match) return null;

  return {
    query: match[2],
    start: beforeCursor.length - match[2].length - 1,
  };
}

function renderMentionText(text: string, agents: Agent[]): ReactNode {
  const mentionNames = Array.from(
    new Set([...agents.map((agent) => agent.name), '老板']),
  )
    .filter(Boolean)
    .sort((left, right) => right.length - left.length);

  if (!mentionNames.length) return text;

  const pattern = new RegExp(
    `@(${mentionNames.map(escapeRegExp).join('|')})(?=\\s|$|[，。！？、,.!?;；:：])`,
    'g',
  );
  const nodes: ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      nodes.push(text.slice(lastIndex, match.index));
    }
    nodes.push(
      <span className="mention-token" key={`${match.index}-${match[0]}`}>
        {match[0]}
      </span>,
    );
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < text.length) nodes.push(text.slice(lastIndex));
  return nodes.length ? nodes : text;
}

function resolveMentionedAgent(
  text: string,
  memberIds: string[],
  agents: Agent[],
) {
  return agents.find(
    (agent) =>
      memberIds.includes(agent.id) &&
      new RegExp(
        `@${escapeRegExp(agent.name)}(?=\\s|$|[，。！？、,.!?;；:：])`,
      ).test(text),
  );
}

function dotColor(status: AgentStatus) {
  return {
    busy: '#3B5BDB',
    wait: '#D97706',
    stuck: '#DC2626',
    idle: '#9AA1AD',
  }[status];
}

function priorityStyle(priority: Priority) {
  if (priority === 'P0') return { background: '#FEECEA', color: '#B42318' };
  if (priority === 'P1') return { background: '#FEF3E2', color: '#B45309' };
  return { background: '#F2F4F7', color: '#475467' };
}

function statusStyle(status: TaskStatus) {
  if (status === '待认领')
    return { background: '#F2F4F7', color: '#475467', bar: '#98A2B3' };
  if (status === '进行中')
    return { background: '#EEF1FB', color: '#3B5BDB', bar: '#3B5BDB' };
  if (status === '待确认')
    return { background: '#FEF3E2', color: '#B45309', bar: '#D97706' };
  if (status === '阻塞')
    return { background: '#FDF1F0', color: '#C0392B', bar: '#DC2626' };
  return { background: '#EEF4EE', color: '#16803C', bar: '#16A34A' };
}

function formatTime(value: string) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
  });
}

function normalizeStatus(value: string): AgentStatus {
  return value === 'busy' ||
    value === 'wait' ||
    value === 'stuck' ||
    value === 'idle'
    ? value
    : 'idle';
}

function normalizePriority(value: string): Priority {
  return value === 'P0' || value === 'P1' || value === 'P2' ? value : 'P2';
}

function normalizeTaskStatus(value: string): TaskStatus {
  return value === '进行中' ||
    value === '待认领' ||
    value === '待确认' ||
    value === '阻塞' ||
    value === '已完成'
    ? value
    : value === '卡住'
      ? '阻塞'
      : '进行中';
}

function nextTaskStatus(status: TaskStatus): TaskStatus {
  if (status === '待认领') return '进行中';
  if (status === '进行中') return '待确认';
  if (status === '待确认') return '已完成';
  if (status === '阻塞') return '进行中';
  return '已完成';
}

function progressForNextStatus(status: TaskStatus, current: number) {
  if (status === '已完成') return 100;
  if (status === '待认领') return 0;
  if (status === '待确认') return Math.max(current, 80);
  if (status === '进行中') return Math.max(current, 20);
  return current;
}

function authHeaders(token: string) {
  return { Authorization: `Bearer ${token}` };
}

async function apiRequest<T>(
  path: string,
  options: RequestInit & { token?: string } = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set('Content-Type', 'application/json');
  if (options.token) headers.set('Authorization', `Bearer ${options.token}`);

  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...options,
    headers,
  });
  const payload = await response
    .json()
    .catch(() => ({ detail: '后端返回了无法解析的响应' }));
  if (!response.ok) {
    throw new Error(formatApiError(payload, response.status));
  }
  return payload as T;
}

function formatApiError(payload: unknown, status: number) {
  if (payload && typeof payload === 'object' && 'detail' in payload) {
    const detail = (payload as { detail: unknown }).detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) {
      const messages = detail
        .map((item) => {
          if (!item || typeof item !== 'object') return '';
          const record = item as {
            loc?: unknown[];
            msg?: unknown;
            type?: unknown;
          };
          const field =
            Array.isArray(record.loc) && record.loc.length
              ? fieldLabel(String(record.loc.at(-1)))
              : '字段';
          const message =
            typeof record.msg === 'string' ? record.msg : '格式不正确';
          if (
            typeof record.type === 'string' &&
            record.type.includes('string_too_short')
          ) {
            return `${field}不能为空`;
          }
          return `${field}${message}`;
        })
        .filter(Boolean);
      if (messages.length) return messages.join('，');
    }
  }
  return `请求失败：${status}`;
}

function fieldLabel(field: string) {
  return (
    {
      email: '邮箱',
      password: '密码',
      display_name: '你的称呼',
      workspace_name: '公司/工作室名称',
      content: '消息',
    }[field] ?? field
  );
}

function mapBootstrap(data: ApiBootstrap) {
  const departmentsById = new Map(
    data.departments.map((department) => [department.id, department]),
  );
  const agents: Agent[] = data.agents.map((agent) => ({
    id: agent.id,
    name: agent.name,
    role: agent.role,
    description: agent.description,
    dept: departmentsById.get(agent.department_id)?.name ?? '未分配',
    departmentId: agent.department_id,
    hue: agent.hue,
    glyph: agent.glyph,
    statusKind: normalizeStatus(agent.status_kind),
    statusLabel: agent.status_label,
    joined: agent.joined,
    prompt: agent.prompt,
    skills: agent.skills,
    mcps: agent.mcps,
    experiences: (data.agent_experiences_by_agent[agent.id] ?? []).map(
      (experience) => ({
        id: experience.id,
        agentId: experience.agent_id,
        taskId: experience.task_id,
        outcome: experience.outcome,
        summary: experience.summary,
        lessons: experience.lessons,
        time: formatTime(experience.created_at),
      }),
    ),
  }));
  const agentById = new Map(agents.map((agent) => [agent.id, agent]));
  const chats: Chat[] = data.conversations.map((chat) => {
    if (chat.kind === 'dm') {
      return {
        id: chat.id,
        kind: 'dm',
        agentId: chat.agent_id ?? chat.member_ids[0] ?? '',
        unread: chat.unread,
        time: formatTime(chat.updated_at),
      };
    }
    return {
      id: chat.id,
      kind: 'group',
      name: chat.name,
      memberIds: chat.member_ids,
      unread: chat.unread,
      time: formatTime(chat.updated_at),
    };
  });
  const messagesByChat: Record<string, Message[]> = Object.fromEntries(
    Object.entries(data.messages_by_conversation).map(
      ([conversationId, rows]) => [
        conversationId,
        rows.map((message) => ({
          id: message.id,
          from:
            message.sender_type === 'user'
              ? 'boss'
              : message.sender_type === 'system'
                ? 'system'
                : message.sender_id,
          type: message.sender_type === 'system' ? 'system' : 'text',
          time: formatTime(message.created_at),
          text: message.content,
          provider: message.provider ?? undefined,
          model: message.model ?? undefined,
        })),
      ],
    ),
  );
  const chatById = new Map(chats.map((chat) => [chat.id, chat]));
  const tasks: Task[] = data.tasks.map((task) => {
    const chat = task.conversation_id
      ? chatById.get(task.conversation_id)
      : null;
    const owner = task.owner_agent_id
      ? agentById.get(task.owner_agent_id)
      : null;
    return {
      id: task.id,
      title: task.title,
      description: task.description,
      pr: normalizePriority(task.priority),
      owner: task.owner_agent_id ?? '',
      status: normalizeTaskStatus(task.status),
      progress: task.progress,
      src: task.conversation_id ?? '',
      srcLabel: chat
        ? chat.kind === 'dm'
          ? `私聊 · ${owner?.name ?? '员工'}`
          : `#${chat.name}`
        : '未关联会话',
      dueDate: task.due_date ?? null,
      parentTaskId: task.parent_task_id ?? null,
      createdAt: formatTime(task.created_at),
      updatedAt: formatTime(task.updated_at),
      events: (data.task_events_by_task[task.id] ?? []).map((event) => ({
        id: event.id,
        taskId: event.task_id,
        conversationId: event.conversation_id,
        agentId: event.agent_id,
        kind: event.kind,
        title: event.title,
        content: event.content,
        time: formatTime(event.created_at),
      })),
      outputs: (data.task_outputs_by_task[task.id] ?? []).map((output) => ({
        id: output.id,
        taskId: output.task_id,
        conversationId: output.conversation_id,
        agentId: output.agent_id,
        title: output.title,
        outputType: output.output_type,
        content: output.content,
        time: formatTime(output.created_at),
      })),
      approvals: (data.approvals_by_task[task.id] ?? []).map((approval) => ({
        id: approval.id,
        taskId: approval.task_id,
        conversationId: approval.conversation_id,
        agentId: approval.agent_id,
        title: approval.title,
        description: approval.description,
        status: approval.status,
        riskLevel: approval.risk_level,
        resolvedBy: approval.resolved_by,
        resolvedAt: approval.resolved_at
          ? formatTime(approval.resolved_at)
          : null,
        time: formatTime(approval.created_at),
      })),
    };
  });
  const templates: HireTemplate[] = data.agent_templates.map((template) => ({
    id: template.id,
    name: template.name,
    categoryId: template.category_id,
    category: template.category,
    dept: template.department,
    desc: template.description,
    prompt: template.prompt,
    skills: template.skills,
    mcps: template.mcps,
    publisher: template.publisher ?? 'AgentPulse 官方',
    version: template.version ?? 'v0.1.0',
    status: template.status ?? 'published',
  }));
  const talentCategories: TalentCategory[] = data.agent_template_categories
    .map((category) => ({
      id: category.id,
      name: category.name,
      description: category.description,
      sortOrder: category.sort_order,
    }))
    .sort((left, right) => left.sortOrder - right.sortOrder);

  return {
    workspace: data.workspace,
    departments: data.departments,
    agents,
    chats,
    messagesByChat,
    tasks,
    templates,
    talentCategories,
  };
}

function App() {
  const [themeMode, setThemeMode] = useState<ThemeMode>(getInitialThemeMode);
  const [systemTheme, setSystemTheme] =
    useState<EffectiveTheme>(getSystemTheme);
  const [token, setToken] = useState(() =>
    localStorage.getItem(tokenStorageKey),
  );
  const [user, setUser] = useState<User | null>(() => {
    const raw = localStorage.getItem(userStorageKey);
    if (!raw) return null;
    try {
      return JSON.parse(raw) as User;
    } catch {
      return null;
    }
  });
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [chats, setChats] = useState<Chat[]>([]);
  const [messagesByChat, setMessagesByChat] = useState<
    Record<string, Message[]>
  >({});
  const [tasks, setTasks] = useState<Task[]>([]);
  const [hireTemplates, setHireTemplates] = useState<HireTemplate[]>([]);
  const [talentCategories, setTalentCategories] = useState<TalentCategory[]>(
    [],
  );
  const [bootLoading, setBootLoading] = useState(Boolean(token));
  const [authError, setAuthError] = useState('');
  const [view, setView] = useState<View>('chat');
  const [chatId, setChatId] = useState('');
  const [draft, setDraft] = useState('');
  const [detailId, setDetailId] = useState<string | null>(null);
  const [hireOpen, setHireOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [groupOpen, setGroupOpen] = useState(false);
  const [inviteOpen, setInviteOpen] = useState(false);
  const [taskOpen, setTaskOpen] = useState(false);
  const [taskDetailId, setTaskDetailId] = useState<string | null>(null);
  const [claimTaskId, setClaimTaskId] = useState<string | null>(null);
  const [claimAgentId, setClaimAgentId] = useState('');
  const [taskFilter, setTaskFilter] = useState<TaskStatus | '全部'>('全部');
  const [libraryTab, setLibraryTab] = useState<LibraryTab>('docs');
  const [typingName, setTypingName] = useState<string | null>(null);
  const [toast, setToast] = useState<ToastState>({
    visible: false,
    message: '',
  });
  const [hireTpl, setHireTpl] = useState('');
  const [hireDept, setHireDept] = useState('');
  const [createName, setCreateName] = useState('');
  const [createDesc, setCreateDesc] = useState('');
  const [createDept, setCreateDept] = useState('');
  const [createPrompt, setCreatePrompt] = useState('');
  const [groupName, setGroupName] = useState('');
  const [groupMembers, setGroupMembers] = useState<string[]>([]);
  const [groupTaskIds, setGroupTaskIds] = useState<string[]>([]);
  const [inviteMembers, setInviteMembers] = useState<string[]>([]);
  const [taskScopeChatId, setTaskScopeChatId] = useState<string | null>(null);
  const [taskTitle, setTaskTitle] = useState('');
  const [taskDesc, setTaskDesc] = useState('');
  const [taskPriority, setTaskPriority] = useState<Priority>('P2');
  const [taskOwnerId, setTaskOwnerId] = useState('');
  const [taskConversationId, setTaskConversationId] = useState('');
  const [onboardingOpen, setOnboardingOpen] = useState(false);
  const [onboardingStep, setOnboardingStep] = useState(0);
  const messagesRef = useRef<HTMLDivElement>(null);
  const toastTimer = useRef<number | undefined>(undefined);

  const showToast = (message: string) => {
    window.clearTimeout(toastTimer.current);
    setToast({ visible: true, message });
    toastTimer.current = window.setTimeout(
      () => setToast({ visible: false, message: '' }),
      2200,
    );
  };

  const applyBootstrap = (data: ApiBootstrap) => {
    const mapped = mapBootstrap(data);
    setWorkspace(mapped.workspace);
    setDepartments(mapped.departments);
    setAgents(mapped.agents);
    setChats(mapped.chats);
    setMessagesByChat(mapped.messagesByChat);
    setTasks(mapped.tasks);
    setHireTemplates(mapped.templates);
    setTalentCategories(mapped.talentCategories);
    setOnboardingOpen(!mapped.workspace.onboarding_completed);

    const preferredChat =
      mapped.chats.find((chat) => chat.kind === 'dm' && chat.agentId) ??
      mapped.chats[0];
    if (preferredChat && !mapped.chats.some((chat) => chat.id === chatId)) {
      setChatId(preferredChat.id);
    }
  };

  const loadBootstrap = async (activeToken = token) => {
    if (!activeToken) return;
    setBootLoading(true);
    try {
      const data = await apiRequest<ApiBootstrap>('/me/bootstrap', {
        token: activeToken,
      });
      applyBootstrap(data);
      setAuthError('');
    } catch (error) {
      setAuthError(error instanceof Error ? error.message : '加载工作台失败');
      localStorage.removeItem(tokenStorageKey);
      setToken(null);
      setUser(null);
      setWorkspace(null);
    } finally {
      setBootLoading(false);
    }
  };

  useEffect(() => {
    localStorage.setItem('agentpulse_theme_mode', themeMode);
  }, [themeMode]);

  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const updateSystemTheme = () =>
      setSystemTheme(mediaQuery.matches ? 'dark' : 'light');

    updateSystemTheme();
    mediaQuery.addEventListener('change', updateSystemTheme);
    return () => mediaQuery.removeEventListener('change', updateSystemTheme);
  }, []);

  useEffect(() => {
    if (token) void loadBootstrap(token);
  }, []);

  useEffect(() => {
    messagesRef.current?.scrollTo({ top: messagesRef.current.scrollHeight });
  }, [chatId, messagesByChat, typingName]);

  useEffect(() => {
    return () => window.clearTimeout(toastTimer.current);
  }, []);

  const effectiveTheme = themeMode === 'system' ? systemTheme : themeMode;

  const handleAuthSuccess = async (payload: {
    access_token: string;
    user: User;
    workspace: Workspace;
  }) => {
    localStorage.setItem(tokenStorageKey, payload.access_token);
    localStorage.setItem(userStorageKey, JSON.stringify(payload.user));
    setToken(payload.access_token);
    setUser(payload.user);
    setWorkspace(payload.workspace);
    await loadBootstrap(payload.access_token);
  };

  const logout = () => {
    localStorage.removeItem(tokenStorageKey);
    localStorage.removeItem(userStorageKey);
    setToken(null);
    setUser(null);
    setWorkspace(null);
    setAgents([]);
    setChats([]);
    setMessagesByChat({});
    setTasks([]);
    setHireTemplates([]);
    setTalentCategories([]);
  };

  const agentById = (id: string) => agents.find((agent) => agent.id === id);
  const activeChat = chats.find((chat) => chat.id === chatId) ?? chats[0];
  const busyCount = agents.filter(
    (agent) => agent.statusKind === 'busy',
  ).length;
  const confirmTasks = tasks.filter((task) => task.status === '待确认');
  const stuckCount = tasks.filter((task) => task.status === '阻塞').length;
  const unreadTotal = chats.reduce((count, chat) => count + chat.unread, 0);
  const allSkills = Array.from(
    new Set(hireTemplates.flatMap((template) => template.skills)),
  );
  const allMcps = Array.from(
    new Set(hireTemplates.flatMap((template) => template.mcps)),
  );

  const lastMessagePreview = (id: string) => {
    const messages = messagesByChat[id] ?? [];
    const last = messages.at(-1);
    if (!last) return '开始对话';

    const author =
      last.from === 'boss'
        ? '我'
        : last.from === 'system'
          ? ''
          : (agentById(last.from)?.name ?? '');
    const prefix = author ? `${author}：` : '';

    return `${prefix}${last.text}`;
  };

  const openChat = (id: string) => {
    setView('chat');
    setChatId(id);
    setDraft('');
    setDetailId(null);
    setTaskDetailId(null);
    setChats((current) =>
      current.map((chat) => (chat.id === id ? { ...chat, unread: 0 } : chat)),
    );
  };

  const openHire = (templateId: string) => {
    const template = hireTemplates.find((item) => item.id === templateId);
    if (!template) return;
    setHireTpl(template.id);
    setHireDept(template.dept);
    setHireOpen(true);
  };

  const openCreateAgent = () => {
    setCreateName('');
    setCreateDesc('');
    setCreateDept('');
    setCreatePrompt('');
    setCreateOpen(true);
  };

  const openGroupModal = () => {
    setGroupName('');
    setGroupMembers([]);
    setGroupTaskIds([]);
    setGroupOpen(true);
  };

  const openAllTasks = () => {
    setTaskScopeChatId(null);
    setView('tasks');
    setDetailId(null);
    setTaskDetailId(null);
  };

  const openRelatedTasks = () => {
    if (!activeChat) return;
    setTaskScopeChatId(activeChat.id);
    setTaskFilter('全部');
    setView('tasks');
    setDetailId(null);
    setTaskDetailId(null);
  };

  const openCreateTask = () => {
    setTaskTitle('');
    setTaskDesc('');
    setTaskPriority('P2');
    setTaskOwnerId('');
    setTaskConversationId(taskScopeChatId ?? activeChat?.id ?? '');
    setTaskOpen(true);
  };

  const send = async () => {
    const text = draft.trim();
    if (!text || !activeChat || !token) return;

    const targetChat = activeChat;
    const memberIds =
      targetChat.kind === 'dm' ? [targetChat.agentId] : targetChat.memberIds;
    const mentionedAgent =
      targetChat.kind === 'group'
        ? resolveMentionedAgent(text, memberIds, agents)
        : null;
    const replierId =
      targetChat.kind === 'dm'
        ? targetChat.agentId
        : (mentionedAgent?.id ?? targetChat.memberIds[0]);
    const replier = replierId ? agentById(replierId) : null;
    if (!replier) return;
    const targetAgentId =
      targetChat.kind === 'group' ? (mentionedAgent?.id ?? null) : null;

    const optimisticId = tempMessageId();
    const optimisticMessage: Message = {
      id: optimisticId,
      from: 'boss',
      type: 'text',
      time: '刚刚',
      text,
    };
    setMessagesByChat((current) => ({
      ...current,
      [targetChat.id]: [...(current[targetChat.id] ?? []), optimisticMessage],
    }));
    setDraft('');
    setTypingName(
      targetChat.kind === 'group' && !mentionedAgent ? '群聊成员' : replier.name,
    );
    setAgents((current) =>
      current.map((agent) =>
        agent.id === replier.id
          ? { ...agent, statusKind: 'busy', statusLabel: '思考中' }
          : agent,
      ),
    );

    try {
      const response = await apiRequest<{
        user_message: ApiBootstrap['messages_by_conversation'][string][number];
        agent_message: ApiBootstrap['messages_by_conversation'][string][number];
        agent_messages?: ApiBootstrap['messages_by_conversation'][string][number][];
        created_task: ApiBootstrap['tasks'][number] | null;
        created_agent: ApiBootstrap['agents'][number] | null;
      }>(`/conversations/${targetChat.id}/messages`, {
        method: 'POST',
        token,
        body: JSON.stringify({
          content: text,
          target_agent_id: targetAgentId,
        }),
      });
      const userMessage = mapApiMessage(response.user_message);
      const agentMessages = (
        response.agent_messages?.length
          ? response.agent_messages
          : [response.agent_message]
      ).map(mapApiMessage);
      const systemTaskMessage: Message | null = response.created_task
        ? {
            id: tempMessageId(),
            from: 'system',
            type: 'system',
            time: '刚刚',
            text: `已自动创建任务：${response.created_task.title}`,
          }
        : null;
      const systemAgentMessage: Message | null = response.created_agent
        ? {
            id: tempMessageId(),
            from: 'system',
            type: 'system',
            time: '刚刚',
            text: `已创建员工：${response.created_agent.name}`,
          }
        : null;
      setMessagesByChat((current) => ({
        ...current,
        [targetChat.id]: [
          ...(current[targetChat.id] ?? []).filter(
            (message) => message.id !== optimisticId,
          ),
          userMessage,
          ...(systemTaskMessage ? [systemTaskMessage] : []),
          ...(systemAgentMessage ? [systemAgentMessage] : []),
          ...agentMessages,
        ],
      }));
      setChats((current) =>
        current.map((chat) =>
          chat.id === targetChat.id ? { ...chat, time: '刚刚' } : chat,
        ),
      );
      if (response.created_task || response.created_agent) {
        await loadBootstrap(token);
        showToast(
          response.created_agent
            ? '已从聊天创建员工'
            : '已从聊天自动创建任务',
        );
      }
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : 'LLM 调用失败，请稍后重试';
      setMessagesByChat((current) => ({
        ...current,
        [targetChat.id]: [
          ...(current[targetChat.id] ?? []),
          {
            id: tempMessageId(),
            from: 'system',
            type: 'system',
            time: '',
            text: `真实调用 DeepSeek 失败：${errorMessage}`,
          },
        ],
      }));
      showToast('DeepSeek 调用失败，请检查后端和 API Key');
    } finally {
      setTypingName(null);
      setAgents((current) =>
        current.map((agent) =>
          agent.id === replier.id
            ? { ...agent, statusKind: 'idle', statusLabel: '在线待命' }
            : agent,
        ),
      );
    }
  };

  const submitHire = async () => {
    if (!token || !hireTpl) return;
    try {
      await apiRequest('/agents/recruit', {
        method: 'POST',
        token,
        body: JSON.stringify({
          template_id: hireTpl,
          department_name: hireDept,
        }),
      });
      await loadBootstrap(token);
      setHireOpen(false);
      setView('staff');
      showToast('招募成功，已加入组织架构');
    } catch (error) {
      showToast(error instanceof Error ? error.message : '招募失败');
    }
  };

  const submitCreateAgent = async () => {
    if (!token) return;
    const name = createName.trim();
    const prompt = createPrompt.trim();
    const departmentName = createDept.trim();
    if (!name || !prompt || !departmentName) {
      showToast('请填写员工名称、部门和工作职责 Prompt');
      return;
    }
    try {
      await apiRequest('/agents', {
        method: 'POST',
        token,
        body: JSON.stringify({
          name,
          description: createDesc.trim(),
          department_name: departmentName,
          prompt,
        }),
      });
      await loadBootstrap(token);
      setCreateOpen(false);
      setView('staff');
      showToast(`已创建「${name}」`);
    } catch (error) {
      showToast(error instanceof Error ? error.message : '创建失败');
    }
  };

  const createGroup = async () => {
    if (!token) return;
    if (!groupMembers.length) {
      showToast('至少拉一位员工进群');
      return;
    }
    try {
      const response = await apiRequest<{ id: string }>(
        '/conversations/group',
        {
          method: 'POST',
          token,
          body: JSON.stringify({
            name: groupName.trim() || '新的讨论',
            member_ids: groupMembers,
            related_task_ids: groupTaskIds,
          }),
        },
      );
      await loadBootstrap(token);
      setGroupOpen(false);
      setGroupName('');
      setGroupMembers([]);
      setGroupTaskIds([]);
      setView('chat');
      setChatId(response.id);
      showToast('群聊已创建，把事情说给他们听吧');
    } catch (error) {
      showToast(error instanceof Error ? error.message : '建群失败');
    }
  };

  const openInviteMembers = () => {
    if (!activeChat || activeChat.kind !== 'group') return;
    setInviteMembers([]);
    setInviteOpen(true);
  };

  const inviteGroupMembers = async () => {
    if (!token || !activeChat || activeChat.kind !== 'group') return;
    if (!inviteMembers.length) {
      showToast('请选择要拉入群聊的员工');
      return;
    }
    try {
      await apiRequest(`/conversations/${activeChat.id}/members`, {
        method: 'POST',
        token,
        body: JSON.stringify({
          member_ids: inviteMembers,
        }),
      });
      await loadBootstrap(token);
      setInviteOpen(false);
      setInviteMembers([]);
      showToast('已拉入群聊');
    } catch (error) {
      showToast(error instanceof Error ? error.message : '拉人失败');
    }
  };

  const submitCreateTask = async () => {
    if (!token) return;
    const title = taskTitle.trim();
    if (!title) {
      showToast('请填写任务标题');
      return;
    }
    try {
      await apiRequest('/tasks', {
        method: 'POST',
        token,
        body: JSON.stringify({
          title,
          description: taskDesc.trim(),
          priority: taskPriority,
          owner_agent_id: taskOwnerId || null,
          conversation_id: taskConversationId || null,
          status: taskOwnerId ? '进行中' : '待认领',
          progress: taskOwnerId ? 10 : 0,
        }),
      });
      await loadBootstrap(token);
      setTaskOpen(false);
      setView('tasks');
      showToast('任务已创建');
    } catch (error) {
      showToast(error instanceof Error ? error.message : '创建任务失败');
    }
  };

  const advanceTask = async (task: Task) => {
    if (!token) return;
    if (task.status === '待认领' && !task.owner) {
      showToast('请先让员工认领这个任务');
      return;
    }
    const nextStatus = nextTaskStatus(task.status);
    try {
      await apiRequest(`/tasks/${task.id}`, {
        method: 'PATCH',
        token,
        body: JSON.stringify({
          status: nextStatus,
          progress: progressForNextStatus(nextStatus, task.progress),
        }),
      });
      await loadBootstrap(token);
      showToast(`任务已更新为「${nextStatus}」`);
    } catch (error) {
      showToast(error instanceof Error ? error.message : '更新任务失败');
    }
  };

  const claimTask = async () => {
    if (!token || !claimTaskId || !claimAgentId) {
      showToast('请选择认领员工');
      return;
    }
    try {
      await apiRequest(`/tasks/${claimTaskId}/claim`, {
        method: 'POST',
        token,
        body: JSON.stringify({ agent_id: claimAgentId }),
      });
      await loadBootstrap(token);
      setClaimTaskId(null);
      setClaimAgentId('');
      showToast('任务已进入执行中');
    } catch (error) {
      showToast(error instanceof Error ? error.message : '认领任务失败');
    }
  };

  const resolveApproval = async (
    approval: Approval,
    status: 'approved' | 'rejected',
  ) => {
    if (!token) return;
    try {
      await apiRequest(`/approvals/${approval.id}/resolve`, {
        method: 'POST',
        token,
        body: JSON.stringify({ status }),
      });
      await loadBootstrap(token);
      showToast(
        status === 'approved' ? '已确认，任务归档完成' : '已驳回，任务进入阻塞',
      );
    } catch (error) {
      showToast(error instanceof Error ? error.message : '处理确认请求失败');
    }
  };

  const finishOnboarding = async () => {
    if (token) {
      await apiRequest('/me/onboarding/complete', {
        method: 'POST',
        token,
        body: JSON.stringify({}),
      }).catch(() => null);
    }
    setOnboardingOpen(false);
    setWorkspace((current) =>
      current ? { ...current, onboarding_completed: true } : current,
    );
    showToast('团队已就位，从给小秘发条消息开始吧');
  };

  const scopedTasks = taskScopeChatId
    ? tasks.filter((task) => task.src === taskScopeChatId)
    : tasks;
  const filteredTasks = scopedTasks.filter(
    (task) => taskFilter === '全部' || task.status === taskFilter,
  );
  const taskTabs = (
    ['全部', '待认领', '进行中', '待确认', '阻塞', '已完成'] as const
  ).map((status) => ({
    status,
    count:
      status === '全部'
        ? scopedTasks.length
        : scopedTasks.filter((task) => task.status === status).length,
  }));
  const libraryTabs: Array<{ key: LibraryTab; label: string }> = [
    { key: 'docs', label: '公司资料库' },
    { key: 'skills', label: 'Skills 技能' },
    { key: 'mcp', label: 'MCP 服务' },
  ];
  const depts = departments
    .map((dept) => ({
      name: dept.name,
      members: agents.filter((agent) => agent.departmentId === dept.id),
    }))
    .filter((dept) => dept.members.length > 0);

  const currentChatAgent =
    activeChat?.kind === 'dm' ? agentById(activeChat.agentId) : null;
  const chatTitle =
    activeChat?.kind === 'dm'
      ? currentChatAgent?.id
        ? `${currentChatAgent.name} · ${currentChatAgent.role}`
        : '消息'
      : activeChat
        ? `# ${activeChat.name}`
        : '消息';
  const relatedTasks = activeChat
    ? tasks.filter((task) => task.src === activeChat.id)
    : [];
  const scopedChat = taskScopeChatId
    ? chats.find((chat) => chat.id === taskScopeChatId)
    : null;
  const taskScopeLabel =
    scopedChat?.kind === 'group'
      ? `# ${scopedChat.name}`
      : scopedChat?.kind === 'dm'
        ? (agentById(scopedChat.agentId)?.name ?? '私聊')
        : null;
  const chatMeta =
    activeChat?.kind === 'dm'
      ? `${currentChatAgent?.role ?? ''} · ${currentChatAgent?.statusLabel ?? ''}`
      : activeChat
        ? `${activeChat.memberIds.length} 名成员 · 讨论与执行结果都沉淀在这里`
        : '登录后开始工作';
  const chatMembers =
    activeChat?.kind === 'group'
      ? activeChat.memberIds
      : activeChat?.kind === 'dm'
        ? [activeChat.agentId]
        : [];
  const detailAgent = detailId ? agentById(detailId) : null;
  const detailTask = taskDetailId
    ? tasks.find((task) => task.id === taskDetailId)
    : null;

  if (!token || !user || !workspace) {
    return (
      <AuthScreen
        theme={effectiveTheme}
        error={authError}
        onAuthSuccess={handleAuthSuccess}
      />
    );
  }

  if (bootLoading) {
    return (
      <main className="workbench-shell auth-shell" data-theme={effectiveTheme}>
        <div className="loading-panel">正在加载你的 AI 公司...</div>
      </main>
    );
  }

  return (
    <main
      className="workbench-shell"
      data-theme={effectiveTheme}
      data-theme-mode={themeMode}
    >
      <Sidebar
        view={view}
        unreadTotal={unreadTotal}
        taskAlerts={confirmTasks.length + stuckCount}
        themeMode={themeMode}
        onThemeModeChange={setThemeMode}
        onLogout={logout}
        onNavigate={(nextView) => {
          if (nextView === 'tasks') setTaskScopeChatId(null);
          setView(nextView);
          setDetailId(null);
          setTaskDetailId(null);
        }}
      />

      {view === 'chat' && (
        <ConversationList
          chats={chats}
          activeChatId={chatId}
          agents={agents}
          lastMessagePreview={lastMessagePreview}
          onOpenChat={openChat}
          onOpenGroupModal={openGroupModal}
        />
      )}

      <section className="main-stage">
        {view === 'chat' && activeChat && (
          <ChatView
            title={chatTitle}
            meta={chatMeta}
            members={chatMembers}
            messages={messagesByChat[activeChat.id] ?? []}
            agents={agents}
            relatedTaskCount={relatedTasks.length}
            draft={draft}
            placeholder={
              activeChat.kind === 'group'
                ? `发消息给 # ${activeChat.name}，@员工 可点名`
                : `发消息给 ${currentChatAgent?.name ?? ''}`
            }
            typingName={typingName}
            messagesRef={messagesRef}
            onDraftChange={setDraft}
            onSend={send}
            onOpenTasks={openRelatedTasks}
            onInviteMembers={
              activeChat.kind === 'group' ? openInviteMembers : undefined
            }
            onOpenAgent={(id) => setDetailId(id)}
          />
        )}

        {view === 'chat' && !activeChat && (
          <EmptyWorkbenchState
            title="暂无会话"
            text="注册后系统会自动创建小秘私聊。"
          />
        )}

        {view === 'staff' && (
          <StaffView
            companyName={workspace.name}
            depts={depts}
            agents={agents}
            tasks={tasks}
            busyCount={busyCount}
            onOpenCreate={openCreateAgent}
            onOpenAgent={(id) => setDetailId(id)}
          />
        )}

        {view === 'market' && (
          <TalentMarketView
            agents={agents}
            templates={hireTemplates}
            categories={talentCategories}
            skillCount={allSkills.length}
            mcpCount={allMcps.length}
            onRecruit={openHire}
          />
        )}

        {view === 'tasks' && (
          <TasksView
            tasks={filteredTasks}
            tabs={taskTabs}
            activeFilter={taskFilter}
            agents={agents}
            scopeLabel={taskScopeLabel}
            onPickFilter={setTaskFilter}
            onClearScope={openAllTasks}
            onOpenCreateTask={openCreateTask}
            onAdvanceTask={advanceTask}
            onOpenClaimTask={(taskId) => {
              setClaimTaskId(taskId);
              setClaimAgentId('');
            }}
            onOpenTask={(taskId) => setTaskDetailId(taskId)}
            onOpenChat={openChat}
            onOpenAgent={(id) => setDetailId(id)}
          />
        )}

        {view === 'lib' && (
          <LibraryView
            tabs={libraryTabs}
            activeTab={libraryTab}
            onPickTab={setLibraryTab}
            skills={allSkills}
            mcps={allMcps}
          />
        )}
      </section>

      {detailAgent && (
        <AgentDetail
          agent={detailAgent}
          tasks={tasks.filter((task) => task.owner === detailAgent.id)}
          onClose={() => setDetailId(null)}
          onDm={() => {
            const chat = chats.find(
              (item) => item.kind === 'dm' && item.agentId === detailAgent.id,
            );
            if (chat) openChat(chat.id);
          }}
        />
      )}

      {detailTask && (
        <TaskDetail
          task={detailTask}
          agent={detailTask.owner ? agentById(detailTask.owner) : undefined}
          onClose={() => setTaskDetailId(null)}
          onOpenChat={openChat}
          onOpenAgent={(id) => setDetailId(id)}
          onAdvanceTask={advanceTask}
          onResolveApproval={resolveApproval}
        />
      )}

      {hireOpen && (
        <HireModal
          template={hireTemplates.find((template) => template.id === hireTpl)}
          departments={depts
            .filter((dept) => dept.name !== '老板办公室')
            .map((dept) => dept.name)}
          hireDept={hireDept}
          onDeptChange={setHireDept}
          onClose={() => setHireOpen(false)}
          onSubmit={submitHire}
        />
      )}

      {createOpen && (
        <CreateAgentModal
          departments={depts
            .filter((dept) => dept.name !== '老板办公室')
            .map((dept) => dept.name)}
          createName={createName}
          createDesc={createDesc}
          createDept={createDept}
          createPrompt={createPrompt}
          onNameChange={setCreateName}
          onDescChange={setCreateDesc}
          onDeptChange={setCreateDept}
          onPromptChange={setCreatePrompt}
          onClose={() => setCreateOpen(false)}
          onSubmit={submitCreateAgent}
        />
      )}

      {groupOpen && (
        <GroupModal
          agents={agents}
          tasks={tasks}
          groupName={groupName}
          groupMembers={groupMembers}
          selectedTaskIds={groupTaskIds}
          onGroupNameChange={setGroupName}
          onToggleMember={(id) =>
            setGroupMembers((current) =>
              current.includes(id)
                ? current.filter((memberId) => memberId !== id)
                : [...current, id],
            )
          }
          onToggleTask={(id) =>
            setGroupTaskIds((current) =>
              current.includes(id)
                ? current.filter((taskId) => taskId !== id)
                : [...current, id],
            )
          }
          onClose={() => setGroupOpen(false)}
          onCreate={createGroup}
        />
      )}

      {inviteOpen && activeChat?.kind === 'group' && (
        <GroupMembersModal
          title="邀请员工"
          description="把更多员工拉进当前群聊，后续可以用 @ 点名。"
          agents={agents.filter(
            (agent) => !activeChat.memberIds.includes(agent.id),
          )}
          selectedMembers={inviteMembers}
          submitLabel="拉入群聊"
          emptyText="所有员工都已经在这个群聊里"
          onToggleMember={(id) =>
            setInviteMembers((current) =>
              current.includes(id)
                ? current.filter((memberId) => memberId !== id)
                : [...current, id],
            )
          }
          onClose={() => setInviteOpen(false)}
          onSubmit={inviteGroupMembers}
        />
      )}

      {taskOpen && (
        <CreateTaskModal
          agents={agents}
          chats={chats}
          taskTitle={taskTitle}
          taskDesc={taskDesc}
          taskPriority={taskPriority}
          taskOwnerId={taskOwnerId}
          taskConversationId={taskConversationId}
          agentById={agentById}
          onTitleChange={setTaskTitle}
          onDescChange={setTaskDesc}
          onPriorityChange={setTaskPriority}
          onOwnerChange={setTaskOwnerId}
          onConversationChange={setTaskConversationId}
          onClose={() => setTaskOpen(false)}
          onSubmit={submitCreateTask}
        />
      )}

      {claimTaskId && (
        <ClaimTaskModal
          task={tasks.find((task) => task.id === claimTaskId)}
          agents={agents}
          selectedAgentId={claimAgentId}
          onAgentChange={setClaimAgentId}
          onClose={() => {
            setClaimTaskId(null);
            setClaimAgentId('');
          }}
          onSubmit={claimTask}
        />
      )}

      {onboardingOpen && (
        <OnboardingModal
          step={onboardingStep}
          templates={hireTemplates}
          onNext={() =>
            setOnboardingStep((current) => Math.min(2, current + 1))
          }
          onFinish={finishOnboarding}
        />
      )}

      {toast.visible && <div className="toast">{toast.message}</div>}
    </main>
  );
}

function mapApiMessage(message: {
  id: string;
  sender_type: 'user' | 'agent' | 'system';
  sender_id: string;
  content: string;
  created_at: string;
  provider?: string | null;
  model?: string | null;
}): Message {
  return {
    id: message.id,
    from:
      message.sender_type === 'user'
        ? 'boss'
        : message.sender_type === 'system'
          ? 'system'
          : message.sender_id,
    type: message.sender_type === 'system' ? 'system' : 'text',
    time: formatTime(message.created_at),
    text: message.content,
    provider: message.provider ?? undefined,
    model: message.model ?? undefined,
  };
}

function AuthScreen({
  theme,
  error,
  onAuthSuccess,
}: {
  theme: EffectiveTheme;
  error: string;
  onAuthSuccess: (payload: {
    access_token: string;
    user: User;
    workspace: Workspace;
  }) => void;
}) {
  const [mode, setMode] = useState<'login' | 'register'>('register');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [workspaceName, setWorkspaceName] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [localError, setLocalError] = useState(error);

  const submit = async () => {
    const nextEmail = email.trim();
    const nextPassword = password.trim();
    const nextDisplayName = displayName.trim();
    const nextWorkspaceName = workspaceName.trim();

    if (!nextEmail) {
      setLocalError('请填写邮箱');
      return;
    }
    if (mode === 'register' && nextPassword.length < 6) {
      setLocalError('密码至少需要 6 位');
      return;
    }
    if (mode === 'login' && !nextPassword) {
      setLocalError('请填写密码');
      return;
    }
    if (mode === 'register' && !nextDisplayName) {
      setLocalError('请填写你的称呼');
      return;
    }
    if (mode === 'register' && !nextWorkspaceName) {
      setLocalError('请填写公司/工作室名称');
      return;
    }

    setSubmitting(true);
    setLocalError('');
    try {
      const path = mode === 'register' ? '/auth/register' : '/auth/login';
      const body =
        mode === 'register'
          ? {
              email: nextEmail,
              password: nextPassword,
              display_name: nextDisplayName,
              workspace_name: nextWorkspaceName,
            }
          : { email: nextEmail, password: nextPassword };
      const payload = await apiRequest<{
        access_token: string;
        user: User;
        workspace: Workspace;
      }>(path, {
        method: 'POST',
        body: JSON.stringify(body),
      });
      await onAuthSuccess(payload);
    } catch (authError) {
      setLocalError(
        authError instanceof Error ? authError.message : '登录失败',
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="workbench-shell auth-shell" data-theme={theme}>
      <section className="auth-hero" aria-label="AgentPulse 介绍">
        <div className="auth-brand">
          <div className="auth-mark">✦</div>
          <span>AgentPulse</span>
        </div>
        <h1>把一人公司，搭成一支 AI 团队。</h1>
        <p>
          创建工作区后，小秘、组织架构、人才市场和会话数据都会写入
          PostgreSQL。第一版先跑通真实 DeepSeek 对话闭环。
        </p>
        <div className="auth-feature-list">
          <div>
            {materialIcon('account_tree')}
            <span>
              <strong>组织化智能体</strong>
              <em>部门、员工、职责 Prompt 都能沉淀</em>
            </span>
          </div>
          <div>
            {materialIcon('forum')}
            <span>
              <strong>从消息开始协作</strong>
              <em>默认进入小秘私聊，后续拉群推进</em>
            </span>
          </div>
          <div>
            {materialIcon('verified')}
            <span>
              <strong>真实模型调用</strong>
              <em>回复会标记 provider 与 model</em>
            </span>
          </div>
        </div>
      </section>

      <section className="auth-panel">
        <div className="auth-panel-header">
          <span>{mode === 'register' ? '开始搭建' : '欢迎回来'}</span>
          <h2>{mode === 'register' ? '创建你的 AI 公司' : '登录工作台'}</h2>
          <p>
            {mode === 'register'
              ? '没有演示账号，提交后会创建你的真实本地工作区。'
              : '使用平台注册邮箱和密码继续进入工作台。'}
          </p>
        </div>

        <div className="auth-tabs">
          <button
            className={mode === 'register' ? 'active' : ''}
            type="button"
            onClick={() => {
              setMode('register');
              setLocalError('');
            }}
          >
            注册
          </button>
          <button
            className={mode === 'login' ? 'active' : ''}
            type="button"
            onClick={() => {
              setMode('login');
              setLocalError('');
            }}
          >
            登录
          </button>
        </div>

        <div className="auth-form">
          <label>
            <span>邮箱</span>
            <input
              value={email}
              placeholder="you@example.com"
              onChange={(event) => setEmail(event.target.value)}
            />
          </label>
          <label>
            <span>密码</span>
            <input
              type="password"
              value={password}
              placeholder="至少 6 位"
              onChange={(event) => setPassword(event.target.value)}
            />
          </label>
          {mode === 'register' && (
            <>
              <label>
                <span>你的称呼</span>
                <input
                  value={displayName}
                  placeholder="例如：老板"
                  onChange={(event) => setDisplayName(event.target.value)}
                />
              </label>
              <label>
                <span>公司/工作室名称</span>
                <input
                  value={workspaceName}
                  placeholder="例如：我的一人公司"
                  onChange={(event) => setWorkspaceName(event.target.value)}
                />
              </label>
            </>
          )}
        </div>

        {(localError || error) && (
          <div className="auth-error">{localError || error}</div>
        )}
        <button
          className="button primary auth-submit"
          type="button"
          onClick={submit}
          disabled={submitting}
        >
          {submitting
            ? '请稍候...'
            : mode === 'register'
              ? '注册并进入'
              : '登录'}
        </button>
      </section>
    </main>
  );
}

function Sidebar({
  view,
  unreadTotal,
  taskAlerts,
  themeMode,
  onThemeModeChange,
  onLogout,
  onNavigate,
}: {
  view: View;
  unreadTotal: number;
  taskAlerts: number;
  themeMode: ThemeMode;
  onThemeModeChange: (themeMode: ThemeMode) => void;
  onLogout: () => void;
  onNavigate: (view: View) => void;
}) {
  const items: Array<{
    key: View;
    icon: string;
    label: string;
    badge: number;
  }> = [
    { key: 'chat', icon: 'forum', label: '消息', badge: unreadTotal },
    { key: 'staff', icon: 'group', label: '员工', badge: 0 },
    { key: 'market', icon: 'storefront', label: '人才市场', badge: 0 },
    { key: 'tasks', icon: 'task_alt', label: '任务', badge: taskAlerts },
    { key: 'lib', icon: 'folder_open', label: '资料库', badge: 0 },
  ];

  return (
    <aside className="sidebar">
      <div className="brand-mark">✦</div>
      {items.map((item) => (
        <button
          className={view === item.key ? 'nav-item active' : 'nav-item'}
          key={item.key}
          type="button"
          onClick={() => onNavigate(item.key)}
          aria-label={item.label}
        >
          {materialIcon(item.icon)}
          <span>{item.label}</span>
          {item.badge > 0 && <em>{item.badge}</em>}
        </button>
      ))}
      <div className="sidebar-spacer" />
      <div className="theme-switcher" aria-label="主题设置">
        {themeOptions.map((option) => (
          <button
            className={themeMode === option.mode ? 'active' : ''}
            key={option.mode}
            type="button"
            title={option.label}
            aria-label={option.label}
            onClick={() => onThemeModeChange(option.mode)}
          >
            {materialIcon(option.icon)}
          </button>
        ))}
      </div>
      <button
        className="logout-nav-button"
        type="button"
        title="退出登录"
        aria-label="退出登录"
        onClick={onLogout}
      >
        <span className="owner-avatar">我</span>
        {materialIcon('logout')}
      </button>
    </aside>
  );
}

function ConversationList({
  chats,
  activeChatId,
  agents,
  lastMessagePreview,
  onOpenChat,
  onOpenGroupModal,
}: {
  chats: Chat[];
  activeChatId: string;
  agents: Agent[];
  lastMessagePreview: (chatId: string) => string;
  onOpenChat: (id: string) => void;
  onOpenGroupModal: () => void;
}) {
  const agentById = (id: string) => agents.find((agent) => agent.id === id);
  const pinnedChats = chats.filter(
    (chat) =>
      chat.kind === 'dm' && agentById(chat.agentId)?.role === '老板秘书',
  );
  const groupChats = chats.filter((chat) => chat.kind === 'group');
  const dmChats = chats.filter(
    (chat) =>
      chat.kind === 'dm' && agentById(chat.agentId)?.role !== '老板秘书',
  );

  const renderChat = (chat: Chat) => {
    const agent = chat.kind === 'dm' ? agentById(chat.agentId) : null;
    const name =
      chat.kind === 'dm'
        ? `${agent?.name ?? ''} · ${agent?.role ?? ''}`
        : chat.name;

    return (
      <button
        className={
          activeChatId === chat.id ? 'chat-list-item active' : 'chat-list-item'
        }
        key={chat.id}
        type="button"
        onClick={() => onOpenChat(chat.id)}
      >
        <div
          className={
            chat.kind === 'group' ? 'chat-avatar group' : 'chat-avatar'
          }
          style={
            chat.kind === 'dm' && agent
              ? { background: avatarColor(agent) }
              : undefined
          }
        >
          {chat.kind === 'group' ? '#' : agent ? avatarText(agent.name) : ''}
        </div>
        <div className="chat-copy">
          <div className="chat-line">
            <strong>{name}</strong>
            <span>{chat.time}</span>
          </div>
          <div className="chat-subline">
            <p>{lastMessagePreview(chat.id)}</p>
            {chat.unread > 0 && <em>{chat.unread}</em>}
          </div>
        </div>
      </button>
    );
  };

  return (
    <aside className="conversation-list">
      <div className="conversation-title">
        <strong>消息</strong>
        <button type="button" title="拉群讨论" onClick={onOpenGroupModal}>
          {materialIcon('group_add')}
        </button>
      </div>
      <div className="search-box">
        {materialIcon('search')}
        <span>搜索会话、员工、任务</span>
      </div>
      <div className="conversation-scroll">
        <SectionLabel label="秘书" />
        {pinnedChats.map(renderChat)}
        <SectionLabel label="群组" />
        {groupChats.length ? (
          groupChats.map(renderChat)
        ) : (
          <EmptyState>暂无群聊</EmptyState>
        )}
        <SectionLabel label="私聊" />
        {dmChats.length ? (
          dmChats.map(renderChat)
        ) : (
          <EmptyState>暂无其他私聊</EmptyState>
        )}
      </div>
    </aside>
  );
}

function SectionLabel({ label }: { label: string }) {
  return <div className="section-label">{label}</div>;
}

function EmptyState({ children }: { children: string }) {
  return <div className="empty-state">{children}</div>;
}

function EmptyWorkbenchState({ title, text }: { title: string; text: string }) {
  return (
    <div className="screen-scroll">
      <div className="screen-inner">
        <article className="card empty-workbench-state">
          <h2>{title}</h2>
          <p>{text}</p>
        </article>
      </div>
    </div>
  );
}

function ChatView({
  title,
  meta,
  members,
  messages,
  agents,
  relatedTaskCount,
  draft,
  placeholder,
  typingName,
  messagesRef,
  onDraftChange,
  onSend,
  onOpenTasks,
  onInviteMembers,
  onOpenAgent,
}: {
  title: string;
  meta: string;
  members: string[];
  messages: Message[];
  agents: Agent[];
  relatedTaskCount: number;
  draft: string;
  placeholder: string;
  typingName: string | null;
  messagesRef: RefObject<HTMLDivElement | null>;
  onDraftChange: (draft: string) => void;
  onSend: () => void;
  onOpenTasks: () => void;
  onInviteMembers?: () => void;
  onOpenAgent: (id: string) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [mentionOpen, setMentionOpen] = useState(false);
  const [mentionQuery, setMentionQuery] = useState('');
  const [mentionStart, setMentionStart] = useState<number | null>(null);
  const [mentionIndex, setMentionIndex] = useState(0);
  const agentById = (id: string) => agents.find((agent) => agent.id === id);
  const mentionableAgents = useMemo(
    () =>
      members
        .map((memberId) => agents.find((agent) => agent.id === memberId))
        .filter((agent): agent is Agent => Boolean(agent)),
    [agents, members],
  );
  const mentionMatches = useMemo(() => {
    const query = mentionQuery.trim().toLocaleLowerCase();
    return mentionableAgents
      .filter((agent) => {
        if (!query) return true;
        return [agent.name, agent.role, agent.dept]
          .join(' ')
          .toLocaleLowerCase()
          .includes(query);
      })
      .slice(0, 6);
  }, [mentionQuery, mentionableAgents]);

  const closeMention = () => {
    setMentionOpen(false);
    setMentionQuery('');
    setMentionStart(null);
    setMentionIndex(0);
  };

  const updateMentionState = (value: string, cursor: number) => {
    const context = getMentionContext(value, cursor);
    if (!context) {
      closeMention();
      return;
    }
    setMentionOpen(true);
    setMentionQuery(context.query);
    setMentionStart(context.start);
    setMentionIndex(0);
  };

  const insertMention = (agent: Agent) => {
    const cursor = inputRef.current?.selectionStart ?? draft.length;
    const context =
      mentionStart === null
        ? getMentionContext(draft, cursor)
        : { query: mentionQuery, start: mentionStart };
    if (!context) return;

    const before = draft.slice(0, context.start);
    const after = draft.slice(cursor).replace(/^\s*/, '');
    const nextDraft = `${before}@${agent.name} ${after}`;
    const nextCursor = `${before}@${agent.name} `.length;

    onDraftChange(nextDraft);
    closeMention();
    window.requestAnimationFrame(() => {
      inputRef.current?.focus();
      inputRef.current?.setSelectionRange(nextCursor, nextCursor);
    });
  };

  return (
    <div className="chat-view">
      <header className="chat-header">
        <div>
          <h2>{title}</h2>
          <p>{meta}</p>
        </div>
        <div className="chat-members">
          {members.map((memberId) => {
            const agent = agentById(memberId);
            if (!agent) return null;
            return (
              <button
                key={memberId}
                style={{ background: avatarColor(agent) }}
                title={`${agent.name} · 查看状态`}
                type="button"
                onClick={() => onOpenAgent(memberId)}
              >
                {avatarText(agent.name)}
              </button>
            );
          })}
        </div>
        {onInviteMembers && (
          <button
            className="chat-icon-button"
            title="邀请员工"
            type="button"
            onClick={onInviteMembers}
          >
            {materialIcon('person_add')}
          </button>
        )}
        <button
          className="related-task-button"
          type="button"
          onClick={onOpenTasks}
        >
          {materialIcon('task_alt')}
          {relatedTaskCount ? `关联任务 ${relatedTaskCount}` : '关联任务'}
        </button>
      </header>

      <div className="messages" ref={messagesRef}>
        {messages.map((message) => (
          <MessageItem
            key={message.id}
            message={message}
            agent={agentById(message.from)}
            onOpenAgent={onOpenAgent}
            agents={agents}
          />
        ))}
        {typingName && (
          <div className="typing-line">
            <i />
            {typingName} 正在输入...
          </div>
        )}
      </div>

      <footer className="composer">
        {mentionOpen && mentionMatches.length > 0 && (
          <div className="mention-popover">
            {mentionMatches.map((agent, index) => (
              <button
                className={mentionIndex === index ? 'active' : ''}
                key={agent.id}
                type="button"
                onMouseDown={(event) => {
                  event.preventDefault();
                  insertMention(agent);
                }}
              >
                <span
                  className="mention-avatar"
                  style={{ background: avatarColor(agent) }}
                >
                  {avatarText(agent.name)}
                </span>
                <span>
                  <strong>{agent.name}</strong>
                  <em>{agent.role}</em>
                </span>
              </button>
            ))}
          </div>
        )}
        <div className="composer-box">
          <input
            ref={inputRef}
            value={draft}
            placeholder={placeholder}
            onChange={(event) => {
              const nextDraft = event.currentTarget.value;
              onDraftChange(nextDraft);
              updateMentionState(
                nextDraft,
                event.currentTarget.selectionStart ?? nextDraft.length,
              );
            }}
            onClick={(event) =>
              updateMentionState(
                draft,
                event.currentTarget.selectionStart ?? draft.length,
              )
            }
            onFocus={(event) =>
              updateMentionState(
                draft,
                event.currentTarget.selectionStart ?? draft.length,
              )
            }
            onKeyDown={(event) => {
              if (mentionOpen && mentionMatches.length > 0) {
                if (event.key === 'ArrowDown') {
                  event.preventDefault();
                  setMentionIndex(
                    (current) => (current + 1) % mentionMatches.length,
                  );
                  return;
                }
                if (event.key === 'ArrowUp') {
                  event.preventDefault();
                  setMentionIndex(
                    (current) =>
                      (current - 1 + mentionMatches.length) %
                      mentionMatches.length,
                  );
                  return;
                }
                if (event.key === 'Enter' || event.key === 'Tab') {
                  event.preventDefault();
                  insertMention(mentionMatches[mentionIndex]);
                  return;
                }
              }
              if (event.key === 'Escape' && mentionOpen) {
                event.preventDefault();
                closeMention();
                return;
              }
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                onSend();
              }
            }}
          />
          <button type="button" onClick={onSend}>
            {materialIcon('send')}
          </button>
        </div>
        <p>Enter 发送 · 群聊里可以 @员工 点名</p>
      </footer>
    </div>
  );
}

function MessageItem({
  message,
  agent,
  agents,
  onOpenAgent,
}: {
  message: Message;
  agent?: Agent;
  agents: Agent[];
  onOpenAgent: (id: string) => void;
}) {
  if (message.type === 'system') {
    return <div className="system-message">{message.text}</div>;
  }

  const isBoss = message.from === 'boss';
  const avatarBg = isBoss ? '#2C313A' : agent ? avatarColor(agent) : '#9AA1AD';

  return (
    <div className="message-row">
      <button
        className="message-avatar"
        style={{ background: avatarBg }}
        type="button"
        onClick={() => agent && onOpenAgent(agent.id)}
      >
        {isBoss ? '我' : agent ? avatarText(agent.name) : ''}
      </button>
      <div className="message-body">
        <div className="message-meta">
          <strong>{isBoss ? '我（老板）' : agent?.name}</strong>
          {!isBoss && <span>{agent?.role}</span>}
          <em>{message.time}</em>
          {message.provider && (
            <em className="model-badge">
              {message.provider}
              {message.model ? ` · ${message.model}` : ''}
            </em>
          )}
        </div>
        <p className="message-text">
          {renderMentionText(message.text, agents)}
        </p>
      </div>
    </div>
  );
}

function StaffView({
  companyName,
  depts,
  agents,
  tasks,
  busyCount,
  onOpenCreate,
  onOpenAgent,
}: {
  companyName: string;
  depts: Array<{ name: string; members: Agent[] }>;
  agents: Agent[];
  tasks: Task[];
  busyCount: number;
  onOpenCreate: () => void;
  onOpenAgent: (id: string) => void;
}) {
  const [selectedDept, setSelectedDept] = useState<string | null>(null);
  const activeDept = selectedDept
    ? depts.find((dept) => dept.name === selectedDept)
    : null;

  return (
    <div className="screen-scroll">
      <div className="screen-inner">
        <section className="org-directory">
          <header className="org-header">
            <div>
              <h1>组织内联系人</h1>
              <p>
                {companyName} · {agents.length} 名 AI 员工 · {depts.length}{' '}
                个部门 · {busyCount} 人执行中
              </p>
            </div>
            <button
              className="button secondary blue"
              type="button"
              onClick={onOpenCreate}
            >
              {materialIcon('add_circle')}创建员工
            </button>
          </header>

          <div className="org-body">
            <nav className="org-breadcrumb" aria-label="组织路径">
              <button type="button" onClick={() => setSelectedDept(null)}>
                {companyName}
              </button>
              {activeDept && (
                <>
                  {materialIcon('chevron_right')}
                  <span>{activeDept.name}</span>
                </>
              )}
            </nav>

            {!activeDept && (
              <div className="org-list" aria-label="部门列表">
                {depts.map((dept) => {
                  const busyMembers = dept.members.filter(
                    (agent) => agent.statusKind === 'busy',
                  ).length;
                  const waitingMembers = dept.members.filter(
                    (agent) => agent.statusKind === 'wait',
                  ).length;

                  return (
                    <div className="org-row" key={dept.name}>
                      <div className="org-node-icon">
                        {materialIcon('account_tree')}
                      </div>
                      <div className="org-row-main">
                        <strong>
                          {dept.name}
                          <span>({dept.members.length})</span>
                        </strong>
                        <p>
                          {busyMembers} 人执行中 · {waitingMembers} 个待确认
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() => setSelectedDept(dept.name)}
                      >
                        下级
                      </button>
                    </div>
                  );
                })}
                {!depts.length && <EmptyState>暂无部门</EmptyState>}
              </div>
            )}

            {activeDept && (
              <div className="org-list" aria-label={`${activeDept.name} 成员`}>
                {activeDept.members.map((agent) => {
                  const currentTask = tasks.find(
                    (task) =>
                      task.owner === agent.id && task.status !== '已完成',
                  );
                  return (
                    <button
                      className="org-member-row"
                      key={agent.id}
                      type="button"
                      onClick={() => onOpenAgent(agent.id)}
                    >
                      <div
                        className="org-member-avatar"
                        style={{ background: avatarColor(agent) }}
                      >
                        {avatarText(agent.name)}
                      </div>
                      <div className="org-member-copy">
                        <strong>
                          {agent.name}
                          {agent.role === '老板秘书' && <em>内置秘书</em>}
                        </strong>
                        <p>
                          {agent.role}
                          {currentTask ? ` | ${currentTask.title}` : ''}
                        </p>
                      </div>
                      <span style={{ color: dotColor(agent.statusKind) }}>
                        <i style={{ background: dotColor(agent.statusKind) }} />
                        {agent.statusLabel}
                      </span>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}

function TalentMarketView({
  agents,
  templates,
  categories,
  skillCount,
  mcpCount,
  onRecruit,
}: {
  agents: Agent[];
  templates: HireTemplate[];
  categories: TalentCategory[];
  skillCount: number;
  mcpCount: number;
  onRecruit: (templateId: string) => void;
}) {
  const [activeCategory, setActiveCategory] = useState('全部');
  const [keyword, setKeyword] = useState('');
  const [detailTemplateId, setDetailTemplateId] = useState<string | null>(null);
  const categoryOptions = [
    {
      id: '全部',
      name: '全部',
      description: '查看官方人才库里的全部可招募员工模板',
    },
    ...categories,
  ];
  const visibleTemplates = templates.filter((template) => {
    const matchCategory =
      activeCategory === '全部' || template.categoryId === activeCategory;
    const query = keyword.trim().toLowerCase();
    if (!query) return matchCategory;
    return (
      matchCategory &&
      [
        template.name,
        template.category,
        template.dept,
        template.desc,
        template.prompt,
        ...template.skills,
        ...template.mcps,
      ]
        .join(' ')
        .toLowerCase()
        .includes(query)
    );
  });
  const detailTemplate = detailTemplateId
    ? templates.find((template) => template.id === detailTemplateId)
    : null;
  const activeCategoryName =
    categoryOptions.find((category) => category.id === activeCategory)?.name ??
    '全部';

  return (
    <>
      <div className="market-screen">
        <header className="page-header compact">
          <div>
            <h1>人才市场中心</h1>
            <p>
              官方提供可招募 AI 员工模板；类目、Prompt、Skills、MCP
              和版本由官方后台统一维护
            </p>
          </div>
        </header>

        <section className="market-summary" aria-label="人才市场概览">
          <div>
            {materialIcon('badge')}
            <span>
              <strong>{templates.length}</strong>
              <em>官方人才</em>
            </span>
          </div>
          <div>
            {materialIcon('verified_user')}
            <span>
              <strong>{skillCount}</strong>
              <em>可绑定技能</em>
            </span>
          </div>
          <div>
            {materialIcon('extension')}
            <span>
              <strong>{mcpCount}</strong>
              <em>MCP 工具</em>
            </span>
          </div>
          <div>
            {materialIcon('group')}
            <span>
              <strong>{agents.length}</strong>
              <em>已入职员工</em>
            </span>
          </div>
        </section>

        <section className="market-layout">
          <aside className="market-filter" aria-label="岗位筛选">
            <strong>官方人才类目</strong>
            <p>
              这里不是你的公司部门。分类来自官方后台，用户侧只负责筛选、查看和招募。
            </p>
            <div>
              {categoryOptions.map((category) => {
                const count =
                  category.id === '全部'
                    ? templates.length
                    : templates.filter(
                        (template) => template.categoryId === category.id,
                      ).length;
                return (
                  <button
                    className={activeCategory === category.id ? 'active' : ''}
                    key={category.id}
                    type="button"
                    title={category.description}
                    onClick={() => setActiveCategory(category.id)}
                  >
                    <span>{category.name}</span>
                    <em>{count}</em>
                  </button>
                );
              })}
            </div>
            <footer>
              分类、模板、默认能力和发布版本后续都在 AgentPulse Admin
              维护；招募时再选择加入你的部门。
            </footer>
          </aside>

          <div className="market-main">
            <div className="market-toolbar">
              <label>
                {materialIcon('search')}
                <input
                  value={keyword}
                  placeholder="搜索人才、能力、工具或官方类目"
                  onChange={(event) => setKeyword(event.target.value)}
                />
              </label>
              <span>
                {activeCategoryName} · {visibleTemplates.length} 个官方人才
              </span>
            </div>

            <div className="market-list">
              {visibleTemplates.map((template, index) => (
                <article
                  className="market-card"
                  key={template.id}
                  role="button"
                  tabIndex={0}
                  onClick={() => setDetailTemplateId(template.id)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault();
                      setDetailTemplateId(template.id);
                    }
                  }}
                >
                  <div className="market-card-main">
                    <div
                      className="market-role-icon"
                      style={{
                        background: `oklch(0.55 0.11 ${220 + index * 30})`,
                      }}
                    >
                      {['◆', '●', '▲', '■', '◗', '✱'][index % 6]}
                    </div>
                    <div className="market-copy">
                      <div>
                        <strong>{template.name}</strong>
                        <span>官方发布</span>
                      </div>
                      <p>
                        {template.category} · 建议入职 {template.dept} ·{' '}
                        {template.desc}
                      </p>
                      <em>{template.prompt}</em>
                      <div className="market-tags">
                        {template.skills.map((skill) => (
                          <span key={skill}>
                            {materialIcon('bolt')}
                            {skill}
                          </span>
                        ))}
                        {template.mcps.map((mcp) => (
                          <span className="muted" key={mcp}>
                            {materialIcon('extension')}
                            {mcp}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                  <div className="market-card-actions">
                    <span>{template.version}</span>
                    <button
                      className="button secondary"
                      type="button"
                      onClick={(event) => {
                        event.stopPropagation();
                        setDetailTemplateId(template.id);
                      }}
                    >
                      {materialIcon('visibility')}详情
                    </button>
                  </div>
                </article>
              ))}
              {visibleTemplates.length === 0 && (
                <div className="market-empty">没有匹配的人才模板</div>
              )}
            </div>
          </div>
        </section>
      </div>
      {detailTemplate && (
        <TalentDetailModal
          template={detailTemplate}
          onClose={() => setDetailTemplateId(null)}
          onRecruit={() => {
            setDetailTemplateId(null);
            onRecruit(detailTemplate.id);
          }}
        />
      )}
    </>
  );
}

function TalentDetailModal({
  template,
  onClose,
  onRecruit,
}: {
  template: HireTemplate;
  onClose: () => void;
  onRecruit: () => void;
}) {
  return (
    <Modal
      title={template.name}
      description={`${template.category} · 建议入职 ${template.dept}`}
      width={760}
      onClose={onClose}
    >
      <div className="talent-detail-head">
        <div
          className="large-avatar"
          style={{ background: 'oklch(0.55 0.11 230)' }}
        >
          {avatarText(template.name)}
        </div>
        <div>
          <strong>{template.name}</strong>
          <p>{template.desc}</p>
          <span>
            {template.publisher} · {template.version} · 官方已发布
          </span>
        </div>
      </div>

      <FieldLabel>基础信息</FieldLabel>
      <div className="talent-detail-grid">
        <div>
          <span>官方类目</span>
          <strong>{template.category}</strong>
        </div>
        <div>
          <span>建议入职部门</span>
          <strong>{template.dept}</strong>
        </div>
        <div>
          <span>模板 ID</span>
          <strong>{template.id}</strong>
        </div>
        <div>
          <span>类目 ID</span>
          <strong>{template.categoryId}</strong>
        </div>
        <div>
          <span>模板来源</span>
          <strong>{template.publisher}</strong>
        </div>
        <div>
          <span>模板状态</span>
          <strong>
            {template.status === 'published' ? '已发布' : template.status}
          </strong>
        </div>
      </div>

      <FieldLabel>岗位描述</FieldLabel>
      <div className="talent-profile-note">{template.desc}</div>

      <FieldLabel>工作职责 Prompt</FieldLabel>
      <div className="prompt-box">{template.prompt}</div>

      <FieldLabel>Skills</FieldLabel>
      <ChipList items={template.skills} emptyText="暂无技能" />

      <FieldLabel>MCP 工具</FieldLabel>
      <ChipList items={template.mcps} emptyText="暂无 MCP 工具" />

      <FieldLabel>平台说明</FieldLabel>
      <div className="market-admin-note">
        官方后台负责创建人才分类、维护模板内容、审核默认 Prompt、Skills、MCP
        权限和发布版本。用户侧不创建市场分类，只查看这个人才是否匹配需求，并在招募时选择加入自己的部门。
      </div>

      <div className="modal-actions">
        <button className="button secondary" type="button" onClick={onClose}>
          关闭
        </button>
        <button className="button primary" type="button" onClick={onRecruit}>
          {materialIcon('person_add')}招募
        </button>
      </div>
    </Modal>
  );
}

function TasksView({
  tasks,
  tabs,
  activeFilter,
  agents,
  scopeLabel,
  onPickFilter,
  onClearScope,
  onOpenCreateTask,
  onAdvanceTask,
  onOpenClaimTask,
  onOpenTask,
  onOpenChat,
  onOpenAgent,
}: {
  tasks: Task[];
  tabs: Array<{ status: TaskStatus | '全部'; count: number }>;
  activeFilter: TaskStatus | '全部';
  agents: Agent[];
  scopeLabel: string | null;
  onPickFilter: (status: TaskStatus | '全部') => void;
  onClearScope: () => void;
  onOpenCreateTask: () => void;
  onAdvanceTask: (task: Task) => void;
  onOpenClaimTask: (taskId: string) => void;
  onOpenTask: (taskId: string) => void;
  onOpenChat: (id: string) => void;
  onOpenAgent: (id: string) => void;
}) {
  return (
    <div className="screen-scroll">
      <div className="screen-inner">
        <header className="page-header compact">
          <div>
            <h1>任务中心</h1>
            <p>任务数据来自后端；后续会由小秘自动拆解生成</p>
          </div>
          <div className="header-actions">
            <button
              className="button primary"
              type="button"
              onClick={onOpenCreateTask}
            >
              {materialIcon('add_task')}创建任务
            </button>
          </div>
        </header>

        {scopeLabel && (
          <div className="task-scope-bar">
            <span>
              {materialIcon('forum')}正在查看 {scopeLabel} 的关联任务
            </span>
            <button type="button" onClick={onClearScope}>
              查看全部任务
            </button>
          </div>
        )}

        <div className="task-filter-bar" aria-label="任务状态筛选">
          {tabs.map((tab) => (
            <button
              className={
                activeFilter === tab.status
                  ? 'task-filter-button active'
                  : 'task-filter-button'
              }
              key={tab.status}
              type="button"
              onClick={() => onPickFilter(tab.status)}
            >
              <span>{tab.status}</span>
              <em>{tab.count}</em>
            </button>
          ))}
        </div>

        <article className="card task-table">
          <div className="task-table-head">
            <span>等级</span>
            <span>任务</span>
            <span>负责人</span>
            <span>进度</span>
            <span>状态</span>
            <span>操作</span>
          </div>
          {tasks.length === 0 && (
            <div className="task-table-empty">
              {scopeLabel
                ? '这个群聊还没有关联任务，可以在创建群聊时选择任务，后续也会支持从任务详情绑定。'
                : '暂无任务。先从给小秘发消息开始。'}
            </div>
          )}
          {tasks.map((task) => {
            const owner = agents.find((agent) => agent.id === task.owner);
            const priority = priorityStyle(task.pr);
            const status = statusStyle(task.status);
            return (
              <div className="task-table-row" key={task.id}>
                <span className="priority-pill" style={priority}>
                  {task.pr}
                </span>
                <div className="task-title-cell">
                  <strong>{task.title}</strong>
                  {task.src && (
                    <button type="button" onClick={() => onOpenChat(task.src)}>
                      {task.srcLabel}
                    </button>
                  )}
                </div>
                <div className="owner-cell">
                  {owner && (
                    <button
                      className="tiny-avatar"
                      style={{ background: avatarColor(owner) }}
                      type="button"
                      onClick={() => onOpenAgent(owner.id)}
                    >
                      {avatarText(owner.name)}
                    </button>
                  )}
                  <span>{owner?.name ?? '未分配'}</span>
                </div>
                <div className="task-progress">
                  <div className="progress-track">
                    <i
                      style={{
                        width: `${task.progress}%`,
                        background: status.bar,
                      }}
                    />
                  </div>
                  <em>{task.progress}%</em>
                </div>
                <span
                  className="status-pill"
                  style={{ background: status.background, color: status.color }}
                >
                  {task.status}
                </span>
                <div className="task-actions">
                  <button type="button" onClick={() => onOpenTask(task.id)}>
                    详情
                  </button>
                  {task.status === '待认领' ? (
                    <button
                      type="button"
                      onClick={() => onOpenClaimTask(task.id)}
                    >
                      认领
                    </button>
                  ) : (
                    <button type="button" onClick={() => onAdvanceTask(task)}>
                      {task.status === '已完成' ? '已完成' : '推进'}
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </article>
      </div>
    </div>
  );
}

function LibraryView({
  tabs,
  activeTab,
  onPickTab,
  skills,
  mcps,
}: {
  tabs: Array<{ key: LibraryTab; label: string }>;
  activeTab: LibraryTab;
  onPickTab: (tab: LibraryTab) => void;
  skills: string[];
  mcps: string[];
}) {
  return (
    <div className="screen-scroll">
      <div className="screen-inner">
        <header className="page-header compact">
          <div>
            <h1>资料库与能力</h1>
            <p>第一版先展示后端模板里的 Skills / MCP，资料上传后续接入</p>
          </div>
        </header>

        <div className="tabs">
          {tabs.map((tab) => (
            <button
              className={activeTab === tab.key ? 'tab active' : 'tab'}
              key={tab.key}
              type="button"
              onClick={() => onPickTab(tab.key)}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {activeTab === 'docs' && (
          <article className="card simple-list">
            <div className="library-row">
              <div className="library-icon">{materialIcon('description')}</div>
              <div>
                <strong>暂无资料</strong>
                <p>资料上传后会从后端读取，这里先保持空状态。</p>
              </div>
            </div>
          </article>
        )}

        {activeTab === 'skills' && (
          <article className="card simple-list">
            {skills.map((skill) => (
              <div className="library-row" key={skill}>
                <div className="library-icon">{materialIcon('bolt')}</div>
                <div>
                  <strong>{skill}</strong>
                  <p>来自后端人才模板，可绑定给员工。</p>
                </div>
              </div>
            ))}
            {!skills.length && <EmptyState>暂无 Skills</EmptyState>}
          </article>
        )}

        {activeTab === 'mcp' && (
          <article className="card simple-list">
            {mcps.map((mcp) => (
              <div className="library-row" key={mcp}>
                <div className="library-icon neutral">
                  {materialIcon('extension')}
                </div>
                <div>
                  <strong>{mcp}</strong>
                  <p>来自后端人才模板，第一版仅做权限占位。</p>
                </div>
                <span>
                  <i />
                  未连接
                </span>
              </div>
            ))}
            {!mcps.length && <EmptyState>暂无 MCP</EmptyState>}
          </article>
        )}
      </div>
    </div>
  );
}

function AgentDetail({
  agent,
  tasks,
  onClose,
  onDm,
}: {
  agent: Agent;
  tasks: Task[];
  onClose: () => void;
  onDm: () => void;
}) {
  return (
    <>
      <div className="overlay" onClick={onClose} />
      <aside className="agent-drawer" aria-label={`${agent.name} 详情`}>
        <header>
          <div className="drawer-topline">
            <div
              className="large-avatar"
              style={{ background: avatarColor(agent) }}
            >
              {avatarText(agent.name)}
            </div>
            <button type="button" title="关闭" onClick={onClose}>
              {materialIcon('close')}
            </button>
          </div>
          <h2>
            {agent.name}
            <span>
              <i style={{ background: dotColor(agent.statusKind) }} />
              {agent.statusLabel}
            </span>
          </h2>
          <p>
            {agent.role} · {agent.dept} · {agent.joined}
          </p>
          <div className="drawer-actions">
            <button className="button primary" type="button" onClick={onDm}>
              {materialIcon('chat')}私信
            </button>
          </div>
        </header>

        <div className="drawer-scroll">
          <section className="drawer-section">
            <h3>员工描述</h3>
            <p className="prompt-box">{agent.description || '暂无描述'}</p>
          </section>

          <section className="drawer-section">
            <h3>工作职责 Prompt</h3>
            <p className="prompt-box">{agent.prompt}</p>
          </section>

          <section className="drawer-section">
            <h3>Skills</h3>
            <ChipList items={agent.skills} emptyText="暂无绑定技能" />
          </section>

          <section className="drawer-section">
            <h3>MCP</h3>
            <ChipList items={agent.mcps} emptyText="暂无 MCP" muted />
          </section>

          <section className="drawer-section">
            <h3>经验沉淀</h3>
            {agent.experiences.length === 0 && (
              <EmptyState>完成并确认任务后会自动沉淀经验</EmptyState>
            )}
            {agent.experiences.slice(0, 5).map((experience) => (
              <article
                className={`experience-card ${experience.outcome}`}
                key={experience.id}
              >
                <div>
                  {materialIcon(
                    experience.outcome === 'success'
                      ? 'check_circle'
                      : 'report',
                  )}
                  <strong>
                    {experience.outcome === 'success' ? '成功经验' : '复盘教训'}
                  </strong>
                  <span>{experience.time}</span>
                </div>
                <p>{experience.summary}</p>
                {experience.lessons && <em>{experience.lessons}</em>}
              </article>
            ))}
          </section>

          <section className="drawer-section">
            <h3>相关任务</h3>
            {tasks.length === 0 && <EmptyState>暂无任务</EmptyState>}
            {tasks.map((task) => {
              const status = statusStyle(task.status);
              const priority = priorityStyle(task.pr);
              return (
                <article className="drawer-task" key={task.id}>
                  <div>
                    <em style={priority}>{task.pr}</em>
                    <strong>{task.title}</strong>
                  </div>
                  <div className="drawer-progress">
                    <div className="progress-track">
                      <i
                        style={{
                          width: `${task.progress}%`,
                          background: status.bar,
                        }}
                      />
                    </div>
                    <span>{task.status}</span>
                  </div>
                </article>
              );
            })}
          </section>
        </div>
      </aside>
    </>
  );
}

function TaskDetail({
  task,
  agent,
  onClose,
  onOpenChat,
  onOpenAgent,
  onAdvanceTask,
  onResolveApproval,
}: {
  task: Task;
  agent?: Agent;
  onClose: () => void;
  onOpenChat: (id: string) => void;
  onOpenAgent: (id: string) => void;
  onAdvanceTask: (task: Task) => void;
  onResolveApproval: (
    approval: Approval,
    status: 'approved' | 'rejected',
  ) => void;
}) {
  const status = statusStyle(task.status);
  const priority = priorityStyle(task.pr);
  const pendingApprovals = task.approvals.filter(
    (approval) => approval.status === 'pending',
  );
  const latestOutput = task.outputs[0];

  return (
    <>
      <div className="overlay" onClick={onClose} />
      <aside className="agent-drawer task-detail-drawer" aria-label="任务详情">
        <header>
          <div className="drawer-topline">
            <span className="priority-pill" style={priority}>
              {task.pr}
            </span>
            <button type="button" title="关闭" onClick={onClose}>
              {materialIcon('close')}
            </button>
          </div>
          <h2>
            {task.title}
            <span style={{ color: status.color }}>
              <i style={{ background: status.bar }} />
              {task.status}
            </span>
          </h2>
          <p>{task.description || '暂无任务说明'}</p>
          <div className="drawer-actions">
            {task.src && (
              <button
                className="button secondary"
                type="button"
                onClick={() => onOpenChat(task.src)}
              >
                {materialIcon('forum')}关联会话
              </button>
            )}
            <button
              className="button primary"
              type="button"
              onClick={() => onAdvanceTask(task)}
            >
              {task.status === '已完成' ? '已完成' : '推进任务'}
            </button>
          </div>
        </header>

        <div className="drawer-scroll">
          <section className="drawer-section">
            <h3>任务概览</h3>
            <div className="task-detail-grid">
              <div>
                <span>负责人</span>
                {agent ? (
                  <button type="button" onClick={() => onOpenAgent(agent.id)}>
                    {avatarText(agent.name)} · {agent.name}
                  </button>
                ) : (
                  <strong>未分配</strong>
                )}
              </div>
              <div>
                <span>关联会话</span>
                <strong>{task.srcLabel}</strong>
              </div>
              <div>
                <span>创建时间</span>
                <strong>{task.createdAt}</strong>
              </div>
              <div>
                <span>更新时间</span>
                <strong>{task.updatedAt}</strong>
              </div>
            </div>
            <div className="task-detail-progress">
              <div className="progress-track">
                <i
                  style={{
                    width: `${task.progress}%`,
                    background: status.bar,
                  }}
                />
              </div>
              <span>{task.progress}%</span>
            </div>
          </section>

          {pendingApprovals.length > 0 && (
            <section className="drawer-section">
              <h3>待老板确认</h3>
              {pendingApprovals.map((approval) => (
                <article className="approval-request" key={approval.id}>
                  <div>
                    {materialIcon('approval', 'warning')}
                    <span>
                      <strong>{approval.title}</strong>
                      <em>{approval.description}</em>
                    </span>
                  </div>
                  <footer>
                    <button
                      className="button secondary"
                      type="button"
                      onClick={() => onResolveApproval(approval, 'rejected')}
                    >
                      驳回
                    </button>
                    <button
                      className="button primary"
                      type="button"
                      onClick={() => onResolveApproval(approval, 'approved')}
                    >
                      确认通过
                    </button>
                  </footer>
                </article>
              ))}
            </section>
          )}

          <section className="drawer-section">
            <h3>最新产出</h3>
            {latestOutput ? (
              <article className="task-output-card">
                <header>
                  <strong>{latestOutput.title}</strong>
                  <span>{latestOutput.time}</span>
                </header>
                <pre>{latestOutput.content}</pre>
              </article>
            ) : (
              <EmptyState>暂无产出，员工回复后会自动沉淀到这里。</EmptyState>
            )}
          </section>

          <section className="drawer-section">
            <h3>执行记录</h3>
            <div className="task-timeline">
              {task.events.length === 0 && (
                <EmptyState>暂无执行记录</EmptyState>
              )}
              {task.events.map((event) => (
                <article className="timeline-event" key={event.id}>
                  <i />
                  <div>
                    <strong>{event.title}</strong>
                    <span>{event.time}</span>
                    {event.content && <p>{event.content}</p>}
                  </div>
                </article>
              ))}
            </div>
          </section>
        </div>
      </aside>
    </>
  );
}

function HireModal({
  template,
  departments,
  hireDept,
  onDeptChange,
  onClose,
  onSubmit,
}: {
  template?: HireTemplate;
  departments: string[];
  hireDept: string;
  onDeptChange: (dept: string) => void;
  onClose: () => void;
  onSubmit: () => void;
}) {
  if (!template) return null;

  return (
    <Modal
      title="招募员工"
      description="从人才市场招募预设岗位，确认部门后加入你的组织。"
      width={560}
      onClose={onClose}
    >
      <div className="hire-summary">
        <div
          className="large-avatar"
          style={{ background: 'oklch(0.55 0.11 230)' }}
        >
          {avatarText(template.name)}
        </div>
        <div>
          <strong>{template.name}</strong>
          <p>
            {template.dept} · {template.desc}
          </p>
        </div>
      </div>

      <FieldLabel>入职部门</FieldLabel>
      <input
        value={hireDept}
        placeholder={`例如：${template.dept}`}
        onChange={(event) => onDeptChange(event.currentTarget.value)}
      />
      {departments.length > 0 && (
        <>
          <FieldLabel>已有部门</FieldLabel>
          <div className="chip-row compact">
            {departments.map((department) => (
              <button
                className={
                  hireDept === department
                    ? 'selector-chip active'
                    : 'selector-chip'
                }
                key={department}
                type="button"
                onClick={() => onDeptChange(department)}
              >
                {department}
              </button>
            ))}
          </div>
        </>
      )}

      <FieldLabel>岗位 Prompt</FieldLabel>
      <textarea readOnly rows={5} value={template.prompt} />

      <FieldLabel>能力标签</FieldLabel>
      <ChipList items={template.skills} emptyText="暂无技能" />

      <div className="modal-actions">
        <button className="button secondary" type="button" onClick={onClose}>
          取消
        </button>
        <button className="button primary" type="button" onClick={onSubmit}>
          {materialIcon('person_add')}确认招募
        </button>
      </div>
    </Modal>
  );
}

function CreateTaskModal({
  agents,
  chats,
  taskTitle,
  taskDesc,
  taskPriority,
  taskOwnerId,
  taskConversationId,
  agentById,
  onTitleChange,
  onDescChange,
  onPriorityChange,
  onOwnerChange,
  onConversationChange,
  onClose,
  onSubmit,
}: {
  agents: Agent[];
  chats: Chat[];
  taskTitle: string;
  taskDesc: string;
  taskPriority: Priority;
  taskOwnerId: string;
  taskConversationId: string;
  agentById: (id: string) => Agent | undefined;
  onTitleChange: (value: string) => void;
  onDescChange: (value: string) => void;
  onPriorityChange: (value: Priority) => void;
  onOwnerChange: (value: string) => void;
  onConversationChange: (value: string) => void;
  onClose: () => void;
  onSubmit: () => void;
}) {
  return (
    <Modal
      title="创建任务"
      description="把想法沉淀成可追踪的工作项，后续会进入员工上下文。"
      width={680}
      onClose={onClose}
    >
      <FieldLabel>任务标题</FieldLabel>
      <input
        value={taskTitle}
        placeholder="例如：官网首屏文案确认"
        onChange={(event) => onTitleChange(event.currentTarget.value)}
      />

      <FieldLabel>任务说明</FieldLabel>
      <textarea
        rows={4}
        value={taskDesc}
        placeholder="写清楚目标、产出格式和验收标准"
        onChange={(event) => onDescChange(event.currentTarget.value)}
      />

      <div className="form-grid even">
        <label>
          <FieldLabel>负责人</FieldLabel>
          <select
            value={taskOwnerId}
            onChange={(event) => onOwnerChange(event.currentTarget.value)}
          >
            <option value="">未分配</option>
            {agents.map((agent) => (
              <option key={agent.id} value={agent.id}>
                {agent.name} · {agent.role}
              </option>
            ))}
          </select>
        </label>
        <label>
          <FieldLabel>关联会话</FieldLabel>
          <select
            value={taskConversationId}
            onChange={(event) =>
              onConversationChange(event.currentTarget.value)
            }
          >
            <option value="">不关联</option>
            {chats.map((chat) => (
              <option key={chat.id} value={chat.id}>
                {chat.kind === 'group'
                  ? `# ${chat.name}`
                  : `私聊 · ${agentById(chat.agentId)?.name ?? '员工'}`}
              </option>
            ))}
          </select>
        </label>
      </div>

      <FieldLabel>优先级</FieldLabel>
      <div className="chip-row compact">
        {(['P0', 'P1', 'P2'] as const).map((priority) => (
          <button
            className={
              taskPriority === priority
                ? 'selector-chip active'
                : 'selector-chip'
            }
            key={priority}
            type="button"
            onClick={() => onPriorityChange(priority)}
          >
            {priority}
          </button>
        ))}
      </div>

      <div className="modal-actions">
        <button className="button secondary" type="button" onClick={onClose}>
          取消
        </button>
        <button className="button primary" type="button" onClick={onSubmit}>
          {materialIcon('add_task')}创建任务
        </button>
      </div>
    </Modal>
  );
}

function CreateAgentModal({
  departments,
  createName,
  createDesc,
  createDept,
  createPrompt,
  onNameChange,
  onDescChange,
  onDeptChange,
  onPromptChange,
  onClose,
  onSubmit,
}: {
  departments: string[];
  createName: string;
  createDesc: string;
  createDept: string;
  createPrompt: string;
  onNameChange: (value: string) => void;
  onDescChange: (value: string) => void;
  onDeptChange: (value: string) => void;
  onPromptChange: (value: string) => void;
  onClose: () => void;
  onSubmit: () => void;
}) {
  return (
    <Modal
      title="创建新员工"
      description="自定义员工名称、描述、部门和工作职责 Prompt。"
      width={680}
      onClose={onClose}
    >
      <div className="form-grid even">
        <label>
          <FieldLabel>员工名称</FieldLabel>
          <input
            value={createName}
            placeholder="例如：增长分析师"
            onChange={(event) => onNameChange(event.currentTarget.value)}
          />
        </label>
        <label>
          <FieldLabel>所属部门</FieldLabel>
          <input
            value={createDept}
            list="agentpulse-departments"
            placeholder="例如：增长与客户"
            onChange={(event) => onDeptChange(event.currentTarget.value)}
          />
          <datalist id="agentpulse-departments">
            {departments.map((department) => (
              <option key={department} value={department} />
            ))}
          </datalist>
        </label>
      </div>

      <FieldLabel>员工描述</FieldLabel>
      <input
        value={createDesc}
        placeholder="一句话说明他擅长什么"
        onChange={(event) => onDescChange(event.currentTarget.value)}
      />

      <FieldLabel>工作职责 Prompt</FieldLabel>
      <textarea
        rows={8}
        value={createPrompt}
        placeholder="写清楚这个员工的职责、边界、输出格式和协作方式"
        onChange={(event) => onPromptChange(event.currentTarget.value)}
      />

      <div className="modal-actions">
        <button className="button secondary" type="button" onClick={onClose}>
          取消
        </button>
        <button className="button primary" type="button" onClick={onSubmit}>
          {materialIcon('add_circle')}创建
        </button>
      </div>
    </Modal>
  );
}

function ClaimTaskModal({
  task,
  agents,
  selectedAgentId,
  onAgentChange,
  onClose,
  onSubmit,
}: {
  task?: Task;
  agents: Agent[];
  selectedAgentId: string;
  onAgentChange: (value: string) => void;
  onClose: () => void;
  onSubmit: () => void;
}) {
  return (
    <Modal
      title="认领任务"
      description={task ? `从任务池认领「${task.title}」` : '从任务池认领任务'}
      width={520}
      onClose={onClose}
    >
      <FieldLabel>执行员工</FieldLabel>
      <select
        value={selectedAgentId}
        onChange={(event) => onAgentChange(event.currentTarget.value)}
      >
        <option value="">选择员工</option>
        {agents.map((agent) => (
          <option key={agent.id} value={agent.id}>
            {agent.name} · {agent.role}
          </option>
        ))}
      </select>
      <div className="market-admin-note">
        认领后任务会进入进行中，并写入任务时间线。后续可以让员工在相关会话里继续执行。
      </div>
      <div className="modal-actions">
        <button className="button secondary" type="button" onClick={onClose}>
          取消
        </button>
        <button className="button primary" type="button" onClick={onSubmit}>
          {materialIcon('assignment_ind')}确认认领
        </button>
      </div>
    </Modal>
  );
}

function GroupModal({
  agents,
  tasks,
  groupName,
  groupMembers,
  selectedTaskIds,
  onGroupNameChange,
  onToggleMember,
  onToggleTask,
  onClose,
  onCreate,
}: {
  agents: Agent[];
  tasks: Task[];
  groupName: string;
  groupMembers: string[];
  selectedTaskIds: string[];
  onGroupNameChange: (value: string) => void;
  onToggleMember: (id: string) => void;
  onToggleTask: (id: string) => void;
  onClose: () => void;
  onCreate: () => void;
}) {
  return (
    <Modal
      title="创建群聊"
      description="把相关员工拉到同一个会话里，后续可以用 @ 点名。"
      width={620}
      onClose={onClose}
    >
      <FieldLabel>群聊名称</FieldLabel>
      <input
        value={groupName}
        placeholder="例如：官网上线作战室"
        onChange={(event) => onGroupNameChange(event.currentTarget.value)}
      />

      <FieldLabel>选择成员</FieldLabel>
      <MemberPicker
        agents={agents}
        selectedMembers={groupMembers}
        onToggleMember={onToggleMember}
      />

      <FieldLabel>关联任务（可选）</FieldLabel>
      <TaskPicker
        tasks={tasks}
        selectedTaskIds={selectedTaskIds}
        onToggleTask={onToggleTask}
      />

      <div className="modal-actions">
        <button className="button secondary" type="button" onClick={onClose}>
          取消
        </button>
        <button className="button primary" type="button" onClick={onCreate}>
          {materialIcon('group_add')}创建群聊
        </button>
      </div>
    </Modal>
  );
}

function TaskPicker({
  tasks,
  selectedTaskIds,
  onToggleTask,
}: {
  tasks: Task[];
  selectedTaskIds: string[];
  onToggleTask: (id: string) => void;
}) {
  if (!tasks.length) {
    return <div className="member-picker-empty">暂无可关联任务</div>;
  }

  return (
    <div className="task-picker">
      {tasks.map((task) => {
        const active = selectedTaskIds.includes(task.id);
        const status = statusStyle(task.status);
        return (
          <button
            className={active ? 'task-option active' : 'task-option'}
            key={task.id}
            type="button"
            onClick={() => onToggleTask(task.id)}
          >
            <span className="task-option-main">
              <strong>{task.title}</strong>
              <em>{task.srcLabel}</em>
            </span>
            <span
              className="status-pill"
              style={{ background: status.background, color: status.color }}
            >
              {task.status}
            </span>
            {materialIcon(active ? 'check_circle' : 'radio_button_unchecked')}
          </button>
        );
      })}
    </div>
  );
}

function GroupMembersModal({
  title,
  description,
  agents,
  selectedMembers,
  submitLabel,
  emptyText,
  onToggleMember,
  onClose,
  onSubmit,
}: {
  title: string;
  description: string;
  agents: Agent[];
  selectedMembers: string[];
  submitLabel: string;
  emptyText: string;
  onToggleMember: (id: string) => void;
  onClose: () => void;
  onSubmit: () => void;
}) {
  return (
    <Modal
      title={title}
      description={description}
      width={620}
      onClose={onClose}
    >
      <FieldLabel>选择成员</FieldLabel>
      <MemberPicker
        agents={agents}
        selectedMembers={selectedMembers}
        emptyText={emptyText}
        onToggleMember={onToggleMember}
      />

      <div className="modal-actions">
        <button className="button secondary" type="button" onClick={onClose}>
          取消
        </button>
        <button className="button primary" type="button" onClick={onSubmit}>
          {materialIcon('person_add')}
          {submitLabel}
        </button>
      </div>
    </Modal>
  );
}

function MemberPicker({
  agents,
  selectedMembers,
  emptyText = '暂无可选员工',
  onToggleMember,
}: {
  agents: Agent[];
  selectedMembers: string[];
  emptyText?: string;
  onToggleMember: (id: string) => void;
}) {
  if (!agents.length) {
    return <div className="member-picker-empty">{emptyText}</div>;
  }

  return (
    <div className="member-picker">
      {agents.map((agent) => {
        const active = selectedMembers.includes(agent.id);
        return (
          <button
            className={active ? 'member-option active' : 'member-option'}
            key={agent.id}
            type="button"
            onClick={() => onToggleMember(agent.id)}
          >
            <span
              className="tiny-avatar"
              style={{ background: avatarColor(agent) }}
            >
              {avatarText(agent.name)}
            </span>
            <span>
              <strong>{agent.name}</strong>
              <em>
                {agent.role} · {agent.dept}
              </em>
            </span>
            {materialIcon(active ? 'check_circle' : 'radio_button_unchecked')}
          </button>
        );
      })}
    </div>
  );
}

function OnboardingModal({
  step,
  templates,
  onNext,
  onFinish,
}: {
  step: number;
  templates: HireTemplate[];
  onNext: () => void;
  onFinish: () => void;
}) {
  const featuredTemplates = templates.slice(0, 4);

  return (
    <>
      <div className="overlay blur" />
      <section className="onboarding-modal" aria-label="新手引导">
        {step === 0 && (
          <div className="onboarding-content centered">
            <div className="onboarding-logo big">✦</div>
            <h2>欢迎来到 AgentPulse</h2>
            <p>
              这里不是聊天 Demo，而是你的 AI
              公司工作台。第一版已经接入账号、组织、员工和真实 LLM 调用链。
            </p>
            <div className="onboarding-feature-grid">
              <OnboardingFeature
                icon="forum"
                title="从消息开始"
                text="默认进入小秘私聊，把想法直接丢进来。"
              />
              <OnboardingFeature
                icon="storefront"
                title="人才市场"
                text="按岗位招募 AI 员工，入职后进入组织。"
              />
              <OnboardingFeature
                icon="account_tree"
                title="组织协作"
                text="创建群聊，用 @ 点名具体员工推进。"
              />
            </div>
          </div>
        )}

        {step === 1 && (
          <div className="onboarding-content">
            <div className="onboarding-logo">✦</div>
            <h2>先认识你的第一批员工</h2>
            <p>
              小秘已经就位。你可以继续从人才市场招募这些角色，让一人公司开始分工。
            </p>
            <div className="role-grid">
              {featuredTemplates.map((template, index) => (
                <div className="role-option active" key={template.id}>
                  <div
                    style={{
                      background: `oklch(0.55 0.11 ${220 + index * 35})`,
                    }}
                  >
                    {['◆', '●', '▲', '■'][index % 4]}
                  </div>
                  <span>
                    <strong>{template.name}</strong>
                    <em>{template.dept}</em>
                  </span>
                  {materialIcon('check_circle')}
                </div>
              ))}
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="onboarding-content centered">
            <div className="onboarding-logo big">✦</div>
            <h2>从给小秘发消息开始</h2>
            <p>
              你可以说“帮我把 AgentPulse
              第一版拆成今天能做的任务”，小秘会用后端真实模型返回下一步。
            </p>
            <div className="try-chip">
              {materialIcon('chat')}
              试试：今天我们先推进什么？
            </div>
          </div>
        )}

        <footer className="onboarding-footer">
          <div className="step-dots">
            {[0, 1, 2].map((item) => (
              <i className={step === item ? 'active' : ''} key={item} />
            ))}
          </div>
          <span />
          <button className="skip-button" type="button" onClick={onFinish}>
            跳过
          </button>
          <button
            className="button primary"
            type="button"
            onClick={step >= 2 ? onFinish : onNext}
          >
            {step >= 2 ? '开始使用' : '下一步'}
          </button>
        </footer>
      </section>
    </>
  );
}

function OnboardingFeature({
  icon,
  title,
  text,
}: {
  icon: string;
  title: string;
  text: string;
}) {
  return (
    <div>
      {materialIcon(icon)}
      <strong>{title}</strong>
      <p>{text}</p>
    </div>
  );
}

function Modal({
  title,
  description,
  width,
  onClose,
  children,
}: {
  title: string;
  description: string;
  width: number;
  onClose: () => void;
  children: ReactNode;
}) {
  return (
    <>
      <div className="overlay blur" onClick={onClose} />
      <section className="modal" style={{ width }} aria-label={title}>
        <header className="modal-header">
          <h2>{title}</h2>
          <p>{description}</p>
        </header>
        <div className="modal-body">{children}</div>
      </section>
    </>
  );
}

function FieldLabel({ children }: { children: ReactNode }) {
  return <div className="field-label">{children}</div>;
}

function ChipList({
  items,
  emptyText,
  muted = false,
}: {
  items: string[];
  emptyText: string;
  muted?: boolean;
}) {
  if (!items.length) return <EmptyState>{emptyText}</EmptyState>;

  return (
    <div className="chip-list">
      {items.map((item) => (
        <span className={muted ? 'chip muted' : 'chip'} key={item}>
          {muted ? materialIcon('extension') : materialIcon('bolt')}
          {item}
        </span>
      ))}
    </div>
  );
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
