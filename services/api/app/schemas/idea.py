"""Pydantic schemas for the idea center API (TD-08)."""

from typing import Literal

from pydantic import BaseModel, Field

IdeaCategory = Literal["improvement", "opportunity", "risk", "learning"]
IdeaStatus = Literal["new", "reviewed", "accepted", "dismissed", "converted"]


class IdeaOut(BaseModel):
    """Idea output schema — ideas row + joined source agent name."""

    id: str
    workspace_id: str
    source_agent_id: str
    source_agent_name: str
    title: str = Field(max_length=120)
    description: str = Field(default="", max_length=1000)
    category: IdeaCategory
    status: IdeaStatus
    converted_brief_id: str | None = None
    created_at: str
    reviewed_at: str | None = None


class CreateIdeaRequest(BaseModel):
    """Create an idea (produced by an agent's idle reflection in TD-08-T2)."""

    source_agent_id: str
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=1000)
    category: IdeaCategory


class ReviewIdeaRequest(BaseModel):
    """Owner reviews an idea: accept or dismiss."""

    action: Literal["accept", "dismiss"]


class IdleThinkingRequest(BaseModel):
    """Toggle / tune an employee's idle-thinking behavior."""

    enabled: bool | None = None
    interval_hours: int | None = Field(default=None, ge=1, le=168)


class ConvertIdeaResponse(BaseModel):
    conversation_id: str
    idea: IdeaOut


class IdleThinkingSettings(BaseModel):
    """Focused view of an employee's idle-thinking configuration."""

    agent_id: str
    idle_thinking_enabled: bool
    idle_think_interval_hours: int
    last_idle_think_at: str | None = None
