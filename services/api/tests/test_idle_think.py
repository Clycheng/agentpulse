"""Tests for IdleThinkService (TD-08-T2).

Always-on tests drive a fake backend to exercise idea parsing, due-agent
selection, and the reflection → ideas persistence + last_idle_think_at stamp.
A guarded e2e (HERMES_E2E=1) drives real Hermes.
"""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from app.core.config import settings
from app.core.database import connect, init_db
from app.runtime.hermes_client import AgentEvent
from app.runtime.idle_think import (
    find_due_idle_agents,
    parse_ideas,
    run_idle_tick,
    trigger_reflection,
)
from app.services.workspace import create_agent, create_workspace_for_user, new_id, now_iso


# ---------------------------------------------------------------- fake backend


class _FakeBackend:
    def __init__(self, events):
        self._events = events

    async def run(self, ctx, *, permission_resolver=None):
        for ev in self._events:
            yield ev


def _msg(text: str) -> AgentEvent:
    return AgentEvent("message", {"content": {"text": text}})


class _BoomBackend:
    async def run(self, ctx, *, permission_resolver=None):
        raise RuntimeError("transport died")
        yield  # pragma: no cover (makes this an async generator)


# ---------------------------------------------------------------- db helpers


def _setup_db(tmp_path, monkeypatch):
    monkeypatch.setattr(
        settings, "database_url", f"sqlite:///{tmp_path / 'idle.sqlite3'}"
    )
    init_db()
    conn = connect()
    user_id = new_id("user")
    conn.execute(
        "INSERT INTO users (id, email, password_hash, display_name, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (user_id, "boss@example.com", "x", "老板", now_iso()),
    )
    ws = create_workspace_for_user(conn, user_id, "测试公司")
    conn.commit()
    return conn, ws["id"]


def _dept_id(conn, ws_id):
    return conn.execute(
        "SELECT id FROM departments WHERE workspace_id = ? LIMIT 1", (ws_id,)
    ).fetchone()["id"]


