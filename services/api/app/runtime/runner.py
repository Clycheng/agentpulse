"""RunService — drive a Hermes run, persist it, and stream it (TD-03-T3).

``stream_agent_run`` consumes a backend's ``AgentEvent`` stream (``HermesBackend``
in prod, a fake in tests), records the run lifecycle + ``run_steps`` (TD-03-T1),
writes the aggregated agent reply back as a message, and yields route-shaped
events (``{"type": "chunk"|"message"|...}``) so the SSE hot path can stream
Hermes output exactly like the temporary DeepSeek path did. ``start_run`` drains
it for non-streaming callers.

Message/thinking deltas are buffered and stored once per turn (not per delta);
tool activity + approvals get one step each — matching the run_steps design.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol

from app.core.database import Database
from app.runtime.hermes_client import RunContext
from app.runtime.runs import (
    RunStatus,
    RunStepType,
    append_run_step,
    create_run,
    get_run,
    transition_run,
)
from app.services.workspace import add_message


class RunBackend(Protocol):
    def run(self, ctx: RunContext, *, permission_resolver: Any = None): ...


def make_bridge_resolver():
    """Permission resolver that suspends the run until the owner resolves it.

    Registers a Future on the in-process approval bridge keyed by the request's
    approval_id and awaits it, so the ACP session (and the run) stays paused in
    place. Returns the owner's decision string ("allow_once" | "deny").
    """
    from app.runtime.approval_bridge import await_decision

    async def resolver(info: dict) -> str:
        return await await_decision(info["approval_id"])

    return resolver


def _persist_run_approval(
    conn: Database, *, approval_id: str, ctx: RunContext, run_id: str,
    category: str, payload: dict,
) -> None:
    """Insert a pending approval row keyed to this exact permission request."""
    tool = payload.get("tool_call") or {}
    tool_name = str(tool.get("title") or tool.get("name") or "高风险动作")
    if category == "clarification":
        title = "员工请求澄清"
        description = str(tool.get("question") or tool.get("text") or tool_name)
    else:
        title = f"高风险动作需确认：{tool_name}"
        description = str(tool.get("text") or tool_name)
    conn.execute(
        """
        INSERT INTO approvals (
          id, workspace_id, task_id, conversation_id, agent_id,
          title, description, status, risk_level, type, run_id, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?)
        """,
        (
            approval_id,
            ctx.workspace_id,
            ctx.task_id or None,
            ctx.conversation_id or None,
            ctx.agent_id or None,
            title,
            description,
            "high" if category != "clarification" else "low",
            "clarification" if category == "clarification" else "high_risk",
            run_id,
            _now_iso(),
        ),
    )


def _now_iso() -> str:
    from app.services.workspace import now_iso

    return now_iso()


def resolve_hermes_profile(conn: Database, agent_id: str) -> str | None:
    """Return the ready Hermes profile for an agent, or None (→ DeepSeek fallback)."""
    row = conn.execute(
        "SELECT hermes_profile, status FROM agent_specs WHERE agent_id = ?",
        (agent_id,),
    ).fetchone()
    if row and row["hermes_profile"] and row["status"] == "ready":
        return row["hermes_profile"]
    return None


def _chunk_text(payload: dict) -> str:
    content = payload.get("content") or {}
    if isinstance(content, dict):
        return content.get("text", "") or ""
    return ""


async def stream_agent_run(
    conn: Database,
    *,
    ctx: RunContext,
    backend: RunBackend,
    input_message_id: str,
    permission_resolver: Any = None,
    persist_message: bool = True,
) -> AsyncIterator[dict]:
    """Drive one run, persist run_steps + the reply, and yield route events.

    Yields dicts shaped for the SSE route:
      {"type": "chunk", "content": str}      per message delta
      {"type": "tool_call"|"tool_result"|"approval_required", "payload": dict}
      {"type": "message", "message": <row|None>}   once, at the end
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
                text = _chunk_text(event.payload)
                if text:
                    message_parts.append(text)
                    yield {"type": "chunk", "content": text}
            elif etype == "thinking":
                thought_parts.append(_chunk_text(event.payload))
            elif etype == "tool_call":
                append_run_step(
                    conn, run_id=run_id, type=RunStepType.TOOL_CALL,
                    title=str(event.payload.get("title", "")), payload=event.payload,
                )
                yield {"type": "tool_call", "payload": event.payload}
            elif etype == "tool_result":
                append_run_step(
                    conn, run_id=run_id, type=RunStepType.TOOL_RESULT,
                    payload=event.payload,
                )
                yield {"type": "tool_result", "payload": event.payload}
            elif etype == "approval_required":
                append_run_step(
                    conn, run_id=run_id, type=RunStepType.APPROVAL_REQUIRED,
                    payload=event.payload,
                )
                approval_id = event.payload.get("approval_id")
                category = event.payload.get("category", "high_risk")
                if approval_id:
                    # TD-03-T4: persist an approval and suspend the run; the ACP
                    # session stays paused (resolver awaits the bridge) until the
                    # owner resolves, which resumes this same run in place.
                    _persist_run_approval(
                        conn, approval_id=approval_id, ctx=ctx, run_id=run_id,
                        category=category, payload=event.payload,
                    )
                    waiting = (
                        RunStatus.WAITING_CLARIFY
                        if category == "clarification"
                        else RunStatus.WAITING_USER
                    )
                    transition_run(conn, run_id, waiting)
                    conn.commit()
                yield {"type": "approval_required", "payload": event.payload}
            elif etype == "usage":
                usage = event.payload
            elif etype == "error":
                error = str(event.payload.get("detail", "unknown error"))
    except Exception as exc:  # backend/transport failure
        error = str(exc)

    thought = "".join(thought_parts).strip()
    if thought:
        append_run_step(
            conn, run_id=run_id, type=RunStepType.THINKING, detail=thought[:4000]
        )

    text = "".join(message_parts).strip()
    message_row = None
    if text:
        append_run_step(
            conn, run_id=run_id, type=RunStepType.MESSAGE, detail=text[:4000]
        )
        if persist_message and ctx.conversation_id:
            message_row = add_message(
                conn,
                conversation_id=ctx.conversation_id,
                sender_type="agent",
                sender_id=ctx.agent_id,
                content=text,
                provider="hermes",
                model="",
            )

    final_status = RunStatus.FAILED if error else RunStatus.COMPLETED
    append_run_step(
        conn, run_id=run_id, type=RunStepType.FINAL, status=final_status,
        payload={"usage": usage, "error": error} if (usage or error) else {},
    )
    transition_run(
        conn, run_id, final_status, error=error,
        output_message_id=(message_row["id"] if message_row else None),
    )
    if final_status == RunStatus.COMPLETED and ctx.agent_id:
        # TD-06-T1: count completed runs toward skill reflection (a background
        # tick runs the actual, expensive reflection off the hot path).
        try:
            from app.runtime.reflection import bump_reflection_counter

            bump_reflection_counter(conn, ctx.agent_id)
        except Exception:
            pass
    conn.commit()
    yield {"type": "message", "message": message_row}


async def start_run(
    conn: Database,
    *,
    ctx: RunContext,
    backend: RunBackend,
    input_message_id: str,
    permission_resolver: Any = None,
    persist_message: bool = True,
) -> dict:
    """Non-streaming convenience: drain stream_agent_run, return a summary."""
    text_parts: list[str] = []
    message_id: str | None = None
    async for ev in stream_agent_run(
        conn,
        ctx=ctx,
        backend=backend,
        input_message_id=input_message_id,
        permission_resolver=permission_resolver,
        persist_message=persist_message,
    ):
        if ev["type"] == "chunk":
            text_parts.append(ev["content"])
        elif ev["type"] == "message" and ev.get("message"):
            message_id = ev["message"]["id"]
    run = get_run(conn, ctx.run_id)
    return {
        "run_id": ctx.run_id,
        "message_id": message_id,
        "text": "".join(text_parts).strip(),
        "status": run["status"] if run else RunStatus.FAILED,
    }
