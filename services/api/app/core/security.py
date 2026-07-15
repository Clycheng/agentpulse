"""Authentication: password hashing (pbkdf2_sha256) + JWT (python-jose).

Switched from a hand-rolled HMAC token to standard python-jose HS256 JWT
for auditability and interop.  The old hand-rolled token format is still
accepted during a transition window (OLD_TOKEN_GRACE_DAYS, default 30 days)
so existing sessions don't break.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from jose.constants import Algorithms

from app.core.config import settings

# ---------------------------------------------------------------------------
# Password hashing (unchanged)
# ---------------------------------------------------------------------------


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def hash_password(password: str) -> str:
    salt = secrets.token_urlsafe(18)
    iterations = settings.password_iterations
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations
    )
    return f"pbkdf2_sha256${iterations}${salt}${_b64encode(digest)}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations_raw, salt, digest = password_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iterations_raw)
        candidate = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations
        )
        return hmac.compare_digest(_b64encode(candidate), digest)
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# JWT (python-jose, HS256)
# ---------------------------------------------------------------------------

JWT_ALGORITHM = Algorithms.HS256
# Grace window for tokens issued by the *old* hand-rolled format so existing
# sessions don't break on deploy.  Set to 0 to reject immediately.
OLD_TOKEN_GRACE_DAYS = 30


def create_access_token(user_id: str) -> str:
    """Issue a standard python-jose HS256 JWT."""
    now = int(time.time())
    payload: dict[str, Any] = {
        "sub": user_id,
        "iat": now,
        "exp": now + settings.access_token_ttl_hours * 3600,
        "jti": secrets.token_urlsafe(8),
        "iss": "agentpulse-api",
    }
    return jwt.encode(payload, settings.auth_secret_key, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """Validate a JWT and return its payload.

    Accepts both the new python-jose format and the old hand-rolled format
    during the grace window so deployments don't immediately invalidate
    every active session.
    """
    # --- Try python-jose first ---
    try:
        payload = jwt.decode(
            token, settings.auth_secret_key, algorithms=[JWT_ALGORITHM]
        )
    except JWTError:
        # --- Fall back to the old hand-rolled format (grace window) ---
        if OLD_TOKEN_GRACE_DAYS <= 0:
            raise ValueError("invalid token")
        payload = _decode_old_token(token)

    if not isinstance(payload.get("sub"), str):
        raise ValueError("invalid token subject")
    return payload


def _decode_old_token(token: str) -> dict[str, Any]:
    """Decode the legacy hand-rolled token format (grace window).
    
    Returns the payload or raises ``ValueError`` if expired / malformed.
    """
    try:
        body, signature = token.split(".", 1)
    except ValueError as exc:
        raise ValueError("invalid token") from exc

    # Re-create the old signer so we can verify the signature
    def _old_sign(data: str) -> str:
        digest = hmac.new(
            settings.auth_secret_key.encode("utf-8"),
            data.encode("ascii"),
            hashlib.sha256,
        ).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

    if not hmac.compare_digest(_old_sign(body), signature):
        raise ValueError("invalid token signature")

    payload = json.loads(
        base64.urlsafe_b64decode(body + "=" * (-len(body) % 4))
    )
    exp = int(payload.get("exp", 0))
    if exp < int(time.time()):
        raise ValueError("legacy token expired")

    # Grace-window check: reject tokens older than OLD_TOKEN_GRACE_DAYS
    iat = int(payload.get("iat", 0))
    cutoff = (datetime.now(UTC) - timedelta(days=OLD_TOKEN_GRACE_DAYS)).timestamp()
    if iat and iat < cutoff:
        raise ValueError("legacy token outside grace window")

    return payload
