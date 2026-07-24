"""Encrypted credentials owned by AgentPulse, never by the Hermes runtime."""

from __future__ import annotations

import base64
import hashlib
import json

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings
from app.core.database import Database
from app.services.workspace import new_id, now_iso

_CIPHERTEXT_VERSION = "fernet-v2:"
_LEGACY_CIPHERTEXT_VERSION = "fernet-v1:"


class CredentialError(ValueError):
    pass


def _fernet(secret: str | None = None, *, legacy: bool = False) -> Fernet:
    material = (
        secret
        or settings.credential_encryption_key
        or settings.auth_secret_key
    ).encode("utf-8")
    context = b"agentpulse:credentials:v1:" if legacy else b"agentpulse:credentials:v2:"
    derived = hashlib.sha256(context + material).digest()
    return Fernet(base64.urlsafe_b64encode(derived))


def encrypt_value(value: str, *, secret: str | None = None) -> str:
    token = _fernet(secret).encrypt(value.encode("utf-8")).decode("ascii")
    return _CIPHERTEXT_VERSION + token


def decrypt_value(value: str, *, secret: str | None = None) -> str:
    legacy = value.startswith(_LEGACY_CIPHERTEXT_VERSION)
    if not value.startswith(_CIPHERTEXT_VERSION) and not legacy:
        raise CredentialError("unsupported credential ciphertext version")
    try:
        version = _LEGACY_CIPHERTEXT_VERSION if legacy else _CIPHERTEXT_VERSION
        legacy_secret = secret or settings.auth_secret_key
        plain = _fernet(legacy_secret if legacy else secret, legacy=legacy).decrypt(
            value.removeprefix(version).encode("ascii")
        )
    except (InvalidToken, ValueError) as exc:
        raise CredentialError("credential cannot be decrypted") from exc
    return plain.decode("utf-8")


def configured_names(conn: Database, agent_id: str) -> set[str]:
    rows = conn.execute(
        "SELECT credential_name FROM agent_credentials WHERE agent_id = ?",
        (agent_id,),
    ).fetchall()
    return {row["credential_name"] for row in rows}


def get_credential(conn: Database, *, agent_id: str, credential_name: str) -> str:
    row = conn.execute(
        "SELECT encrypted_value FROM agent_credentials "
        "WHERE agent_id = ? AND credential_name = ?",
        (agent_id, credential_name),
    ).fetchone()
    if row is None:
        raise CredentialError(f"credential {credential_name} is not configured")
    return decrypt_value(row["encrypted_value"])


def put_credential(
    conn: Database,
    *,
    workspace_id: str,
    agent_id: str,
    credential_name: str,
    value: str,
) -> None:
    timestamp = now_iso()
    conn.execute(
        """INSERT INTO agent_credentials (
          id, workspace_id, agent_id, credential_name, encrypted_value,
          created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (agent_id, credential_name) DO UPDATE SET
          encrypted_value = excluded.encrypted_value,
          updated_at = excluded.updated_at""",
        (
            new_id("cred"),
            workspace_id,
            agent_id,
            credential_name,
            encrypt_value(value),
            timestamp,
            timestamp,
        ),
    )
    refresh_capability_credentials(conn, agent_id=agent_id)


def delete_credential(
    conn: Database, *, workspace_id: str, agent_id: str, credential_name: str
) -> bool:
    existed = conn.execute(
        "SELECT id FROM agent_credentials WHERE workspace_id = ? AND agent_id = ? "
        "AND credential_name = ?",
        (workspace_id, agent_id, credential_name),
    ).fetchone()
    if existed is None:
        return False
    conn.execute(
        "DELETE FROM agent_credentials WHERE id = ?", (existed["id"],)
    )
    refresh_capability_credentials(conn, agent_id=agent_id)
    return True


def refresh_capability_credentials(conn: Database, *, agent_id: str) -> None:
    available = configured_names(conn, agent_id)
    rows = conn.execute(
        "SELECT id, required_credentials_json, status FROM agent_capabilities "
        "WHERE agent_id = ?",
        (agent_id,),
    ).fetchall()
    timestamp = now_iso()
    for row in rows:
        required = set(json.loads(row["required_credentials_json"] or "[]"))
        if not required or row["status"] == "disabled":
            continue
        status = "enabled" if required.issubset(available) else "credential_missing"
        if status != row["status"]:
            conn.execute(
                "UPDATE agent_capabilities SET status = ?, updated_at = ? WHERE id = ?",
                (status, timestamp, row["id"]),
            )


def reconcile_all_capability_credentials(conn: Database) -> None:
    """Repair pre-TD-10 rows that were marked enabled without stored credentials."""
    rows = conn.execute(
        "SELECT DISTINCT agent_id FROM agent_capabilities "
        "WHERE required_credentials_json <> '[]'"
    ).fetchall()
    for row in rows:
        refresh_capability_credentials(conn, agent_id=row["agent_id"])
