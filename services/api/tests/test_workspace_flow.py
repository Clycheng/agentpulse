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


def create_confirmed_brief(
    client: TestClient,
    token: str,
    conversation_id: str,
    agent_id: str,
    goal: str,
) -> dict:
    """Helper: create a draft brief and confirm it for task creation."""
    brief = client.post(
        "/api/briefs",
        headers=auth_header(token),
        json={
            "discussion_conversation_id": conversation_id,
            "goal": goal,
            "created_by_agent_id": agent_id,
        },
    )
    assert brief.status_code == 200
    brief_id = brief.json()["id"]

    confirmed = client.post(
        f"/api/briefs/{brief_id}/confirm",
        headers=auth_header(token),
    )
    assert confirmed.status_code == 200
    return confirmed.json()


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
    conn = connect()
    try:
        table_count = conn.execute(
            "SELECT COUNT(*) AS count FROM official_agent_templates"
        ).fetchone()
        assert table_count["count"] == len(payload["templates"])
    finally:
        conn.close()


def test_login_secretary_chat_persists_deepseek_metadata(tmp_path, monkeypatch):
    async def fake_complete(self, payload):
        assert payload.agent.name == "小秘"
        assert payload.messages[-1].content == "帮我拆一下今天的推进计划"
        # NOTE: Auto-task creation has been removed (ADR 0006)
        # related_tasks is now empty unless explicitly created
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
    secretary_agent = bootstrap["agents"][0]  # 小秘
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
    # NOTE: Auto-task creation removed (ADR 0006) - created_task is now None
    assert payload["created_task"] is None

    reloaded = client.get("/api/me/bootstrap", headers=auth_header(token)).json()
    messages = reloaded["messages_by_conversation"][secretary_chat["id"]]
    assert [message["sender_type"] for message in messages] == [
        "agent",
        "user",
        "agent",
    ]
    assert messages[-1]["provider"] == "deepseek"
    assert messages[-1]["model"] == "deepseek-v4-flash"


def test_knowledge_source_is_injected_into_agent_context(tmp_path, monkeypatch):
    async def fake_complete(self, payload):
        assert payload.knowledge_sources
        assert payload.knowledge_sources[0].title == "品牌定位"
        assert "一人公司 AI 工作台" in payload.knowledge_sources[0].content
        return LlmChatResponse(
            reply="我会按品牌定位来写：突出一人公司 AI 工作台。",
            provider="deepseek",
            model="deepseek-v4-flash",
            usage={"total_tokens": 72},
        )

    monkeypatch.setattr(
        workspace_routes.DeepSeekChatClient,
        "complete",
        fake_complete,
    )
    client = make_client(tmp_path, monkeypatch)
    auth = register_user(client)
    token = auth["access_token"]

    created_source = client.post(
        "/api/knowledge-sources",
        headers=auth_header(token),
        json={
            "title": "品牌定位",
            "category": "品牌资料",
            "content": "AgentPulse 是一人公司 AI 工作台，帮助老板招聘 AI 员工、拉群协作和验收成果。",
        },
    )
    assert created_source.status_code == 200
    assert created_source.json()["category"] == "品牌资料"

    bootstrap = client.get("/api/me/bootstrap", headers=auth_header(token)).json()
    assert bootstrap["knowledge_sources"][0]["title"] == "品牌定位"
    secretary_chat = bootstrap["conversations"][0]

    sent = client.post(
        f"/api/conversations/{secretary_chat['id']}/messages",
        headers=auth_header(token),
        json={"content": "参考品牌定位，帮我写一句官网首屏文案"},
    )
    assert sent.status_code == 200
    assert "一人公司 AI 工作台" in sent.json()["agent_message"]["content"]


