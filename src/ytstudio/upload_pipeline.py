from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator


class Privacy(StrEnum):
    private = "private"
    unlisted = "unlisted"
    public = "public"


class UploadSpec(BaseModel):
    """Schema for a single video upload sidecar (.yaml next to the video file)."""

    title: str = Field(min_length=1, max_length=100)
    description: str = ""
    privacy: Privacy = Privacy.private
    publish_at: datetime | None = None
    tags: list[str] = Field(default_factory=list)
    category_id: str = "22"  # YouTube category 22 = People & Blogs
    default_language: str | None = None
    default_audio_language: str | None = None
    made_for_kids: bool = False
    video_id: str | None = None
    uploaded_at: datetime | None = None

    model_config = {"extra": "forbid"}

    @field_validator("publish_at")
    @classmethod
    def _publish_at_must_have_tz(cls, v: datetime | None) -> datetime | None:
        if v is None:
            return v
        if v.tzinfo is None:
            raise ValueError("publish_at must include a timezone (e.g. +02:00)")
        return v

    @model_validator(mode="after")
    def _apply_publish_at_rules(self) -> "UploadSpec":
        if self.publish_at is not None:
            now = datetime.now(timezone.utc)  # noqa: UP017 - `datetime` here is the class, not the module
            if self.publish_at <= now:
                raise ValueError("publish_at must be in the future")
            self.privacy = Privacy.private
        return self
