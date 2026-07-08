# TD-07：业务岗位能力目录（Business Capability Catalog）

- 关联：[TD-05](TD-05-capability-catalog.md)（已有技术岗能力种子）、[DATA-MODEL §6.3](DATA-MODEL-AND-API.md)（catalog 唯一真相源）、[agent-model-and-capabilities.md](agent-model-and-capabilities.md)（能力体系说明）
- 执行会话：**否**（纯代码常量扩展 + 单测，不碰 Hermes）。

## 背景与目标

TD-05 只有技术岗能力（write_code / git_push / deploy_*）。一个真实公司的一人公司/小团队有客服、运营、数据、HR、财务等需求，这些岗位的 agent 缺能力配方，用户招募时无法自动完成配置。

本 TD 目标：**把常见业务岗位的能力 bundle 也加进 capability_catalog**，让用户说"我要一个数据分析师"能像"我要一个前端工程师"一样自动配置完整。

---

## 新增能力条目（`capability_catalog.py` 扩展）

以下所有新增条目遵循现有格式：`capability_key → {skills, toolsets, mcp, required_credentials, risk_gate, description}`。

### 客户服务类

| capability_key | toolsets | mcp | creds | risk_gate | 说明 |
|---|---|---|---|---|---|
| `customer_service` | `clarify, memory, web` | — | — | `auto` | 意图识别 + 知识检索 + FAQ 回复 |
| `ticket_management` | `clarify, memory` | ticket_system | TICKET_API_KEY | `auto` | 创建/查询/更新工单 |
| `refund_processing` | `clarify` | order_system | ORDER_API_KEY | `approval` | 退款/换货（超阈值强制审批） |
| `customer_data_lookup` | `memory` | crm_system | CRM_API_KEY | `auto` | 查询客户订单/档案 |

### 内容与运营类

| capability_key | toolsets | mcp | creds | risk_gate | 说明 |
|---|---|---|---|---|---|
| `content_writing` | `file, web` | — | — | `auto` | 各类文案/文章/报告撰写 |
| `image_creation` | `image_gen, vision` | — | — | `auto` | 生成配图、设计素材 |
| `social_content` | `web, image_gen, vision` | — | — | `approval` | 内容生产✅；发布平台无官方 API → approval 让人点发布 |
| `email_drafting` | `file` | — | — | `auto` | 起草邮件/信函 |
| `email_sending` | — | email_service | EMAIL_API_KEY | `approval` | 发送邮件（代发需审批）|
| `seo_content` | `web, terminal` | — | — | `auto` | SEO 优化建议 + 关键词分析 |
| `ad_analysis` | `web` | ad_platform | AD_API_KEY | `auto` | 广告数据分析/报告（不含出价操作） |
| `ad_bidding` | — | ad_platform | AD_API_KEY | `approval` | 广告出价/预算修改（花钱需审批） |

### 数据与分析类

| capability_key | toolsets | mcp | creds | risk_gate | 说明 |
|---|---|---|---|---|---|
| `data_query` | `terminal, code_execution` | database | DB_URL | `auto` | SQL 查询/数据提取 |
| `data_analysis` | `terminal, code_execution, file` | — | — | `auto` | 数据分析/统计/可视化 |
| `report_generation` | `terminal, code_execution, file` | — | — | `auto` | 自动生成数据报告/看板截图 |
| `web_scraping` | `web, terminal` | — | — | `auto` | 网页数据抓取（合规范围内） |

### 人力资源类

| capability_key | toolsets | mcp | creds | risk_gate | 说明 |
|---|---|---|---|---|---|
| `resume_screening` | `file, web` | — | — | `auto` | 简历筛选/打分/对比 |
| `jd_generation` | `file` | — | — | `auto` | 岗位描述起草 |
| `interview_prep` | `file` | — | — | `auto` | 面试题生成/评分标准 |
| `onboarding_docs` | `file, web` | — | — | `auto` | 入职材料/培训内容生成 |
| `hr_data_analysis` | `terminal, code_execution` | hris_system | HRIS_API_KEY | `auto` | HR 数据分析（人员流动/薪酬分布）|
| `payroll_processing` | — | hris_system | HRIS_API_KEY | `approval` | 薪酬核算辅助（提交需人工审批） |

### 法务与合规类

