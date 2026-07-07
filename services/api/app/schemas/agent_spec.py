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


class AgentCapabilityOut(BaseModel):
    """Serialized agent_capability row."""

    id: str
    agent_id: str
    capability_key: str
    skill_refs: list[str]
    toolset_refs: list[str]
    mcp_refs: list[str]
    required_credentials: list[str]
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
