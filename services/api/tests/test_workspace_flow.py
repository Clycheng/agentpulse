from fastapi.testclient import TestClient

from app.api.routes import workspace as workspace_routes
from app.core.config import settings
from app.core.database import connect, init_db
from app.main import app
from app.schemas.run import LlmChatResponse
from app.services.workspace import new_id, now_iso


def make_client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setattr(
        settings,
        "database_url",
        f"sqlite:///{tmp_path / 'agentpulse.sqlite3'}",
    )
    monkeypatch.setattr(settings, "password_iterations", 1_000)
    init_db()
    return TestClient(app)


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def register_user(client: TestClient) -> dict:
    response = client.post(
        "/api/auth/register",
        json={
            "email": "founder@example.com",
            "password": "agentpulse123",
            "display_name": "老板",
            "workspace_name": "AgentPulse 工作室",
        },
    )
    assert response.status_code == 200
    return response.json()


def test_register_bootstrap_creates_real_workspace_foundation(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)

    auth = register_user(client)
    bootstrap = client.get(
        "/api/me/bootstrap",
        headers=auth_header(auth["access_token"]),
    )

    assert bootstrap.status_code == 200
    data = bootstrap.json()
    assert data["workspace"]["name"] == "AgentPulse 工作室"
    assert data["workspace"]["onboarding_completed"] is False
    assert [department["name"] for department in data["departments"]] == [
        "老板办公室",
    ]
    assert [agent["name"] for agent in data["agents"]] == ["小秘"]
    assert data["agents"][0]["role"] == "老板秘书"
    assert data["tasks"] == []
    assert len(data["conversations"]) == 1
    assert data["conversations"][0]["kind"] == "dm"
    welcome_messages = data["messages_by_conversation"][data["conversations"][0]["id"]]
    assert len(welcome_messages) == 1
    assert welcome_messages[0]["sender_type"] == "agent"
    assert "我是小秘" in welcome_messages[0]["content"]
    assert data["agent_template_categories"]
    assert data["agent_template_categories"][0]["id"] == "business-ops"
    assert data["agent_templates"]
    assert data["agent_templates"][0]["category_id"] == "business-ops"

    completed = client.post(
        "/api/me/onboarding/complete",
        headers=auth_header(auth["access_token"]),
        json={},
    )
    assert completed.status_code == 200
    reloaded = client.get(
        "/api/me/bootstrap",
        headers=auth_header(auth["access_token"]),
    ).json()
    assert reloaded["workspace"]["onboarding_completed"] is True


def test_admin_talent_market_catalog_exposes_official_templates(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)

    response = client.get("/api/admin/talent-market")

    assert response.status_code == 200
    payload = response.json()
    assert payload["categories"][0]["id"] == "business-ops"
    assert payload["templates"][0]["publisher"] == "AgentPulse 官方"
    assert payload["templates"][0]["status"] == "published"


