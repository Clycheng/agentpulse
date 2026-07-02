import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import {
  Bell,
  Bot,
  CheckCircle2,
  ClipboardList,
  Database,
  FileText,
  Home,
  LockKeyhole,
  Settings,
} from 'lucide-react';
import './styles.css';

const agents = [
  ['老板助理', '拆解目标', '正在把本周增长目标拆成 4 个任务'],
  ['内容策划', '生成计划', '待整理小红书 7 天内容选题'],
  ['运营执行', '准备发布', '等待用户确认后再对外发布'],
];

const tasks = [
  ['内容计划', '小红书一周选题表', '内容策划', '进行中'],
  ['资料连接', '读取品牌语气与历史爆款', '老板助理', '已完成'],
  ['发布确认', '周三笔记发布到外部平台', '运营执行', '待确认'],
];

function App() {
  return (
    <main className="desktop-shell">
      <aside className="sidebar">
        <div className="brand-mark">IP</div>
        <button aria-label="公司">
          <Home aria-hidden="true" />
        </button>
        <button aria-label="AI 员工">
          <Bot aria-hidden="true" />
        </button>
        <button aria-label="任务">
          <ClipboardList aria-hidden="true" />
        </button>
        <button aria-label="资料库">
          <Database aria-hidden="true" />
        </button>
        <button aria-label="通知">
          <Bell aria-hidden="true" />
        </button>
        <button aria-label="设置">
          <Settings aria-hidden="true" />
        </button>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <p>小红书内容工作室</p>
            <h1>一人自媒体公司工作台</h1>
          </div>
          <button className="confirm-button">
            <LockKeyhole aria-hidden="true" />
            发布前确认
          </button>
        </header>

        <section className="dashboard-grid" aria-label="今日工作概览">
          <article className="summary">
            <span>AI 员工</span>
            <strong>3</strong>
            <p>老板助理、内容策划、运营执行已就绪。</p>
          </article>
          <article className="summary">
            <span>开放任务</span>
            <strong>6</strong>
            <p>2 个进行中，1 个等待用户确认。</p>
          </article>
          <article className="summary">
            <span>资料连接</span>
            <strong>4</strong>
            <p>品牌语气、选题库、素材文件、发布清单。</p>
          </article>
        </section>

        <section className="workbench-grid">
          <article className="panel agent-panel">
            <div className="panel-heading">
              <h2>AI 员工</h2>
              <span>角色边界清晰</span>
            </div>
            {agents.map(([name, state, detail]) => (
              <div className="agent-row" key={name}>
                <Bot aria-hidden="true" />
                <div>
                  <strong>{name}</strong>
                  <p>{detail}</p>
                </div>
                <span>{state}</span>
              </div>
            ))}
          </article>

          <article className="panel">
            <div className="panel-heading">
              <h2>任务流</h2>
              <span>从目标到交付</span>
            </div>
            {tasks.map(([name, detail, owner, status]) => (
              <div className="task-row" key={name}>
                <CheckCircle2 aria-hidden="true" />
                <div>
                  <strong>{name}</strong>
                  <p>{detail}</p>
                </div>
                <div className="task-meta">
                  <span>{owner}</span>
                  <em>{status}</em>
                </div>
              </div>
            ))}
          </article>

          <article className="panel content-plan">
            <div className="panel-heading">
              <h2>内容计划</h2>
              <span>Markdown / 表格 / 本地文件</span>
            </div>
            <div className="plan-card">
              <FileText aria-hidden="true" />
              <div>
                <strong>本周主题：AI 工具如何帮个人创作者省时间</strong>
                <p>待生成：7 条笔记标题、正文大纲、封面关键词和发布节奏。</p>
              </div>
            </div>
          </article>

          <article className="panel approval-panel">
            <LockKeyhole aria-hidden="true" />
            <div>
              <h2>确认节点</h2>
              <p>
                对外发布、发送邮件、修改重要文件之前，工作台会停下来等待用户确认。
              </p>
            </div>
          </article>
        </section>
      </section>
    </main>
  );
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