def _add_agent_with_spec(
    conn,
    ws_id,
    *,
    name="阿伦",
    profile="p_arun",
    status="ready",
    enabled=1,
    interval=6,
    last_idle=None,
):
    agent_id = create_agent(
        conn,
        workspace_id=ws_id,
        department_id=_dept_id(conn, ws_id),
        name=name,
        role="内容主笔",
        description="",
        prompt="",
        skills=[],
        mcps=[],
    )
    conn.execute(
        """
        INSERT INTO agent_specs (
          id, agent_id, workspace_id, role_name, hermes_profile, status,
          idle_thinking_enabled, idle_think_interval_hours, last_idle_think_at,
          created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            new_id("spec"),
            agent_id,
            ws_id,
            "内容主笔",
            profile,
            status,
            enabled,
            interval,
            last_idle,
            now_iso(),
            now_iso(),
        ),
    )
    conn.commit()
    return agent_id


# ---------------------------------------------------------------- parse_ideas


def test_parse_ideas_plain_json():
    text = (
        '[{"title":"做开头模板","description":"前三句制造场景冲突",'
        '"category":"improvement"}]'
    )
    ideas = parse_ideas(text)
    assert len(ideas) == 1
    assert ideas[0]["category"] == "improvement"


def test_parse_ideas_strips_code_fence_and_prose():
    text = '好的，这是我的想法：\n```json\n[{"title":"蓝海词","description":"通勤效率","category":"opportunity"}]\n```'
    ideas = parse_ideas(text)
    assert len(ideas) == 1
    assert ideas[0]["title"] == "蓝海词"


def test_parse_ideas_filters_invalid_and_caps_and_clamps():
    text = (
        "["
        '{"title":"a","description":"d","category":"improvement"},'
        '{"title":"bad","description":"d","category":"nonsense"},'  # invalid cat
        '{"title":"","description":"d","category":"risk"},'          # empty title
        '{"title":"b","description":"d","category":"risk"},'
        '{"title":"c","description":"d","category":"learning"},'
        '{"title":"d","description":"d","category":"opportunity"}'   # 4th valid -> capped
        "]"
    )
    ideas = parse_ideas(text)
    assert len(ideas) == 3  # capped, invalids dropped
    assert all(i["category"] in {"improvement", "risk", "learning", "opportunity"} for i in ideas)


def test_parse_ideas_empty_and_garbage():
    assert parse_ideas("[]") == []
    assert parse_ideas("") == []
    assert parse_ideas("not json at all") == []
    assert parse_ideas('{"title":"x"}') == []  # object, not array


# ---------------------------------------------------------------- due selection


def test_find_due_selects_ready_enabled_never_reflected(tmp_path, monkeypatch):
    conn, ws_id = _setup_db(tmp_path, monkeypatch)
    agent_id = _add_agent_with_spec(conn, ws_id)
    due = find_due_idle_agents(conn)
    assert [d["agent_id"] for d in due] == [agent_id]


def test_find_due_excludes_not_ready_disabled_and_no_profile(tmp_path, monkeypatch):
    conn, ws_id = _setup_db(tmp_path, monkeypatch)
    _add_agent_with_spec(conn, ws_id, name="draft", profile="p1", status="draft")
    _add_agent_with_spec(conn, ws_id, name="disabled", profile="p2", enabled=0)
    _add_agent_with_spec(conn, ws_id, name="noprofile", profile="")
    assert find_due_idle_agents(conn) == []


def test_find_due_excludes_recently_reflected(tmp_path, monkeypatch):
    conn, ws_id = _setup_db(tmp_path, monkeypatch)
    recent = datetime.now(UTC).isoformat()
    _add_agent_with_spec(conn, ws_id, last_idle=recent, interval=6)
    assert find_due_idle_agents(conn) == []
    # but due once the interval has elapsed
    old = (datetime.now(UTC) - timedelta(hours=7)).isoformat()
    conn.execute("UPDATE agent_specs SET last_idle_think_at = ?", (old,))
    conn.commit()
    assert len(find_due_idle_agents(conn)) == 1


def test_find_due_excludes_agent_with_active_run(tmp_path, monkeypatch):
    conn, ws_id = _setup_db(tmp_path, monkeypatch)
    agent_id = _add_agent_with_spec(conn, ws_id)
    conv_id = new_id("conv")
    conn.execute(
        "INSERT INTO conversations (id, workspace_id, kind, name, unread, created_at, updated_at) "
        "VALUES (?, ?, 'group', 'g', 0, ?, ?)",
        (conv_id, ws_id, now_iso(), now_iso()),
    )
    conn.execute(
        "INSERT INTO runs (id, workspace_id, conversation_id, agent_id, status, "
        "input_message_id, created_at) VALUES (?, ?, ?, ?, 'running', ?, ?)",
        (new_id("run"), ws_id, conv_id, agent_id, new_id("msg"), now_iso()),
    )
    conn.commit()
    assert find_due_idle_agents(conn) == []


# ---------------------------------------------------------------- reflection


def test_trigger_reflection_creates_ideas_and_stamps(tmp_path, monkeypatch):
    conn, ws_id = _setup_db(tmp_path, monkeypatch)
    agent_id = _add_agent_with_spec(conn, ws_id)
    backend = _FakeBackend(
        [
            _msg('[{"title":"做开头模板",'),
            _msg('"description":"前三句制造场景冲突","category":"improvement"}]'),
        ]
    )
    created = asyncio.run(
        trigger_reflection(
            conn, agent_id=agent_id, workspace_id=ws_id, profile="p_arun", backend=backend
        )
    )
    assert len(created) == 1
    rows = conn.execute(
        "SELECT title, category, source_agent_id FROM ideas WHERE workspace_id = ?",
        (ws_id,),
    ).fetchall()
    assert rows[0]["title"] == "做开头模板"
    assert rows[0]["source_agent_id"] == agent_id
    stamp = conn.execute(
        "SELECT last_idle_think_at FROM agent_specs WHERE agent_id = ?", (agent_id,)
    ).fetchone()["last_idle_think_at"]
    assert stamp  # stamped


def test_trigger_reflection_empty_output_stamps_no_ideas(tmp_path, monkeypatch):
    conn, ws_id = _setup_db(tmp_path, monkeypatch)
    agent_id = _add_agent_with_spec(conn, ws_id)
    created = asyncio.run(
        trigger_reflection(
            conn, agent_id=agent_id, workspace_id=ws_id, profile="p_arun",
            backend=_FakeBackend([_msg("[]")]),
        )
    )
    assert created == []
    assert conn.execute("SELECT COUNT(*) AS c FROM ideas").fetchone()["c"] == 0
    assert conn.execute(
        "SELECT last_idle_think_at FROM agent_specs WHERE agent_id = ?", (agent_id,)
    ).fetchone()["last_idle_think_at"]


def test_trigger_reflection_backend_error_stamps_and_survives(tmp_path, monkeypatch):
    conn, ws_id = _setup_db(tmp_path, monkeypatch)
    agent_id = _add_agent_with_spec(conn, ws_id)
    created = asyncio.run(
        trigger_reflection(
            conn, agent_id=agent_id, workspace_id=ws_id, profile="p_arun",
            backend=_BoomBackend(),
        )
    )
    assert created == []
    assert conn.execute(
        "SELECT last_idle_think_at FROM agent_specs WHERE agent_id = ?", (agent_id,)
    ).fetchone()["last_idle_think_at"]


def test_run_idle_tick_processes_due_agents(tmp_path, monkeypatch):
    conn, ws_id = _setup_db(tmp_path, monkeypatch)
    _add_agent_with_spec(conn, ws_id, name="A", profile="pa")
    _add_agent_with_spec(conn, ws_id, name="B", profile="pb")
    backend = _FakeBackend(
        [_msg('[{"title":"t","description":"d","category":"risk"}]')]
    )
    summary = asyncio.run(run_idle_tick(conn, backend=backend))
    assert summary == {"agents_processed": 2, "ideas_created": 2}
    # second pass: both just reflected -> not due
    summary2 = asyncio.run(run_idle_tick(conn, backend=backend))
    assert summary2 == {"agents_processed": 0, "ideas_created": 0}


@pytest.mark.skipif(
    __import__("os").environ.get("HERMES_E2E") != "1",
    reason="requires real Hermes (HERMES_E2E=1) + a ready agentpulse profile",
)
def test_trigger_reflection_real_hermes(tmp_path, monkeypatch):
    from app.runtime.hermes_client import HermesBackend

    conn, ws_id = _setup_db(tmp_path, monkeypatch)
    agent_id = _add_agent_with_spec(conn, ws_id, profile="agentpulse")
    created = asyncio.run(
        trigger_reflection(
            conn, agent_id=agent_id, workspace_id=ws_id, profile="agentpulse",
            backend=HermesBackend(),
        )
    )
    # real model may return 0-3 ideas; assert it ran + stamped without error
    assert isinstance(created, list)
    assert conn.execute(
        "SELECT last_idle_think_at FROM agent_specs WHERE agent_id = ?", (agent_id,)
    ).fetchone()["last_idle_think_at"]
