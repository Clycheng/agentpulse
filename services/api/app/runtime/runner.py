"""RunService — drive a Hermes run and persist it (TD-03-T3, write half).

Consumes the ``AgentEvent`` stream from a backend (``HermesBackend`` in prod, a
fake in tests), records the run lifecycle + ``run_steps`` (TD-03-T1), and writes
the aggregated agent reply back as a message. Message/thinking chunks are
buffered and stored once per turn (not per delta); tool activity gets one step
each — matching the run_steps design in TD-03.

Not yet wired into the live discussion/reply hot path (that swap is the second
half of TD-03-T3); this is the standalone, testable execution+persistence core.
"""

from __future__ import annotations

from typing import Any, Protocol

from app.core.database import Database
from app.runtime.hermes_client import AgentEvent, RunContext
from app.runtime.runs import (
    RunStatus,
    RunStepType,
    append_run_step,
    create_run,
    transition_run,
)
from app.services.workspace import add_message


class RunBackend(Protocol):
    def run(self, ctx: RunContext, *, permission_resolver: Any = None): ...


def _chunk_text(payload: dict) -> str:
    content = payload.get("content") or {}
    if isinstance(content, dict):
        return content.get("text", "") or ""
    return ""


async def start_run(
    conn: Database,
    *,
    ctx: RunContext,
    backend: RunBackend,
    input_message_id: str,
    permission_resolver: Any = None,
    persist_message: bool = True,
) -> dict:
    """Create a run, drive the backend, persist steps + the final reply.

    Returns {run_id, message_id, text, status}.
    """
    run_id = create_run(
        conn,
        workspace_id=ctx.workspace_id,
        conversation_id=ctx.conversation_id,
        agent_id=ctx.agent_id,
        input_message_id=input_message_id,
        task_id=ctx.task_id or None,
        hermes_profile_id=ctx.profile,
        workdir=ctx.workdir,
        provider="hermes",
        status=RunStatus.QUEUED,
    )
    ctx.run_id = run_id
    transition_run(conn, run_id, RunStatus.RUNNING)
    conn.commit()

    message_parts: list[str] = []
    thought_parts: list[str] = []
    usage: dict = {}
    error: str | None = None

    try:
        async for event in backend.run(ctx, permission_resolver=permission_resolver):
            etype = event.type
            if etype == "message":
                message_parts.append(_chunk_text(event.payload))
            elif etype == "thinking":
                thought_parts.append(_chunk_text(event.payload))
            elif etype == "tool_call":
                append_run_step(
                    conn,
                    run_id=run_id,
                    type=RunStepType.TOOL_CALL,
                    title=str(event.payload.get("title", "")),
                    payload=event.payload,
                )
            elif etype == "tool_result":
                append_run_step(
                    conn,
                    run_id=run_id,
                    type=RunStepType.TOOL_RESULT,
                    payload=event.payload,
                )
            elif etype == "approval_required":
                append_run_step(
                    conn,
                    run_id=run_id,
                    type=RunStepType.APPROVAL_REQUIRED,
                    payload=event.payload,
                )
            elif etype == "usage":
                usage = event.payload
            elif etype == "error":
                error = str(event.payload.get("detail", "unknown error"))
    except Exception as exc:  # backend/transport failure
        error = str(exc)

    # Aggregate buffered thinking + message into single steps (per-turn, not per-delta).
    thought = "".join(thought_parts).strip()
    if thought:
        append_run_step(
            conn, run_id=run_id, type=RunStepType.THINKING, detail=thought[:4000]
        )

    text = "".join(message_parts).strip()
    message_id: str | None = None
    if text:
        append_run_step(
            conn, run_id=run_id, type=RunStepType.MESSAGE, detail=text[:4000]
        )
        if persist_message and ctx.conversation_id:
            msg = add_message(
                conn,
                conversation_id=ctx.conversation_id,
                sender_type="agent",
                sender_id=ctx.agent_id,
                content=text,
                provider="hermes",
                model="",
            )
            message_id = msg["id"]

    final_status = RunStatus.FAILED if error else RunStatus.COMPLETED
    append_run_step(
        conn,
        run_id=run_id,
        type=RunStepType.FINAL,
        status=final_status,
        payload={"usage": usage, "error": error} if (usage or error) else {},
    )
    transition_run(
        conn,
        run_id,
        final_status,
        error=error,
        output_message_id=message_id,
    )
    conn.commit()
    return {
        "run_id": run_id,
        "message_id": message_id,
        "text": text,
        "status": final_status,
    }
