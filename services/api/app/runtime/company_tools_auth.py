from __future__ import annotations

import secrets
import time

import jwt
from jwt.exceptions import InvalidTokenError

from app.core.config import settings

ALGORITHM = "HS256"


def create_company_tool_token(
    *, workspace_id: str, plan_id: str, task_id: str, run_id: str, agent_id: str
) -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "type": "company_tool",
            "workspace_id": workspace_id,
            "plan_id": plan_id,
            "task_id": task_id,
            "run_id": run_id,
            "agent_id": agent_id,
            "iat": now,
            "exp": now + settings.company_tool_token_ttl_seconds,
            "iss": "agentpulse-api",
            "aud": "agentpulse-company-tools",
            "jti": secrets.token_urlsafe(12),
        },
        settings.auth_secret_key,
        algorithm=ALGORITHM,
    )


def decode_company_tool_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            settings.auth_secret_key,
            algorithms=[ALGORITHM],
            issuer="agentpulse-api",
            audience="agentpulse-company-tools",
            options={"require": ["exp", "iat", "iss", "aud", "jti", "type"]},
        )
    except InvalidTokenError as exc:
        raise ValueError("invalid or expired company tool token") from exc
    if payload.get("type") != "company_tool":
        raise ValueError("invalid company tool token type")
    required = ("workspace_id", "plan_id", "task_id", "run_id", "agent_id")
    if any(not payload.get(key) for key in required):
        raise ValueError("incomplete company tool token")
    return payload
