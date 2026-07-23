"""DTO schemas for agent_specs and agent_capabilities (TD-04-T1).

See DATA-MODEL §6.1/6.2 for field definitions.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class RoleSpecIn(BaseModel):
    """Input for creating an agent with a role spec."""

    role_name: str = Field(..., max_length=80, description="如'前端工程师'")
    source_request: str = Field("", max_length=2000, description="用户原始 NL 需求")
    responsibilities: list[str] = Field(
        default_factory=list, max_length=12, description="职责数组，≤12 条"
    )
    capability_keys: list[str] = Field(
        default_factory=list, description="能力 key 列表，来自 catalog"
    )
    role_bundle_key: str | None = Field(
        default=None,
        description="预配角色名（如'数据分析师'）；有值时其能力清单会并入 capability_keys",
    )


class ResolvedBundleOut(BaseModel):
    """The merged effect of a set of capabilities."""

    skills: list[str] = Field(default_factory=list)
    toolsets: list[str] = Field(default_factory=list)
    mcp: list[str] = Field(default_factory=list)
    required_credentials: list[str] = Field(default_factory=list)
    risk_gate: str


class RoleBundleOut(BaseModel):
    """A preset role and the capabilities it grants (for 'hire by role' UI)."""

    role_name: str
    capability_keys: list[str]
    resolved: ResolvedBundleOut


class AgentCapabilityOut(BaseModel):
    """Serialized agent_capability row."""

    id: str
    agent_id: str
    capability_key: str
    skill_refs: list[str]
    toolset_refs: list[str]
    mcp_refs: list[str]
    required_credentials: list[str]
    credential_status: dict[str, bool] = Field(default_factory=dict)
    risk_gate: str
    status: str
    created_at: str
    updated_at: str


class AgentSpecOut(BaseModel):
    """Serialized agent_spec row."""

    id: str
    agent_id: str
    workspace_id: str
    role_name: str
    source_request: str
    responsibilities: list[str]
    hermes_profile: str | None = None
    status: str
    capabilities: list[AgentCapabilityOut] = Field(default_factory=list)
    created_at: str
    updated_at: str


class CapabilityCatalogEntryOut(BaseModel):
    """One entry from the full capability catalog (for the owner-initiated
    '+ grant capability' picker — ADR 0008 §5)."""

    key: str
    description: str
    risk_gate: str
    required_credentials: list[str] = Field(default_factory=list)
    business_tool: str | None = None


class GrantCapabilityRequest(BaseModel):
    """Owner-initiated capability grant (ADR 0008 §5) — no pending approval
    needed, the owner is directly deciding, not approving a suspended run."""

    capability_key: str = Field(..., min_length=1, max_length=80)


class CredentialRequest(BaseModel):
    """Input for providing a credential value."""

    credential_name: str = Field(..., min_length=1, max_length=120)
    value: str = Field(..., min_length=1, max_length=10000)


class DraftTeamRequest(BaseModel):
    """A free-text org/team description to compile into role drafts."""

    description: str = Field(..., min_length=1, max_length=6000)


class TeamMemberDraft(BaseModel):
    """One drafted (not yet created) team member — editable before
    POST /agents/create-team actually provisions it."""

    name: str = Field(..., min_length=1, max_length=24)
    role: str = Field(..., min_length=1, max_length=24)
    department: str = Field("", max_length=40)
    description: str = Field("", max_length=400)
    responsibilities: list[str] = Field(default_factory=list, max_length=12)
    capability_keys: list[str] = Field(default_factory=list)


class DraftTeamResponse(BaseModel):
    members: list[TeamMemberDraft]


class CreateTeamRequest(BaseModel):
    """The (owner-reviewed, possibly edited) member list to actually create."""

    members: list[TeamMemberDraft] = Field(..., min_length=1, max_length=20)
    group_name: str | None = Field(default=None, max_length=80)


class CreateTeamMemberOut(BaseModel):
    id: str
    name: str
    role: str
    department: str


class CreateTeamResponse(BaseModel):
    agents: list[CreateTeamMemberOut]
    conversation_id: str | None = None
