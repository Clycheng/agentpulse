"""Anonymous, aggregate-only website events for the public alpha."""

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel

from app.core.config import settings
from app.core.database import Database, get_db
from app.core.rate_limit import anonymized_client_key, auth_rate_limiter

router = APIRouter(prefix="/telemetry", tags=["telemetry"])

SiteEvent = Literal[
    "download_macos",
    "download_windows",
    "install_help_macos",
    "install_help_windows",
]


class SiteEventRequest(BaseModel):
    event: SiteEvent


@router.post("/events", status_code=204)
def record_site_event(
    payload: SiteEventRequest,
    request: Request,
    conn: Database = Depends(get_db),
) -> Response:
    auth_rate_limiter.check(
        conn,
        f"telemetry:{anonymized_client_key(request)}",
        limit=settings.telemetry_rate_limit,
        window_seconds=settings.telemetry_rate_window_seconds,
    )
    event_day = datetime.now(UTC).date().isoformat()
    conn.execute(
        """INSERT INTO site_event_daily (event_name, event_day, count)
        VALUES (?, ?, 1)
        ON CONFLICT (event_name, event_day) DO UPDATE SET
          count = site_event_daily.count + 1""",
        (payload.event, event_day),
    )
    return Response(status_code=204)
