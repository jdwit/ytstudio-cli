from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field, field_validator, model_validator
from ruamel.yaml import YAML


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
            now = datetime.now(UTC)
            if self.publish_at <= now:
                raise ValueError("publish_at must be in the future")
            self.privacy = Privacy.private
        return self


VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm"}
THUMBNAIL_EXTENSIONS = (".jpg", ".png")


class DiscoveryError(Exception):
    pass


@dataclass
class UploadJob:
    video_path: Path
    sidecar_path: Path
    spec: UploadSpec
    thumbnail_path: Path | None
    already_uploaded: bool


def _yaml_loader() -> YAML:
    yaml = YAML(typ="rt")
    yaml.preserve_quotes = True
    return yaml


def _load_sidecar(path: Path) -> UploadSpec:
    raw = _yaml_loader().load(path.read_text())
    if raw is None:
        raise DiscoveryError(f"{path}: sidecar is empty")
    try:
        return UploadSpec.model_validate(dict(raw))
    except Exception as exc:
        raise DiscoveryError(f"{path}: {exc}") from exc


def _find_thumbnail(video_path: Path) -> Path | None:
    for ext in THUMBNAIL_EXTENSIONS:
        candidate = video_path.with_suffix(ext)
        if candidate.exists():
            return candidate
    return None


def _pair(video_path: Path) -> UploadJob:
    sidecar = video_path.with_suffix(".yaml")
    if not sidecar.exists():
        raise DiscoveryError(f"{video_path.name}: no sidecar yaml next to it")
    spec = _load_sidecar(sidecar)
    return UploadJob(
        video_path=video_path,
        sidecar_path=sidecar,
        spec=spec,
        thumbnail_path=_find_thumbnail(video_path),
        already_uploaded=spec.video_id is not None,
    )


def discover(path: Path) -> list[UploadJob]:
    """Return one UploadJob per video file in `path`.

    `path` is either a single video file or a directory whose direct children
    are scanned (no recursion).
    """
    path = Path(path)
    if path.is_file():
        if path.suffix.lower() not in VIDEO_EXTENSIONS:
            raise DiscoveryError(f"{path}: not a supported video file")
        return [_pair(path)]
    if not path.is_dir():
        raise DiscoveryError(f"{path}: not a file or directory")

    videos = sorted(
        child
        for child in path.iterdir()
        if child.is_file() and child.suffix.lower() in VIDEO_EXTENSIONS
    )
    return [_pair(v) for v in videos]
