from fastapi import Depends, Header, HTTPException

from app.core.database import Database, Row, get_db
from app.core.security import decode_access_token
from app.services.workspace import get_workspace_for_user


def get_current_user(
    authorization: str | None = Header(default=None),
    conn: Database = Depends(get_db),
) -> Row:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")

    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = decode_access_token(token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="登录已失效") from exc

    user = conn.execute(
        "SELECT * FROM users WHERE id = ?", (payload["sub"],)
    ).fetchone()
    if user is None:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user


def get_current_user_id(
    current_user: Row = Depends(get_current_user),
) -> str:
    """Extract user ID from current user."""
    return current_user["id"]


def get_workspace_id(
    current_user: Row = Depends(get_current_user),
    conn: Database = Depends(get_db),
) -> str:
    """Get workspace ID for current user."""
    workspace = get_workspace_for_user(conn, current_user["id"])
    if workspace is None:
        raise HTTPException(status_code=404, detail="工作区不存在")
    return workspace["id"]
