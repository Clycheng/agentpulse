"""Tests for RunService.start_run (TD-03-T3 write half).

Always-on tests drive a fake backend to exercise run_steps aggregation +
message persistence + lifecycle. The guarded e2e drives real Hermes (ACP):

    HERMES_E2E=1 pytest tests/test_runner.py
"""

import asyncio
import os
import shutil
import sqlite3
import tempfile

import pytest

from app.core.database import Database
from app.runtime.hermes_client import AgentEvent, HermesBackend, RunContext
from app.runtime.runner import start_run


def _make_db() -> Database:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db = Database(conn, "sqlite")
    db.executescript(
        """
        CREATE TABLE conversations (
            id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, kind TEXT NOT NULL DEFAULT 'group',
            name TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL DEFAULT '', unread INTEGER DEFAULT 0
        );
        CREATE TABLE messages (
            id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL, sender_type TEXT NOT NULL,
            sender_id TEXT NOT NULL DEFAULT '', content TEXT NOT NULL,
            provider TEXT, model TEXT, created_at TEXT NOT NULL, external_message_id TEXT
        );
        CREATE TABLE runs (
            id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, conversation_id TEXT NOT NULL,
            agent_id TEXT NOT NULL, task_id TEXT, status TEXT NOT NULL, input_message_id TEXT,
            output_message_id TEXT, hermes_profile_id TEXT, hermes_run_id TEXT, workdir TEXT,
            provider TEXT NOT NULL DEFAULT 'hermes', model TEXT NOT NULL DEFAULT '',
            usage_json TEXT NOT NULL DEFAULT '{}', error TEXT NOT NULL DEFAULT '',
            attempt_no INTEGER NOT NULL DEFAULT 1, lease_owner TEXT,
            lease_expires_at TEXT, started_at TEXT,
            created_at TEXT NOT NULL, completed_at TEXT
        );
        CREATE TABLE run_steps (
            id TEXT PRIMARY KEY, run_id TEXT NOT NULL, type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT '', title TEXT NOT NULL DEFAULT '',
            detail TEXT NOT NULL DEFAULT '', payload_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL
        );
        INSERT INTO conversations (id, workspace_id, name, updated_at)
        VALUES ('conv_1', 'ws_1', 'g', '2026-01-01T00:00:00');
        """
    )
    return db


class _FakeBackend:
    def __init__(self, events):
        self._events = events

    async def run(self, ctx, *, permission_resolver=None):
        for ev in self._events:
            yield ev


def _ctx() -> RunContext:
    return RunContext(
        run_id="",
        prompt="hi",
        workdir="/tmp/ap-fake",
        profile="agentpulse",
        agent_id="agent_1",
        workspace_id="ws_1",
        conversation_id="conv_1",
    )


def test_start_run_aggregates_and_persists():
    db = _make_db()
    events = [
        AgentEvent("thinking", {"content": {"text": "let me "}}),
        AgentEvent("thinking", {"content": {"text": "think"}}),
        AgentEvent("tool_call", {"title": "web.search", "content": {}}),
        AgentEvent("message", {"content": {"text": "Hello "}}),
        AgentEvent("message", {"content": {"text": "world"}}),
        AgentEvent("usage", {"used": 123}),
        AgentEvent("final", {"stop_reason": "end_turn"}),
    ]
    result = asyncio.run(
        start_run(db, ctx=_ctx(), backend=_FakeBackend(events), input_message_id="msg_u")
    )
    assert result["status"] == "completed"
    assert result["text"] == "Hello world"
    assert result["message_id"] is not None

    # agent message persisted
    row = db.execute(
        "SELECT * FROM messages WHERE id = ?", (result["message_id"],)
    ).fetchone()
    assert row["content"] == "Hello world"
    assert row["sender_type"] == "agent"

    # run_steps: tool_call (mid-stream) + aggregated thinking + message + final
    steps = db.execute(
        "SELECT type, detail FROM run_steps WHERE run_id = ? ORDER BY created_at, id",
        (result["run_id"],),
    ).fetchall()
    types = [s["type"] for s in steps]
    assert set(types) == {"tool_call", "thinking", "message", "final"}
    thinking = next(s for s in steps if s["type"] == "thinking")
    assert thinking["detail"] == "let me think"  # aggregated

    # run row completed + linked to the output message
    run = db.execute("SELECT * FROM runs WHERE id = ?", (result["run_id"],)).fetchone()
    assert run["status"] == "completed"
    assert run["output_message_id"] == result["message_id"]
    assert run["completed_at"] is not None


def test_start_run_records_error_as_failed():
    db = _make_db()
    events = [AgentEvent("error", {"detail": "boom"})]
    result = asyncio.run(
        start_run(db, ctx=_ctx(), backend=_FakeBackend(events), input_message_id="msg_u")
    )
    assert result["status"] == "failed"
    run = db.execute("SELECT * FROM runs WHERE id = ?", (result["run_id"],)).fetchone()
    assert run["status"] == "failed"
    assert run["error"] == "boom"


_E2E = os.environ.get("HERMES_E2E") == "1" and shutil.which("hermes") is not None


@pytest.mark.skipif(not _E2E, reason="set HERMES_E2E=1 with hermes + agentpulse profile")
def test_start_run_real_hermes():
    db = _make_db()
    work = tempfile.mkdtemp(prefix="ap-runner-")
    ctx = RunContext(
        run_id="",
        prompt="Reply with exactly: OK",
        workdir=work,
        profile="agentpulse",
        agent_id="agent_1",
        workspace_id="ws_1",
        conversation_id="conv_1",
        timeout=120,
    )
    result = asyncio.run(
        start_run(db, ctx=ctx, backend=HermesBackend(), input_message_id="msg_u")
    )
    assert result["status"] == "completed"
    assert "OK" in result["text"]
    steps = db.execute(
        "SELECT type FROM run_steps WHERE run_id = ?", (result["run_id"],)
    ).fetchall()
    types = {s["type"] for s in steps}
    assert "message" in types and "final" in types
