import json

from fastapi.testclient import TestClient

from app.api.routes import model_settings as model_settings_routes
from app.core.config import settings
from app.core.database import connect, init_db
from app.main import app
from app.runtime.profile_provisioner import RecordOnlyProvisioner
from app.services.credentials import CredentialError, decrypt_value
from app.services.model_credentials import runtime_model_environment


def _client(tmp_path, monkeypatch):
    monkeypatch.setattr(
        settings, "database_url", f"sqlite:///{tmp_path / 'model-settings.sqlite3'}"
    )
    monkeypatch.setattr(settings, "password_iterations", 1_000)
    monkeypatch.setattr(settings, "model_byok_required", True)
    monkeypatch.setattr(settings, "hermes_provisioning", True)
    monkeypatch.setattr(settings, "hermes_bin", "true")
    monkeypatch.setattr(settings, "deepseek_allowed_models", [settings.deepseek_model])

    recorder = RecordOnlyProvisioner()
    import app.orchestration.supply as supply_module

    monkeypatch.setattr(
        supply_module, "build_provisioner_from_settings", lambda: recorder
    )

    async def accept_key(_api_key: str) -> None:
        return None

    monkeypatch.setattr(model_settings_routes, "validate_deepseek_key", accept_key)
    init_db()
    client = TestClient(app)
    response = client.post(
        "/api/auth/register",
        json={
            "email": "owner@example.com",
            "password": "agentpulse123",
            "display_name": "老板",
            "workspace_name": "内容公司",
        },
    )
    assert response.status_code == 200
    auth = response.json()
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    return client, headers, auth["workspace"]["id"], recorder


def test_model_key_is_encrypted_and_provisions_default_team(tmp_path, monkeypatch):
    client, headers, workspace_id, recorder = _client(tmp_path, monkeypatch)
    secret = "sk-deepseek-private-123456789"

    before = client.get("/api/settings/model-provider", headers=headers)
    assert before.status_code == 200
    assert before.json()["configured"] is False
    assert before.json()["agents_waiting"] == 4

    response = client.put(
        "/api/settings/model-provider",
        headers=headers,
        json={"provider": "deepseek", "api_key": secret},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["configured"] is True
    assert payload["agents_ready"] == 4
    assert secret not in response.text
    assert payload["masked_api_key"].startswith("sk-")

    conn = connect()
    try:
        row = conn.execute(
            "SELECT encrypted_api_key FROM workspace_model_credentials "
            "WHERE workspace_id = ?",
            (workspace_id,),
        ).fetchone()
        assert row is not None
        assert row["encrypted_api_key"] != secret
        assert secret not in json.dumps(dict(row))
        assert runtime_model_environment(conn, workspace_id) == {
            "DEEPSEEK_API_KEY": secret
        }
    finally:
        conn.close()

    actions = recorder.get_actions()
    assert sum(action.action == "create_profile" for action in actions) == 4
    assert all(action.action != "write_credentials" for action in actions)


def test_delete_key_blocks_new_model_runs_without_deleting_profiles(
    tmp_path, monkeypatch
):
    client, headers, workspace_id, _ = _client(tmp_path, monkeypatch)
    client.put(
        "/api/settings/model-provider",
        headers=headers,
        json={"api_key": "sk-deepseek-private-abcdef"},
    )

    response = client.delete("/api/settings/model-provider", headers=headers)
    assert response.status_code == 200
    assert response.json()["configured"] is False
    assert response.json()["agents_waiting"] == 4

    conn = connect()
    try:
        profiles = conn.execute(
            "SELECT hermes_profile, status FROM agent_specs WHERE workspace_id = ?",
            (workspace_id,),
        ).fetchall()
        assert all(row["hermes_profile"] for row in profiles)
        assert {row["status"] for row in profiles} == {"blocked_on_credentials"}
    finally:
        conn.close()


def test_workspace_model_keys_are_isolated_and_wrong_secret_fails(
    tmp_path, monkeypatch
):
    client, headers, workspace_id, _ = _client(tmp_path, monkeypatch)
    first_key = "sk-first-workspace-123456"
    client.put(
        "/api/settings/model-provider",
        headers=headers,
        json={"api_key": first_key},
    )
    second = client.post(
        "/api/auth/register",
        json={
            "email": "other@example.com",
            "password": "agentpulse123",
            "display_name": "另一位老板",
            "workspace_name": "另一家公司",
        },
    ).json()
    second_headers = {"Authorization": f"Bearer {second['access_token']}"}
    second_key = "sk-second-workspace-654321"
    client.put(
        "/api/settings/model-provider",
        headers=second_headers,
        json={"api_key": second_key},
    )

    conn = connect()
    try:
        assert runtime_model_environment(conn, workspace_id)["DEEPSEEK_API_KEY"] == first_key
        assert (
            runtime_model_environment(conn, second["workspace"]["id"])[
                "DEEPSEEK_API_KEY"
            ]
            == second_key
        )
        encrypted = conn.execute(
            "SELECT encrypted_api_key FROM workspace_model_credentials "
            "WHERE workspace_id = ?",
            (workspace_id,),
        ).fetchone()["encrypted_api_key"]
        try:
            decrypt_value(encrypted, secret="different-auth-secret")
        except CredentialError:
            pass
        else:
            raise AssertionError("ciphertext decrypted with the wrong server secret")
    finally:
        conn.close()


def test_invalid_key_or_model_is_not_stored(tmp_path, monkeypatch):
    client, headers, workspace_id, _ = _client(tmp_path, monkeypatch)

    async def reject_key(_api_key: str) -> None:
        from app.services.model_credentials import ModelCredentialValidationError

        raise ModelCredentialValidationError("DeepSeek API Key 无效或无权访问")

    monkeypatch.setattr(model_settings_routes, "validate_deepseek_key", reject_key)
    response = client.put(
        "/api/settings/model-provider",
        headers=headers,
        json={"api_key": "sk-invalid-key"},
    )
    assert response.status_code == 422

    response = client.put(
        "/api/settings/model-provider",
        headers=headers,
        json={"api_key": "sk-valid-shape", "model": "unapproved-model"},
    )
    assert response.status_code == 422

    conn = connect()
    try:
        assert conn.execute(
            "SELECT id FROM workspace_model_credentials WHERE workspace_id = ?",
            (workspace_id,),
        ).fetchone() is None
    finally:
        conn.close()
