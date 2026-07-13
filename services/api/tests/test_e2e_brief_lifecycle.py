"""
TD-01-T2: End-to-end brief lifecycle verification.

Simulates the 5-step manual test from TD-01 via the FastAPI TestClient.
Focuses on brief lifecycle + task gate — does NOT depend on a working LLM.
"""

import json

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import connect, init_db
from app.main import app
from app.services.workspace import new_id, now_iso


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(
        settings, "database_url", f"sqlite:///{tmp_path / 'e2e.sqlite3'}"
    )
    monkeypatch.setattr(settings, "password_iterations", 1_000)
    init_db()
    client = TestClient(app)

    reg = client.post(
        "/api/auth/register",
        json={
            "email": "boss@test.com",
            "password": "test1234",
            "display_name": "老板",
            "workspace_name": "测试公司",
        },
    ).json()
    token = reg["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    bootstrap = client.get("/api/me/bootstrap", headers=headers).json()
    workspace_id = bootstrap["workspace"]["id"]
    # Use first agent as "secretary"
    secretary = bootstrap["agents"][0]
    group = client.post(
        "/api/conversations/group",
        headers=headers,
        json={"name": "测试组", "member_ids": [secretary["id"]]},
    ).json()
    conv_id = group["id"]

    return client, headers, workspace_id, secretary, conv_id


@pytest.mark.xfail(reason="DeepSeek SOCKS proxy not configured in CI/test env", strict=False)
def test_step1_no_auto_task(setup):
    """Step 1: send message -> no auto task."""
    client, headers, ws_id, secretary, conv_id = setup

    # The streaming endpoint doesn't try DeepSeek on the server side
    # but the non-streaming one does. Use streaming to verify no auto task.
    resp = client.post(
        f"/api/conversations/{conv_id}/messages",
        headers=headers,
        json={"content": "帮我搞下周内容"},
    )
    # This may fail if DeepSeek is not configured (SOCKS proxy issue).
    # The key assertion: if it succeeds, no task was auto-created.
    if resp.status_code == 200:
        data = resp.json()
        assert data.get("created_task") is None, "Task should not be auto-created"

    # Conversation should still be 'discussing'
    bootstrap = client.get("/api/me/bootstrap", headers=headers).json()
    conv = next(c for c in bootstrap["conversations"] if c["id"] == conv_id)
    assert conv.get("discussion_status", "discussing") == "discussing"


def test_step2_create_brief(setup):
    """Step 2: create brief -> draft + BRIEF_CARD."""
    client, headers, ws_id, secretary, conv_id = setup

    resp = client.post(
        "/api/briefs",
        headers=headers,
        json={
            "discussion_conversation_id": conv_id,
            "goal": "策划下周3篇减脂餐小红书内容",
            "scope": "面向减肥上班族，3篇图文",
            "constraints": "周三前至少发1篇",
            "success_criteria": "3篇选题+结构定稿",
            "owner_agent_id": secretary["id"],
            "participant_agent_ids": [secretary["id"]],
            "created_by_agent_id": secretary["id"],
        },
    )
    assert resp.status_code == 200, f"create brief failed: {resp.text}"
    brief = resp.json()
    assert brief["status"] == "draft"
    assert brief["goal"] == "策划下周3篇减脂餐小红书内容"

    # Verify BRIEF_CARD system message
    db = connect()
    try:
        msgs = db.execute(
            "SELECT content FROM messages WHERE conversation_id=? AND sender_type='system'",
            (conv_id,),
        ).fetchall()
        card_found = any(m["content"].startswith("BRIEF_CARD:") for m in msgs)
        assert card_found, "No BRIEF_CARD system message"
    finally:
        db.close()


def test_step3_reject_brief(setup):
    """Step 3: reject -> rejected, discussion continues."""
    client, headers, ws_id, secretary, conv_id = setup

    # Create
    brief = client.post(
        "/api/briefs",
        headers=headers,
        json={
            "discussion_conversation_id": conv_id,
            "goal": "测试reject",
            "created_by_agent_id": secretary["id"],
        },
    ).json()

    # Reject
    resp = client.post(f"/api/briefs/{brief['id']}/reject", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"

    # Discussion status stays discussing
    bootstrap = client.get("/api/me/bootstrap", headers=headers).json()
    conv = next(c for c in bootstrap["conversations"] if c["id"] == conv_id)
    assert conv.get("discussion_status", "discussing") == "discussing"


def test_step4_confirm_and_create_task(setup):
    """Step 4: confirm -> aligned + can create task from brief."""
    client, headers, ws_id, secretary, conv_id = setup

    brief = client.post(
        "/api/briefs",
        headers=headers,
        json={
            "discussion_conversation_id": conv_id,
            "goal": "本周输出3篇内容",
            "owner_agent_id": secretary["id"],
            "created_by_agent_id": secretary["id"],
        },
    ).json()
    brief_id = brief["id"]

    # Confirm
    resp = client.post(f"/api/briefs/{brief_id}/confirm", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "confirmed"

    # Discussion status should be 'aligned'
    bootstrap = client.get("/api/me/bootstrap", headers=headers).json()
    conv = next(c for c in bootstrap["conversations"] if c["id"] == conv_id)
    assert conv.get("discussion_status") == "aligned", (
        f"Expected aligned, got {conv.get('discussion_status')}"
    )

    # Create task from confirmed brief (should pass gate)
    resp = client.post(
        "/api/tasks",
        headers=headers,
        json={
            "title": "写3篇减脂餐文案",
            "owner_agent_id": secretary["id"],
            "conversation_id": conv_id,
            "consensus_brief_id": brief_id,
        },
    )
    assert resp.status_code == 200, f"create task failed: {resp.text}"
    task = resp.json()
    assert task["consensus_brief_id"] == brief_id
    assert task["status"] == "进行中"

    # Task should appear in bootstrap
    bootstrap = client.get("/api/me/bootstrap", headers=headers).json()
    task_ids = [t["id"] for t in bootstrap["tasks"]]
    assert task["id"] in task_ids, "Task not found in bootstrap"


def test_step5_gate_rejects(setup):
    """Step 5: task without brief -> 400."""
    client, headers, ws_id, secretary, conv_id = setup

    resp = client.post(
        "/api/tasks",
        headers=headers,
        json={
            "title": "没有brief的任务",
            "owner_agent_id": secretary["id"],
            "conversation_id": conv_id,
        },
    )
    assert resp.status_code == 400, (
        f"Gate should reject, got {resp.status_code}: {resp.text}"
    )
