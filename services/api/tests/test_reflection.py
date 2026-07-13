"""Tests for ReflectionService (TD-06-T1 skill self-sedimentation).

Always-on tests drive a fake backend + RecordOnly provisioner to exercise skill
parsing, the run counter, due-agent selection, and reflection → update_skill +
counter reset. A guarded e2e (HERMES_E2E=1) drives real Hermes.
"""

import asyncio

import pytest

from app.core.config import settings
from app.core.database import connect, init_db
from app.runtime.hermes_client import AgentEvent
from app.runtime.profile_provisioner import RecordOnlyProvisioner
from app.runtime.reflection import (
    bump_reflection_counter,
    find_agents_due_for_reflection,
    parse_skills,
    run_reflection,
    run_reflection_tick,
)
from app.services.workspace import create_agent, create_workspace_for_user, new_id, now_iso


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
        raise RuntimeError("boom")
        yield  # pragma: no cover


def _setup_db(tmp_path, monkeypatch):
    monkeypatch.setattr(
        settings, "database_url", f"sqlite:///{tmp_path / 'reflect.sqlite3'}"
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


def _add_agent_with_spec(conn, ws_id, *, profile="p_arun", status="ready", interval=5):
    dept = conn.execute(
        "SELECT id FROM departments WHERE workspace_id = ? LIMIT 1", (ws_id,)
    ).fetchone()["id"]
    agent_id = create_agent(
        conn, workspace_id=ws_id, department_id=dept, name="阿伦", role="内容主笔",
        description="", prompt="", skills=[], mcps=[],
    )
    conn.execute(
        "INSERT INTO agent_specs (id, agent_id, workspace_id, role_name, hermes_profile, "
        "status, reflection_interval, runs_since_last_reflection, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?)",
        (new_id("spec"), agent_id, ws_id, "内容主笔", profile, status, interval,
         now_iso(), now_iso()),
    )
    conn.commit()
    return agent_id


def _add_completed_run_with_steps(conn, ws_id, agent_id):
    conv_id = new_id("conv")
    conn.execute(
        "INSERT INTO conversations (id, workspace_id, kind, name, unread, created_at, updated_at) "
        "VALUES (?, ?, 'group', 'g', 0, ?, ?)",
        (conv_id, ws_id, now_iso(), now_iso()),
    )
    run_id = new_id("run")
    conn.execute(
        "INSERT INTO runs (id, workspace_id, conversation_id, agent_id, status, "
        "input_message_id, created_at, completed_at) "
        "VALUES (?, ?, ?, ?, 'completed', ?, ?, ?)",
        (run_id, ws_id, conv_id, agent_id, new_id("msg"), now_iso(), now_iso()),
    )
    for i, (typ, detail) in enumerate(
        [("tool_call", "web_search 办公好物"), ("message", "写好了 5 篇选题草稿")]
    ):
        conn.execute(
            "INSERT INTO run_steps (id, run_id, type, title, detail, created_at) "
            "VALUES (?, ?, ?, '', ?, ?)",
            (new_id("step"), run_id, typ, detail, f"2026-01-01T00:0{i}:00+00:00"),
        )
    conn.commit()
    return run_id


# ---------------------------------------------------------------- parse_skills


def test_parse_skills_valid_and_fenced():
    text = '```json\n[{"skill_name":"选题复用","content":"# 选题\\n用爆款结构"}]\n```'
    skills = parse_skills(text)
    assert len(skills) == 1
    assert skills[0]["skill_name"] == "选题复用"


def test_parse_skills_filters_and_caps():
    text = (
        "["
        '{"skill_name":"a","content":"c"},'
        '{"skill_name":"","content":"c"},'      # empty name dropped
        '{"skill_name":"b","content":""},'      # empty content dropped
        '{"skill_name":"d","content":"c"},'
        '{"skill_name":"e","content":"c"},'
        '{"skill_name":"f","content":"c"}'      # 4th valid -> capped at 3
        "]"
    )
    assert len(parse_skills(text)) == 3


def test_parse_skills_garbage():
    assert parse_skills("") == []
    assert parse_skills("no json") == []
    assert parse_skills("[]") == []


def test_skill_filename_distinct_for_cjk_names():
    from app.runtime.profile_provisioner import LocalHermesProvisioner

    f = LocalHermesProvisioner._skill_filename
    # ASCII slugs stay readable
    assert f("Office Picks") == "office-picks.md"
    # distinct CJK names must not collide (regression: both -> "skill.md")
    a, b = f("办公好物选题法"), f("客户分级话术")
    assert a != b and a.endswith(".md") and b.endswith(".md")


# ---------------------------------------------------------------- counter


def test_bump_counter_reaches_interval(tmp_path, monkeypatch):
    conn, ws_id = _setup_db(tmp_path, monkeypatch)
    agent_id = _add_agent_with_spec(conn, ws_id, interval=3)
    assert bump_reflection_counter(conn, agent_id) is False  # 1
    assert bump_reflection_counter(conn, agent_id) is False  # 2
    assert bump_reflection_counter(conn, agent_id) is True   # 3 == interval
    conn.commit()


def test_bump_counter_no_spec_is_noop(tmp_path, monkeypatch):
    conn, ws_id = _setup_db(tmp_path, monkeypatch)
    assert bump_reflection_counter(conn, "agent_nope") is False


# ---------------------------------------------------------------- due selection


def test_find_due_selects_at_interval(tmp_path, monkeypatch):
    conn, ws_id = _setup_db(tmp_path, monkeypatch)
    agent_id = _add_agent_with_spec(conn, ws_id, interval=5)
    assert find_agents_due_for_reflection(conn) == []  # counter 0
    conn.execute(
        "UPDATE agent_specs SET runs_since_last_reflection = 5 WHERE agent_id = ?",
        (agent_id,),
    )
    conn.commit()
    due = find_agents_due_for_reflection(conn)
    assert [d["agent_id"] for d in due] == [agent_id]


# ---------------------------------------------------------------- reflection


def test_run_reflection_writes_skills_and_resets(tmp_path, monkeypatch):
    conn, ws_id = _setup_db(tmp_path, monkeypatch)
    agent_id = _add_agent_with_spec(conn, ws_id)
    _add_completed_run_with_steps(conn, ws_id, agent_id)
    conn.execute(
        "UPDATE agent_specs SET runs_since_last_reflection = 5 WHERE agent_id = ?",
        (agent_id,),
    )
    conn.commit()
    prov = RecordOnlyProvisioner()
    backend = _FakeBackend(
        [_msg('[{"skill_name":"办公好物选题法","content":"# 办公好物\\n前三句造场景"}]')]
    )
    names = asyncio.run(
        run_reflection(conn, agent_id=agent_id, backend=backend, provisioner=prov)
    )
    assert names == ["办公好物选题法"]
    assert prov.list_skills("p_arun")[0]["name"] == "办公好物选题法"
    spec = conn.execute(
        "SELECT runs_since_last_reflection, last_skill_reflection_at "
        "FROM agent_specs WHERE agent_id = ?",
        (agent_id,),
    ).fetchone()
    assert spec["runs_since_last_reflection"] == 0  # reset
    assert spec["last_skill_reflection_at"]  # stamped


def test_run_reflection_no_steps_skips_backend_but_stamps(tmp_path, monkeypatch):
    conn, ws_id = _setup_db(tmp_path, monkeypatch)
    agent_id = _add_agent_with_spec(conn, ws_id)  # no runs/steps
    prov = RecordOnlyProvisioner()
    names = asyncio.run(
        run_reflection(conn, agent_id=agent_id, backend=_BoomBackend(), provisioner=prov)
    )
    assert names == []  # no summary -> backend never called (Boom not raised)
    assert prov.list_skills("p_arun") == []
    assert conn.execute(
        "SELECT last_skill_reflection_at FROM agent_specs WHERE agent_id = ?",
        (agent_id,),
    ).fetchone()["last_skill_reflection_at"]


def test_run_reflection_backend_error_stamps(tmp_path, monkeypatch):
    conn, ws_id = _setup_db(tmp_path, monkeypatch)
    agent_id = _add_agent_with_spec(conn, ws_id)
    _add_completed_run_with_steps(conn, ws_id, agent_id)
    prov = RecordOnlyProvisioner()
    names = asyncio.run(
        run_reflection(conn, agent_id=agent_id, backend=_BoomBackend(), provisioner=prov)
    )
    assert names == []
    assert conn.execute(
        "SELECT runs_since_last_reflection FROM agent_specs WHERE agent_id = ?",
        (agent_id,),
    ).fetchone()["runs_since_last_reflection"] == 0


def test_run_reflection_tick_processes_due(tmp_path, monkeypatch):
    conn, ws_id = _setup_db(tmp_path, monkeypatch)
    agent_id = _add_agent_with_spec(conn, ws_id)
    _add_completed_run_with_steps(conn, ws_id, agent_id)
    conn.execute(
        "UPDATE agent_specs SET runs_since_last_reflection = 5 WHERE agent_id = ?",
        (agent_id,),
    )
    conn.commit()
    prov = RecordOnlyProvisioner()
    backend = _FakeBackend([_msg('[{"skill_name":"s","content":"c"}]')])
    summary = asyncio.run(
        run_reflection_tick(conn, backend=backend, provisioner=prov)
    )
    assert summary == {"agents_reflected": 1, "skills_learned": 1}
    # counter reset -> not due on second pass
    summary2 = asyncio.run(
        run_reflection_tick(conn, backend=backend, provisioner=prov)
    )
    assert summary2 == {"agents_reflected": 0, "skills_learned": 0}


@pytest.mark.skipif(
    __import__("os").environ.get("HERMES_E2E") != "1",
    reason="requires real Hermes (HERMES_E2E=1) + a ready agentpulse profile",
)
def test_run_reflection_real_hermes(tmp_path, monkeypatch):
    from app.runtime.hermes_client import HermesBackend
    from app.runtime.profile_provisioner import LocalHermesProvisioner

    conn, ws_id = _setup_db(tmp_path, monkeypatch)
    agent_id = _add_agent_with_spec(conn, ws_id, profile="agentpulse")
    _add_completed_run_with_steps(conn, ws_id, agent_id)
    import os as _os

    work_root = _os.path.abspath(".hermes-data")
    prov = LocalHermesProvisioner(work_root=work_root)
    names = asyncio.run(
        run_reflection(
            conn, agent_id=agent_id, backend=HermesBackend(), provisioner=prov,
            hermes_work_root=work_root,
        )
    )
    assert isinstance(names, list)
    assert conn.execute(
        "SELECT runs_since_last_reflection FROM agent_specs WHERE agent_id = ?",
        (agent_id,),
    ).fetchone()["runs_since_last_reflection"] == 0
