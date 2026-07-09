"""API routes for the idea center (TD-08-T1)."""

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_db, get_workspace_id
from app.core.database import Database
from app.schemas.idea import (
    ConvertIdeaResponse,
    CreateIdeaRequest,
    IdeaOut,
    IdleThinkingRequest,
    IdleThinkingSettings,
    ReviewIdeaRequest,
)
from app.services.ideas import (
    convert_idea,
    create_idea,
    get_idea,
    list_ideas,
    review_idea,
    set_idle_thinking,
)

router = APIRouter(tags=["ideas"])


@router.get("/ideas", response_model=list[IdeaOut])
def list_ideas_route(
    status: str | None = None,
    agent_id: str | None = None,
    category: str | None = None,
    workspace_id: str = Depends(get_workspace_id),
    conn: Database = Depends(get_db),
) -> list[IdeaOut]:
    ideas = list_ideas(
        conn,
        workspace_id=workspace_id,
        status=status,
        agent_id=agent_id,
        category=category,
    )
    return [IdeaOut(**idea) for idea in ideas]


@router.post("/ideas", response_model=IdeaOut)
def create_idea_route(
    payload: CreateIdeaRequest,
    workspace_id: str = Depends(get_workspace_id),
    conn: Database = Depends(get_db),
) -> IdeaOut:
    try:
        idea = create_idea(
            conn,
            workspace_id=workspace_id,
            source_agent_id=payload.source_agent_id,
            title=payload.title,
            description=payload.description,
            category=payload.category,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return IdeaOut(**idea)


@router.get("/ideas/{idea_id}", response_model=IdeaOut)
def get_idea_route(
    idea_id: str,
    workspace_id: str = Depends(get_workspace_id),
    conn: Database = Depends(get_db),
) -> IdeaOut:
    idea = get_idea(conn, workspace_id, idea_id)
    if idea is None:
        raise HTTPException(status_code=404, detail="想法不存在")
    return IdeaOut(**idea)


@router.post("/ideas/{idea_id}/review", response_model=IdeaOut)
def review_idea_route(
    idea_id: str,
    payload: ReviewIdeaRequest,
    workspace_id: str = Depends(get_workspace_id),
    conn: Database = Depends(get_db),
) -> IdeaOut:
    try:
        idea = review_idea(
            conn, workspace_id=workspace_id, idea_id=idea_id, action=payload.action
        )
    except ValueError as exc:
        status_code = 404 if str(exc) == "idea not found" else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return IdeaOut(**idea)


@router.post("/ideas/{idea_id}/convert", response_model=ConvertIdeaResponse)
def convert_idea_route(
    idea_id: str,
    workspace_id: str = Depends(get_workspace_id),
    conn: Database = Depends(get_db),
) -> ConvertIdeaResponse:
    try:
        conversation_id, idea = convert_idea(
            conn, workspace_id=workspace_id, idea_id=idea_id
        )
    except ValueError as exc:
        status_code = 404 if str(exc) == "idea not found" else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return ConvertIdeaResponse(conversation_id=conversation_id, idea=IdeaOut(**idea))


@router.patch("/agents/{agent_id}/idle-thinking", response_model=IdleThinkingSettings)
def update_idle_thinking_route(
    agent_id: str,
    payload: IdleThinkingRequest,
    workspace_id: str = Depends(get_workspace_id),
    conn: Database = Depends(get_db),
) -> IdleThinkingSettings:
    try:
        settings = set_idle_thinking(
            conn,
            workspace_id=workspace_id,
            agent_id=agent_id,
            enabled=payload.enabled,
            interval_hours=payload.interval_hours,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="该员工尚未配置角色规格") from exc
    return IdleThinkingSettings(**settings)
