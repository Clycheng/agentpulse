from typing import Any, Literal

from pydantic import BaseModel, Field


class LlmChatAgent(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=80)
    role: str = Field(default="", max_length=120)
    department: str = Field(default="", max_length=120)
    prompt: str = Field(min_length=1, max_length=12000)
    skills: list[str] = Field(default_factory=list, max_length=20)


class LlmChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=12000)
    name: str | None = Field(default=None, max_length=80)


class LlmTaskContext(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=160)
    status: str = Field(default="", max_length=40)
    priority: str = Field(default="", max_length=20)
    progress: int = Field(default=0, ge=0, le=100)
    owner_name: str | None = Field(default=None, max_length=80)
    description: str = Field(default="", max_length=2000)


class LlmChatRequest(BaseModel):
    company_name: str = Field(default="一人公司", max_length=120)
    conversation_title: str = Field(default="", max_length=160)
    agent: LlmChatAgent
    messages: list[LlmChatMessage] = Field(min_length=1, max_length=24)
    related_tasks: list[LlmTaskContext] = Field(default_factory=list, max_length=12)


class LlmChatResponse(BaseModel):
    reply: str
    provider: str = "deepseek"
    model: str
    usage: dict[str, Any] | None = None