def test_secretary_chat_can_create_agent_from_recruit_intent(tmp_path, monkeypatch):
    async def fake_complete(self, payload):
        assert payload.agent.name == "小秘"
        return LlmChatResponse(
            reply="我已经先帮你把市场分析师建好，后续可以继续补充工具和资料库权限。",
            provider="deepseek",
            model="deepseek-v4-flash",
            usage={"total_tokens": 66},
        )

    monkeypatch.setattr(
        workspace_routes.DeepSeekChatClient,
        "complete",
        fake_complete,
    )
    client = make_client(tmp_path, monkeypatch)
    auth = register_user(client)
    token = auth["access_token"]
    bootstrap = client.get("/api/me/bootstrap", headers=auth_header(token)).json()
    secretary_chat = bootstrap["conversations"][0]

    send = client.post(
        f"/api/conversations/{secretary_chat['id']}/messages",
        headers=auth_header(token),
        json={"content": "帮我招一个市场分析师"},
    )

    assert send.status_code == 200
    payload = send.json()
    assert payload["created_task"] is None
    assert payload["created_agent"]["name"] == "市场分析师"
    assert payload["created_agent"]["source"] == "chat_factory"

    reloaded = client.get("/api/me/bootstrap", headers=auth_header(token)).json()
    agents = {agent["name"]: agent for agent in reloaded["agents"]}
    assert "市场分析师" in agents
    departments = {department["name"] for department in reloaded["departments"]}
    assert "市场部" in departments
    dm_chats = [
        chat
        for chat in reloaded["conversations"]
        if chat["kind"] == "dm" and chat["agent_id"] == agents["市场分析师"]["id"]
    ]
    assert dm_chats
    messages = reloaded["messages_by_conversation"][secretary_chat["id"]]
    assert any("已创建员工：市场分析师" in message["content"] for message in messages)


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

    # Create brief first (ADR 0006 gate)
    bootstrap = client.get("/api/me/bootstrap", headers=auth_header(token)).json()
    secretary_chat = bootstrap["conversations"][0]
    secretary_agent = bootstrap["agents"][0]
    brief = create_confirmed_brief(
        client, token, secretary_chat["id"], secretary_agent["id"], "本周增长打法"
    )

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
            "consensus_brief_id": brief["id"],
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
    # In discussion mode (TD-02), agents reply via round-robin orchestration.
    # Two agents × 4 max turns = 4 messages alternating between them.
    sender_ids = [message["sender_id"] for message in payload["agent_messages"]]
    assert len(sender_ids) == 4  # MAX_AGENT_TURNS_PER_ROUND
    # First speaker is the one who spoke least recently (round-robin)
    assert sender_ids[0] in [analyst["id"], writer["id"]]
    # Speakers alternate
    assert len(set(sender_ids)) == 2
    # All agents were called (captured_agents may include "主持人" from speaker selection)
    assert {"增长分析师", "内容策划"}.issubset(set(captured_agents))

    reloaded = client.get("/api/me/bootstrap", headers=auth_header(token)).json()
    persisted = reloaded["messages_by_conversation"][group_id]
    # In discussion mode: 1 user message + 4 agent messages
    assert [message["sender_type"] for message in persisted[-5:]] == [
        "user",
        "agent",
        "agent",
        "agent",
        "agent",
    ]
    # Agent IDs alternate between the two members
    agent_sender_ids = [m["sender_id"] for m in persisted[-4:]]
    assert len(set(agent_sender_ids)) == 2
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
    secretary_chat = bootstrap["conversations"][0]
    secretary_agent = bootstrap["agents"][0]

    # Create brief first (ADR 0006 gate)
    brief = create_confirmed_brief(
        client, token, secretary_chat["id"], secretary_agent["id"], "官网首屏文案"
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
            "consensus_brief_id": brief["id"],
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
    experiences = completed["agent_experiences_by_agent"][agent["id"]]
    assert experiences[0]["task_id"] == task_payload["id"]
    assert experiences[0]["outcome"] == "success"
    assert "老板已确认通过" in experiences[0]["summary"]

    follow_up = client.post(
        f"/api/conversations/{dm_chat['id']}/messages",
        headers=auth_header(token),
        json={"content": "参考之前的经验，再给我一个下一步建议"},
    )
    assert follow_up.status_code == 200
    experience_payload = captured_payloads[-1]
    assert experience_payload.agent_experiences
    assert experience_payload.agent_experiences[0].outcome == "success"
    assert "官网首屏文案" in experience_payload.agent_experiences[0].summary


def test_rejected_approval_creates_agent_lesson_experience(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    auth = register_user(client)
    token = auth["access_token"]

    created = client.post(
        "/api/agents",
        headers=auth_header(token),
        json={
            "name": "销售顾问",
            "description": "负责线索跟进",
            "department_name": "增长与客户",
            "prompt": "你负责线索跟进、报价和成交卡点复盘。",
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
    secretary_chat = bootstrap["conversations"][0]
    secretary_agent = bootstrap["agents"][0]

    # Create brief first (ADR 0006 gate)
    brief = create_confirmed_brief(
        client, token, secretary_chat["id"], secretary_agent["id"], "整理报价策略"
    )

    task = client.post(
        "/api/tasks",
        headers=auth_header(token),
        json={
            "title": "整理报价策略",
            "description": "输出报价策略和风险提示。",
            "priority": "P1",
            "owner_agent_id": agent["id"],
            "conversation_id": dm_chat["id"],
            "status": "进行中",
            "progress": 40,
            "consensus_brief_id": brief["id"],
        },
    )
    assert task.status_code == 200
    task_payload = task.json()
    patched = client.patch(
        f"/api/tasks/{task_payload['id']}",
        headers=auth_header(token),
        json={"status": "待确认", "progress": 80},
    )
    assert patched.status_code == 200
    approval = client.get("/api/me/bootstrap", headers=auth_header(token)).json()[
        "approvals_by_task"
    ][task_payload["id"]][0]

    rejected = client.post(
        f"/api/approvals/{approval['id']}/resolve",
        headers=auth_header(token),
        json={"status": "rejected"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"

    reloaded = client.get("/api/me/bootstrap", headers=auth_header(token)).json()
    rejected_task = next(
        task for task in reloaded["tasks"] if task["id"] == task_payload["id"]
    )
    assert rejected_task["status"] == "阻塞"
    experiences = reloaded["agent_experiences_by_agent"][agent["id"]]
    assert experiences[0]["outcome"] == "lesson"
    assert "被老板驳回" in experiences[0]["summary"]


def test_unassigned_task_enters_pool_and_can_be_claimed(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    auth = register_user(client)
    token = auth["access_token"]

    agent = client.post(
        "/api/agents",
        headers=auth_header(token),
        json={
            "name": "运营助理",
            "description": "负责运营执行",
            "department_name": "运营部",
            "prompt": "你负责把运营任务拆成可执行动作。",
        },
    ).json()

    bootstrap = client.get("/api/me/bootstrap", headers=auth_header(token)).json()
    secretary_chat = bootstrap["conversations"][0]
    secretary_agent = bootstrap["agents"][0]

    # Create brief first (ADR 0006 gate)
    brief = create_confirmed_brief(
        client, token, secretary_chat["id"], secretary_agent["id"], "整理本周运营事项"
    )

    task = client.post(
        "/api/tasks",
        headers=auth_header(token),
        json={
            "title": "整理本周运营事项",
            "description": "从任务池认领后推进。",
            "priority": "P2",
            "status": "进行中",
            "progress": 10,
            "consensus_brief_id": brief["id"],
        },
    )
    assert task.status_code == 200
    task_payload = task.json()
    assert task_payload["owner_agent_id"] is None
    assert task_payload["status"] == "待认领"
    assert task_payload["progress"] == 0

    claimed = client.post(
        f"/api/tasks/{task_payload['id']}/claim",
        headers=auth_header(token),
        json={"agent_id": agent["id"]},
    )
    assert claimed.status_code == 200
    claimed_payload = claimed.json()
    assert claimed_payload["owner_agent_id"] == agent["id"]
    assert claimed_payload["status"] == "进行中"
    assert claimed_payload["progress"] == 20

    reloaded = client.get("/api/me/bootstrap", headers=auth_header(token)).json()
    events = reloaded["task_events_by_task"][task_payload["id"]]
    assert any(event["kind"] == "task_claimed" for event in events)


def test_task_pool_suggests_matching_agent_for_unassigned_task(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    auth = register_user(client)
    token = auth["access_token"]

    writer = client.post(
        "/api/agents",
        headers=auth_header(token),
        json={
            "name": "内容策划",
            "description": "负责公众号文案和官网内容",
            "department_name": "内容部",
            "prompt": "你负责选题、文案和官网内容产出。",
        },
    ).json()
    client.post(
        "/api/agents",
        headers=auth_header(token),
        json={
            "name": "财务助理",
            "description": "负责记账和对账",
            "department_name": "财务行政",
            "prompt": "你负责财务报表和费用对账。",
        },
    )

    bootstrap = client.get("/api/me/bootstrap", headers=auth_header(token)).json()
    secretary_chat = bootstrap["conversations"][0]
    secretary_agent = bootstrap["agents"][0]

    # Create brief first (ADR 0006 gate)
    brief = create_confirmed_brief(
        client, token, secretary_chat["id"], secretary_agent["id"], "写官网首页文案"
    )

    task = client.post(
        "/api/tasks",
        headers=auth_header(token),
        json={
            "title": "写官网首页文案",
            "description": "输出一版官网首屏内容和价值主张。",
            "priority": "P1",
            "consensus_brief_id": brief["id"],
        },
    ).json()
    reloaded = client.get("/api/me/bootstrap", headers=auth_header(token)).json()
    matched_task = next(item for item in reloaded["tasks"] if item["id"] == task["id"])

    assert matched_task["status"] == "待认领"
    assert matched_task["suggested_agent_id"] == writer["id"]
    assert matched_task["suggested_agent_reason"]


def test_discussion_status_changes_on_brief_lifecycle(tmp_path, monkeypatch):
    """Test that discussion_status updates correctly on brief confirm/reject.

    TD-01-T1: brief confirm/reject 接线讨论态状态机 (G3)
    - create_brief → discussion_status = 'discussing'
    - confirm_brief → discussion_status = 'aligned'
    - reject_brief → discussion_status = 'discussing'
    """
    client = make_client(tmp_path, monkeypatch)
    auth = register_user(client)
    token = auth["access_token"]

    bootstrap = client.get("/api/me/bootstrap", headers=auth_header(token)).json()
    secretary_chat = bootstrap["conversations"][0]
    secretary_agent = bootstrap["agents"][0]

    # Initial status should be 'discussing'
    assert secretary_chat["discussion_status"] == "discussing"

    # Create a brief draft
    brief = client.post(
        "/api/briefs",
        headers=auth_header(token),
        json={
            "discussion_conversation_id": secretary_chat["id"],
            "goal": "本周增长打法",
            "created_by_agent_id": secretary_agent["id"],
        },
    )
    assert brief.status_code == 200

    # After creating brief, status should still be 'discussing'
    reloaded = client.get("/api/me/bootstrap", headers=auth_header(token)).json()
    chat_after_create = next(
        c for c in reloaded["conversations"] if c["id"] == secretary_chat["id"]
    )
    assert chat_after_create["discussion_status"] == "discussing"

    # Reject the brief
    rejected = client.post(
        f"/api/briefs/{brief.json()['id']}/reject",
        headers=auth_header(token),
    )
    assert rejected.status_code == 200

    # After reject, status should still be 'discussing'
    reloaded = client.get("/api/me/bootstrap", headers=auth_header(token)).json()
    chat_after_reject = next(
        c for c in reloaded["conversations"] if c["id"] == secretary_chat["id"]
    )
    assert chat_after_reject["discussion_status"] == "discussing"

    # Create another brief and confirm it
    brief2 = client.post(
        "/api/briefs",
        headers=auth_header(token),
        json={
            "discussion_conversation_id": secretary_chat["id"],
            "goal": "官网改版计划",
            "created_by_agent_id": secretary_agent["id"],
        },
    )
    assert brief2.status_code == 200

    confirmed = client.post(
        f"/api/briefs/{brief2.json()['id']}/confirm",
        headers=auth_header(token),
    )
    assert confirmed.status_code == 200

    # After confirm, status should be 'aligned'
    reloaded = client.get("/api/me/bootstrap", headers=auth_header(token)).json()
    chat_after_confirm = next(
        c for c in reloaded["conversations"] if c["id"] == secretary_chat["id"]
    )
    assert chat_after_confirm["discussion_status"] == "aligned"


def test_task_out_includes_consensus_brief_id(tmp_path, monkeypatch):
    """Test that TaskOut includes consensus_brief_id field.

    TD-01-T1b: TaskOut 补 consensus_brief_id (G2)
    - Task created with consensus_brief_id should return it
    - bootstrap should include consensus_brief_id in task data
    """
    client = make_client(tmp_path, monkeypatch)
    auth = register_user(client)
    token = auth["access_token"]

    bootstrap = client.get("/api/me/bootstrap", headers=auth_header(token)).json()
    secretary_chat = bootstrap["conversations"][0]
    secretary_agent = bootstrap["agents"][0]

    # Create and confirm a brief
    brief = create_confirmed_brief(
        client, token, secretary_chat["id"], secretary_agent["id"], "官网改版"
    )

    # Create task with consensus_brief_id
    task = client.post(
        "/api/tasks",
        headers=auth_header(token),
        json={
            "title": "官网改版执行",
            "description": "执行官网改版计划",
            "priority": "P1",
            "owner_agent_id": secretary_agent["id"],
            "consensus_brief_id": brief["id"],
        },
    )
    assert task.status_code == 200
    task_data = task.json()
    assert task_data["consensus_brief_id"] == brief["id"]

    # bootstrap should also include consensus_brief_id
    reloaded = client.get("/api/me/bootstrap", headers=auth_header(token)).json()
    task_in_bootstrap = next(
        t for t in reloaded["tasks"] if t["id"] == task_data["id"]
    )
    assert task_in_bootstrap["consensus_brief_id"] == brief["id"]
