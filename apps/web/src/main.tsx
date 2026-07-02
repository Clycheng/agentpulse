import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import {
  ArrowRight,
  Bot,
  BriefcaseBusiness,
  CheckCircle2,
  Database,
  FileText,
  LockKeyhole,
  Sparkles,
  Users,
} from 'lucide-react';
import './styles.css';

const employeeCards = [
  {
    icon: BriefcaseBusiness,
    name: '老板助理',
    description: '把经营目标拆成可执行任务，提醒你哪些节点需要亲自决定。',
  },
  {
    icon: FileText,
    name: '内容策划',
    description: '围绕账号定位、选题库和热点，生成一周内容计划与初稿。',
  },
  {
    icon: Users,
    name: '运营执行',
    description: '整理发布清单、互动回复和复盘指标，减少重复运营工作。',
  },
];

const workflowSteps = [
  '创建“一人自媒体公司”工作区',
  '选择 AI 员工并连接品牌资料、选题库和常用工具',
  '输入业务目标，系统拆解任务并分配给不同员工',
  '在发布、发送、改重要文件前停下来等你确认',
];

function App() {
  return (
    <main>
      <header className="site-header">
        <a className="brand" href="/">
          <Sparkles aria-hidden="true" />
          <span>AgentPulse</span>
        </a>
        <nav aria-label="Primary navigation">
          <a href="#product">产品</a>
          <a href="#scenario">场景</a>
          <a href="#access">早期访问</a>
        </nav>
      </header>

      <section className="hero" id="product">
        <div className="hero-content">
          <p className="eyebrow">一人自媒体公司 AI 工作台</p>
          <h1>AgentPulse</h1>
          <p className="hero-copy">
            像搭建一家小公司一样，创建 AI 员工、分配任务、连接资料和工具，
            让内容策划、运营执行与复盘协作起来。
          </p>
          <div className="hero-actions">
            <a className="primary-action" href="#access">
              申请早期访问
              <ArrowRight aria-hidden="true" />
            </a>
            <a className="secondary-action" href="#scenario">
              查看 MVP 场景
            </a>
          </div>
        </div>

        <div className="workspace-preview" aria-label="AgentPulse 工作台预览">
          <div className="preview-toolbar">
            <span>小红书内容工作室</span>
            <strong>本周计划</strong>
          </div>
          <div className="preview-grid">
            <div className="preview-company">
              <p>公司资料</p>
              <h2>个人知识 IP</h2>
              <span>品牌语气 / 选题库 / 素材文件</span>
            </div>
            <div className="preview-task">
              <p>当前任务</p>
              <h2>生成 7 天内容计划</h2>
              <span>老板助理 → 内容策划 → 运营执行</span>
            </div>
            <div className="preview-confirm">
              <LockKeyhole aria-hidden="true" />
              <div>
                <strong>发布前确认</strong>
                <span>外部发布、发送邮件、改重要文件都需要用户确认。</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="section" id="scenario">
        <div className="section-heading">
          <p className="eyebrow">MVP 使用场景</p>
          <h2>先服务一个人经营内容业务，而不是做泛化平台。</h2>
        </div>

        <div className="feature-grid">
          {employeeCards.map(({ icon: Icon, name, description }) => (
            <article key={name}>
              <Icon aria-hidden="true" />
              <h3>{name}</h3>
              <p>{description}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="workflow-band">
        <div>
          <p className="eyebrow">工作方式</p>
          <h2>从目标到任务流，再到可控交付。</h2>
        </div>
        <ol className="workflow-list">
          {workflowSteps.map((step) => (
            <li key={step}>
              <CheckCircle2 aria-hidden="true" />
              <span>{step}</span>
            </li>
          ))}
        </ol>
      </section>

      <section className="section resource-section">
        <div className="section-heading">
          <p className="eyebrow">资料与工具</p>
          <h2>让 AI 员工围绕真实业务资料工作。</h2>
        </div>
        <div className="resource-grid">
          <article>
            <Database aria-hidden="true" />
            <h3>公司记忆库</h3>
            <p>沉淀账号定位、用户画像、内容风格、历史复盘和常用素材。</p>
          </article>
          <article>
            <Bot aria-hidden="true" />
            <h3>多智能体协作</h3>
            <p>每个 AI 员工负责清晰边界，任务过程和产出都能追踪。</p>
          </article>
          <article>
            <LockKeyhole aria-hidden="true" />
            <h3>确认节点</h3>
            <p>涉及外部发布、发送、重要文件修改时，必须先获得用户确认。</p>
          </article>
        </div>
      </section>

      <section className="contact-band" id="access">
        <div>
          <p className="eyebrow">Early access</p>
          <h2>正在打磨一人自媒体公司的第一版工作台。</h2>
        </div>
        <a className="primary-action dark" href="mailto:hello@agentpulse.dev">
          hello@agentpulse.dev
        </a>
      </section>
    </main>
  );
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
