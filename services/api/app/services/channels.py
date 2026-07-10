"""Channel management service (TD-09-T2): CRUD, stats, signature verification.

The inbound routing itself lives in app/channels/router.py; this module is the
owner-facing management surface plus the webhook auth helpers.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets

from app.core.database import Database, Row
from app.services.workspace import new_id, now_iso

WEBHOOK_PATH_PREFIX = "/webhooks"


def generate_token() -> str:
    return secrets.token_urlsafe(24)


def webhook_url(channel_type: str, token: str) -> str:
    return f"{WEBHOOK_PATH_PREFIX}/{channel_type}/{token}"


def create_channel(
    conn: Database,
    *,
    workspace_id: str,
    channel_type: str,
    name: str,
    config: dict | None = None,
    target_agent_id: str | None = None,
    target_conversation_id: str | None = None,
) -> dict:
    channel_id = new_id("chan")
    token = generate_token()
    conn.execute(
        """
        INSERT INTO channel_configs (
          id, workspace_id, channel_type, name, token, config_json,
          target_agent_id, target_conversation_id, active, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
        """,
        (
            channel_id,
            workspace_id,
            channel_type,
            name,
            token,
            json.dumps(config or {}, ensure_ascii=False),
            target_agent_id,
            target_conversation_id,
            now_iso(),
        ),
    )
    return serialize_channel(_row(conn, workspace_id, channel_id))  # type: ignore[arg-type]


def _row(conn: Database, workspace_id: str, channel_id: str) -> Row | None:
    return conn.execute(
        "SELECT * FROM channel_configs WHERE id = ? AND workspace_id = ?",
        (channel_id, workspace_id),
    ).fetchone()


def get_channel(conn: Database, workspace_id: str, channel_id: str) -> dict | None:
    row = _row(conn, workspace_id, channel_id)
    return serialize_channel(row) if row else None


def get_channel_by_token(conn: Database, channel_type: str, token: str) -> Row | None:
    """Look up an *active* channel by its webhook token + type (for webhooks)."""
    return conn.execute(
        """
        SELECT * FROM channel_configs
        WHERE token = ? AND channel_type = ? AND active = 1
        """,
        (token, channel_type),
    ).fetchone()


def list_channels(conn: Database, workspace_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM channel_configs WHERE workspace_id = ? ORDER BY created_at DESC",
        (workspace_id,),
    ).fetchall()
    return [serialize_channel(row) for row in rows]


def update_channel(
    conn: Database, *, workspace_id: str, channel_id: str, changes: dict
) -> dict:
    row = _row(conn, workspace_id, channel_id)
    if row is None:
        raise ValueError("channel not found")

    sets: list[str] = []
    params: list[object] = []
    if "name" in changes and changes["name"] is not None:
        sets.append("name = ?")
        params.append(changes["name"])
    if "config" in changes and changes["config"] is not None:
        sets.append("config_json = ?")
        params.append(json.dumps(changes["config"], ensure_ascii=False))
    if "target_agent_id" in changes:
        sets.append("target_agent_id = ?")
        params.append(changes["target_agent_id"])
    if "target_conversation_id" in changes:
        sets.append("target_conversation_id = ?")
        params.append(changes["target_conversation_id"])
    if "active" in changes and changes["active"] is not None:
        sets.append("active = ?")
        params.append(1 if changes["active"] else 0)

    if sets:
        params.extend([channel_id, workspace_id])
        conn.execute(
            f"UPDATE channel_configs SET {', '.join(sets)} WHERE id = ? AND workspace_id = ?",
            tuple(params),
        )
    return serialize_channel(_row(conn, workspace_id, channel_id))  # type: ignore[arg-type]


def deactivate_channel(conn: Database, *, workspace_id: str, channel_id: str) -> dict:
    """Soft delete — the token stops accepting webhooks (active=0)."""
    row = _row(conn, workspace_id, channel_id)
    if row is None:
        raise ValueError("channel not found")
    conn.execute(
        "UPDATE channel_configs SET active = 0 WHERE id = ? AND workspace_id = ?",
        (channel_id, workspace_id),
    )
    return serialize_channel(_row(conn, workspace_id, channel_id))  # type: ignore[arg-type]


def channel_stats(conn: Database, channel: Row) -> dict:
    """Rough usage stats for a channel: today's inbound + distinct external users."""
    today = now_iso()[:10]
    channel_type = channel["channel_type"]
    workspace_id = channel["workspace_id"]

    messages_today = conn.execute(
        """
        SELECT COUNT(*) AS n
        FROM messages
        JOIN conversations ON conversations.id = messages.conversation_id
        WHERE conversations.workspace_id = ?
          AND conversations.source_channel = ?
          AND messages.sender_type = 'user'
          AND substr(messages.created_at, 1, 10) = ?
        """,
        (workspace_id, channel_type, today),
    ).fetchone()["n"]

    active_users = conn.execute(
        """
        SELECT COUNT(DISTINCT external_conversation_id) AS n
        FROM conversations
        WHERE workspace_id = ? AND source_channel = ?
          AND external_conversation_id IS NOT NULL
        """,
        (workspace_id, channel_type),
    ).fetchone()["n"]

    return {"messages_today": messages_today, "active_external_users": active_users}


def verify_signature(channel: Row, raw_body: bytes, signature: str | None) -> bool:
    """Verify an inbound webhook.

    Auth model: the unguessable token in the URL is the primary credential. If
    the channel's config carries a ``secret``, we additionally require an
    HMAC-SHA256 (hex) of the raw body in the ``X-Signature`` header. No secret
    configured → token alone is accepted.
    """
    config = json.loads(channel["config_json"] or "{}")
    secret = config.get("secret")
    if not secret:
        return True
    if not signature:
        return False
    expected = hmac.new(
        secret.encode("utf-8"), raw_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature.strip())


def serialize_channel(row: Row) -> dict:
    return {
        "id": row["id"],
        "workspace_id": row["workspace_id"],
        "channel_type": row["channel_type"],
        "name": row["name"],
        "token": row["token"],
        "config": json.loads(row["config_json"] or "{}"),
        "target_agent_id": row["target_agent_id"],
        "target_conversation_id": row["target_conversation_id"],
        "active": bool(row["active"]),
        "created_at": row["created_at"],
        "webhook_url": webhook_url(row["channel_type"], row["token"]),
    }
