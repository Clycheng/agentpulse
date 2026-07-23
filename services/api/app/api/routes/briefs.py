"""API routes for consensus briefs."""

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_user_id, get_db, get_workspace_id
from app.orchestration import (
    create_brief,
    reject_brief,
    get_brief_by_id,
    serialize_brief,
)
from app.schemas.brief import BriefOut, CreateBriefRequest
from app.schemas.task_plan import TaskPlanOut
from app.services.task_plans import TaskPlanError, launch_brief

router = APIRouter(prefix="/briefs", tags=["briefs"])


@router.post("", response_model=BriefOut)
async def create_brief_route(
    payload: CreateBriefRequest,
    workspace_id: str = Depends(get_workspace_id),
    db = Depends(get_db),
) -> BriefOut:
    """Create a consensus brief in draft status.

    This is called by an agent to propose a discussion outcome.
    The brief must be confirmed by the user before creating tasks.
    """
    try:
        brief = create_brief(
            db,
            workspace_id=workspace_id,
            discussion_conversation_id=payload.discussion_conversation_id,
            goal=payload.goal,
            scope=payload.scope,
            constraints=payload.constraints,
            success_criteria=payload.success_criteria,
            owner_agent_id=payload.owner_agent_id,
            participant_agent_ids=payload.participant_agent_ids,
            work_items=[item.model_dump() for item in payload.work_items],
            created_by_agent_id=payload.created_by_agent_id,
            supersedes_brief_id=payload.supersedes_brief_id,
            derived_from_brief_id=payload.derived_from_brief_id,
        )
        return BriefOut(**brief)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{brief_id}/confirm", response_model=BriefOut)
async def confirm_brief_route(
    brief_id: str,
    workspace_id: str = Depends(get_workspace_id),
    user_id: str = Depends(get_current_user_id),
    db = Depends(get_db),
) -> BriefOut:
    """Confirm a brief (owner action).

    Compatibility endpoint: delegates to the same atomic launch service as
    /launch, but keeps returning BriefOut for older clients.
    """
    try:
        launch_brief(
            db,
            workspace_id=workspace_id,
            brief_id=brief_id,
            confirmed_by_user_id=user_id,
        )
        brief = get_brief_by_id(db, brief_id)
        return BriefOut(**brief)
    except (ValueError, TaskPlanError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{brief_id}/launch", response_model=TaskPlanOut)
async def launch_brief_route(
    brief_id: str,
    workspace_id: str = Depends(get_workspace_id),
    user_id: str = Depends(get_current_user_id),
    db=Depends(get_db),
) -> TaskPlanOut:
    try:
        return TaskPlanOut(
            **launch_brief(
                db,
                workspace_id=workspace_id,
                brief_id=brief_id,
                confirmed_by_user_id=user_id,
            )
        )
    except TaskPlanError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{brief_id}/reject", response_model=BriefOut)
async def reject_brief_route(
    brief_id: str,
    workspace_id: str = Depends(get_workspace_id),
    user_id: str = Depends(get_current_user_id),
    db = Depends(get_db),
) -> BriefOut:
    """Reject a brief (owner action).

    Changes brief status from 'draft' to 'rejected'.
    Discussion should continue and a new brief may be proposed.
    """
    try:
        brief = reject_brief(
            db,
            workspace_id=workspace_id,
            brief_id=brief_id,
            confirmed_by_user_id=user_id,
        )
        return BriefOut(**brief)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{brief_id}", response_model=BriefOut)
async def get_brief_route(
    brief_id: str,
    workspace_id: str = Depends(get_workspace_id),
    db = Depends(get_db),
) -> BriefOut:
    """Get a brief by ID."""
    brief = get_brief_by_id(db, brief_id)
    if brief is None:
        raise HTTPException(status_code=404, detail="brief not found")
    if brief["workspace_id"] != workspace_id:
        raise HTTPException(status_code=404, detail="brief not found")
    return BriefOut(**brief)
