"""Capability catalog — system-level static asset.

Maps capability keys (what a user asks for, e.g. "write_code") to concrete
bundles (skills + toolsets + MCP + credentials + risk_gate).

Security rule: risk_gate is hardcoded here and CANNOT be relaxed by any caller
(including LLM-drafted role_spec). resolve_bundle takes the strictest gate.

See TD-05 and DATA-MODEL §6.3 for design details.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CapabilityDef:
    """Definition of a capability — what it needs and how risky it is."""

    key: str
    description: str
    skills: tuple[str, ...] = ()
    toolsets: tuple[str, ...] = ()
    mcp: tuple[str, ...] = ()
    required_credentials: tuple[str, ...] = ()
    risk_gate: str = "auto"  # auto | approval | prohibited_auto


# Risk gate severity ordering — higher = stricter
_RISK_SEVERITY = {
    "auto": 0,
    "approval": 1,
    "prohibited_auto": 2,
}

# Seed catalog (v1) — must match DATA-MODEL §6.3 exactly.
# toolset names verified via Hermes V1 (hermes tools list):
#   terminal, file, web, code_execution, vision, image_gen, etc.
CATALOG: dict[str, CapabilityDef] = {
    "write_code": CapabilityDef(
        key="write_code",
        description="编写、修改代码文件",
        toolsets=("terminal", "file"),
        risk_gate="auto",
    ),
    "run_tests": CapabilityDef(
        key="run_tests",
        description="运行测试套件并收集结果",
        toolsets=("terminal",),
        risk_gate="auto",
    ),
    "git_push": CapabilityDef(
        key="git_push",
        description="推送代码到远程仓库",
        toolsets=("terminal",),
        mcp=("github",),
        required_credentials=("GITHUB_TOKEN",),
        risk_gate="approval",
    ),
    "deploy_preview": CapabilityDef(
        key="deploy_preview",
        description="部署到预览/测试环境",
        toolsets=("terminal",),
        required_credentials=("PLATFORM_TOKEN",),
        risk_gate="auto",
    ),
    "deploy_prod": CapabilityDef(
        key="deploy_prod",
        description="部署到生产环境",
        toolsets=("terminal",),
        required_credentials=("PLATFORM_TOKEN",),
        risk_gate="approval",
    ),
    "domain_register": CapabilityDef(
        key="domain_register",
        description="注册/续费域名（涉及付费+不可逆，必须人工）",
        required_credentials=("REGISTRAR_KEY", "PAYMENT_METHOD"),
        risk_gate="prohibited_auto",
    ),
    "seo_audit": CapabilityDef(
        key="seo_audit",
        description="执行 SEO 审计（Lighthouse + 网页抓取）",
        toolsets=("terminal", "web"),
        risk_gate="auto",
    ),
    "social_content": CapabilityDef(
        key="social_content",
        description="生成社交媒体内容（发布环节须人工确认）",
        toolsets=("web", "image_gen", "vision"),
        risk_gate="approval",
    ),
    # --- Business capabilities (TD-07) ---
    # Customer service
    "customer_service": CapabilityDef(
        key="customer_service",
        description="意图识别 + 知识检索 + FAQ 回复",
        toolsets=("clarify", "memory", "web"),
        risk_gate="auto",
    ),
    "ticket_management": CapabilityDef(
        key="ticket_management",
        description="创建/查询/更新工单",
        toolsets=("clarify", "memory"),
        mcp=("ticket_system",),
        required_credentials=("TICKET_API_KEY",),
        risk_gate="auto",
    ),
    "refund_processing": CapabilityDef(
        key="refund_processing",
        description="退款/换货（超阈值强制审批）",
        toolsets=("clarify",),
        mcp=("order_system",),
        required_credentials=("ORDER_API_KEY",),
        risk_gate="approval",
    ),
    "customer_data_lookup": CapabilityDef(
        key="customer_data_lookup",
        description="查询客户订单/档案",
        toolsets=("memory",),
        mcp=("crm_system",),
        required_credentials=("CRM_API_KEY",),
        risk_gate="auto",
    ),
    # Content & operations
    "content_writing": CapabilityDef(
        key="content_writing",
        description="各类文案/文章/报告撰写",
        toolsets=("file", "web"),
        risk_gate="auto",
    ),
    "image_creation": CapabilityDef(
        key="image_creation",
        description="生成配图、设计素材",
        toolsets=("image_gen", "vision"),
        risk_gate="auto",
    ),
    "email_drafting": CapabilityDef(
        key="email_drafting",
        description="起草邮件/信函",
        toolsets=("file",),
        risk_gate="auto",
    ),
    "email_sending": CapabilityDef(
        key="email_sending",
        description="发送邮件（代发需审批）",
        mcp=("email_service",),
        required_credentials=("EMAIL_API_KEY",),
        risk_gate="approval",
    ),
    "seo_content": CapabilityDef(
        key="seo_content",
        description="SEO 优化建议 + 关键词分析",
        toolsets=("web", "terminal"),
        risk_gate="auto",
    ),
    "ad_analysis": CapabilityDef(
        key="ad_analysis",
        description="广告数据分析/报告（不含出价操作）",
        toolsets=("web",),
        mcp=("ad_platform",),
        required_credentials=("AD_API_KEY",),
        risk_gate="auto",
    ),
    "ad_bidding": CapabilityDef(
        key="ad_bidding",
        description="广告出价/预算修改（花钱需审批）",
        mcp=("ad_platform",),
        required_credentials=("AD_API_KEY",),
        risk_gate="approval",
    ),
    # Data & analytics
    "data_query": CapabilityDef(
        key="data_query",
        description="SQL 查询/数据提取",
        toolsets=("terminal", "code_execution"),
        mcp=("database",),
        required_credentials=("DB_URL",),
        risk_gate="auto",
    ),
    "data_analysis": CapabilityDef(
        key="data_analysis",
        description="数据分析/统计/可视化",
        toolsets=("terminal", "code_execution", "file"),
        risk_gate="auto",
    ),
    "report_generation": CapabilityDef(
        key="report_generation",
        description="自动生成数据报告/看板截图",
        toolsets=("terminal", "code_execution", "file"),
        risk_gate="auto",
    ),
    "web_scraping": CapabilityDef(
        key="web_scraping",
        description="网页数据抓取（合规范围内）",
        toolsets=("web", "terminal"),
        risk_gate="auto",
    ),
    "browser_automation": CapabilityDef(
        key="browser_automation",
        description="真实浏览器自动化——打开网页、点击、填表、登录站点",
        toolsets=("browser", "web"),
        risk_gate="approval",
    ),
    "computer_use": CapabilityDef(
        key="computer_use",
        description="直接操作电脑桌面——控制鼠标键盘、操作任意本地 App（Hermes cua-driver）",
        toolsets=("computer_use",),
        risk_gate="approval",
    ),
    # Human resources
    "resume_screening": CapabilityDef(
        key="resume_screening",
        description="简历筛选/打分/对比",
        toolsets=("file", "web"),
        risk_gate="auto",
    ),
    "jd_generation": CapabilityDef(
        key="jd_generation",
        description="岗位描述起草",
        toolsets=("file",),
        risk_gate="auto",
    ),
    "interview_prep": CapabilityDef(
        key="interview_prep",
        description="面试题生成/评分标准",
        toolsets=("file",),
        risk_gate="auto",
    ),
    "onboarding_docs": CapabilityDef(
        key="onboarding_docs",
        description="入职材料/培训内容生成",
        toolsets=("file", "web"),
        risk_gate="auto",
    ),
    "hr_data_analysis": CapabilityDef(
        key="hr_data_analysis",
        description="HR 数据分析（人员流动/薪酬分布）",
        toolsets=("terminal", "code_execution"),
        mcp=("hris_system",),
        required_credentials=("HRIS_API_KEY",),
        risk_gate="auto",
    ),
    "payroll_processing": CapabilityDef(
        key="payroll_processing",
        description="薪酬核算辅助（提交需人工审批）",
        mcp=("hris_system",),
        required_credentials=("HRIS_API_KEY",),
        risk_gate="approval",
    ),
    # Legal & compliance
    "contract_review": CapabilityDef(
        key="contract_review",
        description="合同条款风险识别/对比/标注",
        toolsets=("file", "web"),
        risk_gate="auto",
    ),
    "contract_drafting": CapabilityDef(
        key="contract_drafting",
        description="合同/协议起草（辅助，非法律意见）",
        toolsets=("file",),
        risk_gate="auto",
    ),
    "compliance_check": CapabilityDef(
        key="compliance_check",
        description="合规性检查/政策匹配",
        toolsets=("file", "web"),
        risk_gate="auto",
    ),
    # Finance
    "expense_analysis": CapabilityDef(
        key="expense_analysis",
        description="费用分析/异常预警/报表",
        toolsets=("terminal", "code_execution", "file"),
        mcp=("accounting_system",),
        required_credentials=("ACCOUNTING_API_KEY",),
        risk_gate="auto",
    ),
    "invoice_processing": CapabilityDef(
        key="invoice_processing",
        description="发票识别/录入辅助",
        toolsets=("file", "vision"),
        mcp=("accounting_system",),
        required_credentials=("ACCOUNTING_API_KEY",),
        risk_gate="auto",
    ),
    "financial_reporting": CapabilityDef(
        key="financial_reporting",
        description="财务报表生成/分析",
        toolsets=("terminal", "code_execution", "file"),
        mcp=("accounting_system",),
        required_credentials=("ACCOUNTING_API_KEY",),
        risk_gate="auto",
    ),
    "payment_execution": CapabilityDef(
        key="payment_execution",
        description="付款操作永远禁止自动（花钱不可逆）",
        mcp=("payment_system",),
        required_credentials=("PAYMENT_API_KEY",),
        risk_gate="prohibited_auto",
    ),
    # Project management
    "task_delegation": CapabilityDef(
        key="task_delegation",
        description="任务拆解/分配/跟进（AgentPulse 原生）",
        toolsets=("delegation", "todo"),
        risk_gate="auto",
    ),
    "meeting_scheduling": CapabilityDef(
        key="meeting_scheduling",
        description="日历查询/会议邀请",
        mcp=("calendar_service",),
        required_credentials=("CALENDAR_API_KEY",),
        risk_gate="auto",
    ),
    "project_reporting": CapabilityDef(
        key="project_reporting",
        description="项目周报/进度报告生成",
        toolsets=("file",),
        risk_gate="auto",
    ),
}


# Role bundles — preset capability combinations for common job types (TD-07).
# The desktop "hire by role" flow uses these so users pick a role instead of
# ticking capabilities one by one. Every key here MUST exist in CATALOG
# (guarded by tests). risk_gate is still resolved per-capability at provision
# time — a bundle never relaxes a gate.
ROLE_BUNDLES: dict[str, tuple[str, ...]] = {
    # Role names below match the official Talent Market templates
    # (app/services/templates.py AGENT_TEMPLATES) so recruit_from_template can
    # look capability_keys up by role name — every official template needs a
    # matching entry here or a Talent Market hire gets zero capabilities.
    "运营负责人": ("ad_analysis", "ad_bidding", "data_analysis", "report_generation"),
    "内容主笔": ("content_writing", "seo_content"),
    "短视频策划": ("content_writing", "image_creation", "social_content"),
    "销售顾问": ("customer_service", "customer_data_lookup", "report_generation"),
    "客服专员": ("customer_service", "ticket_management", "customer_data_lookup"),
    "售后专员": (
        "customer_service",
        "ticket_management",
        "refund_processing",
        "customer_data_lookup",
    ),
    "内容运营": ("content_writing", "image_creation", "social_content", "seo_content"),
    "广告投放": ("ad_analysis", "ad_bidding", "data_analysis"),
    "数据分析师": ("data_query", "data_analysis", "report_generation"),
    "HR 专员": ("resume_screening", "jd_generation", "interview_prep", "onboarding_docs"),
    "财务助理": ("expense_analysis", "invoice_processing", "financial_reporting"),
    "法务助理": ("contract_review", "contract_drafting", "compliance_check"),
    "项目经理": (
        "task_delegation",
        "meeting_scheduling",
        "project_reporting",
        "report_generation",
    ),
    "前端工程师": ("write_code", "run_tests", "git_push", "deploy_preview"),
    "后端工程师": (
        "write_code",
        "run_tests",
        "git_push",
        "deploy_preview",
        "deploy_prod",
    ),
    "DevOps": ("write_code", "git_push", "deploy_preview", "deploy_prod"),
}


def get_capability(key: str) -> CapabilityDef:
    """Get a capability definition by key.

    Args:
        key: Capability key (e.g. "write_code")

    Returns:
        CapabilityDef for the key

    Raises:
        ValueError: If key is not in catalog
    """
    cap = CATALOG.get(key)
    if cap is None:
        raise ValueError(f"Unknown capability key: {key}")
    return cap


def validate_capability_keys(keys: list[str]) -> None:
    """Validate that all keys exist in the catalog.

    Args:
        keys: List of capability keys

    Raises:
        ValueError: If any key is unknown, with all invalid keys listed
    """
    invalid = [k for k in keys if k not in CATALOG]
    if invalid:
        raise ValueError(f"Unknown capability keys: {invalid}")


def _strictest_risk(gates: list[str]) -> str:
    """Return the strictest risk gate from a list."""
    if not gates:
        return "auto"
    return max(gates, key=lambda g: _RISK_SEVERITY.get(g, 0))


def resolve_bundle(keys: list[str]) -> dict:
    """Merge multiple capabilities into a single bundle.

    Combines skills, toolsets, MCP servers, and credentials (deduplicated).
    risk_gate takes the strictest value (prohibited_auto > approval > auto).

    Args:
        keys: List of capability keys to merge

    Returns:
        dict with keys: skills, toolsets, mcp, required_credentials, risk_gate

    Raises:
        ValueError: If any key is unknown
    """
    validate_capability_keys(keys)

    skills: set[str] = set()
    toolsets: set[str] = set()
    mcp: set[str] = set()
    creds: set[str] = set()
    risk_gates: list[str] = []

    for key in keys:
        cap = CATALOG[key]
        skills.update(cap.skills)
        toolsets.update(cap.toolsets)
        mcp.update(cap.mcp)
        creds.update(cap.required_credentials)
        risk_gates.append(cap.risk_gate)

    return {
        "skills": sorted(skills),
        "toolsets": sorted(toolsets),
        "mcp": sorted(mcp),
        "required_credentials": sorted(creds),
        "risk_gate": _strictest_risk(risk_gates),
    }


def split_by_credentials(keys: list[str]) -> tuple[list[str], list[str]]:
    """Split capability keys into (immediately-usable, needs-credentials).

    provision() is all-or-nothing: a single credential_missing capability
    blocks the *whole* agent_spec at 'blocked_on_credentials' with no real
    Hermes profile at all — a role bundle that mixes a credential-free
    capability (e.g. content_writing) with a credential-needing one (e.g.
    ad_bidding, which needs AD_API_KEY nobody has configured on a fresh
    install) would otherwise leave the employee with *zero* working
    capabilities instead of the ones that could have worked immediately.

    Callers should provision only the first list, then register the second
    list's capabilities afterward via the profile-already-exists fast path
    (runtime.upgrade.execute_upgrade) so they show up as "待补凭证" instead
    of silently blocking everything else.
    """
    validate_capability_keys(keys)
    ready = [k for k in keys if not CATALOG[k].required_credentials]
    pending = [k for k in keys if CATALOG[k].required_credentials]
    return ready, pending


def list_role_bundles() -> list[str]:
    """Return the available role-bundle names."""
    return list(ROLE_BUNDLES.keys())


def get_role_bundle(role_name: str) -> list[str]:
    """Return the capability keys for a role bundle.

    Raises:
        ValueError: If the role name is unknown.
    """
    bundle = ROLE_BUNDLES.get(role_name)
    if bundle is None:
        raise ValueError(f"Unknown role bundle: {role_name}")
    return list(bundle)
