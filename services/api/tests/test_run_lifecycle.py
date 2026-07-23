"""Tests for the Run / RunStep data model + lifecycle (TD-03-T1).

Covers:
- runs status state machine (legal + illegal transitions, terminal stamping)
- run_steps append + incremental listing
- schema migration: init_db adds the new columns / run_steps table (idempotent)
"""

import sqlite3

import pytest

from app.core.config import settings
from app.core.database import Database, connect, init_db
from app.runtime.runs import (
    ALLOWED_TRANSITIONS,
    RunStateError,
    RunStatus,
    RunStepType,
    append_run_step,
    create_run,
    get_run,
    list_run_steps,
    transition_run,
)


def _make_db() -> Database:
    """In-memory SQLite mirroring the final runs/run_steps/approvals schema.

    Foreign keys are left disabled so lifecycle logic can be tested without
    seeding parent workspace/conversation/agent rows.
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db = Database(conn, "sqlite")
    db.executescript(
        """
        CREATE TABLE runs (
            id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL,
            conversation_id TEXT NOT NULL,
            agent_id TEXT NOT NULL,
            task_id TEXT,
            status TEXT NOT NULL,
            input_message_id TEXT,
            output_message_id TEXT,
            hermes_profile_id TEXT,
            hermes_run_id TEXT,
            workdir TEXT,
            provider TEXT NOT NULL DEFAULT 'hermes',
            model TEXT NOT NULL DEFAULT '',
            usage_json TEXT NOT NULL DEFAULT '{}',
            error TEXT NOT NULL DEFAULT '',
            attempt_no INTEGER NOT NULL DEFAULT 1,
            lease_owner TEXT,
            lease_expires_at TEXT,
            started_at TEXT,
            created_at TEXT NOT NULL,
            completed_at TEXT
        );
        CREATE TABLE run_steps (
            id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT '',
            title TEXT NOT NULL DEFAULT '',
            detail TEXT NOT NULL DEFAULT '',
            payload_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL
        );
        """
    )
    return db


def _new_run(db: Database, status: str = RunStatus.QUEUED) -> str:
    return create_run(
        db,
        workspace_id="ws_1",
        conversation_id="conv_1",
        agent_id="agent_1",
        input_message_id="msg_1",
        task_id="task_1",
        hermes_profile_id="profile_1",
        workdir="/abs/agents/profile_1/work/runs/run_1",
        status=status,
    )


# --- Run creation + state machine ---

class TestCreateRun:
    def test_creates_queued_run_with_fields(self):
        db = _make_db()
        run_id = _new_run(db)
        run = get_run(db, run_id)
        assert run is not None
        assert run["status"] == RunStatus.QUEUED
        assert run["task_id"] == "task_1"
        assert run["hermes_profile_id"] == "profile_1"
        assert run["workdir"].startswith("/abs/")
        assert run["completed_at"] is None

    def test_invalid_initial_status_raises(self):
        db = _make_db()
        with pytest.raises(RunStateError):
            create_run(
                db,
                workspace_id="ws_1",
                conversation_id="conv_1",
                agent_id="agent_1",
                input_message_id="msg_1",
                status="bogus",
            )


class TestTransitionRun:
    def test_full_happy_path(self):
        db = _make_db()
        run_id = _new_run(db)
        assert transition_run(db, run_id, RunStatus.RUNNING)["status"] == RunStatus.RUNNING
        assert (
            transition_run(db, run_id, RunStatus.WAITING_USER)["status"]
            == RunStatus.WAITING_USER
        )
        # resume after approval
        assert transition_run(db, run_id, RunStatus.RUNNING)["status"] == RunStatus.RUNNING
        done = transition_run(db, run_id, RunStatus.COMPLETED)
        assert done["status"] == RunStatus.COMPLETED
        assert done["completed_at"] is not None

    def test_clarify_branch(self):
        db = _make_db()
        run_id = _new_run(db)
        transition_run(db, run_id, RunStatus.RUNNING)
        transition_run(db, run_id, RunStatus.WAITING_CLARIFY)
        resumed = transition_run(db, run_id, RunStatus.RUNNING)
        assert resumed["status"] == RunStatus.RUNNING

    def test_illegal_transition_raises(self):
        db = _make_db()
        run_id = _new_run(db)
        # queued -> completed is not allowed (must run first)
        with pytest.raises(RunStateError):
            transition_run(db, run_id, RunStatus.COMPLETED)

    def test_terminal_states_have_no_exits(self):
        db = _make_db()
        run_id = _new_run(db)
        transition_run(db, run_id, RunStatus.RUNNING)
        transition_run(db, run_id, RunStatus.FAILED)
        assert ALLOWED_TRANSITIONS[RunStatus.FAILED] == set()
        with pytest.raises(RunStateError):
            transition_run(db, run_id, RunStatus.RUNNING)

    def test_failure_records_error(self):
        db = _make_db()
        run_id = _new_run(db)
        transition_run(db, run_id, RunStatus.RUNNING)
        failed = transition_run(db, run_id, RunStatus.FAILED, error="hermes timeout")
        assert failed["status"] == RunStatus.FAILED
        assert failed["error"] == "hermes timeout"
        assert failed["completed_at"] is not None

    def test_same_status_is_noop(self):
        db = _make_db()
        run_id = _new_run(db, status=RunStatus.RUNNING)
        run = transition_run(db, run_id, RunStatus.RUNNING)
        assert run["status"] == RunStatus.RUNNING

    def test_unknown_run_raises(self):
        db = _make_db()
        with pytest.raises(RunStateError):
            transition_run(db, "nope", RunStatus.RUNNING)


# --- Run steps ---

class TestRunSteps:
    def test_append_and_list_in_order(self):
        db = _make_db()
        run_id = _new_run(db)
        append_run_step(db, run_id=run_id, type=RunStepType.THINKING, detail="想一想")
        append_run_step(
            db, run_id=run_id, type=RunStepType.TOOL_CALL, title="web.search",
            payload={"query": "增长"},
        )
        append_run_step(db, run_id=run_id, type=RunStepType.FINAL, detail="done")

        steps = list_run_steps(db, run_id)
        assert [s["type"] for s in steps] == ["thinking", "tool_call", "final"]
        assert steps[1]["payload"] == {"query": "增长"}

    def test_incremental_after_step_id(self):
        db = _make_db()
        run_id = _new_run(db)
        first = append_run_step(db, run_id=run_id, type=RunStepType.MESSAGE, detail="a")
        append_run_step(db, run_id=run_id, type=RunStepType.MESSAGE, detail="b")

        rest = list_run_steps(db, run_id, after_step_id=first)
        assert [s["detail"] for s in rest] == ["b"]

    def test_invalid_step_type_raises(self):
        db = _make_db()
        run_id = _new_run(db)
        with pytest.raises(RunStateError):
            append_run_step(db, run_id=run_id, type="bogus")


# --- Schema migration (real init_db against a temp sqlite) ---

def _columns(db: Database, table: str) -> set[str]:
    rows = db.execute(f"PRAGMA table_info({table})").fetchall()
    return {row["name"] for row in rows}


def test_init_db_applies_td03_schema(tmp_path, monkeypatch):
    monkeypatch.setattr(
        settings, "database_url", f"sqlite:///{tmp_path / 'agentpulse.sqlite3'}"
    )
    # Idempotent: running twice must not error (ensure_column guards duplicates).
    init_db()
    init_db()

    db = connect()
    try:
        run_cols = _columns(db, "runs")
        assert {"task_id", "hermes_profile_id", "hermes_run_id", "workdir"} <= run_cols
        assert _columns(db, "run_steps") == {
            "id",
            "run_id",
            "type",
            "status",
            "title",
            "detail",
            "payload_json",
            "created_at",
        }
        assert {"run_id", "type"} <= _columns(db, "approvals")
        assert "hermes_gateway_port" in _columns(db, "agents")
    finally:
        db.close()
