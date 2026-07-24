from __future__ import annotations

import hashlib
import hmac
import time

from fastapi import HTTPException, Request

from app.core.config import settings
from app.core.database import Database


class DurableRateLimiter:
    """Database-backed limiter shared across restarts and API connections."""

    def check(
        self,
        conn: Database,
        key: str,
        *,
        limit: int,
        window_seconds: int,
    ) -> None:
        now = int(time.time())
        cutoff = now - window_seconds
        retention_seconds = max(
            settings.registration_rate_window_seconds,
            settings.login_rate_window_seconds,
            settings.telemetry_rate_window_seconds,
        )
        conn.execute(
            "DELETE FROM request_rate_limits WHERE occurred_at <= ?",
            (now - retention_seconds,),
        )
        if conn.dialect == "postgres":
            conn.execute("SELECT pg_advisory_xact_lock(hashtext(?))", (key,))
        conn.execute(
            "DELETE FROM request_rate_limits WHERE bucket = ? AND occurred_at <= ?",
            (key, cutoff),
        )
        row = conn.execute(
            "SELECT COUNT(*) AS count, MIN(occurred_at) AS oldest "
            "FROM request_rate_limits WHERE bucket = ?",
            (key,),
        ).fetchone()
        if row is not None and int(row["count"] or 0) >= limit:
            oldest = int(row["oldest"] or now)
            retry_after = max(1, window_seconds - (now - oldest))
            raise HTTPException(
                status_code=429,
                detail="请求太频繁，请稍后再试",
                headers={"Retry-After": str(retry_after)},
            )
        conn.execute(
            "INSERT INTO request_rate_limits (bucket, occurred_at) VALUES (?, ?)",
            (key, now),
        )

    def reset(self) -> None:
        # Tests use isolated databases, so there is no process-global state.
        return None


auth_rate_limiter = DurableRateLimiter()


def client_ip(request: Request) -> str:
    if settings.trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            # AgentPulse is only exposed through its own Caddy container. Use
            # the hop closest to that trusted proxy so a client-supplied first
            # entry cannot rotate rate-limit buckets.
            return forwarded.rsplit(",", 1)[-1].strip()
    return request.client.host if request.client else "unknown"


def anonymized_client_key(request: Request) -> str:
    digest = hmac.new(
        settings.auth_secret_key.encode("utf-8"),
        client_ip(request).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return digest[:32]


def enforce_auth_rate_limit(
    request: Request,
    conn: Database,
    *,
    kind: str,
    limit: int,
    window_seconds: int,
) -> None:
    if not settings.auth_rate_limit_enabled:
        return
    auth_rate_limiter.check(
        conn,
        f"{kind}:{anonymized_client_key(request)}",
        limit=limit,
        window_seconds=window_seconds,
    )
