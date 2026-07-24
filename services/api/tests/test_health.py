from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import init_db
from app.main import app


def test_health_check() -> None:
    client = TestClient(app)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "agentpulse-api"}


def test_live_and_ready_health_checks(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        settings, "database_url", f"sqlite:///{tmp_path / 'health.sqlite3'}"
    )
    monkeypatch.setattr(settings, "hermes_provisioning", False)
    monkeypatch.setattr(settings, "task_worker_enabled", False)
    monkeypatch.setattr(settings, "business_worker_enabled", False)
    init_db()
    client = TestClient(app)

    live = client.get("/api/health/live")
    ready = client.get("/api/health/ready")

    assert live.status_code == 200
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"
    assert ready.json()["checks"]["database"] == "ok"
