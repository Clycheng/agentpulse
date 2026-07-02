from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "IntentPulse API"
    app_version: str = "0.1.0"
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:5174",
    ]

    model_config = SettingsConfigDict(env_file=".env", env_prefix="INTENTPULSE_")


settings = Settings()
