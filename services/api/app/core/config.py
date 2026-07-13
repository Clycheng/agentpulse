from pydantic_settings import BaseSettings, SettingsConfigDict


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
    deepseek_model: str = "deepseek-v4-flash"
    deepseek_timeout_seconds: float = 60.0
    deepseek_temperature: float = 0.7
    deepseek_thinking_enabled: bool = False
    database_url: str = "postgresql://agentpulse:agentpulse@127.0.0.1:55432/agentpulse"
    # Absolute root for Hermes per-employee work dirs (ADR 0005). Empty → resolved
    # to an absolute ".hermes-data" under the server's cwd at run time.
    hermes_work_root: str = ""
    hermes_bin: str = "hermes"
    # When true, provisioning drives the real `hermes` CLI (creates profiles).
    # Off by default so tests / non-Hermes envs use the record-only provisioner.
    hermes_provisioning: bool = False
    auth_secret_key: str = "agentpulse-local-dev-secret"
    access_token_ttl_hours: int = 24 * 14
    password_iterations: int = 260_000

    model_config = SettingsConfigDict(env_file=".env", env_prefix="AGENTPULSE_")


settings = Settings()
