"""Tests for UpgradeService (TD-06-T2 proactive capability upgrade).

Always-on tests drive a RecordOnly provisioner: approving a capability upgrade
installs it onto the employee's profile and records an agent_capabilities row
(enabled, or credential_missing when the bundle needs creds). Also covers the
resolve endpoint's capability_upgrade branch end to end.
"""

import json

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import connect, init_db
from app.main import app
from app.runtime.profile_provisioner import RecordOnlyProvisioner
from app.runtime.runs import RunStatus, create_run, get_run
from app.runtime.upgrade import UpgradeError, execute_upgrade
from app.services.workspace import (
    add_message, create_agent, create_workspace_for_user, new_id, now_iso,
)


def _setup(tmp_path, monkeypatch):
    monkeypatch.setattr(
        settings, "database_url", f"sqlite:///{tmp_path / 'upgrade.sqlite3'}"
    )
    init_db()
    conn = connect()
    user_id = new_id("user")
    conn.execute(
        "INSERT INTO users (id, email, password_hash, display_name, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (user_id, "boss@ex.com", "x", "老板", now_iso()),
    )
    ws = create_workspace_for_user(conn, user_id, "公司")
    dept = conn.execute(
        "SELECT id FROM departments WHERE workspace_id = ? LIMIT 1", (ws["id"],)
    ).fetchone()["id"]
    agent_id = create_agent(
        conn, workspace_id=ws["id"], department_id=dept, name="阿码", role="前端工程师",
        description="", prompt="", skills=[], mcps=[],
    )
    conn.execute(
        "INSERT INTO agent_specs (id, agent_id, workspace_id, role_name, hermes_profile, "
        "status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 'ready', ?, ?)",
        (new_id("spec"), agent_id, ws["id"], "前端工程师", "p_ama", now_iso(), now_iso()),
    )
    conn.commit()
    return conn, ws["id"], agent_id


def _approval(ws_id, agent_id):
    return {"agent_id": agent_id, "workspace_id": ws_id}


def test_upgrade_no_creds_enabled(tmp_path, monkeypatch):
    conn, ws_id, agent_id = _setup(tmp_path, monkeypatch)
    prov = RecordOnlyProvisioner()
    result = execute_upgrade(
        conn, approval=_approval(ws_id, agent_id),
        approved_capability_key="write_code", provisioner=prov,
    )
    assert result["status"] == "enabled"
    assert result["profile"] == "p_ama"
    # provisioner was told to add the capability
    assert any(a.action == "add_capability" and a.details["capability_key"] == "write_code"
               for a in prov.get_actions())
    # agent_capabilities row recorded
    row = conn.execute(
        "SELECT capability_key, status FROM agent_capabilities WHERE agent_id = ?",
        (agent_id,),
    ).fetchone()
    assert row["capability_key"] == "write_code" and row["status"] == "enabled"


def test_upgrade_with_creds_is_credential_missing(tmp_path, monkeypatch):
    conn, ws_id, agent_id = _setup(tmp_path, monkeypatch)
    result = execute_upgrade(
        conn, approval=_approval(ws_id, agent_id),
        approved_capability_key="git_push", provisioner=RecordOnlyProvisioner(),
    )
    assert result["status"] == "credential_missing"
    assert "GITHUB_TOKEN" in result["required_credentials"]
    row = conn.execute(
        "SELECT status FROM agent_capabilities WHERE agent_id = ? AND capability_key = 'git_push'",
        (agent_id,),
    ).fetchone()
    assert row["status"] == "credential_missing"


def test_upgrade_unknown_key_raises(tmp_path, monkeypatch):
    conn, ws_id, agent_id = _setup(tmp_path, monkeypatch)
    with pytest.raises(UpgradeError):
        execute_upgrade(
            conn, approval=_approval(ws_id, agent_id),
            approved_capability_key="does_not_exist", provisioner=RecordOnlyProvisioner(),
        )


