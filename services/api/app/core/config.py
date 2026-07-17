from __future__ import annotations

import os
import sys

from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_AUTH_SECRET = "agentpulse-local-dev-secret"


class Settings(BaseSettings):
    app_name: str = "AgentPulse API"
    app_version: str = "0.1.0"
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5175",
    ]
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-v4-pro"
    deepseek_timeout_seconds: float = 60.0
    deepseek_temperature: float = 0.7
    deepseek_thinking_enabled: bool = False
    database_url: str = "postgresql://agentpulse:agentpulse@127.0.0.1:55432/agentpulse"
    # Absolute root for Hermes per-employee work dirs (ADR 0005). Empty → resolved
    # to an absolute ".hermes-data" under the server's cwd at run time.
    hermes_work_root: str = ""
    hermes_bin: str = "hermes"
    # When true, provisioning drives the real `hermes` CLI (creates profiles).
    hermes_provisioning: bool = False
    # ADR 0008 item 4: how long our own approval_bridge waits for the owner
    # before auto-denying a suspended run. MUST stay comfortably under 60 —
    # Hermes's ACP adapter hardcodes a 60s fail-closed timeout for
    # request_permission (acp_adapter/permissions.py::make_approval_callback,
    # called with no `timeout=` override at acp_adapter/server.py:1421) and
    # does NOT read the `approvals.timeout` config key on that path (only the
    # CLI-interactive prompt_dangerous_approval() does). If our timeout ever
    # creeps above ~55s, Hermes's own timeout can fire first, racing our
    # bridge Future's cancellation against a late owner click. Re-verify this
    # constant against the installed Hermes version after any `hermes update`.
    approval_bridge_timeout_seconds: int = 50
    # TD-08-T2: idle-reflection cron.
    idle_thinking_cron: bool = False
    idle_cron_interval_seconds: int = 3600
    auth_secret_key: str = _DEFAULT_AUTH_SECRET
    access_token_ttl_hours: int = 24 * 14
    password_iterations: int = 260_000

    model_config = SettingsConfigDict(env_file=".env", env_prefix="AGENTPULSE_")


settings = Settings()


def _validate_secret_key() -> None:
    """Refuse to start with the default dev secret in non-dev environments."""
    if settings.auth_secret_key == _DEFAULT_AUTH_SECRET:
        # Allow the default only when explicitly opted-in via env var
        if os.environ.get("AGENTPULSE_ALLOW_DEFAULT_SECRET", "").lower() not in (
            "1",
            "true",
            "yes",
        ):
            print(
                "ERROR: AGENTPULSE_AUTH_SECRET_KEY is still the default dev value.\n"
                "       Set AGENTPULSE_AUTH_SECRET_KEY to a strong random secret,\n"
                "       or set AGENTPULSE_ALLOW_DEFAULT_SECRET=1 for local dev only.",
                file=sys.stderr,
            )
            sys.exit(1)


_validate_secret_key()
