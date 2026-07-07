"""Discussion state machine for conversations.

A conversation can be in one of two states:
- 'discussing': Active discussion, no consensus reached
- 'aligned': Consensus reached, brief confirmed

See ADR 0006 for design details.
"""

from __future__ import annotations

from app.core.database import Database


class DiscussionStatus:
    """Discussion status constants."""
    DISCUSSING = "discussing"
    ALIGNED = "aligned"
    VALID_STATES = (DISCUSSING, ALIGNED)


def get_discussion_status(conn: Database, conversation_id: str) -> str:
    """Get the discussion status of a conversation.

    Args:
        conn: Database connection
        conversation_id: Conversation ID

    Returns:
        Discussion status ('discussing' or 'aligned')
    """
    row = conn.execute(
        "SELECT discussion_status FROM conversations WHERE id = ?",
        (conversation_id,),
    ).fetchone()
    if row is None:
        raise ValueError("conversation not found")
    return row["discussion_status"] or DiscussionStatus.DISCUSSING


def set_discussion_status(
    conn: Database,
    conversation_id: str,
    status: str,
) -> None:
    """Set the discussion status of a conversation.

    Args:
        conn: Database connection
        conversation_id: Conversation ID
        status: New status ('discussing' or 'aligned')

    Raises:
        ValueError: If status is invalid or conversation not found
    """
    if status not in DiscussionStatus.VALID_STATES:
        raise ValueError(f"Invalid discussion status: {status}")

    existing = conn.execute(
        "SELECT id FROM conversations WHERE id = ?",
        (conversation_id,),
    ).fetchone()
    if existing is None:
        raise ValueError("conversation not found")

    conn.execute(
        "UPDATE conversations SET discussion_status = ? WHERE id = ?",
        (status, conversation_id),
    )