def test_upgrade_no_profile_raises(tmp_path, monkeypatch):
    conn, ws_id, agent_id = _setup(tmp_path, monkeypatch)
    conn.execute("UPDATE agent_specs SET hermes_profile = '' WHERE agent_id = ?", (agent_id,))
    conn.commit()
    with pytest.raises(UpgradeError):
        execute_upgrade(
            conn, approval=_approval(ws_id, agent_id),
            approved_capability_key="write_code", provisioner=RecordOnlyProvisioner(),
        )


def test_upgrade_idempotent_upsert(tmp_path, monkeypatch):
    conn, ws_id, agent_id = _setup(tmp_path, monkeypatch)
    prov = RecordOnlyProvisioner()
    for _ in range(2):
        execute_upgrade(
            conn, approval=_approval(ws_id, agent_id),
            approved_capability_key="write_code", provisioner=prov,
        )
    count = conn.execute(
        "SELECT COUNT(*) AS c FROM agent_capabilities WHERE agent_id = ? AND capability_key = 'write_code'",
        (agent_id,),
    ).fetchone()["c"]
    assert count == 1  # UNIQUE(agent_id, capability_key) → upsert, no dup


# --------------------------------------------------------------- resolve endpoint


def test_resolve_capability_upgrade_installs_and_resumes(tmp_path, monkeypatch):
    monkeypatch.setattr(
        settings, "database_url", f"sqlite:///{tmp_path / 'upg_api.sqlite3'}"
    )
    monkeypatch.setattr(settings, "password_iterations", 1_000)
    # Force the record-only provisioner regardless of the ambient .env flag, so
    # the endpoint doesn't try to drive the real `hermes` CLI in tests.
    monkeypatch.setattr(settings, "hermes_provisioning", False)
    init_db()
    client = TestClient(app)
    reg = client.post("/api/auth/register", json={
        "email": "b@ex.com", "password": "agentpulse123",
        "display_name": "老板", "workspace_name": "公司"})
    token = reg.json()["access_token"]
    boot = client.get("/api/me/bootstrap", headers={"Authorization": f"Bearer {token}"}).json()
    ws_id = boot["workspace"]["id"]
    agent_id = boot["agents"][0]["id"]

    conn = connect()
    conn.execute(
        "INSERT INTO agent_specs (id, agent_id, workspace_id, role_name, hermes_profile, "
        "status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 'ready', ?, ?)",
        (new_id("spec"), agent_id, ws_id, "前端", "p_boot", now_iso(), now_iso()),
    )
    conv_id = new_id("conv")
    conn.execute(
        "INSERT INTO conversations (id, workspace_id, kind, name, unread, created_at, updated_at) "
        "VALUES (?, ?, 'group', 'g', 0, ?, ?)",
        (conv_id, ws_id, now_iso(), now_iso()),
    )
    msg = add_message(conn, conversation_id=conv_id, sender_type="user", sender_id="u", content="推代码")
    run_id = create_run(
        conn, workspace_id=ws_id, conversation_id=conv_id, agent_id=agent_id,
        input_message_id=msg["id"], status=RunStatus.RUNNING,
    )
    from app.runtime.runs import transition_run
    transition_run(conn, run_id, RunStatus.WAITING_USER)
    aid = new_id("appr")
    conn.execute(
        "INSERT INTO approvals (id, workspace_id, conversation_id, agent_id, title, "
        "description, status, risk_level, type, run_id, payload_json, created_at) "
        "VALUES (?, ?, ?, ?, '申请能力升级', '', 'pending', 'medium', 'capability_upgrade', ?, ?, ?)",
        (aid, ws_id, conv_id, agent_id, run_id,
         json.dumps({"suggested_capability_key": "write_code"}), now_iso()),
    )
    conn.commit()

    resp = client.post(
        f"/api/approvals/{aid}/resolve", json={"status": "approved"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"
    conn2 = connect()
    cap = conn2.execute(
        "SELECT capability_key, status FROM agent_capabilities WHERE agent_id = ?",
        (agent_id,),
    ).fetchone()
    assert cap["capability_key"] == "write_code"  # installed via the suggested key
    assert get_run(conn2, run_id)["status"] == RunStatus.RUNNING  # resumed
