import os
from pathlib import Path
import shutil

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import Database, get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "agentpulse-api"}


@router.get("/health/live")
def liveness() -> dict[str, str]:
    return {"status": "ok", "service": "agentpulse-api"}


@router.get("/health/ready")
def readiness(request: Request, conn: Database = Depends(get_db)):
    checks: dict[str, str] = {}
    try:
        conn.execute("SELECT 1")
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "unavailable"

    if settings.hermes_provisioning:
        checks["hermes"] = "ok" if shutil.which(settings.hermes_bin) else "missing"
        work_root = Path(os.path.abspath(settings.hermes_work_root or ".hermes-data"))
        checks["work_root"] = (
            "ok" if work_root.is_dir() and os.access(work_root, os.W_OK) else "unavailable"
        )
    else:
        checks["hermes"] = "disabled"
        checks["work_root"] = "disabled"

    for name, enabled in (
        ("task_worker", settings.task_worker_enabled),
        ("business_worker", settings.business_worker_enabled),
    ):
        task = getattr(request.app.state, name, None)
        checks[name] = "disabled" if not enabled else (
            "ok" if task is not None and not task.done() else "stopped"
        )

    ready = all(value not in {"unavailable", "missing", "stopped"} for value in checks.values())
    payload = {"status": "ready" if ready else "not_ready", "checks": checks}
    return payload if ready else JSONResponse(status_code=503, content=payload)
