"""Pydantic schemas for consensus brief API."""

from typing import Literal

from pydantic import BaseModel, Field


class WorkItem(BaseModel):
    key: str = Field(min_length=1, max_length=80, pattern=r"^[a-z][a-z0-9_-]*$")
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=2000)
    owner_agent_id: str
    expected_output: str = Field(min_length=1, max_length=2000)
    output_type: str = Field(min_length=1, max_length=80)
    depends_on_keys: list[str] = Field(default_factory=list, max_length=5)
    final_delivery: bool = False


class BriefOut(BaseModel):
    """Brief output schema."""
    id: str
    workspace_id: str
    discussion_conversation_id: str
    status: Literal["draft", "confirmed", "rejected", "superseded"]
    goal: str = Field(max_length=500)
    scope: str = Field(default="", max_length=500)
    constraints: str = Field(default="", max_length=500)
    success_criteria: str = Field(default="", max_length=500)
    owner_agent_id: str | None = None
    participant_agent_ids: list[str] = Field(default_factory=list)
    work_items: list[WorkItem] = Field(default_factory=list)
    created_by_agent_id: str
    supersedes_brief_id: str | None = None
    derived_from_brief_id: str | None = None
    created_at: str
    confirmed_at: str | None = None
    confirmed_by_user_id: str | None = None


class CreateBriefRequest(BaseModel):
    """Create brief request schema."""
    discussion_conversation_id: str
    goal: str = Field(min_length=1, max_length=500)
    scope: str = Field(default="", max_length=500)
    constraints: str = Field(default="", max_length=500)
    success_criteria: str = Field(default="", max_length=500)
    owner_agent_id: str | None = None
    participant_agent_ids: list[str] = Field(default_factory=list, max_length=12)
    work_items: list[WorkItem] = Field(min_length=3, max_length=6)
    created_by_agent_id: str
    supersedes_brief_id: str | None = None
    derived_from_brief_id: str | None = None


class ConfirmBriefRequest(BaseModel):
    """Confirm brief request schema (owner action)."""
    # Empty body - user ID comes from auth token
    pass


class RejectBriefRequest(BaseModel):
    """Reject brief request schema (owner action)."""
    # Empty body - user ID comes from auth token
    pass
