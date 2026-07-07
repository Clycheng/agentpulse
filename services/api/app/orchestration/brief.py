"""Consensus brief management.

A consensus brief is a structured record of discussion outcome:
- goal: What to achieve (required)
- scope: What's included/excluded
- constraints: Time/resource/tech limits
- success_criteria: How to measure completion
- owner_agent_id: Who leads execution

See ADR 0006 for design details.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

from app.core.database import Database
from app.orchestration.discussion import DiscussionStatus, set_discussion_status


class BriefStatus:
    """Brief status constants."""
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"
    VALID_STATES = (DRAFT, CONFIRMED, REJECTED, SUPERSEDED)


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def new_id() -> str:
    return f"brief_{uuid4().hex}"


def _add_brief_card_message(
    conn: Database,
    conversation_id: str,
    brief_id: str,
    brief_data: dict,
) -> None:
    """Add a system message with brief card data to the conversation.

    The message content is JSON-encoded brief data that the frontend
    can render as an interactive card.
    """
    from app.services.workspace import now_iso as svc_now_iso, new_id as svc_new_id

    message_id = svc_new_id("msg")
    created_at = svc_now_iso()
    # Use special content format: "BRIEF_CARD:{json}"
    card_content = f"BRIEF_CARD:{json.dumps(brief_data, ensure_ascii=False)}"

    conn.execute(
        """
        INSERT INTO messages (id, conversation_id, sender_type, sender_id, content, created_at)
        VALUES (?, ?, 'system', '', ?, ?)
        """,
        (message_id, conversation_id, card_content, created_at),
    )


def create_brief(
    conn: Database,
    *,
    workspace_id: str,
    discussion_conversation_id: str,
    goal: str,
    scope: str = "",
    constraints: str = "",
    success_criteria: str = "",
    owner_agent_id: str | None = None,
    participant_agent_ids: list[str] | None = None,
    created_by_agent_id: str,
    supersedes_brief_id: str | None = None,
    derived_from_brief_id: str | None = None,
) -> dict:
    """Create a new consensus brief in draft status.

    Args:
        conn: Database connection
        workspace_id: Workspace ID
        discussion_conversation_id: Conversation ID where discussion happened
        goal: What to achieve (required, max 500 chars)
        scope: What's included/excluded (max 500 chars)
        constraints: Time/resource/tech limits (max 500 chars)
        success_criteria: How to measure completion (max 500 chars)
        owner_agent_id: Who leads execution (optional, can be set later)
        participant_agent_ids: List of participating agent IDs
        created_by_agent_id: Agent who created this brief
        supersedes_brief_id: Previous brief this one supersedes
        derived_from_brief_id: Previous brief this one derives from

    Returns:
        Serialized brief dict

    Raises:
        ValueError: If required fields missing or validation fails
    """
    # Validate required fields
    if not goal or len(goal) > 500:
        raise ValueError("goal is required and must be <= 500 chars")
    if scope and len(scope) > 500:
        raise ValueError("scope must be <= 500 chars")
    if constraints and len(constraints) > 500:
        raise ValueError("constraints must be <= 500 chars")
    if success_criteria and len(success_criteria) > 500:
        raise ValueError("success_criteria must be <= 500 chars")

    # Validate conversation exists
    conversation = conn.execute(
        "SELECT id FROM conversations WHERE id = ? AND workspace_id = ?",
        (discussion_conversation_id, workspace_id),
    ).fetchone()
    if conversation is None:
        raise ValueError("conversation not found")

    # Validate created_by_agent exists
    agent = conn.execute(
        "SELECT id FROM agents WHERE id = ? AND workspace_id = ?",
        (created_by_agent_id, workspace_id),
    ).fetchone()
    if agent is None:
        raise ValueError("created_by_agent not found")

    # Validate owner_agent if provided
    if owner_agent_id:
        owner = conn.execute(
            "SELECT id FROM agents WHERE id = ? AND workspace_id = ?",
            (owner_agent_id, workspace_id),
        ).fetchone()
        if owner is None:
            raise ValueError("owner_agent not found")

    # Validate supersedes_brief if provided
    if supersedes_brief_id:
        prev_brief = conn.execute(
            "SELECT id FROM consensus_briefs WHERE id = ? AND workspace_id = ?",
            (supersedes_brief_id, workspace_id),
        ).fetchone()
        if prev_brief is None:
            raise ValueError("supersedes_brief not found")

    # Validate derived_from_brief if provided
    if derived_from_brief_id:
        source_brief = conn.execute(
            "SELECT id FROM consensus_briefs WHERE id = ? AND workspace_id = ?",
            (derived_from_brief_id, workspace_id),
        ).fetchone()
        if source_brief is None:
            raise ValueError("derived_from_brief not found")

    brief_id = new_id()
    created_at = now_iso()
    participant_json = json.dumps(participant_agent_ids or [], ensure_ascii=False)

    conn.execute(
        """
        INSERT INTO consensus_briefs (
          id, workspace_id, discussion_conversation_id, status,
          goal, scope, constraints, success_criteria,
          owner_agent_id, participant_agent_ids_json, created_by_agent_id,
          supersedes_brief_id, derived_from_brief_id, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            brief_id,
            workspace_id,
            discussion_conversation_id,
            BriefStatus.DRAFT,
            goal,
            scope,
            constraints,
            success_criteria,
            owner_agent_id,
            participant_json,
            created_by_agent_id,
            supersedes_brief_id,
            derived_from_brief_id,
            created_at,
        ),
    )

    # Send brief card message to the conversation
    brief_row = conn.execute(
        "SELECT * FROM consensus_briefs WHERE id = ?", (brief_id,)
    ).fetchone()
    brief_data = serialize_brief(brief_row)
    _add_brief_card_message(
        conn,
        discussion_conversation_id,
        brief_id,
        brief_data,
    )

    # Set conversation discussion status to 'discussing'
    # (new brief draft means discussion is still ongoing)
    set_discussion_status(conn, discussion_conversation_id, DiscussionStatus.DISCUSSING)

    return brief_data


