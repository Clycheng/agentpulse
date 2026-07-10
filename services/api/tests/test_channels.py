"""Tests for the channel router (TD-09-T1).

Covers: generic-webhook normalization, dedup on external_message_id, threading
one external user into one conversation, and routing to a pinned target group.
"""

import pytest
from fastapi.testclient import TestClient

from app.channels.router import route_inbound
from app.core.config import settings
from app.core.database import Database, connect, init_db
from app.main import app
from app.services.workspace import new_id, now_iso


def _setup(tmp_path, monkeypatch) -> tuple[Database, str, str]:
    """Init a temp DB + a registered workspace. Returns (conn, workspace_id, agent_id)."""
    monkeypatch.setattr(
        settings, "database_url", f"sqlite:///{tmp_path / 'test_channels.sqlite3'}"
    )
    monkeypatch.setattr(settings, "password_iterations", 1_000)
    init_db()
    client = TestClient(app)
    resp = client.post(
        "/api/auth/register",
        json={
            "email": "founder@example.com",
            "password": "agentpulse123",
            "display_name": "老板",
            "workspace_name": "测试公司",
        },
    )
    assert resp.status_code == 200
    conn = connect()
    ws = conn.execute("SELECT id FROM workspaces LIMIT 1").fetchone()
    agent = conn.execute(
        "SELECT id FROM agents WHERE workspace_id = ? LIMIT 1", (ws["id"],)
    ).fetchone()
    return conn, ws["id"], agent["id"]


def _make_channel(
    conn,
    workspace_id,
    *,
    token,
    config=None,
    target_agent_id=None,
    target_conversation_id=None,
):
    import json

    conn.execute(
        """
        INSERT INTO channel_configs (
          id, workspace_id, channel_type, name, token, config_json,
          target_agent_id, target_conversation_id, active, created_at
        )
        VALUES (?, ?, 'generic_webhook', '官网客服', ?, ?, ?, ?, 1, ?)
        """,
        (
            new_id("chan"),
            workspace_id,
            token,
            json.dumps(config or {}),
            target_agent_id,
            target_conversation_id,
            now_iso(),
        ),
    )
    conn.commit()
    return conn.execute(
        "SELECT * FROM channel_configs WHERE token = ?", (token,)
    ).fetchone()


def _payload(user, text, msg_id=None):
    p = {"user_id": user, "message": text}
    if msg_id is not None:
        p["message_id"] = msg_id
    return p


def test_inbound_creates_conversation_and_message(tmp_path, monkeypatch):
    conn, ws, agent = _setup(tmp_path, monkeypatch)
    chan = _make_channel(conn, ws, token="tok1", target_agent_id=agent)

    result = route_inbound(conn, chan, _payload("cust_1", "你们几点营业？", "m1"))
    assert result["deduped"] is False
    assert result["message_id"] is not None

    msgs = conn.execute(
        "SELECT * FROM messages WHERE conversation_id = ?",
        (result["conversation_id"],),
    ).fetchall()
    assert len(msgs) == 1
    assert msgs[0]["sender_type"] == "user"
    assert msgs[0]["sender_id"] == "cust_1"
    assert msgs[0]["content"] == "你们几点营业？"
    assert msgs[0]["external_message_id"] == "m1"

    conv = conn.execute(
        "SELECT * FROM conversations WHERE id = ?", (result["conversation_id"],)
    ).fetchone()
    assert conv["source_channel"] == "generic_webhook"
    assert conv["external_conversation_id"] == "cust_1"

    # target agent joined the conversation
    member = conn.execute(
        "SELECT 1 FROM conversation_members WHERE conversation_id = ? AND agent_id = ?",
        (result["conversation_id"], agent),
    ).fetchone()
    assert member is not None


def test_dedup_on_external_message_id(tmp_path, monkeypatch):
    conn, ws, agent = _setup(tmp_path, monkeypatch)
    chan = _make_channel(conn, ws, token="tok2")

    first = route_inbound(conn, chan, _payload("cust_1", "hi", "dup1"))
    second = route_inbound(conn, chan, _payload("cust_1", "hi", "dup1"))
    assert first["deduped"] is False
    assert second["deduped"] is True
    assert second["message_id"] is None

    count = conn.execute(
        "SELECT COUNT(*) AS n FROM messages WHERE conversation_id = ?",
        (first["conversation_id"],),
    ).fetchone()["n"]
    assert count == 1


def test_threads_same_user_and_separates_different_users(tmp_path, monkeypatch):
    conn, ws, agent = _setup(tmp_path, monkeypatch)
    chan = _make_channel(conn, ws, token="tok3")

    a1 = route_inbound(conn, chan, _payload("cust_1", "first", "a1"))
    a2 = route_inbound(conn, chan, _payload("cust_1", "second", "a2"))
    b1 = route_inbound(conn, chan, _payload("cust_2", "hello", "b1"))

    assert a1["conversation_id"] == a2["conversation_id"]
    assert b1["conversation_id"] != a1["conversation_id"]

    n = conn.execute(
        "SELECT COUNT(*) AS n FROM messages WHERE conversation_id = ?",
        (a1["conversation_id"],),
    ).fetchone()["n"]
    assert n == 2


def test_pinned_target_conversation(tmp_path, monkeypatch):
    conn, ws, agent = _setup(tmp_path, monkeypatch)
    fixed_id = new_id("conv")
    conn.execute(
        """
        INSERT INTO conversations (id, workspace_id, kind, name, unread, created_at, updated_at)
        VALUES (?, ?, 'group', '客服总群', 0, ?, ?)
        """,
        (fixed_id, ws, now_iso(), now_iso()),
    )
    conn.commit()
    chan = _make_channel(conn, ws, token="tok4", target_conversation_id=fixed_id)

    r1 = route_inbound(conn, chan, _payload("cust_1", "q1", "x1"))
    r2 = route_inbound(conn, chan, _payload("cust_9", "q2", "x2"))
    # both external users land in the pinned group
    assert r1["conversation_id"] == fixed_id
    assert r2["conversation_id"] == fixed_id


def test_no_message_id_means_no_dedup(tmp_path, monkeypatch):
    conn, ws, agent = _setup(tmp_path, monkeypatch)
    chan = _make_channel(conn, ws, token="tok5")

    r1 = route_inbound(conn, chan, _payload("cust_1", "same text"))
    r2 = route_inbound(conn, chan, _payload("cust_1", "same text"))
    assert r1["deduped"] is False and r2["deduped"] is False
    n = conn.execute(
        "SELECT COUNT(*) AS n FROM messages WHERE conversation_id = ?",
        (r1["conversation_id"],),
    ).fetchone()["n"]
    assert n == 2


def test_custom_paths_and_missing_content(tmp_path, monkeypatch):
    conn, ws, agent = _setup(tmp_path, monkeypatch)
    chan = _make_channel(
        conn,
        ws,
        token="tok6",
        config={
            "message_path": "$.data.text",
            "user_id_path": "$.from.id",
            "message_id_path": "id",
        },
    )
    ok = route_inbound(
        conn,
        chan,
        {"data": {"text": "嵌套消息"}, "from": {"id": "u42"}, "id": "e1"},
    )
    msg = conn.execute(
        "SELECT content, sender_id FROM messages WHERE id = ?", (ok["message_id"],)
    ).fetchone()
    assert msg["content"] == "嵌套消息"
    assert msg["sender_id"] == "u42"

    with pytest.raises(ValueError):
        route_inbound(conn, chan, {"from": {"id": "u42"}, "id": "e2"})  # no text
