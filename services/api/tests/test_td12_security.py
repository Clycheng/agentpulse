from __future__ import annotations

import jwt
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.config import _validate_secret_key
from app.core.database import connect, init_db
from app.core.security import create_access_token, decode_access_token
from app.main import app
from app.runtime.hermes_client import HermesBackendError, _subprocess_environment
from app.services.credentials import decrypt_value, encrypt_value


def test_access_token_requires_issuer_audience_and_type():
    valid = create_access_token("user_1")
    assert decode_access_token(valid)["sub"] == "user_1"

    invalid = jwt.encode(
        {"sub": "user_1", "exp": 4_102_444_800},
        settings.auth_secret_key,
        algorithm="HS256",
    )
    try:
        decode_access_token(invalid)
    except ValueError:
        pass
    else:  # pragma: no cover
        raise AssertionError("JWT without required claims was accepted")


def test_credentials_use_independent_v2_key(monkeypatch):
    monkeypatch.setattr(settings, "credential_encryption_key", "credential-key-a")
    encrypted = encrypt_value("secret-value")
    assert encrypted.startswith("fernet-v2:")
    assert "secret-value" not in encrypted
    assert decrypt_value(encrypted) == "secret-value"

    monkeypatch.setattr(settings, "credential_encryption_key", "credential-key-b")
    try:
        decrypt_value(encrypted)
    except ValueError:
        pass
    else:  # pragma: no cover
        raise AssertionError("ciphertext decrypted with the wrong key")


def test_hermes_subprocess_does_not_inherit_server_secrets(monkeypatch):
    monkeypatch.setenv("AGENTPULSE_DATABASE_URL", "postgresql://secret")
    monkeypatch.setenv("AGENTPULSE_AUTH_SECRET_KEY", "server-secret")
    environment = _subprocess_environment({"DEEPSEEK_API_KEY": "model-secret"})
    assert environment["DEEPSEEK_API_KEY"] == "model-secret"
    assert "AGENTPULSE_DATABASE_URL" not in environment
    assert "AGENTPULSE_AUTH_SECRET_KEY" not in environment

    try:
        _subprocess_environment({"DATABASE_URL": "forbidden"})
    except HermesBackendError:
        pass
    else:  # pragma: no cover
        raise AssertionError("unexpected Hermes environment key was accepted")


def test_telemetry_is_aggregate_only(tmp_path, monkeypatch):
    monkeypatch.setattr(
        settings, "database_url", f"sqlite:///{tmp_path / 'telemetry.sqlite3'}"
    )
    init_db()
    client = TestClient(app)
    response = client.post(
        "/api/telemetry/events",
        json={"event": "download_macos"},
        headers={"User-Agent": "must-not-be-stored"},
    )
    assert response.status_code == 204
    assert client.post(
        "/api/telemetry/events", json={"event": "unknown"}
    ).status_code == 422

    conn = connect()
    try:
        event = conn.execute("SELECT * FROM site_event_daily").fetchone()
        assert event["event_name"] == "download_macos"
        assert event["count"] == 1
        schema = conn.execute(
            "SELECT sql FROM sqlite_master WHERE name = 'site_event_daily'"
        ).fetchone()["sql"]
        assert "user_agent" not in schema.lower()
        assert "ip" not in schema.lower()
    finally:
        conn.close()


def test_request_body_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(
        settings, "database_url", f"sqlite:///{tmp_path / 'body-limit.sqlite3'}"
    )
    init_db()
    client = TestClient(app)
    response = client.post(
        "/api/auth/login",
        content=b"x" * (settings.max_request_body_bytes + 1),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413


def test_chunked_request_body_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(
        settings, "database_url", f"sqlite:///{tmp_path / 'chunked-limit.sqlite3'}"
    )
    init_db()
    client = TestClient(app)

    def oversized_chunks():
        yield b"x" * (settings.max_request_body_bytes // 2 + 1)
        yield b"x" * (settings.max_request_body_bytes // 2 + 1)

    response = client.post(
        "/api/auth/login",
        content=oversized_chunks(),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413


def test_production_configuration_fails_closed(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "auth_secret_key", "short")
    monkeypatch.setattr(settings, "credential_encryption_key", "short")
    monkeypatch.setattr(settings, "cors_origins", ["http://localhost:5174"])
    monkeypatch.setattr(settings, "hermes_provisioning", True)
    monkeypatch.setattr(settings, "hermes_hosted_safe_mode", False)
    monkeypatch.setattr(settings, "model_byok_required", False)
    monkeypatch.setattr(settings, "inbound_webhooks_enabled", True)

    with pytest.raises(SystemExit):
        _validate_secret_key()
