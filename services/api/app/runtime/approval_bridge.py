"""In-process suspend/resume bridge for run approvals (TD-03-T4).

When a Hermes run hits a high-risk action (or pauses to ask a question), the ACP
``request_permission`` callback awaits a Future registered here; a separate
``/approvals/{id}/resolve`` (or ``/answer``) request sets that Future, unblocking
the *same* in-flight run so it resumes. Single uvicorn process only (the desktop
deployment) — the registry is module-level and the run state lives in the ACP
subprocess, so resume must wake the live coroutine, not re-invoke Hermes.

The resolve request runs in a threadpool (sync route), so it wakes the Future
via ``call_soon_threadsafe`` on the loop that created it.
"""

from __future__ import annotations

import asyncio

_pending: dict[str, asyncio.Future] = {}


def register_pending(approval_id: str) -> asyncio.Future:
    """Create + register a Future for an approval, on the running loop."""
    fut: asyncio.Future = asyncio.get_running_loop().create_future()
    _pending[approval_id] = fut
    return fut


async def await_decision(approval_id: str) -> str:
    """Suspend until the owner resolves ``approval_id``; return the decision string.

    Used by the permission resolver inside HermesBackend: registering here and
    awaiting keeps the ACP session (and thus the run) paused in place.
    """
    fut = register_pending(approval_id)
    try:
        return await fut
    finally:
        discard_pending(approval_id)


def resolve_pending(approval_id: str, decision: str) -> bool:
    """Wake a suspended run with ``decision`` (thread-safe). True if one waited."""
    fut = _pending.get(approval_id)
    if fut is None or fut.done():
        return False
    fut.get_loop().call_soon_threadsafe(_safe_set, fut, decision)
    return True


def _safe_set(fut: asyncio.Future, value: str) -> None:
    if not fut.done():
        fut.set_result(value)


def discard_pending(approval_id: str) -> None:
    _pending.pop(approval_id, None)


def has_pending(approval_id: str) -> bool:
    fut = _pending.get(approval_id)
    return fut is not None and not fut.done()
