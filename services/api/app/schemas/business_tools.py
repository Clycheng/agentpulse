from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class BusinessToolOut(BaseModel):
    capability_key: str
    tool_name: str
    description: str
    risk_gate: str
    required_credentials: list[str] = Field(default_factory=list)
    provider_implemented: bool


class BusinessActionOut(BaseModel):
    id: str
    workspace_id: str
    run_id: str | None
    task_id: str | None
    conversation_id: str | None
    agent_id: str | None
    capability_key: str
    tool_name: str
    preview: dict[str, Any] = Field(default_factory=dict)
    status: str
    approval_id: str | None
    provider: str
    external_id: str
    result: dict[str, Any] = Field(default_factory=dict)
    error: str
    attempt_no: int
    created_at: str
    updated_at: str
    completed_at: str | None


class BusinessToolPolicyOut(BaseModel):
    id: str
    workspace_id: str
    agent_id: str
    tool_name: str
    active: bool
    created_by: str
    created_at: str
    updated_at: str
    revoked_at: str | None
