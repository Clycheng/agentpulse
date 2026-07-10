"""Owner-facing channel management API (TD-09-T2)."""

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_db, get_workspace_id
from app.core.database import Database
from app.schemas.channel import (
    ChannelDetailOut,
    ChannelOut,
    CreateChannelRequest,
    UpdateChannelRequest,
)
from app.services.channels import (
    channel_stats,
    create_channel,
    deactivate_channel,
    get_channel,
    list_channels,
    update_channel,
)

router = APIRouter(prefix="/channels", tags=["channels"])


def _validate_targets(conn, workspace_id, target_agent_id, target_conversation_id):
    if target_agent_id is not None:
        row = conn.execute(
            "SELECT 1 FROM agents WHERE id = ? AND workspace_id = ?",
            (target_agent_id, workspace_id),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=400, detail="目标员工不存在")
    if target_conversation_id is not None:
        row = conn.execute(
            "SELECT 1 FROM conversations WHERE id = ? AND workspace_id = ?",
            (target_conversation_id, workspace_id),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=400, detail="目标会话不存在")


@router.get("", response_model=list[ChannelOut])
def list_channels_route(
    workspace_id: str = Depends(get_workspace_id),
    conn: Database = Depends(get_db),
) -> list[ChannelOut]:
    return [ChannelOut(**c) for c in list_channels(conn, workspace_id)]


@router.post("", response_model=ChannelOut)
def create_channel_route(
    payload: CreateChannelRequest,
    workspace_id: str = Depends(get_workspace_id),
    conn: Database = Depends(get_db),
) -> ChannelOut:
    _validate_targets(
        conn, workspace_id, payload.target_agent_id, payload.target_conversation_id
    )
    channel = create_channel(
        conn,
        workspace_id=workspace_id,
        channel_type=payload.channel_type,
        name=payload.name,
        config=payload.config,
        target_agent_id=payload.target_agent_id,
        target_conversation_id=payload.target_conversation_id,
    )
    return ChannelOut(**channel)


@router.get("/{channel_id}", response_model=ChannelDetailOut)
def get_channel_route(
    channel_id: str,
    workspace_id: str = Depends(get_workspace_id),
    conn: Database = Depends(get_db),
) -> ChannelDetailOut:
    channel = get_channel(conn, workspace_id, channel_id)
    if channel is None:
        raise HTTPException(status_code=404, detail="渠道不存在")
    row = conn.execute(
        "SELECT * FROM channel_configs WHERE id = ?", (channel_id,)
    ).fetchone()
    return ChannelDetailOut(**channel, stats=channel_stats(conn, row))


@router.patch("/{channel_id}", response_model=ChannelOut)
def update_channel_route(
    channel_id: str,
    payload: UpdateChannelRequest,
    workspace_id: str = Depends(get_workspace_id),
    conn: Database = Depends(get_db),
) -> ChannelOut:
    changes = payload.model_dump(exclude_unset=True)
    _validate_targets(
        conn,
        workspace_id,
        changes.get("target_agent_id"),
        changes.get("target_conversation_id"),
    )
    try:
        channel = update_channel(
            conn, workspace_id=workspace_id, channel_id=channel_id, changes=changes
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="渠道不存在") from exc
    return ChannelOut(**channel)


@router.delete("/{channel_id}", response_model=ChannelOut)
def delete_channel_route(
    channel_id: str,
    workspace_id: str = Depends(get_workspace_id),
    conn: Database = Depends(get_db),
) -> ChannelOut:
    """Soft delete — sets active=0 so the webhook token stops accepting posts."""
    try:
        channel = deactivate_channel(
            conn, workspace_id=workspace_id, channel_id=channel_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="渠道不存在") from exc
    return ChannelOut(**channel)
