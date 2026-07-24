"""Password hashing and strict, short-lived access tokens."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
from typing import Any

import jwt
from jwt.exceptions import InvalidTokenError

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
# JWT (PyJWT, HS256)
# ---------------------------------------------------------------------------

JWT_ALGORITHM = "HS256"
JWT_ISSUER = "agentpulse-api"
JWT_AUDIENCE = "agentpulse-desktop"


def create_access_token(user_id: str) -> str:
    now = int(time.time())
    payload: dict[str, Any] = {
        "sub": user_id,
        "iat": now,
        "exp": now + settings.access_token_ttl_hours * 3600,
        "jti": secrets.token_urlsafe(16),
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "typ": "access",
    }
    return jwt.encode(payload, settings.auth_secret_key, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            settings.auth_secret_key,
            algorithms=[JWT_ALGORITHM],
            issuer=JWT_ISSUER,
            audience=JWT_AUDIENCE,
            options={
                "require": ["sub", "iat", "exp", "jti", "iss", "aud", "typ"]
            },
        )
    except InvalidTokenError as exc:
        raise ValueError("invalid token") from exc

    if not isinstance(payload.get("sub"), str) or payload.get("typ") != "access":
        raise ValueError("invalid token subject")
    return payload