| capability_key | toolsets | mcp | creds | risk_gate | 说明 |
|---|---|---|---|---|---|
| `contract_review` | `file, web` | — | — | `auto` | 合同条款风险识别/对比/标注 |
| `contract_drafting` | `file` | — | — | `auto` | 合同/协议起草（辅助，非法律意见）|
| `compliance_check` | `file, web` | — | — | `auto` | 合规性检查/政策匹配 |

### 财务类

| capability_key | toolsets | mcp | creds | risk_gate | 说明 |
|---|---|---|---|---|---|
| `expense_analysis` | `terminal, code_execution, file` | accounting_system | ACCOUNTING_API_KEY | `auto` | 费用分析/异常预警/报表 |
| `invoice_processing` | `file, vision` | accounting_system | ACCOUNTING_API_KEY | `auto` | 发票识别/录入辅助 |
| `financial_reporting` | `terminal, code_execution, file` | accounting_system | ACCOUNTING_API_KEY | `auto` | 财务报表生成/分析 |
| `payment_execution` | — | payment_system | PAYMENT_API_KEY | `prohibited_auto` | 付款操作永远禁止自动（花钱不可逆）|

### 项目管理类

| capability_key | toolsets | mcp | creds | risk_gate | 说明 |
|---|---|---|---|---|---|
| `task_delegation` | `delegation, todo` | — | — | `auto` | 任务拆解/分配/跟进（AgentPulse 原生） |
| `meeting_scheduling` | — | calendar_service | CALENDAR_API_KEY | `auto` | 日历查询/会议邀请 |
| `project_reporting` | `file` | — | — | `auto` | 项目周报/进度报告生成 |

---

## 岗位能力 Bundle（常见工种预配组合）

worker AI 按此表给用户"一键选角色"，不用逐条勾选能力：

```python
ROLE_BUNDLES = {
    "客服专员":   ["customer_service", "ticket_management", "customer_data_lookup"],
    "售后专员":   ["customer_service", "ticket_management", "refund_processing", "customer_data_lookup"],
    "内容运营":   ["content_writing", "image_creation", "social_content", "seo_content"],
    "广告投放":   ["ad_analysis", "ad_bidding", "data_analysis"],
    "数据分析师": ["data_query", "data_analysis", "report_generation"],
    "HR 专员":    ["resume_screening", "jd_generation", "interview_prep", "onboarding_docs"],
    "财务助理":   ["expense_analysis", "invoice_processing", "financial_reporting"],
    "法务助理":   ["contract_review", "contract_drafting", "compliance_check"],
    "项目经理":   ["task_delegation", "meeting_scheduling", "project_reporting", "report_generation"],
    # 技术岗（已有）
    "前端工程师": ["write_code", "run_tests", "git_push", "deploy_preview"],
    "后端工程师": ["write_code", "run_tests", "git_push", "deploy_preview", "deploy_prod"],
    "DevOps":     ["write_code", "git_push", "deploy_preview", "deploy_prod"],
}
```

---

## 数据模型

无新建表。`capability_catalog.py` 扩展即可。DATA-MODEL §6.3 同步更新（本文件是真相源，代码是实现）。

---

## Tech-Tasks

### TD-07-T1：扩展 capability_catalog.py
- 改动点：`orchestration/capability_catalog.py` 加入上表全部条目；新增 `ROLE_BUNDLES` 常量。
- 验收：单测覆盖——每个 capability_key 有 description / risk_gate 合法值；所有 ROLE_BUNDLES 里的 key 在 catalog 里能找到；未知 key 仍正确拒绝 400。
- 依赖：TD-05-T1（已完成）。需 agentpulse 会话：否。估算：1 天。

### TD-07-T2：创建员工 UI 接入 ROLE_BUNDLES
- 改动点：桌面端"创建员工"弹窗加「按职位选」标签页——选择角色后自动勾选对应能力清单（可手动增减）；`POST /api/agents` 接受 `role_bundle_key` 参数作为 capability_keys 预填入口。
- 验收：用户选"客服专员"后能力清单自动填好；仍可手动增减；走完供给流程员工就绪。
- 依赖：TD-07-T1 + TD-04-T5（API + 前端已有）。需 agentpulse 会话：否。估算：0.5 天。

## Definition of Done
- 用户说"我要一个数据分析师"，能力清单自动匹配并展示；招募完毕的员工有对应的 MCP/工具权限，能真正完成数据分析类任务。
- DATA-MODEL §6.3 与 capability_catalog.py 保持同步。
