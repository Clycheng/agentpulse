from fastapi.testclient import TestClient

from app.api.routes import runs
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


def test_llm_chat_returns_deepseek_reply(monkeypatch) -> None:
    async def fake_complete(self, payload):
        return LlmChatResponse(
            reply="收到，我先帮你拆成三个优先级。",
            provider="deepseek",
            model="deepseek-v4-flash",
            usage={"total_tokens": 42},
        )

    monkeypatch.setattr(runs.DeepSeekChatClient, "complete", fake_complete)
    client = TestClient(app)

    response = client.post("/api/runs/llm-chat", json=chat_payload())

    assert response.status_code == 200
    assert response.json()["reply"] == "收到，我先帮你拆成三个优先级。"
    assert response.json()["model"] == "deepseek-v4-flash"


def test_llm_chat_requires_messages() -> None:
    payload = chat_payload()
    payload["messages"] = []
    client = TestClient(app)

    response = client.post("/api/runs/llm-chat", json=payload)

    assert response.status_code == 422
