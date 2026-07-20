"""RunService — drive a Hermes run, persist it, and stream it (TD-03-T3/T4).

``stream_agent_run`` consumes a backend's ``AgentEvent`` stream (``HermesBackend``
in prod, a fake in tests), records the run lifecycle + ``run_steps`` (TD-03-T1),
writes the aggregated agent reply back as a message, and yields route-shaped
events (``{"type": "chunk"|"message"|...}``) so the SSE hot path can stream
Hermes output exactly like the temporary DeepSeek path did. ``start_run`` drains
it for non-streaming callers.

Message/thinking deltas are buffered and stored once per turn (not per delta);
tool activity + approvals get one step each — matching the run_steps design.

TD-03-T4 suspension: when a Hermes backend fires ``request_permission`` it emits
an ``approval_required`` event; ``stream_agent_run`` persists an ``approvals`` row
(via ``_persist_run_approval``) and transitions the run to ``waiting_user`` /
``waiting_clarify``, while the injected ``make_bridge_resolver`` awaits an
``approval_bridge`` Future. The ``/approvals/{id}/resolve`` (or ``/answer``) HTTP
endpoint wakes that Future, and the resolver returns ``allow_once`` / ``deny`` to
the ACP callback — all without dropping the run's ACP connection across requests.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
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


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class RunBackend(Protocol):
    def run(self, ctx: RunContext, *, permission_resolver: Any = None): ...


def make_bridge_resolver(conn: Database | None = None):
    """Permission resolver that suspends the run until the owner resolves it.

    Registers a Future on the in-process approval bridge keyed by the request's
    approval_id and awaits it, so the ACP session (and the run) stays paused in
    place. Returns the owner's decision string ("allow_once" | "deny").

    ADR 0008 item 4: if the owner never answers, ``await_decision`` resolves to
    the "expired" sentinel once our own timeout elapses (comfortably before
    Hermes's own hardcoded 60s ACP fail-close). When that happens — and only
    if a ``conn`` was supplied — mark the pending approvals row 'expired'
    instead of leaving it stuck at 'pending' forever with no record of what
    happened; ACP still gets a plain "deny" either way.
    """
    from app.runtime.approval_bridge import await_decision

    async def resolver(info: dict) -> str:
        decision = await await_decision(info["approval_id"])
        if decision == "expired":
            if conn is not None:
                conn.execute(
                    "UPDATE approvals SET status = 'expired', resolved_at = ? "
                    "WHERE id = ? AND status = 'pending'",
                    (_now_iso(), info["approval_id"]),
                )
                conn.commit()
            return "deny"
        return decision

    return resolver


def _persist_run_approval(
    conn: Database, *, approval_id: str, ctx: RunContext, run_id: str,
    category: str, payload: dict,
) -> None:
    """Insert a pending approval row keyed to this exact permission request."""
    import json as _json

    tool = payload.get("tool_call") or {}
    tool_name = str(tool.get("title") or tool.get("name") or "高风险动作")
    approval_payload: dict = {}
    if category == "clarification":
        # ADR 0008 §4/item 7: no real trigger source — the `clarify` toolset
        # was never exposed to the model over ACP, and the SOUL no longer
        # instructs agents to look for it (they just ask in normal chat
        # instead). Kept only so historical/seeded rows of this type still
        # render; a future business-tool gate (⑤, independent TD) could
        # reintroduce a real trigger here.
        title = "员工请求澄清"
        description = str(tool.get("question") or tool.get("text") or tool_name)
        approval_type, risk = "clarification", "low"
    elif category == "capability_upgrade":
        # TD-06-T2: agent hit a capability gap and asked to be upgraded.
        # ADR 0008 §5/item 7: same as above — SOUL no longer tells agents to
        # self-request this (no real `clarify` trigger existed anyway). The
        # real path is owner-initiated: see POST /api/agents/{id}/capabilities
        # in workspace.py, which calls execute_upgrade() directly without a
        # pending approval row. This branch stays for historical/seeded rows.
        title = "员工申请能力升级"
        description = str(tool.get("capability_description") or tool.get("text") or tool_name)
        approval_type, risk = "capability_upgrade", "medium"
        approval_payload = {
            "capability_description": description,
            "suggested_capability_key": tool.get("suggested_capability_key"),
        }
    else:
        title = f"高风险动作需确认：{tool_name}"
        description = str(tool.get("text") or tool_name)
        approval_type, risk = "high_risk", "high"
    conn.execute(
        """
        INSERT INTO approvals (
          id, workspace_id, task_id, conversation_id, agent_id,
          title, description, status, risk_level, type, run_id, payload_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?)
        """,
        (
            approval_id,
            ctx.workspace_id,
            ctx.task_id or None,
            ctx.conversation_id or None,
            ctx.agent_id or None,
            title,
            description,
            risk,
            approval_type,
            run_id,
            _json.dumps(approval_payload, ensure_ascii=False),
            _now_iso(),
        ),
    )


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

    # Build the approval suspension resolver (TD-03-T4) if not injected.
    # Uses make_bridge_resolver which only awaits the bridge — the
    # approval row + run transition are handled by _persist_run_approval
    # inside stream_agent_run's approval_required event handler.
    if permission_resolver is None and ctx.workspace_id and ctx.conversation_id:
        permission_resolver = make_bridge_resolver(conn)

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
