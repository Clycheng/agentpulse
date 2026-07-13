"""E2E: the live /messages/stream hot path executes via Hermes (TD-03-T3 后半).

SKIPPED by default. Requires Hermes + the `agentpulse` profile (DeepSeek key) +
an agentpulse-anchored shell (ADR 0005):

    HERMES_E2E=1 pytest tests/test_hot_path_hermes.py

Proves that when an employee has a ready Hermes profile, a DM reply is produced
by Hermes (a runs row with provider='hermes' + run_steps), not the DeepSeek
fallback. Agents without a profile keep the DeepSeek path (covered by the always-on
suite, which stays green).
"""

import os
import shutil

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import connect, init_db
from app.main import app
from app.services.workspace import new_id, now_iso

_E2E = os.environ.get("HERMES_E2E") == "1" and shutil.which("hermes") is not None
requires_hermes = pytest.mark.skipif(
    not _E2E, reason="set HERMES_E2E=1 with hermes + agentpulse profile"
)


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@requires_hermes
def test_dm_reply_runs_via_hermes(tmp_path, monkeypatch):
    monkeypatch.setattr(
        settings, "database_url", f"sqlite:///{tmp_path / 'hotpath.sqlite3'}"
    )
    monkeypatch.setattr(settings, "password_iterations", 1_000)
    init_db()
    client = TestClient(app)

    reg = client.post(
        "/api/auth/register",
        json={
            "email": "founder@example.com",
            "password": "agentpulse123",
            "display_name": "老板",
            "workspace_name": "测试公司",
        },
    )
    token = reg.json()["access_token"]

    agent = client.post(
        "/api/agents",
        headers=auth_header(token),
        json={
            "name": "小研",
            "description": "研究员",
            "department_name": "研究部",
            "prompt": "你是研究员",
        },
    ).json()

    # Provision this agent onto the real `agentpulse` Hermes profile.
    db = connect()
    try:
        ws = db.execute("SELECT id FROM workspaces LIMIT 1").fetchone()["id"]
        dm = db.execute(
            "SELECT id FROM conversations WHERE kind='dm' AND agent_id=?",
            (agent["id"],),
        ).fetchone()["id"]
        now = now_iso()
        db.execute(
            """INSERT INTO agent_specs
               (id, agent_id, workspace_id, role_name, source_request,
                responsibilities_json, hermes_profile, status, created_at, updated_at)
               VALUES (?, ?, ?, '研究员', '', '[]', 'agentpulse', 'ready', ?, ?)""",
            (new_id("spec"), agent["id"], ws, now, now),
        )
        db.commit()
    finally:
        db.close()

    resp = client.post(
        f"/api/conversations/{dm}/messages/stream",
        headers=auth_header(token),
        json={"content": "Reply with exactly: OK"},
    )
    assert resp.status_code == 200
    body = resp.text
    assert "event: done" in body

    # The reply was produced by Hermes, not DeepSeek.
    db = connect()
    try:
        run = db.execute(
            "SELECT * FROM runs WHERE conversation_id=? AND provider='hermes'",
            (dm,),
        ).fetchone()
        assert run is not None, "expected a Hermes run row"
        assert run["status"] == "completed"
        steps = db.execute(
            "SELECT type FROM run_steps WHERE run_id=?", (run["id"],)
        ).fetchall()
        types = {s["type"] for s in steps}
        assert "message" in types and "final" in types
        # an agent message landed in the DM
        msg = db.execute(
            "SELECT content FROM messages WHERE conversation_id=? AND sender_type='agent'",
            (dm,),
        ).fetchone()
        assert msg is not None and "OK" in msg["content"]
    finally:
        db.close()
