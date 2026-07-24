from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import connect
from app.core.database import init_db
from app.core.rate_limit import auth_rate_limiter
from app.core.rate_limit import client_ip
from app.main import app


def _configure(tmp_path, monkeypatch, name: str) -> TestClient:
    monkeypatch.setattr(
        settings, "database_url", f"sqlite:///{tmp_path / f'{name}.sqlite3'}"
    )
    monkeypatch.setattr(settings, "password_iterations", 1_000)
    monkeypatch.setattr(settings, "hermes_provisioning", False)
    auth_rate_limiter.reset()
    init_db()
    return TestClient(app)


def _registration(email: str) -> dict[str, str]:
    return {
        "email": email,
        "password": "agentpulse123",
        "display_name": "老板",
        "workspace_name": "测试公司",
    }


def test_registration_is_rate_limited_by_ip(tmp_path, monkeypatch):
    client = _configure(tmp_path, monkeypatch, "register-rate")
    monkeypatch.setattr(settings, "auth_rate_limit_enabled", True)
    monkeypatch.setattr(settings, "registration_rate_limit", 1)
    monkeypatch.setattr(settings, "registration_rate_window_seconds", 3600)

    assert client.post("/api/auth/register", json=_registration("one@example.com")).status_code == 200
    response = client.post("/api/auth/register", json=_registration("two@example.com"))
    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) >= 1


def test_registration_stops_at_public_alpha_capacity(tmp_path, monkeypatch):
    client = _configure(tmp_path, monkeypatch, "register-capacity")
    monkeypatch.setattr(settings, "auth_rate_limit_enabled", False)
    monkeypatch.setattr(settings, "registration_max_users", 1)

    assert client.post("/api/auth/register", json=_registration("one@example.com")).status_code == 200
    response = client.post("/api/auth/register", json=_registration("two@example.com"))
    assert response.status_code == 503
    assert response.json()["detail"] == "内测名额已满"


def test_login_is_rate_limited_by_ip(tmp_path, monkeypatch):
    client = _configure(tmp_path, monkeypatch, "login-rate")
    monkeypatch.setattr(settings, "auth_rate_limit_enabled", False)
    client.post("/api/auth/register", json=_registration("owner@example.com"))
    monkeypatch.setattr(settings, "auth_rate_limit_enabled", True)
    monkeypatch.setattr(settings, "login_rate_limit", 1)
    monkeypatch.setattr(settings, "login_rate_window_seconds", 600)

    credentials = {"email": "owner@example.com", "password": "agentpulse123"}
    assert client.post("/api/auth/login", json=credentials).status_code == 200
    assert client.post("/api/auth/login", json=credentials).status_code == 429


def test_trusted_proxy_uses_nearest_forwarded_hop(monkeypatch):
    from starlette.requests import Request

    monkeypatch.setattr(settings, "trust_proxy_headers", True)
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(b"x-forwarded-for", b"spoofed, 198.51.100.12")],
            "client": ("127.0.0.1", 1234),
        }
    )
    assert client_ip(request) == "198.51.100.12"


def test_rate_limit_cleanup_bounds_storage_without_shortening_other_windows(
    tmp_path, monkeypatch
):
    _configure(tmp_path, monkeypatch, "rate-cleanup")
    monkeypatch.setattr(settings, "registration_rate_window_seconds", 3600)
    monkeypatch.setattr(settings, "login_rate_window_seconds", 600)
    monkeypatch.setattr(settings, "telemetry_rate_window_seconds", 3600)
    monkeypatch.setattr("app.core.rate_limit.time.time", lambda: 10_000)

    conn = connect()
    try:
        conn.execute(
            "INSERT INTO request_rate_limits (bucket, occurred_at) VALUES (?, ?)",
            ("expired-other-bucket", 6_000),
        )
        conn.execute(
            "INSERT INTO request_rate_limits (bucket, occurred_at) VALUES (?, ?)",
            ("active-registration-bucket", 8_800),
        )

        auth_rate_limiter.check(
            conn,
            "login:new-client",
            limit=10,
            window_seconds=600,
        )

        assert conn.execute(
            "SELECT COUNT(*) AS count FROM request_rate_limits "
            "WHERE bucket = 'expired-other-bucket'"
        ).fetchone()["count"] == 0
        assert conn.execute(
            "SELECT COUNT(*) AS count FROM request_rate_limits "
            "WHERE bucket = 'active-registration-bucket'"
        ).fetchone()["count"] == 1
    finally:
        conn.close()
