from fastapi.testclient import TestClient

from app.api.routes import runs
from app.core.config import settings
from app.core.database import init_db
from app.main import app
from app.schemas.run import LlmChatResponse


def chat_payload() -> dict:
    return {
        "company_name": "星野工作室",
        "conversation_title": "私聊 · 小秘",
        "agent": {
            "id": "sec",
            "name": "小秘",
            "role": "老板秘书",
            "department": "老板办公室",
            "prompt": "你负责帮老板拆解任务、整理下一步。",
            "skills": ["任务拆解"],
        },
        "messages": [{"role": "user", "name": "老板", "content": "帮我规划今天任务"}],
    }


def _authenticated_client(tmp_path, monkeypatch) -> tuple[TestClient, dict[str, str]]:
    monkeypatch.setattr(
        settings, "database_url", f"sqlite:///{tmp_path / 'runs.sqlite3'}"
    )
    monkeypatch.setattr(settings, "password_iterations", 1_000)
    init_db()
    client = TestClient(app)
    response = client.post(
        "/api/auth/register",
        json={
            "email": "runs@example.com",
            "password": "agentpulse123",
            "display_name": "老板",
            "workspace_name": "测试公司",
        },
    )
    token = response.json()["access_token"]
    return client, {"Authorization": f"Bearer {token}"}


def test_llm_chat_returns_deepseek_reply(tmp_path, monkeypatch) -> None:
    async def fake_complete(self, payload):
        return LlmChatResponse(
            reply="收到，我先帮你拆成三个优先级。",
            provider="deepseek",
            model="deepseek-v4-flash",
            usage={"total_tokens": 42},
        )

    monkeypatch.setattr(runs.DeepSeekChatClient, "complete", fake_complete)
    client, headers = _authenticated_client(tmp_path, monkeypatch)

    response = client.post("/api/runs/llm-chat", json=chat_payload(), headers=headers)

    assert response.status_code == 200
    assert response.json()["reply"] == "收到，我先帮你拆成三个优先级。"
    assert response.json()["model"] == "deepseek-v4-flash"


def test_llm_chat_requires_messages(tmp_path, monkeypatch) -> None:
    payload = chat_payload()
    payload["messages"] = []
    client, headers = _authenticated_client(tmp_path, monkeypatch)

    response = client.post("/api/runs/llm-chat", json=payload, headers=headers)

    assert response.status_code == 422