def confirm_brief(
    conn: Database,
    *,
    workspace_id: str,
    brief_id: str,
    confirmed_by_user_id: str,
) -> dict:
    """Confirm a brief (owner action).

    This changes status from 'draft' to 'confirmed' and records
    who confirmed it. Only confirmed briefs can be used to create tasks.

    Args:
        conn: Database connection
        workspace_id: Workspace ID
        brief_id: Brief ID to confirm
        confirmed_by_user_id: User ID who confirmed

    Returns:
        Serialized brief dict

    Raises:
        ValueError: If brief not found, not in draft status, or user not found
    """
    brief = conn.execute(
        "SELECT * FROM consensus_briefs WHERE id = ? AND workspace_id = ?",
        (brief_id, workspace_id),
    ).fetchone()
    if brief is None:
        raise ValueError("brief not found")

    if brief["status"] != BriefStatus.DRAFT:
        raise ValueError(f"brief must be in draft status, current: {brief['status']}")

    # Validate user exists
    user = conn.execute(
        "SELECT id FROM users WHERE id = ?", (confirmed_by_user_id,)
    ).fetchone()
    if user is None:
        raise ValueError("user not found")

    confirmed_at = now_iso()
    conn.execute(
        """
        UPDATE consensus_briefs
        SET status = ?, confirmed_at = ?, confirmed_by_user_id = ?
        WHERE id = ? AND workspace_id = ?
        """,
        (BriefStatus.CONFIRMED, confirmed_at, confirmed_by_user_id, brief_id, workspace_id),
    )

    # Set conversation discussion status to 'aligned'
    # (confirmed brief means consensus reached)
    set_discussion_status(conn, brief["discussion_conversation_id"], DiscussionStatus.ALIGNED)

    return serialize_brief(
        conn.execute(
            "SELECT * FROM consensus_briefs WHERE id = ?", (brief_id,)
        ).fetchone()
    )


def reject_brief(
    conn: Database,
    *,
    workspace_id: str,
    brief_id: str,
    confirmed_by_user_id: str,
) -> dict:
    """Reject a brief (owner action).

    This changes status from 'draft' to 'rejected'. Discussion should continue.

    Args:
        conn: Database connection
        workspace_id: Workspace ID
        brief_id: Brief ID to reject
        confirmed_by_user_id: User ID who rejected

    Returns:
        Serialized brief dict

    Raises:
        ValueError: If brief not found or not in draft status
    """
    brief = conn.execute(
        "SELECT * FROM consensus_briefs WHERE id = ? AND workspace_id = ?",
        (brief_id, workspace_id),
    ).fetchone()
    if brief is None:
        raise ValueError("brief not found")

    if brief["status"] != BriefStatus.DRAFT:
        raise ValueError(f"brief must be in draft status, current: {brief['status']}")

    confirmed_at = now_iso()
    conn.execute(
        """
        UPDATE consensus_briefs
        SET status = ?, confirmed_at = ?, confirmed_by_user_id = ?
        WHERE id = ? AND workspace_id = ?
        """,
        (BriefStatus.REJECTED, confirmed_at, confirmed_by_user_id, brief_id, workspace_id),
    )

    # Keep conversation in 'discussing' status
    # (rejected brief means discussion should continue)
    set_discussion_status(conn, brief["discussion_conversation_id"], DiscussionStatus.DISCUSSING)

    return serialize_brief(
        conn.execute(
            "SELECT * FROM consensus_briefs WHERE id = ?", (brief_id,)
        ).fetchone()
    )


def get_brief_by_id(conn: Database, brief_id: str) -> dict | None:
    """Get a brief by ID.

    Args:
        conn: Database connection
        brief_id: Brief ID

    Returns:
        Serialized brief dict or None if not found
    """
    row = conn.execute(
        "SELECT * FROM consensus_briefs WHERE id = ?", (brief_id,)
    ).fetchone()
    if row is None:
        return None
    return serialize_brief(row)


def serialize_brief(row: dict) -> dict:
    """Serialize a brief row to dict."""
    return {
        "id": row["id"],
        "workspace_id": row["workspace_id"],
        "discussion_conversation_id": row["discussion_conversation_id"],
        "status": row["status"],
        "goal": row["goal"],
        "scope": row["scope"] or "",
        "constraints": row["constraints"] or "",
        "success_criteria": row["success_criteria"] or "",
        "owner_agent_id": row["owner_agent_id"],
        "participant_agent_ids": json.loads(row["participant_agent_ids_json"] or "[]"),
        "created_by_agent_id": row["created_by_agent_id"],
        "supersedes_brief_id": row["supersedes_brief_id"],
        "derived_from_brief_id": row["derived_from_brief_id"],
        "created_at": row["created_at"],
        "confirmed_at": row["confirmed_at"],
        "confirmed_by_user_id": row["confirmed_by_user_id"],
    }