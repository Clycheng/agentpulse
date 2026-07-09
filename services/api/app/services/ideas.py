"""Idea center service (TD-08-T1).

CRUD + status flow for ideas, plus converting an idea into a group discussion.
Idle-reflection generation (how ideas get created by employees) is TD-08-T2 and
lives in the runtime layer; this module is the pure data/API surface.
"""

from __future__ import annotations

from app.core.database import Database, Row
from app.services.workspace import add_message, new_id, now_iso

VALID_CATEGORIES = ("improvement", "opportunity", "risk", "learning")


def create_idea(
    conn: Database,
    *,
    workspace_id: str,
    source_agent_id: str,
    title: str,
    description: str,
    category: str,
) -> dict:
    """Insert a new idea (status='new'). Raises ValueError on bad input."""
    if category not in VALID_CATEGORIES:
        raise ValueError(f"invalid idea category: {category}")
    agent = conn.execute(
        "SELECT id FROM agents WHERE id = ? AND workspace_id = ?",
        (source_agent_id, workspace_id),
    ).fetchone()
    if agent is None:
        raise ValueError("source agent not found in workspace")

    idea_id = new_id("idea")
    conn.execute(
        """
        INSERT INTO ideas (
          id, workspace_id, source_agent_id, title, description,
          category, status, converted_brief_id, created_at, reviewed_at
        )
        VALUES (?, ?, ?, ?, ?, ?, 'new', NULL, ?, NULL)
        """,
        (
            idea_id,
            workspace_id,
            source_agent_id,
            title,
            description,
            category,
            now_iso(),
        ),
    )
    return get_idea(conn, workspace_id, idea_id)  # type: ignore[return-value]


def _idea_row(conn: Database, workspace_id: str, idea_id: str) -> Row | None:
    return conn.execute(
        """
        SELECT ideas.*, agents.name AS source_agent_name
        FROM ideas
        JOIN agents ON agents.id = ideas.source_agent_id
        WHERE ideas.id = ? AND ideas.workspace_id = ?
        """,
        (idea_id, workspace_id),
    ).fetchone()


def get_idea(conn: Database, workspace_id: str, idea_id: str) -> dict | None:
    row = _idea_row(conn, workspace_id, idea_id)
    return serialize_idea(row) if row else None


def list_ideas(
    conn: Database,
    *,
    workspace_id: str,
    status: str | None = None,
    agent_id: str | None = None,
    category: str | None = None,
) -> list[dict]:
    """List ideas, newest-unreviewed first. Optional filters."""
    clauses = ["ideas.workspace_id = ?"]
    params: list[object] = [workspace_id]
    if status is not None:
        clauses.append("ideas.status = ?")
        params.append(status)
    if agent_id is not None:
        clauses.append("ideas.source_agent_id = ?")
        params.append(agent_id)
    if category is not None:
        clauses.append("ideas.category = ?")
        params.append(category)

    rows = conn.execute(
        f"""
        SELECT ideas.*, agents.name AS source_agent_name
        FROM ideas
        JOIN agents ON agents.id = ideas.source_agent_id
        WHERE {" AND ".join(clauses)}
        ORDER BY
          CASE ideas.status WHEN 'new' THEN 0 ELSE 1 END,
          ideas.created_at DESC
        """,
        tuple(params),
    ).fetchall()
    return [serialize_idea(row) for row in rows]


def review_idea(
    conn: Database, *, workspace_id: str, idea_id: str, action: str
) -> dict:
    """Owner accepts or dismisses an idea. Raises ValueError if not found."""
    row = _idea_row(conn, workspace_id, idea_id)
    if row is None:
        raise ValueError("idea not found")
    new_status = {"accept": "accepted", "dismiss": "dismissed"}.get(action)
    if new_status is None:
        raise ValueError(f"invalid review action: {action}")
    conn.execute(
        "UPDATE ideas SET status = ?, reviewed_at = ? WHERE id = ?",
        (new_status, now_iso(), idea_id),
    )
    return get_idea(conn, workspace_id, idea_id)  # type: ignore[return-value]


def convert_idea(
    conn: Database, *, workspace_id: str, idea_id: str
) -> tuple[str, dict]:
    """Turn an idea into a group discussion seeded with the idea as context.

    Creates a group conversation (traced back via conversations.idea_id) with the
    source agent as a member, drops the idea text as the first system message,
    and marks the idea 'converted'. Returns (conversation_id, updated_idea).
    """
    row = _idea_row(conn, workspace_id, idea_id)
    if row is None:
        raise ValueError("idea not found")
    if row["status"] == "converted":
        raise ValueError("idea already converted")

    conversation_id = new_id("conv")
    created_at = now_iso()
    title = row["title"]
    name = f"想法讨论 · {title[:40]}"
    conn.execute(
        """
        INSERT INTO conversations (
          id, workspace_id, kind, name, unread, created_at, updated_at, idea_id
        )
        VALUES (?, ?, 'group', ?, 0, ?, ?, ?)
        """,
        (conversation_id, workspace_id, name, created_at, created_at, idea_id),
    )
    conn.execute(
        """
        INSERT INTO conversation_members (conversation_id, agent_id)
        VALUES (?, ?)
        """,
        (conversation_id, row["source_agent_id"]),
    )
    add_message(
        conn,
        conversation_id=conversation_id,
        sender_type="system",
        sender_id="",
        content=(
            f"由想法发起讨论：【{row['category']}】{title}\n\n{row['description']}"
        ),
    )
    conn.execute(
        "UPDATE ideas SET status = 'converted', reviewed_at = ? WHERE id = ?",
        (created_at, idea_id),
    )
    updated = get_idea(conn, workspace_id, idea_id)
    return conversation_id, updated  # type: ignore[return-value]


def set_idle_thinking(
    conn: Database,
    *,
    workspace_id: str,
    agent_id: str,
    enabled: bool | None = None,
    interval_hours: int | None = None,
) -> dict:
    """Update an employee's idle-thinking config on its agent_specs row.

    Raises ValueError if the agent has no provisioned spec.
    """
    spec = conn.execute(
        """
        SELECT agent_specs.* FROM agent_specs
        JOIN agents ON agents.id = agent_specs.agent_id
        WHERE agent_specs.agent_id = ? AND agents.workspace_id = ?
        """,
        (agent_id, workspace_id),
    ).fetchone()
    if spec is None:
        raise ValueError("agent spec not found")

    if enabled is not None:
        conn.execute(
            "UPDATE agent_specs SET idle_thinking_enabled = ? WHERE agent_id = ?",
            (1 if enabled else 0, agent_id),
        )
    if interval_hours is not None:
        conn.execute(
            "UPDATE agent_specs SET idle_think_interval_hours = ? WHERE agent_id = ?",
            (interval_hours, agent_id),
        )

    updated = conn.execute(
        "SELECT * FROM agent_specs WHERE agent_id = ?", (agent_id,)
    ).fetchone()
    return {
        "agent_id": agent_id,
        "idle_thinking_enabled": bool(updated["idle_thinking_enabled"]),
        "idle_think_interval_hours": updated["idle_think_interval_hours"],
        "last_idle_think_at": updated["last_idle_think_at"],
    }


def serialize_idea(row: Row) -> dict:
    return {
        "id": row["id"],
        "workspace_id": row["workspace_id"],
        "source_agent_id": row["source_agent_id"],
        "source_agent_name": row["source_agent_name"],
        "title": row["title"],
        "description": row["description"],
        "category": row["category"],
        "status": row["status"],
        "converted_brief_id": row["converted_brief_id"],
        "created_at": row["created_at"],
        "reviewed_at": row["reviewed_at"],
    }
