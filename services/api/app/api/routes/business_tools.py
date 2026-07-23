from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_db, get_workspace_id
from app.core.database import Database
from app.orchestration.capability_catalog import CATALOG
from app.schemas.business_tools import (
    BusinessActionOut,
    BusinessToolOut,
    BusinessToolPolicyOut,
)
from app.schemas.workspace import ApprovalOut
from app.services.business_actions import list_actions, list_policies, revoke_policy
from app.services.workspace import serialize_approval

router = APIRouter(tags=["business-tools"])


def _agent_in_workspace(conn: Database, workspace_id: str, agent_id: str) -> None:
    if conn.execute(
        "SELECT 1 FROM agents WHERE id = ? AND workspace_id = ?",
        (agent_id, workspace_id),
    ).fetchone() is None:
        raise HTTPException(status_code=404, detail="员工不存在")


@router.get("/business-tools", response_model=list[BusinessToolOut])
def list_business_tools_route(
    _: str = Depends(get_workspace_id),
) -> list[BusinessToolOut]:
    return [
        BusinessToolOut(
            capability_key=cap.key,
            tool_name=cap.business_tool,
            description=cap.description,
            risk_gate=cap.risk_gate,
            required_credentials=list(cap.required_credentials),
            provider_implemented=cap.business_tool == "send_email",
        )
        for cap in CATALOG.values()
        if cap.business_tool
    ]


@router.get("/business-actions", response_model=list[BusinessActionOut])
def list_business_actions_route(
    agent_id: str | None = Query(default=None),
    task_id: str | None = Query(default=None),
    run_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    workspace_id: str = Depends(get_workspace_id),
    conn: Database = Depends(get_db),
) -> list[BusinessActionOut]:
    if agent_id:
        _agent_in_workspace(conn, workspace_id, agent_id)
    return [
        BusinessActionOut(**item)
        for item in list_actions(
            conn,
            workspace_id=workspace_id,
            agent_id=agent_id,
            task_id=task_id,
            run_id=run_id,
            status=status,
        )
    ]


@router.get(
    "/conversations/{conversation_id}/approvals", response_model=list[ApprovalOut]
)
def list_conversation_approvals_route(
    conversation_id: str,
    status: str | None = Query(default=None),
    workspace_id: str = Depends(get_workspace_id),
    conn: Database = Depends(get_db),
) -> list[ApprovalOut]:
    conversation = conn.execute(
        "SELECT 1 FROM conversations WHERE id = ? AND workspace_id = ?",
        (conversation_id, workspace_id),
    ).fetchone()
    if conversation is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    where = ["conversation_id = ?", "workspace_id = ?"]
    params: list[object] = [conversation_id, workspace_id]
    if status:
        where.append("status = ?")
        params.append(status)
    rows = conn.execute(
        f"SELECT * FROM approvals WHERE {' AND '.join(where)} ORDER BY created_at",
        tuple(params),
    ).fetchall()
    return [ApprovalOut(**serialize_approval(row)) for row in rows]


@router.get(
    "/agents/{agent_id}/business-tool-policies",
    response_model=list[BusinessToolPolicyOut],
)
def list_business_tool_policies_route(
    agent_id: str,
    workspace_id: str = Depends(get_workspace_id),
    conn: Database = Depends(get_db),
) -> list[BusinessToolPolicyOut]:
    _agent_in_workspace(conn, workspace_id, agent_id)
    return [
        BusinessToolPolicyOut(**{**row, "active": bool(row["active"])})
        for row in list_policies(conn, workspace_id=workspace_id, agent_id=agent_id)
    ]


@router.delete("/agents/{agent_id}/business-tool-policies/{tool_name}")
def revoke_business_tool_policy_route(
    agent_id: str,
    tool_name: str,
    workspace_id: str = Depends(get_workspace_id),
    conn: Database = Depends(get_db),
) -> dict:
    _agent_in_workspace(conn, workspace_id, agent_id)
    if not revoke_policy(
        conn, workspace_id=workspace_id, agent_id=agent_id, tool_name=tool_name
    ):
        raise HTTPException(status_code=404, detail="长期放行策略不存在")
    return {"ok": True}
