from __future__ import annotations

from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt

from app.core.config import settings

ALGORITHM = "HS256"


def create_business_tool_token(
    *,
    workspace_id: str,
    conversation_id: str,
    run_id: str,
    agent_id: str,
    task_id: str | None = None,
) -> str:
    expires = datetime.now(UTC) + timedelta(
        seconds=settings.business_tool_token_ttl_seconds
    )
    return jwt.encode(
        {
            "type": "business_tool",
            "workspace_id": workspace_id,
            "conversation_id": conversation_id,
            "run_id": run_id,
            "agent_id": agent_id,
            "task_id": task_id,
            "exp": expires,
        },
        settings.auth_secret_key,
        algorithm=ALGORITHM,
    )


def decode_business_tool_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.auth_secret_key, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise ValueError("invalid or expired business tool token") from exc
    if payload.get("type") != "business_tool":
        raise ValueError("invalid business tool token type")
    required = ("workspace_id", "conversation_id", "run_id", "agent_id")
    if any(not payload.get(key) for key in required):
        raise ValueError("incomplete business tool token")
    return payload
