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
import re
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


def validate_work_items(
    work_items: list[dict], *, allowed_agent_ids: set[str]
) -> list[dict]:
    """Validate the executable assignment contract attached to a brief."""
    if not 3 <= len(work_items) <= 6:
        raise ValueError("brief must contain 3-6 work items")

    normalized: list[dict] = []
    keys: set[str] = set()
    for raw in work_items:
        key = str(raw.get("key") or "").strip()
        if not re.fullmatch(r"[a-z][a-z0-9_-]{0,79}", key):
            raise ValueError(f"invalid work item key: {key or '<empty>'}")
        if key in keys:
            raise ValueError(f"duplicate work item key: {key}")
        keys.add(key)
        owner_agent_id = str(raw.get("owner_agent_id") or "").strip()
        if owner_agent_id not in allowed_agent_ids:
            raise ValueError(f"work item owner is not a group member: {owner_agent_id}")
        title = str(raw.get("title") or "").strip()
        description = str(raw.get("description") or "").strip()
        expected_output = str(raw.get("expected_output") or "").strip()
        output_type = str(raw.get("output_type") or "").strip()
        if not all((title, description, expected_output, output_type)):
            raise ValueError(f"work item {key} has incomplete delivery fields")
        depends = [str(value).strip() for value in raw.get("depends_on_keys") or []]
        if len(depends) != len(set(depends)):
            raise ValueError(f"work item {key} has duplicate dependencies")
        normalized.append(
            {
                "key": key,
                "title": title[:160],
                "description": description[:2000],
                "owner_agent_id": owner_agent_id,
                "expected_output": expected_output[:2000],
                "output_type": output_type[:80],
                "depends_on_keys": depends,
                "final_delivery": bool(raw.get("final_delivery", False)),
            }
        )

    for item in normalized:
        unknown = set(item["depends_on_keys"]) - keys
        if unknown:
            raise ValueError(
                f"work item {item['key']} has unknown dependencies: {', '.join(sorted(unknown))}"
            )
        if item["key"] in item["depends_on_keys"]:
            raise ValueError(f"work item {item['key']} cannot depend on itself")

    graph = {item["key"]: item["depends_on_keys"] for item in normalized}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(key: str) -> None:
        if key in visiting:
            raise ValueError("work item dependencies must be acyclic")
        if key in visited:
            return
        visiting.add(key)
        for dependency in graph[key]:
            visit(dependency)
        visiting.remove(key)
        visited.add(key)

    for key in graph:
        visit(key)

    finals = [
        item
        for item in normalized
        if item["final_delivery"] and item["output_type"] == "content_package_v1"
    ]
    if len(finals) != 1:
        raise ValueError(
            "brief must contain exactly one final content_package_v1 work item"
        )
    if any(
        item["final_delivery"] or item["output_type"] == "content_package_v1"
        for item in normalized
        if item is not finals[0]
    ):
        raise ValueError("only the final delivery may use content_package_v1")
    return normalized


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
    work_items: list[dict] | None = None,
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
        "SELECT id, kind FROM conversations WHERE id = ? AND workspace_id = ?",
        (discussion_conversation_id, workspace_id),
    ).fetchone()
    if conversation is None:
        raise ValueError("conversation not found")

    member_rows = conn.execute(
        "SELECT agent_id FROM conversation_members WHERE conversation_id = ?",
        (discussion_conversation_id,),
    ).fetchall()
    allowed_agent_ids = {row["agent_id"] for row in member_rows}
    if conversation["kind"] == "dm":
        dm = conn.execute(
            "SELECT agent_id FROM conversations WHERE id = ?",
            (discussion_conversation_id,),
        ).fetchone()
        if dm and dm["agent_id"]:
            allowed_agent_ids.add(dm["agent_id"])
    participants = list(dict.fromkeys(participant_agent_ids or allowed_agent_ids))
    if not set(participants).issubset(allowed_agent_ids):
        raise ValueError("participant_agent_ids must be conversation members")
    normalized_work_items = validate_work_items(
        work_items or [], allowed_agent_ids=allowed_agent_ids
    )

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
    participant_json = json.dumps(participants, ensure_ascii=False)
    work_items_json = json.dumps(normalized_work_items, ensure_ascii=False)

    conn.execute(
        """
        INSERT INTO consensus_briefs (
          id, workspace_id, discussion_conversation_id, status,
          goal, scope, constraints, success_criteria,
          owner_agent_id, participant_agent_ids_json, work_items_json, created_by_agent_id,
          supersedes_brief_id, derived_from_brief_id, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            work_items_json,
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
        "work_items": json.loads(row.get("work_items_json") or "[]"),
        "created_by_agent_id": row["created_by_agent_id"],
        "supersedes_brief_id": row["supersedes_brief_id"],
        "derived_from_brief_id": row["derived_from_brief_id"],
        "created_at": row["created_at"],
        "confirmed_at": row["confirmed_at"],
        "confirmed_by_user_id": row["confirmed_by_user_id"],
    }