def test_login_secretary_chat_persists_deepseek_metadata(tmp_path, monkeypatch):
    async def fake_complete(self, payload):
        assert payload.agent.name == "小秘"
        assert payload.messages[-1].content == "帮我拆一下今天的推进计划"
        assert payload.related_tasks
        assert payload.related_tasks[0].title == "拆一下今天的推进计划"
        return LlmChatResponse(
            reply="先做三件事：确认目标、拆任务、安排负责人。",
            provider="deepseek",
            model="deepseek-v4-flash",
            usage={"total_tokens": 88},
        )

    monkeypatch.setattr(
        workspace_routes.DeepSeekChatClient,
        "complete",
        fake_complete,
    )
    client = make_client(tmp_path, monkeypatch)
    register_user(client)

    login = client.post(
        "/api/auth/login",
        json={"email": "founder@example.com", "password": "agentpulse123"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    bootstrap = client.get("/api/me/bootstrap", headers=auth_header(token)).json()
    secretary_chat = bootstrap["conversations"][0]
    send = client.post(
        f"/api/conversations/{secretary_chat['id']}/messages",
        headers=auth_header(token),
        json={"content": "帮我拆一下今天的推进计划"},
    )

    assert send.status_code == 200
    payload = send.json()
    assert payload["user_message"]["sender_type"] == "user"
    assert payload["agent_message"]["content"] == "先做三件事：确认目标、拆任务、安排负责人。"
    assert payload["agent_message"]["provider"] == "deepseek"
    assert payload["agent_message"]["model"] == "deepseek-v4-flash"
    assert payload["created_task"]["title"] == "拆一下今天的推进计划"

    reloaded = client.get("/api/me/bootstrap", headers=auth_header(token)).json()
    messages = reloaded["messages_by_conversation"][secretary_chat["id"]]
    assert [message["sender_type"] for message in messages] == [
        "agent",
        "user",
        "system",
        "agent",
    ]
    assert "已创建任务：拆一下今天的推进计划" in messages[2]["content"]
    assert messages[-1]["provider"] == "deepseek"
    assert messages[-1]["model"] == "deepseek-v4-flash"
    task = reloaded["tasks"][0]
    assert task["title"] == "拆一下今天的推进计划"
    assert task["conversation_id"] == secretary_chat["id"]
    events = reloaded["task_events_by_task"][task["id"]]
    assert any(event["kind"] == "task_created_from_chat" for event in events)


def test_agent_creation_recruitment_and_group_conversation(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    auth = register_user(client)
    token = auth["access_token"]

    created = client.post(
        "/api/agents",
        headers=auth_header(token),
        json={
            "name": "增长分析师",
            "description": "负责增长数据分析",
            "department_name": "增长与客户",
            "prompt": "你负责分析渠道数据，输出下一步增长实验建议。",
        },
    )
    assert created.status_code == 200
    created_agent = created.json()
    assert created_agent["name"] == "增长分析师"
    assert created_agent["source"] == "custom"

    recruited = client.post(
        "/api/agents/recruit",
        headers=auth_header(token),
        json={"template_id": "content-writer", "department_name": "内容部"},
    )
    assert recruited.status_code == 200
    recruited_agent = recruited.json()
    assert recruited_agent["name"] == "内容主笔"
    assert recruited_agent["source"] == "template:content-writer"

    task_id = new_id("task")
    conn = connect()
    try:
        created_at = now_iso()
        conn.execute(
            """
            INSERT INTO tasks (
              id, workspace_id, title, priority, owner_agent_id, status,
              progress, conversation_id, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_id,
                auth["workspace"]["id"],
                "官网首屏文案确认",
                "P1",
                created_agent["id"],
                "进行中",
                30,
                None,
                created_at,
                created_at,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    group = client.post(
        "/api/conversations/group",
        headers=auth_header(token),
        json={
            "name": "官网改版作战室",
            "member_ids": [created_agent["id"], recruited_agent["id"]],
            "related_task_ids": [task_id],
        },
    )
    assert group.status_code == 200
    group_id = group.json()["id"]

    bootstrap = client.get("/api/me/bootstrap", headers=auth_header(token)).json()
    agents = {agent["id"]: agent for agent in bootstrap["agents"]}
    departments = {department["name"] for department in bootstrap["departments"]}
    conversations = {chat["id"]: chat for chat in bootstrap["conversations"]}
    assert created_agent["id"] in agents
    assert recruited_agent["id"] in agents
    assert {"老板办公室", "增长与客户", "内容部"} <= departments
    assert conversations[group_id]["kind"] == "group"
    assert conversations[group_id]["member_ids"] == [
        created_agent["id"],
        recruited_agent["id"],
    ]
    tasks = {task["id"]: task for task in bootstrap["tasks"]}
    assert tasks[task_id]["conversation_id"] == group_id
    group_messages = bootstrap["messages_by_conversation"][group_id]
    system_message = group_messages[0]
    assert system_message["sender_type"] == "system"
    assert "官网改版作战室" not in system_message["content"]
    assert "增长分析师" in system_message["content"]
    assert "内容主笔" in system_message["content"]
    assert group_messages[1]["sender_type"] == "system"
    assert "官网首屏文案确认" in group_messages[1]["content"]

    extra = client.post(
        "/api/agents",
        headers=auth_header(token),
        json={
            "name": "客服专员",
            "description": "负责客户问题整理",
            "department_name": "增长与客户",
            "prompt": "你负责整理客户问题，输出 FAQ 和跟进建议。",
        },
    )
    assert extra.status_code == 200
    extra_agent = extra.json()

    add_members = client.post(
        f"/api/conversations/{group_id}/members",
        headers=auth_header(token),
        json={"member_ids": [extra_agent["id"]]},
    )
    assert add_members.status_code == 200
    assert add_members.json()["added_member_ids"] == [extra_agent["id"]]

    reloaded = client.get("/api/me/bootstrap", headers=auth_header(token)).json()
    reloaded_conversations = {chat["id"]: chat for chat in reloaded["conversations"]}
    assert reloaded_conversations[group_id]["member_ids"] == [
        created_agent["id"],
        recruited_agent["id"],
        extra_agent["id"],
    ]
    group_messages = reloaded["messages_by_conversation"][group_id]
    assert group_messages[-1]["sender_type"] == "system"
    assert "客服专员" in group_messages[-1]["content"]


def test_group_chat_returns_multiple_agent_replies_when_not_mentioned(
    tmp_path, monkeypatch
):
    captured_agents = []

    async def fake_complete(self, payload):
        captured_agents.append(payload.agent.name)
        return LlmChatResponse(
            reply=f"{payload.agent.name}：我基于群聊上下文补充一条建议。",
            provider="deepseek",
            model="deepseek-v4-flash",
            usage={"total_tokens": 42},
        )

    monkeypatch.setattr(
        workspace_routes.DeepSeekChatClient,
        "complete",
        fake_complete,
    )
    client = make_client(tmp_path, monkeypatch)
    auth = register_user(client)
    token = auth["access_token"]

    analyst = client.post(
        "/api/agents",
        headers=auth_header(token),
        json={
            "name": "增长分析师",
            "description": "负责增长数据分析",
            "department_name": "增长与客户",
            "prompt": "你负责分析渠道数据，输出下一步增长实验建议。",
        },
    ).json()
    writer = client.post(
        "/api/agents",
        headers=auth_header(token),
        json={
            "name": "内容策划",
            "description": "负责内容方案",
            "department_name": "内容部",
            "prompt": "你负责把需求转成内容选题和文案计划。",
        },
    ).json()
    task = client.post(
        "/api/tasks",
        headers=auth_header(token),
        json={
            "title": "本周增长打法",
            "description": "形成渠道、内容和执行节奏建议。",
            "priority": "P1",
            "owner_agent_id": analyst["id"],
            "status": "进行中",
            "progress": 20,
        },
    ).json()
    group = client.post(
        "/api/conversations/group",
        headers=auth_header(token),
        json={
            "name": "增长作战室",
            "member_ids": [analyst["id"], writer["id"]],
            "related_task_ids": [task["id"]],
        },
    )
    assert group.status_code == 200
    group_id = group.json()["id"]

    send = client.post(
        f"/api/conversations/{group_id}/messages",
        headers=auth_header(token),
        json={"content": "我们一起讨论下本周增长打法"},
    )

    assert send.status_code == 200
    payload = send.json()
    assert payload["agent_message"]["sender_id"] == analyst["id"]
    assert [message["sender_id"] for message in payload["agent_messages"]] == [
        analyst["id"],
        writer["id"],
    ]
    assert captured_agents == ["增长分析师", "内容策划"]

    reloaded = client.get("/api/me/bootstrap", headers=auth_header(token)).json()
    persisted = reloaded["messages_by_conversation"][group_id]
    assert [message["sender_type"] for message in persisted[-3:]] == [
        "user",
        "agent",
        "agent",
    ]
    assert persisted[-2]["sender_id"] == analyst["id"]
    assert persisted[-1]["sender_id"] == writer["id"]
    outputs = reloaded["task_outputs_by_task"][task["id"]]
    assert {output["agent_id"] for output in outputs} == {analyst["id"], writer["id"]}

    mentioned = client.post(
        f"/api/conversations/{group_id}/messages",
        headers=auth_header(token),
        json={
            "content": "@内容策划 你单独给个文案方向",
            "target_agent_id": writer["id"],
        },
    )
    assert mentioned.status_code == 200
    mentioned_payload = mentioned.json()
    assert [message["sender_id"] for message in mentioned_payload["agent_messages"]] == [
        writer["id"],
    ]


def test_task_api_updates_and_injects_related_context(tmp_path, monkeypatch):
    captured_payloads = []

    async def fake_complete(self, payload):
        captured_payloads.append(payload)
        return LlmChatResponse(
            reply="我会基于关联任务推进：先确认文案目标，再产出首屏草案。",
            provider="deepseek",
            model="deepseek-v4-flash",
            usage={"total_tokens": 96},
        )

    monkeypatch.setattr(
        workspace_routes.DeepSeekChatClient,
        "complete",
        fake_complete,
    )
    client = make_client(tmp_path, monkeypatch)
    auth = register_user(client)
    token = auth["access_token"]

    created = client.post(
        "/api/agents",
        headers=auth_header(token),
        json={
            "name": "内容策划",
            "description": "负责官网内容策划",
            "department_name": "内容部",
            "prompt": "你负责把老板的想法转成官网文案和内容计划。",
        },
    )
    assert created.status_code == 200
    agent = created.json()

    bootstrap = client.get("/api/me/bootstrap", headers=auth_header(token)).json()
    dm_chat = next(
        chat
        for chat in bootstrap["conversations"]
        if chat["kind"] == "dm" and chat["agent_id"] == agent["id"]
    )

    task = client.post(
        "/api/tasks",
        headers=auth_header(token),
        json={
            "title": "官网首屏文案",
            "description": "输出三版首屏标题、副标题和 CTA。",
            "priority": "P1",
            "owner_agent_id": agent["id"],
            "conversation_id": dm_chat["id"],
            "status": "进行中",
            "progress": 20,
        },
    )
    assert task.status_code == 200
    task_payload = task.json()
    assert task_payload["description"] == "输出三版首屏标题、副标题和 CTA。"
    assert task_payload["conversation_id"] == dm_chat["id"]

    after_create = client.get("/api/me/bootstrap", headers=auth_header(token)).json()
    created_events = after_create["task_events_by_task"][task_payload["id"]]
    assert created_events[0]["kind"] == "task_created"
    assert any(event["kind"] == "task_assigned" for event in created_events)

    patched = client.patch(
        f"/api/tasks/{task_payload['id']}",
        headers=auth_header(token),
        json={"status": "待确认", "progress": 80},
    )
    assert patched.status_code == 200
    assert patched.json()["status"] == "待确认"
    assert patched.json()["progress"] == 80

    send = client.post(
        f"/api/conversations/{dm_chat['id']}/messages",
        headers=auth_header(token),
        json={"content": "继续推进这个任务"},
    )
    assert send.status_code == 200
    assert captured_payloads
    llm_payload = captured_payloads[-1]
    assert llm_payload.related_tasks[0].title == "官网首屏文案"
    assert llm_payload.related_tasks[0].status == "待确认"
    assert llm_payload.related_tasks[0].owner_name == "内容策划"

    reloaded = client.get("/api/me/bootstrap", headers=auth_header(token)).json()
    messages = reloaded["messages_by_conversation"][dm_chat["id"]]
    assert any("已创建任务：官网首屏文案" in message["content"] for message in messages)
    assert any("任务更新：官网首屏文案 · 待确认" in message["content"] for message in messages)
    events = reloaded["task_events_by_task"][task_payload["id"]]
    assert any(event["kind"] == "approval_requested" for event in events)
    assert any(event["kind"] == "agent_output_generated" for event in events)
    outputs = reloaded["task_outputs_by_task"][task_payload["id"]]
    assert outputs[0]["content"] == "我会基于关联任务推进：先确认文案目标，再产出首屏草案。"
    approvals = reloaded["approvals_by_task"][task_payload["id"]]
    assert approvals[0]["status"] == "pending"

    resolved = client.post(
        f"/api/approvals/{approvals[0]['id']}/resolve",
        headers=auth_header(token),
        json={"status": "approved"},
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "approved"

    completed = client.get("/api/me/bootstrap", headers=auth_header(token)).json()
    completed_task = next(
        task for task in completed["tasks"] if task["id"] == task_payload["id"]
    )
    assert completed_task["status"] == "已完成"
    completed_events = completed["task_events_by_task"][task_payload["id"]]
    assert any(event["kind"] == "approval_resolved" for event in completed_events)
