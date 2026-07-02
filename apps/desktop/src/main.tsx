import { StrictMode, useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';

type View = 'home' | 'chat' | 'staff' | 'tasks' | 'lib';
type AgentStatus = 'busy' | 'wait' | 'stuck' | 'idle';
type TaskStatus = '进行中' | '待确认' | '卡住' | '已完成';
type Priority = 'P0' | 'P1' | 'P2';
type LibraryTab = 'docs' | 'skills' | 'mcp';

type Agent = {
  id: string;
  name: string;
  role: string;
  dept: string;
  hue: number;
  glyph: string;
  statusKind: AgentStatus;
  statusLabel: string;
  joined: string;
  prompt: string;
  skills: string[];
  mcps: string[];
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

type Message =
  | {
      id: string;
      from: string;
      type: 'system' | 'text';
      time: string;
      text: string;
    }
  | {
      id: string;
      from: string;
      type: 'result';
      time: string;
      cardTitle: string;
      cardDesc: string;
      cardFile: string;
    }
  | {
      id: string;
      from: string;
      type: 'approval';
      time: string;
      apQ: string;
      apDesc: string;
      apOptA: string;
      apOptB: string;
      apStatus: 'pending' | 'A' | 'B';
      taskId: string;
      followA: string;
      followB: string;
    }
  | {
      id: string;
      from: string;
      type: 'task';
      time: string;
      taskTitle: string;
      taskPr: Priority;
    };

type Task = {
  id: string;
  title: string;
  pr: Priority;
  owner: string;
  status: TaskStatus;
  progress: number;
  src: string;
  srcLabel: string;
};

type HireTemplate = {
  name: string;
  dept: string;
  desc: string;
  prompt: string;
  skills: string[];
  mcps: string[];
};

type ToastState = {
  visible: boolean;
  message: string;
};

const accent = '#3B5BDB';
const companyName = '星野工作室';
const hueCycle = [200, 40, 320, 110, 250, 10];
const glyphCycle = ['◆', '●', '▲', '■', '◗', '✱'];
const allSkills = [
  '公众号文案',
  '竞品分析',
  '数据报表',
  'SEO 优化',
  '客服话术',
  '任务拆解',
  '投放策略',
];
const allMcps = ['飞书文档', 'Notion', '企业邮箱', 'Stripe', '微信公众号'];
const secretaryReplies = [
  '收到。我整理一下要点，稍后把建议和分工方案发给你。',
  '好的。需要我直接建任务，还是先拉个群让大家讨论？',
  '明白，已记到任务池。等你确认优先级后我就分配下去。',
];

let messageCounter = 500;
const messageId = () => `m${messageCounter++}`;
const makeMessage = <T extends Omit<Message, 'id'>>(
  message: T,
): T & { id: string } => ({
  id: messageId(),
  ...message,
});

const initialAgents: Agent[] = [
  {
    id: 'sec',
    name: '小秘',
    role: '老板秘书',
    dept: '老板办公室',
    hue: 262,
    glyph: '✦',
    statusKind: 'idle',
    statusLabel: '在线待命',
    joined: '系统内置',
    prompt:
      '你是老板的贴身秘书兼幕僚长。接收老板的任何想法，转化为任务、招聘建议或群组讨论；跟踪全公司任务进度；需要老板拍板时，整理好决策要点再去打扰他。',
    skills: ['任务拆解', '会议纪要', '信息检索'],
    mcps: ['飞书文档', '企业邮箱'],
  },
  {
    id: 'alan',
    name: '阿澜',
    role: '运营负责人',
    dept: '运营部',
    hue: 230,
    glyph: '▲',
    statusKind: 'busy',
    statusLabel: '执行中',
    joined: '2026-04 入职',
    prompt:
      '你是一名资深运营负责人。负责渠道盘点、预算分配与节奏把控，输出可直接执行的运营方案，并统筹团队成员分工。',
    skills: ['数据报表', '竞品分析', '投放策略'],
    mcps: ['飞书文档', 'Notion'],
  },
  {
    id: 'jianyi',
    name: '简一',
    role: '运营专家',
    dept: '运营部',
    hue: 205,
    glyph: '●',
    statusKind: 'busy',
    statusLabel: '执行中',
    joined: '2026-04 入职',
    prompt:
      '你是一名运营专家，擅长竞品拆解与增长实验设计。输出结论时给出数据依据和可复制的打法。',
    skills: ['竞品分析', '数据报表'],
    mcps: ['飞书文档'],
  },
  {
    id: 'xiaohe',
    name: '小禾',
    role: '运营同学',
    dept: '运营部',
    hue: 170,
    glyph: '■',
    statusKind: 'wait',
    statusLabel: '等待确认',
    joined: '2026-05 入职',
    prompt:
      '你是一名运营执行同学。负责渠道调研、素材整理与投放执行，结果用结构化报告沉淀到群里。',
    skills: ['数据报表'],
    mcps: ['飞书文档'],
  },
  {
    id: 'mobai',
    name: '墨白',
    role: '内容主笔',
    dept: '内容部',
    hue: 300,
    glyph: '◆',
    statusKind: 'stuck',
    statusLabel: '卡住了',
    joined: '2026-04 入职',
    prompt:
      '你是一名内容主笔。擅长品牌叙事与转化型文案，为官网、公众号与销售物料产出高质量内容。',
    skills: ['公众号文案', 'SEO 优化'],
    mcps: ['飞书文档', '微信公众号'],
  },
  {
    id: 'qingzhu',
    name: '青竹',
    role: '短视频策划',
    dept: '内容部',
    hue: 140,
    glyph: '◗',
    statusKind: 'busy',
    statusLabel: '执行中',
    joined: '2026-05 入职',
    prompt:
      '你是一名短视频策划。负责选题、脚本与分发节奏，选题要能挂钩获客目标。',
    skills: ['公众号文案'],
    mcps: ['飞书文档'],
  },
  {
    id: 'tuyuan',
    name: '途远',
    role: '销售顾问',
    dept: '增长与客户',
    hue: 55,
    glyph: '✱',
    statusKind: 'wait',
    statusLabel: '等待确认',
    joined: '2026-04 入职',
    prompt:
      '你是一名销售顾问。负责线索跟进、报价与周报，成交卡点要及时上报老板拍板。',
    skills: ['客服话术', '数据报表'],
    mcps: ['企业邮箱', 'Notion'],
  },
  {
    id: 'anran',
    name: '安然',
    role: '客服专员',
    dept: '增长与客户',
    hue: 20,
    glyph: '◍',
    statusKind: 'idle',
    statusLabel: '空闲',
    joined: '2026-05 入职',
    prompt:
      '你是一名客服专员。基于公司 FAQ 与话术库回复客户，超出权限的承诺必须请老板拍板。',
    skills: ['客服话术'],
    mcps: ['企业邮箱'],
  },
  {
    id: 'jiansuan',
    name: '简算',
    role: '财务助理',
    dept: '财务行政',
    hue: 330,
    glyph: '◉',
    statusKind: 'idle',
    statusLabel: '空闲',
    joined: '2026-05 入职',
    prompt:
      '你是一名财务助理。负责记账、对账与月度报表，任何异常支出立即标红上报。',
    skills: ['数据报表'],
    mcps: ['Stripe', '飞书文档'],
  },
];

const initialMessages: Record<string, Message[]> = {
  sec: [
    makeMessage({
      from: 'sec',
      type: 'text',
      time: '08:30',
      text: '早上好，老板。今天有 2 件事需要你拍板，5 个任务在推进中。\n有任何想法直接丢给我 —— 我可以帮你创建任务、招聘员工、或者拉群讨论。',
    }),
    makeMessage({
      from: 'boss',
      type: 'text',
      time: '09:02',
      text: '我想做个老客户回访的事，还没想清楚找谁。',
    }),
    makeMessage({
      from: 'sec',
      type: 'text',
      time: '09:02',
      text: '建议：由途远负责整理回访清单，安然跟进执行回访。\n我先建一个 P2 任务放进任务池，等你确认优先级；需要的话我再拉一个「客户回访」群。',
    }),
    makeMessage({
      from: 'sec',
      type: 'task',
      time: '09:03',
      taskTitle: '老客户回访计划',
      taskPr: 'P2',
    }),
  ],
  g1: [
    makeMessage({
      from: 'system',
      type: 'system',
      time: '',
      text: '你创建了群聊，拉入了 阿澜、简一、小禾',
    }),
    makeMessage({
      from: 'boss',
      type: 'text',
      time: '09:32',
      text: '下半年重点是拉新。Q3 我想做一波获客，预算 2 万以内，先出个完整方案。目标：新增 500 个付费用户。',
    }),
    makeMessage({
      from: 'alan',
      type: 'text',
      time: '09:33',
      text: '收到。我先拆解：1. 渠道盘点与调研（小禾）2. 竞品打法分析（简一）3. 预算分配与节奏（我）。今天下班前给你第一版框架。',
    }),
    makeMessage({
      from: 'alan',
      type: 'task',
      time: '09:33',
      taskTitle: 'Q3 拉新方案 v1',
      taskPr: 'P0',
    }),
    makeMessage({
      from: 'jianyi',
      type: 'text',
      time: '09:41',
      text: '一个问题：目标用户还是以设计师群体为主吗？还是要往中小企业主扩？这影响竞品选取。',
    }),
    makeMessage({
      from: 'boss',
      type: 'text',
      time: '09:52',
      text: '以设计师为主，中小企业主作为次要人群观察就行。',
    }),
    makeMessage({
      from: 'xiaohe',
      type: 'result',
      time: '11:47',
      cardTitle: '渠道调研报告 v1',
      cardDesc:
        '盘点了 12 个获客渠道，按 CAC 与起量速度排序，推荐优先测试其中 3 个：设计社区投放、垂类 KOC、SEO 专题页。',
      cardFile: '渠道调研报告v1.pdf · 14 页',
    }),
    makeMessage({
      from: 'alan',
      type: 'approval',
      time: '14:20',
      apQ: '预算分配需要你拍板',
      apDesc:
        '方案A：70% 投放 + 30% 内容，起量快，预估 CAC 约 42 元；方案B：40% 投放 + 60% 内容，起量慢一拍，但能沉淀私域和搜索资产。',
      apOptA: '方案A · 投放优先',
      apOptB: '方案B · 内容优先',
      apStatus: 'pending',
      taskId: 't1',
      followA:
        '收到，按「方案A · 投放优先」推进：本周内上线两条投放计划，预算表我更新后同步到群里。',
      followB:
        '收到，按「方案B · 内容优先」推进：我和内容部对齐排期，预算表更新后同步到群里。',
    }),
  ],
  g2: [
    makeMessage({
      from: 'system',
      type: 'system',
      time: '',
      text: '你创建了群聊，拉入了 墨白、青竹、途远',
    }),
    makeMessage({
      from: 'boss',
      type: 'text',
      time: '昨天',
      text: '官网首页要改版，重点突出客户案例和评价，下周五前上线。',
    }),
    makeMessage({
      from: 'mobai',
      type: 'text',
      time: '昨天',
      text: '结构我重排了：首屏价值主张 → 案例墙 → 客户评价 → 价格。文案今天出，视觉稿明天。',
    }),
    makeMessage({
      from: 'qingzhu',
      type: 'text',
      time: '昨天',
      text: '我配套出 3 条官网上线的预热短视频脚本，选题清单整理中。',
    }),
    makeMessage({
      from: 'mobai',
      type: 'approval',
      time: '10:15',
      apQ: '视觉素材缺失，需要你拍板',
      apDesc:
        '品牌素材库里没有高清客户案例图。先用占位图继续排版，还是等你上传素材再继续？',
      apOptA: '用占位图继续',
      apOptB: '等我上传素材',
      apStatus: 'pending',
      taskId: 't4',
      followA:
        '好的，先用占位图完成整版排版，素材到位后替换即可，不影响下周五上线。',
      followB:
        '好的，我先完成文案与结构部分，等素材到位再出视觉稿，需要占用你一点时间上传。',
    }),
  ],
  mobai: [
    makeMessage({
      from: 'boss',
      type: 'text',
      time: '周一',
      text: '案例页的文案这周内给我初稿。',
    }),
    makeMessage({
      from: 'mobai',
      type: 'text',
      time: '周一',
      text: '好的。我列了 6 个案例的叙事角度，先给你两个方向的小样，你挑一个我再铺开写。',
    }),
  ],
  tuyuan: [
    makeMessage({
      from: 'tuyuan',
      type: 'result',
      time: '17:40',
      cardTitle: '6月销售周报（W26）',
      cardDesc:
        '新增线索 86 条，成交 9 单，环比 +12%。两个大客户卡在报价环节，建议下周电话跟进。',
      cardFile: '销售周报-W26.pdf · 6 页',
    }),
    makeMessage({
      from: 'tuyuan',
      type: 'text',
      time: '17:41',
      text: '周报已完成，待你确认后我归档，并把两个卡单客户建成跟进任务。',
    }),
  ],
};

const initialChats: Chat[] = [
  { id: 'sec', kind: 'dm', agentId: 'sec', unread: 0, time: '09:03' },
  {
    id: 'g1',
    kind: 'group',
    name: 'Q3 拉新方案',
    memberIds: ['alan', 'jianyi', 'xiaohe'],
    unread: 0,
    time: '14:20',
  },
  {
    id: 'g2',
    kind: 'group',
    name: '官网改版',
    memberIds: ['mobai', 'qingzhu', 'tuyuan'],
    unread: 2,
    time: '10:15',
  },
  { id: 'mobai', kind: 'dm', agentId: 'mobai', unread: 0, time: '周一' },
  { id: 'tuyuan', kind: 'dm', agentId: 'tuyuan', unread: 1, time: '17:41' },
];

const initialTasks: Task[] = [
  {
    id: 't1',
    title: 'Q3 拉新方案 v1',
    pr: 'P0',
    owner: 'alan',
    status: '进行中',
    progress: 60,
    src: 'g1',
    srcLabel: '#Q3 拉新方案',
  },
  {
    id: 't2',
    title: '渠道调研报告',
    pr: 'P1',
    owner: 'xiaohe',
    status: '待确认',
    progress: 100,
    src: 'g1',
    srcLabel: '#Q3 拉新方案',
  },
  {
    id: 't3',
    title: '竞品打法分析',
    pr: 'P1',
    owner: 'jianyi',
    status: '进行中',
    progress: 45,
    src: 'g1',
    srcLabel: '#Q3 拉新方案',
  },
  {
    id: 't4',
    title: '官网改版视觉稿',
    pr: 'P1',
    owner: 'mobai',
    status: '卡住',
    progress: 40,
    src: 'g2',
    srcLabel: '#官网改版',
  },
  {
    id: 't5',
    title: '官网案例页文案',
    pr: 'P2',
    owner: 'mobai',
    status: '进行中',
    progress: 70,
    src: 'mobai',
    srcLabel: '私聊 · 墨白',
  },
  {
    id: 't6',
    title: '短视频选题清单',
    pr: 'P2',
    owner: 'qingzhu',
    status: '进行中',
    progress: 30,
    src: 'g2',
    srcLabel: '#官网改版',
  },
  {
    id: 't7',
    title: '6月销售周报',
    pr: 'P2',
    owner: 'tuyuan',
    status: '待确认',
    progress: 100,
    src: 'tuyuan',
    srcLabel: '私聊 · 途远',
  },
  {
    id: 't8',
    title: '6月账目核对',
    pr: 'P2',
    owner: 'jiansuan',
    status: '已完成',
    progress: 100,
    src: 'sec',
    srcLabel: '秘书 · 小秘',
  },
  {
    id: 't9',
    title: '老客户回访计划',
    pr: 'P2',
    owner: 'tuyuan',
    status: '进行中',
    progress: 10,
    src: 'sec',
    srcLabel: '秘书 · 小秘',
  },
];

const hireTemplates: HireTemplate[] = [
  {
    name: '运营负责人',
    dept: '运营部',
    desc: '渠道·预算·节奏',
    prompt:
      '你是一名资深运营负责人。负责渠道盘点、预算分配与节奏把控，输出可直接执行的运营方案，并统筹团队成员分工。',
    skills: ['数据报表', '竞品分析', '投放策略'],
    mcps: ['飞书文档', 'Notion'],
  },
  {
    name: '内容主笔',
    dept: '内容部',
    desc: '文案·品牌叙事',
    prompt:
      '你是一名内容主笔。擅长品牌叙事与转化型文案，为官网、公众号与销售物料产出高质量内容。',
    skills: ['公众号文案', 'SEO 优化'],
    mcps: ['飞书文档', '微信公众号'],
  },
  {
    name: '短视频策划',
    dept: '内容部',
    desc: '选题·脚本·分发',
    prompt:
      '你是一名短视频策划。负责选题、脚本与分发节奏，选题要能挂钩获客目标。',
    skills: ['公众号文案'],
    mcps: ['飞书文档'],
  },
  {
    name: '销售顾问',
    dept: '增长与客户',
    desc: '线索·报价·周报',
    prompt:
      '你是一名销售顾问。负责线索跟进、报价与周报，成交卡点要及时上报老板拍板。',
    skills: ['客服话术', '数据报表'],
    mcps: ['企业邮箱', 'Notion'],
  },
  {
    name: '客服专员',
    dept: '增长与客户',
    desc: 'FAQ·话术·响应',
    prompt:
      '你是一名客服专员。基于公司 FAQ 与话术库回复客户，超出权限的承诺必须请老板拍板。',
    skills: ['客服话术'],
    mcps: ['企业邮箱'],
  },
  {
    name: '财务助理',
    dept: '财务行政',
    desc: '记账·对账·报表',
    prompt:
      '你是一名财务助理。负责记账、对账与月度报表，任何异常支出立即标红上报。',
    skills: ['数据报表'],
    mcps: ['Stripe', '飞书文档'],
  },
];

const docs = [
  {
    name: '公司介绍.md',
    desc: '公司定位、业务范围与团队结构',
    meta: '全员可见 · 更新于 6月28日',
    icon: 'description',
  },
  {
    name: '品牌视觉手册.pdf',
    desc: 'Logo、色彩、字体与使用规范',
    meta: '全员可见 · 更新于 6月12日',
    icon: 'palette',
  },
  {
    name: '产品定价表.xlsx',
    desc: '各版本定价、折扣权限与报价口径',
    meta: '全员可见 · 更新于 6月30日',
    icon: 'table',
  },
  {
    name: '客户 FAQ.md',
    desc: '高频问题与标准答复，客服与销售共用',
    meta: '全员可见 · 更新于 6月25日',
    icon: 'quiz',
  },
  {
    name: '常用文案素材库',
    desc: '标语、案例故事、客户评价原文',
    meta: '全员可见 · 更新于 6月20日',
    icon: 'style',
  },
];

const skills = [
  {
    name: '公众号文案',
    desc: '结构化写作框架 + 品牌语气校验',
    users: '2 名员工绑定',
  },
  {
    name: '竞品分析',
    desc: '竞品拆解模板，输出打法对比矩阵',
    users: '2 名员工绑定',
  },
  {
    name: '数据报表',
    desc: '数据清洗、图表生成与周报格式',
    users: '5 名员工绑定',
  },
  { name: 'SEO 优化', desc: '关键词研究与页面优化清单', users: '1 名员工绑定' },
  {
    name: '客服话术',
    desc: '基于 FAQ 的应答策略与升级规则',
    users: '2 名员工绑定',
  },
  {
    name: '任务拆解',
    desc: '把模糊想法拆成可执行任务树',
    users: '1 名员工绑定',
  },
];

const mcps = [
  {
    name: '飞书文档',
    desc: '读写云文档、多维表格',
    status: '已连接',
    users: 6,
  },
  { name: 'Notion', desc: '知识库读写与页面创建', status: '已连接', users: 2 },
  {
    name: '企业邮箱',
    desc: '收发邮件、跟进客户会话',
    status: '已连接',
    users: 3,
  },
  { name: 'Stripe', desc: '订单、账单与收入数据', status: '未连接', users: 0 },
  {
    name: '微信公众号',
    desc: '草稿发布与留言管理',
    status: '未连接',
    users: 0,
  },
];

const materialIcon = (name: string, className?: string) => (
  <span
    aria-hidden="true"
    className={className ? `material-symbol ${className}` : 'material-symbol'}
  >
    {name}
  </span>
);

const avatarColor = (agent: Agent) => `oklch(0.55 0.11 ${agent.hue})`;

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
  if (status === '进行中')
    return { background: '#EEF1FB', color: '#3B5BDB', bar: '#3B5BDB' };
  if (status === '待确认')
    return { background: '#FEF3E2', color: '#B45309', bar: '#D97706' };
  if (status === '卡住')
    return { background: '#FDF1F0', color: '#C0392B', bar: '#DC2626' };
  return { background: '#EEF4EE', color: '#16803C', bar: '#16A34A' };
}

function App() {
  const [view, setView] = useState<View>('home');
  const [chatId, setChatId] = useState('g1');
  const [draft, setDraft] = useState('');
  const [detailId, setDetailId] = useState<string | null>(null);
  const [hireOpen, setHireOpen] = useState(false);
  const [groupOpen, setGroupOpen] = useState(false);
  const [taskFilter, setTaskFilter] = useState<TaskStatus | '全部'>('全部');
  const [libraryTab, setLibraryTab] = useState<LibraryTab>('docs');
  const [agents, setAgents] = useState<Agent[]>(initialAgents);
  const [chats, setChats] = useState<Chat[]>(initialChats);
  const [messagesByChat, setMessagesByChat] = useState(initialMessages);
  const [tasks, setTasks] = useState<Task[]>(initialTasks);
  const [typingName, setTypingName] = useState<string | null>(null);
  const [toast, setToast] = useState<ToastState>({
    visible: false,
    message: '',
  });
  const [hireTpl, setHireTpl] = useState(0);
  const [hireName, setHireName] = useState('');
  const [hireDept, setHireDept] = useState(hireTemplates[0].dept);
  const [hirePrompt, setHirePrompt] = useState(hireTemplates[0].prompt);
  const [hireSkills, setHireSkills] = useState<string[]>(
    hireTemplates[0].skills,
  );
  const [hireMcps, setHireMcps] = useState<string[]>(hireTemplates[0].mcps);
  const [groupName, setGroupName] = useState('');
  const [groupMembers, setGroupMembers] = useState<string[]>([]);
  const [onboardingOpen, setOnboardingOpen] = useState(
    () => !localStorage.getItem('agentpulse_onboarded'),
  );
  const [onboardingStep, setOnboardingStep] = useState(0);
  const [onboardingRoles, setOnboardingRoles] = useState([0, 1, 4]);
  const secretaryReplyIndex = useRef(0);
  const messagesRef = useRef<HTMLDivElement>(null);
  const toastTimer = useRef<number | undefined>(undefined);
  const replyTimerA = useRef<number | undefined>(undefined);
  const replyTimerB = useRef<number | undefined>(undefined);

  useEffect(() => {
    messagesRef.current?.scrollTo({ top: messagesRef.current.scrollHeight });
  }, [chatId, messagesByChat, typingName]);

  useEffect(() => {
    return () => {
      window.clearTimeout(toastTimer.current);
      window.clearTimeout(replyTimerA.current);
      window.clearTimeout(replyTimerB.current);
    };
  }, []);

  const showToast = (message: string) => {
    window.clearTimeout(toastTimer.current);
    setToast({ visible: true, message });
    toastTimer.current = window.setTimeout(
      () => setToast({ visible: false, message: '' }),
      2200,
    );
  };

  const agentById = (id: string) => agents.find((agent) => agent.id === id);
  const activeChat = chats.find((chat) => chat.id === chatId) ?? chats[0];
  const busyCount = agents.filter(
    (agent) => agent.statusKind === 'busy',
  ).length;
  const confirmTasks = tasks.filter((task) => task.status === '待确认');
  const stuckCount = tasks.filter((task) => task.status === '卡住').length;
  const unreadTotal = chats.reduce((count, chat) => count + chat.unread, 0);
  const pendingApprovals = chats.flatMap((chat) =>
    (messagesByChat[chat.id] ?? [])
      .filter(
        (message): message is Extract<Message, { type: 'approval' }> =>
          message.type === 'approval' && message.apStatus === 'pending',
      )
      .map((message) => ({ chat, message })),
  );
  const inboxCount = pendingApprovals.length + confirmTasks.length;

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

    if (last.type === 'text') return `${prefix}${last.text}`;
    if (last.type === 'system') return `${prefix}${last.text}`;
    if (last.type === 'result') return `${prefix}[执行结果] ${last.cardTitle}`;
    if (last.type === 'approval') return `${prefix}[待拍板] ${last.apQ}`;
    if (last.type === 'task') return `${prefix}[任务] ${last.taskTitle}`;
    return prefix;
  };

  const openChat = (id: string) => {
    setView('chat');
    setChatId(id);
    setDraft('');
    setDetailId(null);
    setChats((current) =>
      current.map((chat) => (chat.id === id ? { ...chat, unread: 0 } : chat)),
    );
  };

  const openHire = () => {
    const template = hireTemplates[0];
    setHireTpl(0);
    setHireName('');
    setHireDept(template.dept);
    setHirePrompt(template.prompt);
    setHireSkills(template.skills);
    setHireMcps(template.mcps);
    setHireOpen(true);
  };

  const pickHireTemplate = (index: number) => {
    const template = hireTemplates[index];
    setHireTpl(index);
    setHireDept(template.dept);
    setHirePrompt(template.prompt);
    setHireSkills(template.skills);
    setHireMcps(template.mcps);
  };

  const send = () => {
    const text = draft.trim();
    if (!text || !activeChat) return;

    const targetChat = activeChat;
    const userMessage: Message = {
      id: messageId(),
      from: 'boss',
      type: 'text',
      time: '刚刚',
      text,
    };

    setMessagesByChat((current) => ({
      ...current,
      [targetChat.id]: [...(current[targetChat.id] ?? []), userMessage],
    }));
    setDraft('');

    const replierId =
      targetChat.kind === 'dm' ? targetChat.agentId : targetChat.memberIds[0];
    if (!replierId) return;
    const replier = agentById(replierId);
    if (!replier) return;

    window.clearTimeout(replyTimerA.current);
    window.clearTimeout(replyTimerB.current);
    replyTimerA.current = window.setTimeout(
      () => setTypingName(replier.name),
      500,
    );
    replyTimerB.current = window.setTimeout(() => {
      let replyText = '收到。我排进今天的工作里，有进展直接发你。';
      if (replierId === 'sec') {
        replyText =
          secretaryReplies[
            secretaryReplyIndex.current % secretaryReplies.length
          ];
        secretaryReplyIndex.current += 1;
      } else if (targetChat.kind === 'group') {
        replyText =
          '收到，我来跟进。有结论我会第一时间在群里同步，需要拍板的地方会 @你。';
      }

      const reply: Message = {
        id: messageId(),
        from: replierId,
        type: 'text',
        time: '刚刚',
        text: replyText,
      };
      setMessagesByChat((current) => ({
        ...current,
        [targetChat.id]: [...(current[targetChat.id] ?? []), reply],
      }));
      setTypingName(null);
    }, 1700);
  };

  const decide = (
    targetChatId: string,
    messageIdToUpdate: string,
    choice: 'A' | 'B',
  ) => {
    let chosenLabel = '';
    let followText = '';
    let ownerId = '';
    let taskId: string | null = null;

    setMessagesByChat((current) => {
      const next = { ...current };
      const updatedMessages = (next[targetChatId] ?? []).map((message) => {
        if (message.id !== messageIdToUpdate || message.type !== 'approval')
          return message;
        chosenLabel = choice === 'A' ? message.apOptA : message.apOptB;
        followText = choice === 'A' ? message.followA : message.followB;
        ownerId = message.from;
        taskId = message.taskId;
        return { ...message, apStatus: choice };
      });

      next[targetChatId] = [
        ...updatedMessages,
        {
          id: messageId(),
          from: 'system',
          type: 'system',
          time: '',
          text: `你拍板了：${chosenLabel}`,
        },
        {
          id: messageId(),
          from: ownerId,
          type: 'text',
          time: '刚刚',
          text: followText,
        },
      ];
      return next;
    });

    if (taskId) {
      setTasks((current) =>
        current.map((task) =>
          task.id === taskId ? { ...task, status: '进行中' } : task,
        ),
      );
    }

    if (targetChatId === 'g2') {
      setAgents((current) =>
        current.map((agent) =>
          agent.id === 'mobai'
            ? { ...agent, statusKind: 'busy', statusLabel: '执行中' }
            : agent,
        ),
      );
    }

    showToast('已拍板，团队继续推进');
  };

  const confirmTask = (id: string) => {
    const targetTask = tasks.find((task) => task.id === id);
    const nextTasks = tasks.map((task) =>
      task.id === id ? { ...task, status: '已完成' as const } : task,
    );
    setTasks(nextTasks);

    if (targetTask) {
      setAgents((current) =>
        current.map((agent) => {
          if (agent.id !== targetTask.owner || agent.statusKind !== 'wait')
            return agent;
          const stillBusy = nextTasks.some(
            (task) =>
              task.owner === agent.id &&
              (task.status === '进行中' || task.status === '卡住'),
          );
          return {
            ...agent,
            statusKind: stillBusy ? 'busy' : 'idle',
            statusLabel: stillBusy ? '执行中' : '空闲',
          };
        }),
      );
    }

    showToast('任务已确认结束，归档完成');
  };

  const continueTask = (id: string) => {
    setTasks((current) =>
      current.map((task) =>
        task.id === id
          ? {
              ...task,
              status: '进行中' as const,
              progress: Math.min(task.progress, 85),
            }
          : task,
      ),
    );
    showToast('已让负责人继续推进');
  };

  const openDm = (agentId: string) => {
    const existing = chats.find(
      (chat) => chat.kind === 'dm' && chat.agentId === agentId,
    );
    if (existing) {
      openChat(existing.id);
      return;
    }

    const agent = agentById(agentId);
    if (!agent) return;
    setChats((current) => [
      ...current,
      { id: agentId, kind: 'dm', agentId, unread: 0, time: '刚刚' },
    ]);
    setMessagesByChat((current) => ({
      ...current,
      [agentId]: [
        {
          id: messageId(),
          from: 'system',
          type: 'system',
          time: '',
          text: `你发起了与 ${agent.name} 的私聊`,
        },
      ],
    }));
    setView('chat');
    setChatId(agentId);
    setDetailId(null);
  };

  const submitHire = () => {
    const template = hireTemplates[hireTpl];
    const name = hireName.trim() || template.name;
    const index = agents.length;
    const newAgent: Agent = {
      id: `new${index}`,
      name,
      role: template.name,
      dept: hireDept,
      hue: hueCycle[index % hueCycle.length],
      glyph: glyphCycle[index % glyphCycle.length],
      statusKind: 'idle',
      statusLabel: '空闲',
      joined: '今天入职',
      prompt: hirePrompt || template.prompt,
      skills: hireSkills.length ? hireSkills : template.skills,
      mcps: hireMcps.length ? hireMcps : template.mcps,
    };

    setAgents((current) => [...current, newAgent]);
    setMessagesByChat((current) => ({
      ...current,
      sec: [
        ...(current.sec ?? []),
        {
          id: messageId(),
          from: 'sec',
          type: 'text',
          time: '刚刚',
          text: `新员工「${name}」已办理入职，加入${newAgent.dept}。赋能配置我已按模板绑定好，随时可以给 TA 分配任务。`,
        },
      ],
    }));
    setHireOpen(false);
    setView('staff');
    showToast(`「${name}」已入职 · ${newAgent.dept}`);
  };

  const createGroup = () => {
    if (!groupMembers.length) {
      showToast('至少拉一位员工进群');
      return;
    }
    const name = groupName.trim() || '新的讨论';
    const id = `g${Date.now()}`;
    const names = groupMembers
      .map((memberId) => agentById(memberId)?.name)
      .filter(Boolean)
      .join('、');

    setChats((current) => [
      ...current,
      {
        id,
        kind: 'group',
        name,
        memberIds: groupMembers,
        unread: 0,
        time: '刚刚',
      },
    ]);
    setMessagesByChat((current) => ({
      ...current,
      [id]: [
        {
          id: messageId(),
          from: 'system',
          type: 'system',
          time: '',
          text: `你创建了群聊，拉入了 ${names}`,
        },
      ],
    }));
    setGroupOpen(false);
    setGroupName('');
    setGroupMembers([]);
    setView('chat');
    setChatId(id);
    showToast('群聊已创建，把事情说给他们听吧');
  };

  const finishOnboarding = () => {
    localStorage.setItem('agentpulse_onboarded', '1');
    setOnboardingOpen(false);
    showToast('团队已就位，从给小秘发条消息开始吧');
  };

  const inboxItems = useMemo(
    () => [
      ...pendingApprovals.map(({ chat, message }) => {
        const agent = agentById(message.from);
        return {
          id: message.id,
          avatarBg: agent ? avatarColor(agent) : '#9AA1AD',
          avatar: agent?.glyph ?? '',
          title: message.apQ,
          detail: `${agent?.name ?? '员工'} 在「${chat.kind === 'group' ? chat.name : '私聊'}」里等你拍板 —— ${message.apDesc}`,
          labelA: message.apOptA,
          labelB: message.apOptB,
          srcLabel: '去群里看',
          actA: () => decide(chat.id, message.id, 'A'),
          actB: () => decide(chat.id, message.id, 'B'),
          goSrc: () => openChat(chat.id),
        };
      }),
      ...confirmTasks.map((task) => {
        const agent = agentById(task.owner);
        return {
          id: task.id,
          avatarBg: agent ? avatarColor(agent) : '#9AA1AD',
          avatar: agent?.glyph ?? '',
          title: `「${task.title}」已执行完毕，等你确认`,
          detail: `${agent?.name ?? '员工'} 已交付结果 · 优先级 ${task.pr} · 确认后任务归档`,
          labelA: '确认结束',
          labelB: '继续推进',
          srcLabel: '看交付',
          actA: () => confirmTask(task.id),
          actB: () => continueTask(task.id),
          goSrc: () => openChat(task.src),
        };
      }),
    ],
    [pendingApprovals, confirmTasks, agents],
  );

  const homeTasks = tasks
    .filter((task) => task.status !== '已完成')
    .slice(0, 5);
  const filteredTasks = tasks.filter(
    (task) => taskFilter === '全部' || task.status === taskFilter,
  );
  const taskTabs = (
    ['全部', '进行中', '待确认', '卡住', '已完成'] as const
  ).map((status) => ({
    status,
    count:
      status === '全部'
        ? tasks.length
        : tasks.filter((task) => task.status === status).length,
  }));
  const libraryTabs: Array<{ key: LibraryTab; label: string }> = [
    { key: 'docs', label: '公司资料库' },
    { key: 'skills', label: 'Skills 技能' },
    { key: 'mcp', label: 'MCP 服务' },
  ];

  const depts = ['老板办公室', '运营部', '内容部', '增长与客户', '财务行政']
    .concat(
      Array.from(
        new Set(
          agents
            .map((agent) => agent.dept)
            .filter(
              (dept) =>
                ![
                  '老板办公室',
                  '运营部',
                  '内容部',
                  '增长与客户',
                  '财务行政',
                ].includes(dept),
            ),
        ),
      ),
    )
    .map((dept) => ({
      name: dept,
      members: agents.filter((agent) => agent.dept === dept),
    }))
    .filter((dept) => dept.members.length > 0);

  const currentChatAgent =
    activeChat.kind === 'dm' ? agentById(activeChat.agentId) : null;
  const chatTitle =
    activeChat.kind === 'dm'
      ? currentChatAgent?.id === 'sec'
        ? '小秘 · 秘书'
        : currentChatAgent?.name
      : `# ${activeChat.name}`;
  const relatedTasks = tasks.filter((task) => task.src === activeChat.id);
  const chatMeta =
    activeChat.kind === 'dm'
      ? `${currentChatAgent?.role ?? ''} · ${currentChatAgent?.statusLabel ?? ''}`
      : `${activeChat.memberIds.length} 名成员 · 讨论与执行结果都沉淀在这里`;
  const chatMembers =
    activeChat.kind === 'group' ? activeChat.memberIds : [activeChat.agentId];
  const detailAgent = detailId ? agentById(detailId) : null;

  return (
    <main className="workbench-shell">
      <Sidebar
        view={view}
        unreadTotal={unreadTotal}
        taskAlerts={confirmTasks.length + stuckCount}
        onNavigate={(nextView) => {
          setView(nextView);
          setDetailId(null);
        }}
      />

      {view === 'chat' && (
        <ConversationList
          chats={chats}
          activeChatId={chatId}
          agents={agents}
          lastMessagePreview={lastMessagePreview}
          onOpenChat={openChat}
          onOpenGroupModal={() => setGroupOpen(true)}
        />
      )}

      <section className="main-stage">
        {view === 'home' && (
          <HomeView
            busyCount={busyCount}
            inboxItems={inboxItems}
            agents={agents}
            tasks={homeTasks}
            onOpenSecretary={() => openChat('sec')}
            onOpenHire={openHire}
            onOpenStaff={() => setView('staff')}
            onOpenTasks={() => setView('tasks')}
            onOpenAgent={(id) => setDetailId(id)}
            onOpenChat={openChat}
          />
        )}

        {view === 'chat' && (
          <ChatView
            title={chatTitle ?? '消息'}
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
            onOpenTasks={() => setView('tasks')}
            onOpenAgent={(id) => setDetailId(id)}
            onViewFile={() => showToast('原型演示：此处将打开文档预览')}
            onDecision={(messageIdToUpdate, choice) =>
              decide(activeChat.id, messageIdToUpdate, choice)
            }
          />
        )}

        {view === 'staff' && (
          <StaffView
            depts={depts}
            agents={agents}
            tasks={tasks}
            busyCount={busyCount}
            onOpenHire={openHire}
            onOpenAgent={(id) => setDetailId(id)}
          />
        )}

        {view === 'tasks' && (
          <TasksView
            tasks={filteredTasks}
            tabs={taskTabs}
            activeFilter={taskFilter}
            agents={agents}
            onPickFilter={setTaskFilter}
            onOpenChat={openChat}
            onOpenAgent={(id) => setDetailId(id)}
            onConfirmTask={confirmTask}
            onContinueTask={continueTask}
          />
        )}

        {view === 'lib' && (
          <LibraryView
            tabs={libraryTabs}
            activeTab={libraryTab}
            onPickTab={setLibraryTab}
            onToast={showToast}
          />
        )}
      </section>

      {detailAgent && (
        <AgentDetail
          agent={detailAgent}
          tasks={tasks.filter((task) => task.owner === detailAgent.id)}
          onClose={() => setDetailId(null)}
          onDm={() => openDm(detailAgent.id)}
          onEdit={() =>
            showToast('原型演示：此处编辑 Prompt / Skill / MCP 绑定')
          }
        />
      )}

      {hireOpen && (
        <HireModal
          templateIndex={hireTpl}
          hireName={hireName}
          hireDept={hireDept}
          hirePrompt={hirePrompt}
          hireSkills={hireSkills}
          hireMcps={hireMcps}
          onPickTemplate={pickHireTemplate}
          onNameChange={setHireName}
          onDeptChange={setHireDept}
          onPromptChange={setHirePrompt}
          onToggleSkill={(skill) =>
            setHireSkills((current) =>
              current.includes(skill)
                ? current.filter((item) => item !== skill)
                : [...current, skill],
            )
          }
          onToggleMcp={(mcp) =>
            setHireMcps((current) =>
              current.includes(mcp)
                ? current.filter((item) => item !== mcp)
                : [...current, mcp],
            )
          }
          onClose={() => setHireOpen(false)}
          onSubmit={submitHire}
        />
      )}

      {groupOpen && (
        <GroupModal
          agents={agents}
          groupName={groupName}
          groupMembers={groupMembers}
          onGroupNameChange={setGroupName}
          onToggleMember={(id) =>
            setGroupMembers((current) =>
              current.includes(id)
                ? current.filter((memberId) => memberId !== id)
                : [...current, id],
            )
          }
          onClose={() => setGroupOpen(false)}
          onCreate={createGroup}
        />
      )}

      {onboardingOpen && (
        <OnboardingModal
          step={onboardingStep}
          selectedRoles={onboardingRoles}
          onToggleRole={(index) =>
            setOnboardingRoles((current) =>
              current.includes(index)
                ? current.filter((item) => item !== index)
                : [...current, index],
            )
          }
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

function Sidebar({
  view,
  unreadTotal,
  taskAlerts,
  onNavigate,
}: {
  view: View;
  unreadTotal: number;
  taskAlerts: number;
  onNavigate: (view: View) => void;
}) {
  const items: Array<{
    key: View;
    icon: string;
    label: string;
    badge: number;
  }> = [
    { key: 'home', icon: 'space_dashboard', label: '首页', badge: 0 },
    { key: 'chat', icon: 'forum', label: '消息', badge: unreadTotal },
    { key: 'staff', icon: 'group', label: '员工', badge: 0 },
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
      <div className="owner-avatar" title="老板（你）">
        我
      </div>
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
    (chat) => chat.kind === 'dm' && chat.agentId === 'sec',
  );
  const groupChats = chats.filter((chat) => chat.kind === 'group');
  const dmChats = chats.filter(
    (chat) => chat.kind === 'dm' && chat.agentId !== 'sec',
  );

  const renderChat = (chat: Chat) => {
    const agent = chat.kind === 'dm' ? agentById(chat.agentId) : null;
    const name =
      chat.kind === 'dm'
        ? agent?.id === 'sec'
          ? '小秘 · 秘书'
          : `${agent?.name ?? ''} · ${agent?.role ?? ''}`
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
          {chat.kind === 'group' ? '#' : agent?.glyph}
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
        {groupChats.map(renderChat)}
        <SectionLabel label="私聊" />
        {dmChats.map(renderChat)}
      </div>
    </aside>
  );
}

function SectionLabel({ label }: { label: string }) {
  return <div className="section-label">{label}</div>;
}

function HomeView({
  busyCount,
  inboxItems,
  agents,
  tasks,
  onOpenSecretary,
  onOpenHire,
  onOpenStaff,
  onOpenTasks,
  onOpenAgent,
  onOpenChat,
}: {
  busyCount: number;
  inboxItems: Array<{
    id: string;
    avatarBg: string;
    avatar: string;
    title: string;
    detail: string;
    labelA: string;
    labelB: string;
    srcLabel: string;
    actA: () => void;
    actB: () => void;
    goSrc: () => void;
  }>;
  agents: Agent[];
  tasks: Task[];
  onOpenSecretary: () => void;
  onOpenHire: () => void;
  onOpenStaff: () => void;
  onOpenTasks: () => void;
  onOpenAgent: (id: string) => void;
  onOpenChat: (id: string) => void;
}) {
  return (
    <div className="screen-scroll">
      <div className="screen-inner">
        <header className="page-header">
          <div>
            <h1>下午好，老板</h1>
            <p>
              {companyName} · 7月2日 周四 · {busyCount} 位员工正在执行任务
            </p>
          </div>
          <div className="header-actions">
            <button
              className="button secondary"
              type="button"
              onClick={onOpenSecretary}
            >
              {materialIcon('auto_awesome')}找秘书交代任务
            </button>
            <button
              className="button primary"
              type="button"
              onClick={onOpenHire}
            >
              {materialIcon('person_add')}招聘员工
            </button>
          </div>
        </header>

        <section className="home-grid">
          <article className="card decision-card">
            <CardHeader
              icon="notifications_active"
              iconClassName="warning"
              title="待你拍板"
              badge={String(inboxItems.length)}
              note="决定权始终在你手里"
            />
            {inboxItems.length === 0 ? (
              <EmptyState>全部处理完了，喝口茶吧</EmptyState>
            ) : (
              inboxItems.map((item) => (
                <div className="approval-row" key={item.id}>
                  <div
                    className="mini-avatar"
                    style={{ background: item.avatarBg }}
                  >
                    {item.avatar}
                  </div>
                  <div>
                    <strong>{item.title}</strong>
                    <p>{item.detail}</p>
                    <div className="approval-actions">
                      <button
                        className="small-button primary"
                        type="button"
                        onClick={item.actA}
                      >
                        {item.labelA}
                      </button>
                      <button
                        className="small-button"
                        type="button"
                        onClick={item.actB}
                      >
                        {item.labelB}
                      </button>
                      <button
                        className="link-button"
                        type="button"
                        onClick={item.goSrc}
                      >
                        {item.srcLabel}
                        {materialIcon('arrow_forward')}
                      </button>
                    </div>
                  </div>
                </div>
              ))
            )}
          </article>

          <article className="card pulse-card">
            <CardHeader
              title="员工动态"
              actionLabel="管理团队 →"
              onAction={onOpenStaff}
            />
            {agents.map((agent) => {
              const currentTask = tasks.find(
                (task) => task.owner === agent.id && task.status !== '已完成',
              );
              return (
                <button
                  className="agent-pulse-row"
                  key={agent.id}
                  type="button"
                  onClick={() => onOpenAgent(agent.id)}
                >
                  <div
                    className="mini-avatar"
                    style={{ background: avatarColor(agent) }}
                  >
                    {agent.glyph}
                  </div>
                  <div>
                    <strong>
                      {agent.name} <span>{agent.role}</span>
                    </strong>
                    <p>
                      {currentTask
                        ? `正在做：${currentTask.title}`
                        : agent.id === 'sec'
                          ? '随时听候差遣'
                          : '暂无任务'}
                    </p>
                  </div>
                  <em style={{ color: dotColor(agent.statusKind) }}>
                    <i style={{ background: dotColor(agent.statusKind) }} />
                    {agent.statusLabel}
                  </em>
                </button>
              );
            })}
          </article>
        </section>

        <article className="card task-progress-card">
          <CardHeader
            title="任务进展"
            actionLabel="进入任务中心 →"
            onAction={onOpenTasks}
          />
          {tasks.map((task) => (
            <TaskProgressRow
              key={task.id}
              task={task}
              owner={agents.find((agent) => agent.id === task.owner)}
              onOpenChat={onOpenChat}
            />
          ))}
        </article>
      </div>
    </div>
  );
}

function CardHeader({
  icon,
  iconClassName,
  title,
  badge,
  note,
  actionLabel,
  onAction,
}: {
  icon?: string;
  iconClassName?: string;
  title: string;
  badge?: string;
  note?: string;
  actionLabel?: string;
  onAction?: () => void;
}) {
  return (
    <div className="card-header">
      <div className="card-heading">
        {icon && materialIcon(icon, iconClassName)}
        <strong>{title}</strong>
        {badge && <em>{badge}</em>}
      </div>
      {note && <span>{note}</span>}
      {actionLabel && (
        <button type="button" onClick={onAction}>
          {actionLabel}
        </button>
      )}
    </div>
  );
}

function EmptyState({ children }: { children: string }) {
  return <div className="empty-state">{children}</div>;
}

function TaskProgressRow({
  task,
  owner,
  onOpenChat,
}: {
  task: Task;
  owner?: Agent;
  onOpenChat: (id: string) => void;
}) {
  const priority = priorityStyle(task.pr);
  const status = statusStyle(task.status);

  return (
    <div className="home-task-row">
      <span className="priority-pill" style={priority}>
        {task.pr}
      </span>
      <button type="button" onClick={() => onOpenChat(task.src)}>
        {task.title}
      </button>
      <div className="owner-cell">
        {owner && (
          <div
            className="tiny-avatar"
            style={{ background: avatarColor(owner) }}
          >
            {owner.glyph}
          </div>
        )}
        <span>{owner?.name}</span>
      </div>
      <div className="progress-track">
        <i style={{ width: `${task.progress}%`, background: status.bar }} />
      </div>
      <span
        className="status-pill"
        style={{ background: status.background, color: status.color }}
      >
        {task.status}
      </span>
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
  onOpenAgent,
  onViewFile,
  onDecision,
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
  messagesRef: React.RefObject<HTMLDivElement | null>;
  onDraftChange: (draft: string) => void;
  onSend: () => void;
  onOpenTasks: () => void;
  onOpenAgent: (id: string) => void;
  onViewFile: () => void;
  onDecision: (messageId: string, choice: 'A' | 'B') => void;
}) {
  const agentById = (id: string) => agents.find((agent) => agent.id === id);

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
                {agent.glyph}
              </button>
            );
          })}
        </div>
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
            onViewFile={onViewFile}
            onDecision={onDecision}
            onOpenTasks={onOpenTasks}
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
        <div className="composer-box">
          <input
            value={draft}
            placeholder={placeholder}
            onChange={(event) => onDraftChange(event.target.value)}
            onKeyDown={(event) => {
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
        <p>Enter 发送 · 员工遇到需要拍板的决定会在这里 @你</p>
      </footer>
    </div>
  );
}

function MessageItem({
  message,
  agent,
  onOpenAgent,
  onViewFile,
  onDecision,
  onOpenTasks,
}: {
  message: Message;
  agent?: Agent;
  onOpenAgent: (id: string) => void;
  onViewFile: () => void;
  onDecision: (messageId: string, choice: 'A' | 'B') => void;
  onOpenTasks: () => void;
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
        {isBoss ? '我' : agent?.glyph}
      </button>
      <div className="message-body">
        <div className="message-meta">
          <strong>{isBoss ? '我（老板）' : agent?.name}</strong>
          {!isBoss && <span>{agent?.role}</span>}
          <em>{message.time}</em>
        </div>

        {message.type === 'text' && (
          <p className="message-text">{message.text}</p>
        )}

        {message.type === 'result' && (
          <div className="result-card">
            <div>
              <span>{materialIcon('check_circle')}</span>
              <em>执行结果</em>
            </div>
            <strong>{message.cardTitle}</strong>
            <p>{message.cardDesc}</p>
            <footer>
              {materialIcon('description')}
              <span>{message.cardFile}</span>
              <button type="button" onClick={onViewFile}>
                查看
              </button>
            </footer>
          </div>
        )}

        {message.type === 'approval' && (
          <div
            className={
              message.apStatus === 'pending'
                ? 'approval-card pending'
                : 'approval-card'
            }
          >
            <div>
              {materialIcon('front_hand')}
              <em>需要你拍板</em>
              <span>@老板</span>
            </div>
            <strong>{message.apQ}</strong>
            <p>{message.apDesc}</p>
            {message.apStatus === 'pending' ? (
              <footer>
                <button
                  className="small-button primary"
                  type="button"
                  onClick={() => onDecision(message.id, 'A')}
                >
                  {message.apOptA}
                </button>
                <button
                  className="small-button"
                  type="button"
                  onClick={() => onDecision(message.id, 'B')}
                >
                  {message.apOptB}
                </button>
              </footer>
            ) : (
              <div className="decided-chip">
                {materialIcon('check_circle')}
                已拍板：
                {message.apStatus === 'A' ? message.apOptA : message.apOptB} ·
                团队已收到
              </div>
            )}
          </div>
        )}

        {message.type === 'task' && (
          <div className="task-message-card">
            {materialIcon('assignment_add')}
            <div>
              <strong>创建了任务「{message.taskTitle}」</strong>
              <p>优先级 {message.taskPr} · 已同步到任务中心</p>
            </div>
            <button type="button" onClick={onOpenTasks}>
              查看
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function StaffView({
  depts,
  agents,
  tasks,
  busyCount,
  onOpenHire,
  onOpenAgent,
}: {
  depts: Array<{ name: string; members: Agent[] }>;
  agents: Agent[];
  tasks: Task[];
  busyCount: number;
  onOpenHire: () => void;
  onOpenAgent: (id: string) => void;
}) {
  return (
    <div className="screen-scroll">
      <div className="screen-inner">
        <header className="page-header">
          <div>
            <h1>员工与部门</h1>
            <p>
              {companyName} · {agents.length} 名员工 · {depts.length} 个部门 ·{' '}
              {busyCount} 人执行中
            </p>
          </div>
          <button className="button primary" type="button" onClick={onOpenHire}>
            {materialIcon('person_add')}招聘员工
          </button>
        </header>

        <div className="dept-grid">
          {depts.map((dept) => (
            <article className="card dept-card" key={dept.name}>
              <CardHeader
                title={dept.name}
                note={`${dept.members.length} 人`}
              />
              {dept.members.map((agent) => {
                const currentTask = tasks.find(
                  (task) => task.owner === agent.id && task.status !== '已完成',
                );
                return (
                  <button
                    className="dept-agent"
                    key={agent.id}
                    type="button"
                    onClick={() => onOpenAgent(agent.id)}
                  >
                    <div
                      className="agent-avatar"
                      style={{ background: avatarColor(agent) }}
                    >
                      {agent.glyph}
                    </div>
                    <div>
                      <strong>
                        {agent.name}
                        <span style={{ color: dotColor(agent.statusKind) }}>
                          <i
                            style={{ background: dotColor(agent.statusKind) }}
                          />
                          {agent.statusLabel}
                        </span>
                      </strong>
                      <p>{agent.role}</p>
                      <em>
                        {currentTask
                          ? `进行中：${currentTask.title}`
                          : '待命中'}
                      </em>
                    </div>
                  </button>
                );
              })}
            </article>
          ))}
        </div>
      </div>
    </div>
  );
}

function TasksView({
  tasks,
  tabs,
  activeFilter,
  agents,
  onPickFilter,
  onOpenChat,
  onOpenAgent,
  onConfirmTask,
  onContinueTask,
}: {
  tasks: Task[];
  tabs: Array<{ status: TaskStatus | '全部'; count: number }>;
  activeFilter: TaskStatus | '全部';
  agents: Agent[];
  onPickFilter: (status: TaskStatus | '全部') => void;
  onOpenChat: (id: string) => void;
  onOpenAgent: (id: string) => void;
  onConfirmTask: (id: string) => void;
  onContinueTask: (id: string) => void;
}) {
  return (
    <div className="screen-scroll">
      <div className="screen-inner">
        <header className="page-header compact">
          <div>
            <h1>任务中心</h1>
            <p>每个任务结束前都需要你确认 —— 完成、继续，还是关掉</p>
          </div>
        </header>

        <div className="tabs">
          {tabs.map((tab) => (
            <button
              className={activeFilter === tab.status ? 'tab active' : 'tab'}
              key={tab.status}
              type="button"
              onClick={() => onPickFilter(tab.status)}
            >
              {tab.status} {tab.count}
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
                  <button type="button" onClick={() => onOpenChat(task.src)}>
                    {task.srcLabel}
                  </button>
                </div>
                <div className="owner-cell">
                  {owner && (
                    <button
                      className="tiny-avatar"
                      style={{ background: avatarColor(owner) }}
                      type="button"
                      onClick={() => onOpenAgent(owner.id)}
                    >
                      {owner.glyph}
                    </button>
                  )}
                  <span>{owner?.name}</span>
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
                  {task.status === '待确认' && (
                    <>
                      <button
                        className="small-button primary"
                        type="button"
                        onClick={() => onConfirmTask(task.id)}
                      >
                        确认结束
                      </button>
                      <button
                        className="small-button"
                        type="button"
                        onClick={() => onContinueTask(task.id)}
                      >
                        继续推进
                      </button>
                    </>
                  )}
                  {task.status === '卡住' && (
                    <button
                      className="small-button danger"
                      type="button"
                      onClick={() => onOpenChat(task.src)}
                    >
                      {materialIcon('forum')}去群里处理
                    </button>
                  )}
                  {(task.status === '进行中' || task.status === '已完成') && (
                    <span>—</span>
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
  onToast,
}: {
  tabs: Array<{ key: LibraryTab; label: string }>;
  activeTab: LibraryTab;
  onPickTab: (tab: LibraryTab) => void;
  onToast: (message: string) => void;
}) {
  return (
    <div className="screen-scroll">
      <div className="screen-inner">
        <header className="page-header compact">
          <div>
            <h1>资料库与能力</h1>
            <p>全公司共享 —— 每位员工都能在这里取用资料、技能与工具连接</p>
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
          <div className="docs-grid">
            {docs.map((doc) => (
              <button
                className="doc-card"
                key={doc.name}
                type="button"
                onClick={() => onToast('原型演示：此处将打开资料详情')}
              >
                <div>{materialIcon(doc.icon)}</div>
                <span>
                  <strong>{doc.name}</strong>
                  <p>{doc.desc}</p>
                  <em>
                    {materialIcon('visibility')}
                    {doc.meta}
                  </em>
                </span>
              </button>
            ))}
            <button
              className="upload-card"
              type="button"
              onClick={() => onToast('原型演示：此处上传资料，全员立即可见')}
            >
              {materialIcon('upload_file')}上传资料，全员可见
            </button>
          </div>
        )}

        {activeTab === 'skills' && (
          <article className="card simple-list">
            {skills.map((skill) => (
              <div className="library-row" key={skill.name}>
                <div className="library-icon">{materialIcon('bolt')}</div>
                <div>
                  <strong>{skill.name}</strong>
                  <p>{skill.desc}</p>
                </div>
                <span>{skill.users}</span>
                <button
                  type="button"
                  onClick={() => onToast('原型演示：此处管理技能与员工的绑定')}
                >
                  管理绑定
                </button>
              </div>
            ))}
          </article>
        )}

        {activeTab === 'mcp' && (
          <article className="card simple-list">
            {mcps.map((mcp) => {
              const connected = mcp.status === '已连接';
              return (
                <div className="library-row" key={mcp.name}>
                  <div className="library-icon neutral">
                    {materialIcon('extension')}
                  </div>
                  <div>
                    <strong>{mcp.name}</strong>
                    <p>{mcp.desc}</p>
                  </div>
                  <span className={connected ? 'connected' : ''}>
                    <i />
                    {mcp.status}
                  </span>
                  <button
                    className={connected ? '' : 'primary-lite'}
                    type="button"
                    onClick={() =>
                      onToast(
                        connected
                          ? '原型演示：此处配置 MCP 权限'
                          : '原型演示：此处发起 MCP 连接授权',
                      )
                    }
                  >
                    {connected ? '配置' : '连接'}
                  </button>
                </div>
              );
            })}
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
  onEdit,
}: {
  agent: Agent;
  tasks: Task[];
  onClose: () => void;
  onDm: () => void;
  onEdit: () => void;
}) {
  return (
    <>
      <button
        className="overlay"
        aria-label="关闭员工详情"
        type="button"
        onClick={onClose}
      />
      <aside className="agent-drawer">
        <header>
          <div className="drawer-topline">
            <div
              className="large-avatar"
              style={{ background: avatarColor(agent) }}
            >
              {agent.glyph}
            </div>
            <button type="button" onClick={onClose}>
              {materialIcon('close')}
            </button>
          </div>
          <h2>
            {agent.name}
            <span style={{ color: dotColor(agent.statusKind) }}>
              <i style={{ background: dotColor(agent.statusKind) }} />
              {agent.statusLabel}
            </span>
          </h2>
          <p>
            {agent.role} · {agent.dept} · {agent.joined}
          </p>
          <div className="drawer-actions">
            <button className="button primary" type="button" onClick={onDm}>
              {materialIcon('chat')}私聊 TA
            </button>
            <button className="button secondary" type="button" onClick={onDm}>
              {materialIcon('assignment_add')}交代任务
            </button>
          </div>
        </header>
        <div className="drawer-scroll">
          <DrawerSection title="手里的任务">
            {tasks.length === 0 ? (
              <EmptyState>暂无任务，处于待命状态</EmptyState>
            ) : (
              tasks.map((task) => {
                const priority = priorityStyle(task.pr);
                const status = statusStyle(task.status);
                return (
                  <div className="drawer-task" key={task.id}>
                    <div>
                      <span className="priority-pill" style={priority}>
                        {task.pr}
                      </span>
                      <strong>{task.title}</strong>
                      <em style={{ color: status.color }}>{task.status}</em>
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
                      <span>{task.progress}%</span>
                    </div>
                  </div>
                );
              })
            )}
          </DrawerSection>
          <DrawerSection title="系统 Prompt">
            <div className="prompt-box">{agent.prompt}</div>
          </DrawerSection>
          <DrawerSection title="Skills 技能">
            <ChipList items={agent.skills} icon="bolt" />
          </DrawerSection>
          <DrawerSection title="MCP 工具连接">
            <ChipList items={agent.mcps} icon="extension" muted />
          </DrawerSection>
          <button className="edit-config" type="button" onClick={onEdit}>
            {materialIcon('tune')}编辑赋能配置
          </button>
        </div>
      </aside>
    </>
  );
}

function DrawerSection({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="drawer-section">
      <h3>{title}</h3>
      {children}
    </section>
  );
}

function ChipList({
  items,
  icon,
  muted = false,
}: {
  items: string[];
  icon: string;
  muted?: boolean;
}) {
  return (
    <div className="chip-list">
      {items.map((item) => (
        <span className={muted ? 'chip muted' : 'chip'} key={item}>
          {materialIcon(icon)}
          {item}
        </span>
      ))}
    </div>
  );
}

function HireModal({
  templateIndex,
  hireName,
  hireDept,
  hirePrompt,
  hireSkills,
  hireMcps,
  onPickTemplate,
  onNameChange,
  onDeptChange,
  onPromptChange,
  onToggleSkill,
  onToggleMcp,
  onClose,
  onSubmit,
}: {
  templateIndex: number;
  hireName: string;
  hireDept: string;
  hirePrompt: string;
  hireSkills: string[];
  hireMcps: string[];
  onPickTemplate: (index: number) => void;
  onNameChange: (name: string) => void;
  onDeptChange: (dept: string) => void;
  onPromptChange: (prompt: string) => void;
  onToggleSkill: (skill: string) => void;
  onToggleMcp: (mcp: string) => void;
  onClose: () => void;
  onSubmit: () => void;
}) {
  return (
    <Modal onClose={onClose} width={620}>
      <header className="modal-header">
        <h2>招聘新员工</h2>
        <p>选一个角色模板，或者从零开始 —— 入职即可分配任务</p>
      </header>
      <div className="modal-body">
        <FieldLabel>角色模板</FieldLabel>
        <div className="chip-row">
          {hireTemplates.map((template, index) => (
            <button
              className={
                templateIndex === index
                  ? 'selector-chip active'
                  : 'selector-chip'
              }
              key={template.name}
              type="button"
              onClick={() => onPickTemplate(index)}
            >
              {template.name}
            </button>
          ))}
        </div>

        <div className="form-grid">
          <label>
            <FieldLabel>名字</FieldLabel>
            <input
              value={hireName}
              placeholder="给 TA 起个名字"
              onChange={(event) => onNameChange(event.target.value)}
            />
          </label>
          <div>
            <FieldLabel>所属部门</FieldLabel>
            <div className="chip-row compact">
              {['运营部', '内容部', '增长与客户', '财务行政'].map((dept) => (
                <button
                  className={
                    hireDept === dept ? 'selector-chip active' : 'selector-chip'
                  }
                  key={dept}
                  type="button"
                  onClick={() => onDeptChange(dept)}
                >
                  {dept}
                </button>
              ))}
            </div>
          </div>
        </div>

        <FieldLabel>系统 Prompt（TA 的岗位职责）</FieldLabel>
        <textarea
          rows={4}
          value={hirePrompt}
          onChange={(event) => onPromptChange(event.target.value)}
        />

        <FieldLabel>绑定 Skills</FieldLabel>
        <div className="chip-row">
          {allSkills.map((skill) => (
            <button
              className={
                hireSkills.includes(skill)
                  ? 'selector-chip active'
                  : 'selector-chip'
              }
              key={skill}
              type="button"
              onClick={() => onToggleSkill(skill)}
            >
              {materialIcon('bolt')}
              {skill}
            </button>
          ))}
        </div>

        <FieldLabel>连接 MCP 工具</FieldLabel>
        <div className="chip-row">
          {allMcps.map((mcp) => (
            <button
              className={
                hireMcps.includes(mcp)
                  ? 'selector-chip active'
                  : 'selector-chip'
              }
              key={mcp}
              type="button"
              onClick={() => onToggleMcp(mcp)}
            >
              {materialIcon('extension')}
              {mcp}
            </button>
          ))}
        </div>

        <div className="modal-actions">
          <button className="button secondary" type="button" onClick={onClose}>
            取消
          </button>
          <button className="button primary" type="button" onClick={onSubmit}>
            完成招聘，立即入职
          </button>
        </div>
      </div>
    </Modal>
  );
}

function GroupModal({
  agents,
  groupName,
  groupMembers,
  onGroupNameChange,
  onToggleMember,
  onClose,
  onCreate,
}: {
  agents: Agent[];
  groupName: string;
  groupMembers: string[];
  onGroupNameChange: (name: string) => void;
  onToggleMember: (id: string) => void;
  onClose: () => void;
  onCreate: () => void;
}) {
  return (
    <Modal onClose={onClose} width={520}>
      <header className="modal-header">
        <h2>拉个群，把事说清楚</h2>
        <p>把相关员工拉进来 —— 讨论、提问、执行结果都沉淀在这个群里</p>
      </header>
      <div className="modal-body">
        <FieldLabel>这件事叫什么</FieldLabel>
        <input
          value={groupName}
          placeholder="例如：客户回访计划"
          onChange={(event) => onGroupNameChange(event.target.value)}
        />
        <FieldLabel>把谁拉进来</FieldLabel>
        <div className="member-picker">
          {agents
            .filter((agent) => agent.id !== 'sec')
            .map((agent) => {
              const picked = groupMembers.includes(agent.id);
              return (
                <button
                  className={picked ? 'member-option active' : 'member-option'}
                  key={agent.id}
                  type="button"
                  onClick={() => onToggleMember(agent.id)}
                >
                  <div
                    className="tiny-avatar"
                    style={{ background: avatarColor(agent) }}
                  >
                    {agent.glyph}
                  </div>
                  <span>
                    <strong>{agent.name}</strong>
                    <em>{agent.role}</em>
                  </span>
                  {materialIcon('check_circle')}
                </button>
              );
            })}
        </div>
        <div className="modal-actions">
          <button className="button secondary" type="button" onClick={onClose}>
            取消
          </button>
          <button className="button primary" type="button" onClick={onCreate}>
            建群并开始讨论
          </button>
        </div>
      </div>
    </Modal>
  );
}

function OnboardingModal({
  step,
  selectedRoles,
  onToggleRole,
  onNext,
  onFinish,
}: {
  step: number;
  selectedRoles: number[];
  onToggleRole: (index: number) => void;
  onNext: () => void;
  onFinish: () => void;
}) {
  return (
    <>
      <div className="overlay blur" />
      <section className="onboarding-modal">
        {step === 0 && (
          <div className="onboarding-content centered">
            <div className="onboarding-logo">✦</div>
            <h2>欢迎，老板</h2>
            <p>
              这不是又一个聊天机器人。
              <br />
              这里是你的公司 —— 一个人当老板，AI 员工替你干活。
            </p>
            <div className="onboarding-feature-grid">
              <OnboardingFeature
                icon="person_add"
                title="招聘 AI 员工"
                text="绑定 Prompt、Skill、MCP 工具，按部门组队"
              />
              <OnboardingFeature
                icon="forum"
                title="拉群协作"
                text="有事拉个群，讨论和执行结果全部沉淀在群里"
              />
              <OnboardingFeature
                icon="front_hand"
                title="你只负责拍板"
                text="关键决定员工会 @你，任务结束由你确认"
              />
            </div>
          </div>
        )}

        {step === 1 && (
          <div className="onboarding-content">
            <h2>招聘你的首批员工</h2>
            <p>先挑几个角色模板，入职后随时可以调整赋能配置</p>
            <div className="role-grid">
              {hireTemplates.map((template, index) => {
                const selected = selectedRoles.includes(index);
                return (
                  <button
                    className={selected ? 'role-option active' : 'role-option'}
                    key={template.name}
                    type="button"
                    onClick={() => onToggleRole(index)}
                  >
                    <div
                      style={{
                        background: `oklch(0.55 0.11 ${hueCycle[index % hueCycle.length]})`,
                      }}
                    >
                      {glyphCycle[index % glyphCycle.length]}
                    </div>
                    <span>
                      <strong>{template.name}</strong>
                      <em>{template.desc}</em>
                    </span>
                    {materialIcon('check_circle')}
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="onboarding-content centered">
            <div className="onboarding-logo big">✦</div>
            <h2>这是小秘，你的秘书</h2>
            <p>
              有任何想法、任务、还没想清楚的事，直接丢给小秘。
              <br />
              TA 会帮你创建任务、招聘员工、拉群分配 —— 你只需要在关键时刻拍板。
            </p>
            <div className="try-chip">
              {materialIcon('chat')}试试对小秘说：「我想做一次老客户回访」
            </div>
          </div>
        )}

        <footer className="onboarding-footer">
          <div className="step-dots">
            {[0, 1, 2].map((item) => (
              <i className={step >= item ? 'active' : ''} key={item} />
            ))}
          </div>
          <span />
          <button className="skip-button" type="button" onClick={onFinish}>
            跳过引导
          </button>
          {step < 2 ? (
            <button className="button primary" type="button" onClick={onNext}>
              下一步
            </button>
          ) : (
            <button className="button primary" type="button" onClick={onFinish}>
              进入工作台
            </button>
          )}
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
  children,
  onClose,
  width,
}: {
  children: React.ReactNode;
  onClose: () => void;
  width: number;
}) {
  return (
    <>
      <button
        className="overlay"
        aria-label="关闭弹窗"
        type="button"
        onClick={onClose}
      />
      <section className="modal" style={{ width }}>
        {children}
      </section>
    </>
  );
}

function FieldLabel({ children }: { children: string }) {
  return <div className="field-label">{children}</div>;
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
