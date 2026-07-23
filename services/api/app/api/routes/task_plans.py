from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_db, get_workspace_id
from app.schemas.task_plan import ResumeTaskRequest, TaskPlanOut, TaskRunOut
from app.services.task_plans import (
    TaskPlanError,
    get_task_plan,
    list_task_runs,
    resume_task,
)

router = APIRouter(tags=["task-plans"])


@router.get("/task-plans/{plan_id}", response_model=TaskPlanOut)
def get_task_plan_route(
    plan_id: str,
    workspace_id: str = Depends(get_workspace_id),
    db=Depends(get_db),
) -> TaskPlanOut:
    try:
        return TaskPlanOut(**get_task_plan(db, plan_id, workspace_id=workspace_id))
    except TaskPlanError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/tasks/{task_id}/runs", response_model=list[TaskRunOut])
def list_task_runs_route(
    task_id: str,
    workspace_id: str = Depends(get_workspace_id),
    db=Depends(get_db),
) -> list[TaskRunOut]:
    try:
        return [TaskRunOut(**run) for run in list_task_runs(db, workspace_id=workspace_id, task_id=task_id)]
    except TaskPlanError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/tasks/{task_id}/resume", response_model=TaskPlanOut)
def resume_task_route(
    task_id: str,
    payload: ResumeTaskRequest,
    workspace_id: str = Depends(get_workspace_id),
    db=Depends(get_db),
) -> TaskPlanOut:
    try:
        return TaskPlanOut(
            **resume_task(
                db,
                workspace_id=workspace_id,
                task_id=task_id,
                message=payload.message,
            )
        )
    except TaskPlanError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
