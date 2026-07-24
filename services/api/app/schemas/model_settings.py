from typing import Literal

from pydantic import BaseModel, Field


class ModelProviderUpdate(BaseModel):
    provider: Literal["deepseek"] = "deepseek"
    api_key: str = Field(min_length=8, max_length=512)
    model: str | None = Field(default=None, min_length=1, max_length=120)


class ModelProviderOut(BaseModel):
    provider: Literal["deepseek"] = "deepseek"
    model: str
    configured: bool
    masked_api_key: str
    validation_status: Literal["unconfigured", "valid", "invalid"]
    last_validated_at: str | None
    agents_total: int
    agents_ready: int
    agents_waiting: int
    agents_failed: int
