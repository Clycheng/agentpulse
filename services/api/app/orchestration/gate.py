"""Task creation gate.

Enforces the structural requirement that Task creation must have
a confirmed consensus brief. This is the core lesson from ADR 0005:
"Discussion alignment must be enforced structurally, not by SOUL.md rules."

The gate can be bypassed when the task is created directly by the owner
(via agent action tool) — only enforced in group discussion workflows.
"""

from __future__ import annotations

from app.core.database import Database


class TaskCreationGateError(Exception):
    """Raised when task creation fails gate validation."""
    pass


def validate_task_creation_gate(
    conn: Database,
    *,
    workspace_id: str,
    consensus_brief_id: str | None,
    parent_task_id: str | None = None,
    bypass_gate: bool = False,
) -> dict | None:
    """Validate that task creation is allowed.

    Gate rules:
    1. If bypass_gate=True — always allow (agent action tool, owner directive)
    2. If consensus_brief_id is provided:
       - Brief must exist in workspace
       - Brief must be in 'confirmed' status
    3. If consensus_brief_id is None AND parent_task_id is provided:
       - Allow (sub-task inherits parent's brief)
    4. If consensus_brief_id is None AND parent_task_id is None:
       - Reject (no brief, no parent)

    Args:
        conn: Database connection
        workspace_id: Workspace ID
        consensus_brief_id: Brief ID (can be None for sub-tasks)
        parent_task_id: Parent task ID (for sub-tasks)
        bypass_gate: If True, skip all validation (agent action tools)

    Returns:
        Brief dict if validation passes, None if inheriting from parent

    Raises:
        TaskCreationGateError: If validation fails
    """
    # Agent action tools: owner directly told the agent to create a task
    if bypass_gate:
        return None

    # Case 1: No brief, no parent - reject
    if consensus_brief_id is None and parent_task_id is None:
        raise TaskCreationGateError(
            "Task creation requires a confirmed consensus_brief_id, "
            "or parent_task_id for sub-tasks that inherit brief."
        )

    # Case 2: No brief but has parent - allow (inherit)
    if consensus_brief_id is None:
        # Validate parent exists
        parent = conn.execute(
            "SELECT id FROM tasks WHERE id = ? AND workspace_id = ?",
            (parent_task_id, workspace_id),
        ).fetchone()
        if parent is None:
            raise TaskCreationGateError(f"parent_task not found: {parent_task_id}")
        return None

    # Case 3: Has brief - validate
    brief = conn.execute(
        "SELECT * FROM consensus_briefs WHERE id = ? AND workspace_id = ?",
        (consensus_brief_id, workspace_id),
    ).fetchone()
    if brief is None:
        raise TaskCreationGateError(f"consensus_brief not found: {consensus_brief_id}")

    if brief["status"] != "confirmed":
        raise TaskCreationGateError(
            f"consensus_brief must be in 'confirmed' status, "
            f"current: {brief['status']}. "
            "Owner must confirm the brief before creating tasks."
        )

    return {
        "id": brief["id"],
        "goal": brief["goal"],
        "status": brief["status"],
    }
