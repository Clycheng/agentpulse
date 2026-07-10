"""Pydantic schemas for external channel management (TD-09-T2)."""

from typing import Literal

from pydantic import BaseModel, Field

ChannelType = Literal["wechat", "email", "web_widget", "generic_webhook"]


class ChannelOut(BaseModel):
    id: str
    workspace_id: str
    channel_type: ChannelType
    name: str
    token: str
    config: dict = Field(default_factory=dict)
    target_agent_id: str | None = None
    target_conversation_id: str | None = None
    active: bool
    created_at: str
    webhook_url: str


class ChannelStats(BaseModel):
    messages_today: int
    active_external_users: int


class ChannelDetailOut(ChannelOut):
    stats: ChannelStats


class CreateChannelRequest(BaseModel):
    channel_type: ChannelType
    name: str = Field(min_length=1, max_length=80)
    config: dict = Field(default_factory=dict)
    target_agent_id: str | None = None
    target_conversation_id: str | None = None


class UpdateChannelRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    config: dict | None = None
    target_agent_id: str | None = None
    target_conversation_id: str | None = None
    active: bool | None = None
