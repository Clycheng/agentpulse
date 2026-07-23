from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class ContentSource(BaseModel):
    id: str | None = None
    title: str = ""
    url: str | None = None

    @model_validator(mode="after")
    def require_reference(self):
        if not self.id and not self.url:
            raise ValueError("each source needs a knowledge id or URL")
        return self

    @property
    def reference(self) -> str:
        return self.id or self.url or ""


class ScheduledContent(BaseModel):
    publish_at: str
    order: int = Field(ge=1)
    content_type: str
    title: str
    hook: str
    body: str | None = None
    script: str | None = None
    cta: str
    asset_suggestion: str
    source_refs: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_body_or_script(self):
        if not (self.body or self.script):
            raise ValueError("each content item needs body or script")
        return self


class ContentPackageV1(BaseModel):
    platform: str
    audience: str
    objective: str
    schedule: list[ScheduledContent] = Field(min_length=1)
    sources: list[ContentSource] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_source_references(self):
        available = {source.reference for source in self.sources}
        for item in self.schedule:
            unknown = set(item.source_refs) - available
            if unknown:
                raise ValueError(
                    f"content item {item.order} cites unknown sources: {sorted(unknown)}"
                )
        return self
