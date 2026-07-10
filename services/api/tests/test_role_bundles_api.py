"""Tests for the role-bundle API (TD-07-T2 API half).

- GET /api/role-bundles lists preset roles + their resolved effect.
- POST /api/agents with role_spec.role_bundle_key expands to capabilities.
"""

from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import init_db
from app.main import app


def make_client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setattr(
        settings, "database_url", f"sqlite:///{tmp_path / 'test_bundles.sqlite3'}"
    )
    monkeypatch.setattr(settings, "password_iterations", 1_000)
    init_db()
    return TestClient(app)


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def register(client: TestClient) -> str:
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
    return resp.json()["access_token"]


def test_list_role_bundles(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    token = register(client)

    resp = client.get("/api/role-bundles", headers=auth_header(token))
    assert resp.status_code == 200
    bundles = resp.json()
    names = {b["role_name"] for b in bundles}
    assert {"客服专员", "数据分析师", "前端工程师"} <= names

    analyst = next(b for b in bundles if b["role_name"] == "数据分析师")
    assert analyst["capability_keys"] == [
        "data_query",
        "data_analysis",
        "report_generation",
    ]
    assert analyst["resolved"]["risk_gate"] in ("auto", "approval", "prohibited_auto")
    assert "code_execution" in analyst["resolved"]["toolsets"]


def test_list_role_bundles_requires_auth(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    resp = client.get("/api/role-bundles")
    assert resp.status_code == 401


def test_create_agent_from_role_bundle(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    token = register(client)

    resp = client.post(
        "/api/agents",
        headers=auth_header(token),
        json={
            "name": "小数",
            "description": "看数据的",
            "department_name": "数据部",
            "prompt": "你负责数据分析",
            "role_spec": {
                "role_name": "数据分析师",
                "source_request": "我要一个数据分析师",
                "role_bundle_key": "数据分析师",
            },
        },
    )
    assert resp.status_code == 200
    spec = resp.json()["spec"]
    cap_keys = {c["capability_key"] for c in spec["capabilities"]}
    assert cap_keys == {"data_query", "data_analysis", "report_generation"}


def test_role_bundle_merges_with_explicit_keys(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    token = register(client)

    resp = client.post(
        "/api/agents",
        headers=auth_header(token),
        json={
            "name": "多面手",
            "description": "d",
            "department_name": "综合部",
            "prompt": "p",
            "role_spec": {
                "role_name": "内容运营",
                "role_bundle_key": "内容运营",
                "capability_keys": ["data_analysis"],  # extra, on top of the bundle
            },
        },
    )
    assert resp.status_code == 200
    cap_keys = {c["capability_key"] for c in resp.json()["spec"]["capabilities"]}
    assert {"content_writing", "social_content", "data_analysis"} <= cap_keys


def test_unknown_role_bundle_rejected(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    token = register(client)

    resp = client.post(
        "/api/agents",
        headers=auth_header(token),
        json={
            "name": "x",
            "description": "d",
            "department_name": "综合部",
            "prompt": "p",
            "role_spec": {"role_name": "x", "role_bundle_key": "不存在的岗位"},
        },
    )
    assert resp.status_code == 400
