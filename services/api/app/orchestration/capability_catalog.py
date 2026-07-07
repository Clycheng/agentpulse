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
        toolsets=("web", "vision"),
        risk_gate="approval",
    ),
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
