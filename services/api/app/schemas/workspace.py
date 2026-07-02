from typing import Literal

from pydantic import BaseModel, Field


class DepartmentOut(BaseModel):
    id: str
    name: str
    sort_order: int


class AgentOut(BaseModel):
    id: str
    name: str
    role: str
    description: str
    department_id: str
    prompt: str
    hue: int
    glyph: str
    status_kind: str
    status_label: str
    joined: str
    source: str
    skills: list[str]
    mcps: list[str]


class ConversationOut(BaseModel):
    id: str
    kind: Literal["dm", "group"]
    name: str
    agent_id: str | None
    member_ids: list[str]
    unread: int
    updated_at: str


class MessageOut(BaseModel):
    id: str
    conversation_id: str
    sender_type: Literal["user", "agent", "system"]
    sender_id: str
    content: str
    created_at: str
    provider: str | None = None
    model: str | None = None


class TaskOut(BaseModel):
    id: str
    title: str
    description: str
    priority: str
    owner_agent_id: str | None
    status: str
    progress: int
    conversation_id: str | None
    due_date: str | None = None
    parent_task_id: str | None = None
    created_at: str
    updated_at: str


class AgentTemplateOut(BaseModel):
    id: str
    name: str
    category_id: str
    category: str
    department: str
    description: str
    prompt: str
    skills: list[str]
    mcps: list[str]
    publisher: str = "AgentPulse 官方"
    version: str = "v0.1.0"
    status: str = "published"


class AgentTemplateCategoryOut(BaseModel):
    id: str
    name: str
    description: str
    sort_order: int


class BootstrapResponse(BaseModel):
    workspace: dict
    departments: list[DepartmentOut]
    agents: list[AgentOut]
    conversations: list[ConversationOut]
    messages_by_conversation: dict[str, list[MessageOut]]
    tasks: list[TaskOut]
    agent_template_categories: list[AgentTemplateCategoryOut]
    agent_templates: list[AgentTemplateOut]


class SendMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=12000)
    target_agent_id: str | None = None


class SendMessageResponse(BaseModel):
    user_message: MessageOut
    agent_message: MessageOut


class CreateAgentRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=255)
    department_name: str = Field(min_length=1, max_length=120)
    prompt: str = Field(min_length=1, max_length=12000)


class RecruitAgentRequest(BaseModel):
    template_id: str
    department_name: str | None = Field(default=None, max_length=120)


class CreateGroupRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    member_ids: list[str] = Field(min_length=1, max_length=12)
    related_task_ids: list[str] = Field(default_factory=list, max_length=12)


class AddConversationMembersRequest(BaseModel):
    member_ids: list[str] = Field(min_length=1, max_length=12)


class CreateTaskRequest(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=2000)
    priority: str = Field(default="P2", max_length=20)
    owner_agent_id: str | None = None
    status: str = Field(default="进行中", max_length=40)
    progress: int = Field(default=0, ge=0, le=100)
    conversation_id: str | None = None
    due_date: str | None = Field(default=None, max_length=40)
    parent_task_id: str | None = None


class UpdateTaskRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    priority: str | None = Field(default=None, max_length=20)
    owner_agent_id: str | None = None
    status: str | None = Field(default=None, max_length=40)
    progress: int | None = Field(default=None, ge=0, le=100)
    conversation_id: str | None = None
    due_date: str | None = Field(default=None, max_length=40)
    parent_task_id: str | None = None
