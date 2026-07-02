from fastapi import Depends, Header, HTTPException

from app.core.database import Database, Row, get_db
from app.core.security import decode_access_token


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
