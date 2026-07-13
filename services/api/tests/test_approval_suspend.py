"""Tests for TD-03-T4: approval suspend/resume via permission_resolver.

Tests that ``_make_approval_resolver`` creates an ``approvals`` row, transitions
the run to ``waiting_user``, blocks on an ``approval_bridge`` Future, and
unblocks with the correct decision when ``resolve_pending`` is called.
See [TD-03-T4](../../docs/tech-design/TD-03-hermes-execution.md).
"""

import asyncio
import sqlite3

import pytest

from app.core.database import Database
from app.runtime.runner import _make_approval_resolver, stream_agent_run
from app.runtime.approval_bridge import resolve_pending, has_pending, discard_pending
from app.runtime.hermes_client import AgentEvent, RunContext


def _db() -> Database:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db = Database(conn, "sqlite")
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, kind TEXT NOT NULL DEFAULT 'group',
            name TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL DEFAULT '', unread INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL, sender_type TEXT NOT NULL,
            sender_id TEXT NOT NULL DEFAULT '', content TEXT NOT NULL,
            provider TEXT, model TEXT, created_at TEXT NOT NULL, external_message_id TEXT
        );
        CREATE TABLE IF NOT EXISTS runs (
            id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, conversation_id TEXT NOT NULL,
            agent_id TEXT NOT NULL, task_id TEXT, status TEXT NOT NULL, input_message_id TEXT NOT NULL,
            output_message_id TEXT, hermes_profile_id TEXT, hermes_run_id TEXT, workdir TEXT,
            provider TEXT NOT NULL DEFAULT 'hermes', model TEXT NOT NULL DEFAULT '',
            usage_json TEXT NOT NULL DEFAULT '{}', error TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL, completed_at TEXT
        );
        CREATE TABLE IF NOT EXISTS run_steps (
            id TEXT PRIMARY KEY, run_id TEXT NOT NULL, type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT '', title TEXT NOT NULL DEFAULT '',
            detail TEXT NOT NULL DEFAULT '', payload_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS approvals (
            id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, task_id TEXT,
            conversation_id TEXT, agent_id TEXT, title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'pending',
            risk_level TEXT NOT NULL DEFAULT 'medium', run_id TEXT,
            type TEXT NOT NULL DEFAULT 'high_risk',
            resolved_by TEXT NOT NULL DEFAULT '', resolved_at TEXT,
            created_at TEXT NOT NULL
        );
        INSERT INTO conversations (id, workspace_id, name, updated_at)
        VALUES ('conv_1', 'ws_1', 'g', '2026-01-01T00:00:00');
        INSERT INTO conversations (id, workspace_id, name, updated_at)
        VALUES ('conv_2', 'ws_1', 'g2', '2026-01-01T00:00:00');
        """
    )
    return db


def _insert_run(db: Database, run_id: str, status: str = "running") -> None:
    db.execute(
        """INSERT INTO runs
           (id, workspace_id, conversation_id, agent_id, task_id, status,
            input_message_id, provider, created_at, workdir)
           VALUES (?, 'ws_1', 'conv_1', 'agent_1', NULL, ?,
                   'msg_1', 'hermes', '2026-01-01T00:00:00', '/tmp/ap')""",
        (run_id, status),
    )


class _PermBackend:
    """Fake backend that emits an approval_required event then calls the resolver."""

    async def run(self, ctx, *, permission_resolver=None):
        yield AgentEvent("thinking", {"content": {"text": "thinking..."}})
        yield AgentEvent("message", {"content": {"text": "About to publish"}})
        # Emit an approval_required event (stream_agent_run persists + transitions)
        yield AgentEvent(
            "approval_required",
            {"approval_id": "appr_stream", "category": "high_risk",
             "tool_call": {"title": "deploy"}},
        )
        # Now call the resolver so it blocks until resolved (simulates ACP flow)
        if permission_resolver is not None:
            decision = await permission_resolver(
                {"approval_id": "appr_stream", "category": "high_risk"}
            )
            yield AgentEvent(
                "tool_result",
                {
                    "title": "deploy",
                    "content": {
                        "text": "done" if str(decision).startswith("allow") else "blocked"
                    },
                },
            )
        yield AgentEvent("message", {"content": {"text": "All done"}})
        yield AgentEvent("final", {"stop_reason": "end_turn"})


# ---------------------------------------------------------------------------
# Unit tests for the resolver in isolation
# ---------------------------------------------------------------------------


def test_resolver_creates_approval_and_blocks():
    """Calling resolver creates an approval row + transitions run to waiting_user."""

    async def _run():
        db = _db()
        _insert_run(db, "run_u1")

        resolver = _make_approval_resolver(
            db,
            run_id="run_u1",
            workspace_id="ws_1",
            conversation_id="conv_1",
            agent_id="agent_1",
            task_id=None,
        )

        # Fire the resolver in the background; it blocks on a Future.
        resolve_task = asyncio.create_task(
            resolver({"title": "publish", "tool": "deploy"})
        )

        await asyncio.sleep(0.05)

        # The resolver should have created an approval and set run=waiting_user.
        appr = db.execute(
            "SELECT * FROM approvals WHERE run_id = 'run_u1'"
        ).fetchone()
        assert appr is not None, "approval row must exist"
        assert appr["status"] == "pending"
        assert appr["type"] == "high_risk"
        assert has_pending(appr["id"])

        run = db.execute("SELECT status FROM runs WHERE id = 'run_u1'").fetchone()
        assert run["status"] == "waiting_user"

        # Wake the resolver with approved.
        resolve_pending(appr["id"], "approved")
        result = await resolve_task
        assert result == "allow_once", f"expected allow_once, got {result}"

        # Run should be back to running.
        run = db.execute("SELECT status FROM runs WHERE id = 'run_u1'").fetchone()
        assert run["status"] == "running"

        discard_pending(appr["id"])

    asyncio.run(_run())


def test_resolver_reject_returns_deny():
    """Rejected permission: resolver returns deny, run completes."""

    async def _run():
        db = _db()
        _insert_run(db, "run_r1")

        resolver = _make_approval_resolver(
            db,
            run_id="run_r1",
            workspace_id="ws_1",
            conversation_id="conv_1",
            agent_id="agent_1",
            task_id=None,
        )

        resolve_task = asyncio.create_task(
            resolver({"title": "publish", "tool": "deploy"})
        )

        await asyncio.sleep(0.05)

        appr = db.execute(
            "SELECT * FROM approvals WHERE run_id = 'run_r1'"
        ).fetchone()
        assert appr is not None

        resolve_pending(appr["id"], "rejected")
        result = await resolve_task
        assert result == "deny", f"expected deny, got {result}"

        discard_pending(appr["id"])

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Integration with stream_agent_run
# ---------------------------------------------------------------------------


def test_stream_approval_suspend_resume():
    """stream_agent_run auto-builds resolver; approval created, resolved, run completes."""

    async def _run():
        db = _db()
        ctx = RunContext(
            run_id="",
            prompt="Do something risky",
            workdir="/tmp/ap-test",
            profile="test",
            agent_id="agent_1",
            workspace_id="ws_1",
            conversation_id="conv_1",
        )

        backend = _PermBackend()

        async def resolve_during_run():
            await asyncio.sleep(0.15)
            appr = db.execute(
                "SELECT * FROM approvals WHERE workspace_id='ws_1'"
            ).fetchone()
            if appr is None:
                await asyncio.sleep(0.2)
                appr = db.execute(
                    "SELECT * FROM approvals WHERE workspace_id='ws_1'"
                ).fetchone()
            assert appr is not None, "expected an approval to be created"
            # The approval should be persisted by _persist_run_approval
            assert appr["type"] == "high_risk"
            # The resolver is blocked on approval_bridge via make_bridge_resolver
            from app.runtime.approval_bridge import has_pending, resolve_pending, discard_pending

            assert has_pending(appr["id"]), "expected pending in bridge"
            resolve_pending(appr["id"], "allow_once")
            discard_pending(appr["id"])

        async def consume():
            events = []
            async for ev in stream_agent_run(
                db,
                ctx=ctx,
                backend=backend,
                input_message_id="msg_u",
                persist_message=False,
            ):
                events.append(ev["type"])
            return events

        stream_task = asyncio.create_task(consume())
        resolve_task = asyncio.create_task(resolve_during_run())
        done, _ = await asyncio.wait(
            {stream_task, resolve_task}, timeout=10,
            return_when=asyncio.ALL_COMPLETED,
        )

        assert stream_task in done, "stream_agent_run should have completed"
        event_types = stream_task.result()
        assert "message" in event_types
        run = db.execute("SELECT * FROM runs WHERE id = ?", (ctx.run_id,)).fetchone()
        assert run is not None
        assert run["status"] == "completed"
        appr = db.execute(
            "SELECT * FROM approvals WHERE run_id = ?", (ctx.run_id,)
        ).fetchone()
        assert appr is not None
        assert appr["type"] == "high_risk"

    asyncio.run(_run())
