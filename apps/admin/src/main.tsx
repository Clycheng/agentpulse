import { StrictMode, useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  BadgeCheck,
  Boxes,
  BrainCircuit,
  CheckCircle2,
  Database,
  Layers3,
  Search,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';
import './styles.css';

type TalentCategory = {
  id: string;
  name: string;
  description: string;
  sort_order: number;
};

type TalentTemplate = {
  id: string;
  name: string;
  category_id: string;
  category: string;
  department: string;
  description: string;
  prompt: string;
  skills: string[];
  mcps: string[];
  publisher: string;
  version: string;
  status: string;
};

type CatalogResponse = {
  categories: TalentCategory[];
  templates: TalentTemplate[];
  note: string;
};

const apiBaseUrl =
  import.meta.env.VITE_AGENTPULSE_API_URL ?? 'http://127.0.0.1:8000/api';

const fallbackCatalog: CatalogResponse = {
  note: '本地 API 未启动时显示内置预览数据。',
  categories: [
    {
      id: 'ops-growth',
      name: '运营增长',
      description: '渠道、投放、数据分析、增长节奏与经营复盘类岗位',
      sort_order: 10,
    },
    {
      id: 'content-production',
      name: '内容创作',
      description: '选题、文案、脚本、品牌叙事与内容分发类岗位',
      sort_order: 20,
    },
    {
      id: 'sales-customer',
      name: '销售客户',
      description: '线索跟进、客户响应、报价、FAQ 与成交支持类岗位',
      sort_order: 30,
    },
  ],
  templates: [
    {
      id: 'ops-lead',
      name: '运营负责人',
      category_id: 'ops-growth',
      category: '运营增长',
      department: '运营部',
      description: '渠道、预算、节奏',
      prompt:
        '你是一名资深运营负责人。负责渠道盘点、预算分配与节奏把控，输出可直接执行的运营方案，并统筹团队成员分工。',
      skills: ['数据报表', '竞品分析', '投放策略'],
      mcps: ['飞书文档', 'Notion'],
      publisher: 'AgentPulse 官方',
      version: 'v0.1.0',
      status: 'published',
    },
    {
      id: 'content-writer',
      name: '内容主笔',
      category_id: 'content-production',
      category: '内容创作',
      department: '内容部',
      description: '文案、品牌叙事',
      prompt:
        '你是一名内容主笔。擅长品牌叙事与转化型文案，为官网、公众号与销售物料产出高质量内容。',
      skills: ['公众号文案', 'SEO 优化'],
      mcps: ['飞书文档', '微信公众号'],
      publisher: 'AgentPulse 官方',
      version: 'v0.1.0',
      status: 'published',
    },
  ],
};

function App() {
  const [catalog, setCatalog] = useState<CatalogResponse>(fallbackCatalog);
  const [activeCategoryId, setActiveCategoryId] = useState('all');
  const [query, setQuery] = useState('');
  const [selectedTemplateId, setSelectedTemplateId] = useState(
    fallbackCatalog.templates[0]?.id ?? '',
  );
  const [sourceLabel, setSourceLabel] = useState('preview');

  useEffect(() => {
    fetch(`${apiBaseUrl}/admin/talent-market`)
      .then((response) => {
        if (!response.ok) throw new Error('API unavailable');
        return response.json() as Promise<CatalogResponse>;
      })
      .then((payload) => {
        setCatalog(payload);
        setSelectedTemplateId(payload.templates[0]?.id ?? '');
        setSourceLabel('api');
      })
      .catch(() => {
        setCatalog(fallbackCatalog);
        setSourceLabel('preview');
      });
  }, []);

  const categories = useMemo(
    () =>
      [...catalog.categories].sort(
        (left, right) => left.sort_order - right.sort_order,
      ),
    [catalog.categories],
  );
  const filteredTemplates = catalog.templates.filter((template) => {
    const matchesCategory =
      activeCategoryId === 'all' || template.category_id === activeCategoryId;
    const keyword = query.trim().toLowerCase();
    if (!keyword) return matchesCategory;
    return (
      matchesCategory &&
      [
        template.name,
        template.category,
        template.department,
        template.description,
        template.prompt,
        ...template.skills,
        ...template.mcps,
      ]
        .join(' ')
        .toLowerCase()
        .includes(keyword)
    );
  });
  const selectedTemplate =
    catalog.templates.find((template) => template.id === selectedTemplateId) ??
    filteredTemplates[0] ??
    catalog.templates[0];

  return (
    <main className="admin-shell">
      <aside className="sidebar">
        <div className="brand">
          <Sparkles aria-hidden="true" />
          <span>AgentPulse</span>
        </div>
        <nav aria-label="后台导航">
          <button className="active" type="button">
            <Boxes aria-hidden="true" />
            人才市场
          </button>
          <button type="button">
            <Layers3 aria-hidden="true" />
            分类管理
          </button>
          <button type="button">
            <BrainCircuit aria-hidden="true" />
            Skills
          </button>
          <button type="button">
            <ShieldCheck aria-hidden="true" />
            MCP 权限
          </button>
        </nav>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <p>官方后台</p>
            <h1>人才市场模板管理</h1>
          </div>
          <span className={sourceLabel === 'api' ? 'source live' : 'source'}>
            <Database aria-hidden="true" />
            {sourceLabel === 'api' ? 'API 数据' : '预览数据'}
          </span>
        </header>

        <section className="metrics" aria-label="人才市场指标">
          <Metric icon={Layers3} label="岗位分类" value={categories.length} />
          <Metric
            icon={Boxes}
            label="员工模板"
            value={catalog.templates.length}
          />
          <Metric
            icon={BrainCircuit}
            label="Skills"
            value={
              new Set(catalog.templates.flatMap((item) => item.skills)).size
            }
          />
          <Metric
            icon={ShieldCheck}
            label="MCP 工具"
            value={new Set(catalog.templates.flatMap((item) => item.mcps)).size}
          />
        </section>

        <section className="manager">
          <aside className="category-panel">
            <div className="panel-title">
              <strong>官方类目</strong>
              <span>由后台统一创建</span>
            </div>
            <button
              className={activeCategoryId === 'all' ? 'active' : ''}
              type="button"
              onClick={() => setActiveCategoryId('all')}
            >
              <span>全部模板</span>
              <em>{catalog.templates.length}</em>
            </button>
            {categories.map((category) => {
              const count = catalog.templates.filter(
                (template) => template.category_id === category.id,
              ).length;
              return (
                <button
                  className={activeCategoryId === category.id ? 'active' : ''}
                  key={category.id}
                  type="button"
                  onClick={() => setActiveCategoryId(category.id)}
                >
                  <span>{category.name}</span>
                  <em>{count}</em>
                </button>
              );
            })}
            <p>{catalog.note}</p>
          </aside>

          <div className="template-panel">
            <div className="toolbar">
              <label>
                <Search aria-hidden="true" />
                <input
                  value={query}
                  placeholder="搜索模板、Prompt、技能或 MCP"
                  onChange={(event) => setQuery(event.target.value)}
                />
              </label>
              <button type="button">新建模板</button>
            </div>

            <div className="template-table">
              <div className="table-head">
                <span>模板</span>
                <span>分类</span>
                <span>默认部门</span>
                <span>状态</span>
                <span>版本</span>
              </div>
              {filteredTemplates.map((template) => (
                <button
                  className={
                    selectedTemplate?.id === template.id
                      ? 'table-row active'
                      : 'table-row'
                  }
                  key={template.id}
                  type="button"
                  onClick={() => setSelectedTemplateId(template.id)}
                >
                  <span>
                    <strong>{template.name}</strong>
                    <em>{template.description}</em>
                  </span>
                  <span>{template.category}</span>
                  <span>{template.department}</span>
                  <span>
                    <i />
                    已上架
                  </span>
                  <span>{template.version}</span>
                </button>
              ))}
              {filteredTemplates.length === 0 && (
                <div className="empty">没有匹配的人才模板</div>
              )}
            </div>
          </div>

          <aside className="detail-panel">
            {selectedTemplate ? (
              <>
                <div className="detail-head">
                  <div>
                    <BadgeCheck aria-hidden="true" />
                  </div>
                  <span>
                    <strong>{selectedTemplate.name}</strong>
                    <em>{selectedTemplate.publisher}</em>
                  </span>
                </div>
                <dl>
                  <div>
                    <dt>模板 ID</dt>
                    <dd>{selectedTemplate.id}</dd>
                  </div>
                  <div>
                    <dt>岗位分类</dt>
                    <dd>{selectedTemplate.category}</dd>
                  </div>
                  <div>
                    <dt>默认部门</dt>
                    <dd>{selectedTemplate.department}</dd>
                  </div>
                  <div>
                    <dt>发布版本</dt>
                    <dd>{selectedTemplate.version}</dd>
                  </div>
                </dl>
                <section>
                  <h2>工作职责 Prompt</h2>
                  <p className="prompt">{selectedTemplate.prompt}</p>
                </section>
                <section>
                  <h2>Skills</h2>
                  <div className="chips">
                    {selectedTemplate.skills.map((skill) => (
                      <span key={skill}>{skill}</span>
                    ))}
                  </div>
                </section>
                <section>
                  <h2>MCP 权限</h2>
                  <div className="chips muted">
                    {selectedTemplate.mcps.map((mcp) => (
                      <span key={mcp}>{mcp}</span>
                    ))}
                  </div>
                </section>
              </>
            ) : (
              <div className="empty">请选择一个模板</div>
            )}
          </aside>
        </section>
      </section>
    </main>
  );
}

function Metric({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof Boxes;
  label: string;
  value: number;
}) {
  return (
    <article>
      <Icon aria-hidden="true" />
      <span>
        <strong>{value}</strong>
        <em>{label}</em>
      </span>
      <CheckCircle2 aria-hidden="true" />
    </article>
  );
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
