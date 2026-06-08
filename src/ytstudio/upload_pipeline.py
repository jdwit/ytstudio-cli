import io
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from googleapiclient.http import MediaFileUpload
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
    category_id: str = Field(min_length=1)
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
# Common image extensions that look like an attempted thumbnail but YouTube
# does not accept here; flag instead of silently dropping.
NEAR_MISS_THUMBNAIL_EXTENSIONS = {".jpeg", ".gif", ".webp", ".bmp"}


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


MAX_THUMBNAIL_BYTES = 2 * 1024 * 1024


class ValidationError(Exception):
    pass


def validate_jobs(jobs: list[UploadJob]) -> None:
    """Raise ValidationError if any job has a file-level problem.

    Spec-level problems (bad YAML, missing fields) are already caught in
    discover(). This catches things only knowable from the filesystem.
    """
    problems: list[str] = []
    for job in jobs:
        if job.thumbnail_path is not None:
            size = job.thumbnail_path.stat().st_size
            if size > MAX_THUMBNAIL_BYTES:
                problems.append(
                    f"{job.thumbnail_path.name}: thumbnail too large "
                    f"({size} bytes > {MAX_THUMBNAIL_BYTES})"
                )
    if problems:
        raise ValidationError("\n".join(problems))


def to_youtube_body(spec: UploadSpec) -> dict:
    """Convert an UploadSpec to a videos.insert request body."""
    snippet: dict[str, Any] = {
        "title": spec.title,
        "description": spec.description,
        "categoryId": spec.category_id,
        "tags": list(spec.tags),
    }
    if spec.default_language:
        snippet["defaultLanguage"] = spec.default_language
    if spec.default_audio_language:
        snippet["defaultAudioLanguage"] = spec.default_audio_language

    status: dict[str, Any] = {
        "privacyStatus": spec.privacy.value,
        "selfDeclaredMadeForKids": spec.made_for_kids,
    }
    if spec.publish_at is not None:
        status["publishAt"] = spec.publish_at.isoformat()

    return {"snippet": snippet, "status": status}


def write_back(sidecar_path: Path, *, video_id: str, uploaded_at_iso: str) -> None:
    """Patch the sidecar yaml with video_id and uploaded_at, preserving comments."""
    yaml = _yaml_loader()
    data = yaml.load(sidecar_path.read_text())
    data["video_id"] = video_id
    data["uploaded_at"] = uploaded_at_iso

    buf = io.StringIO()
    yaml.dump(data, buf)
    sidecar_path.write_text(buf.getvalue())


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

    children = [c for c in path.iterdir() if c.is_file()]
    videos = sorted(c for c in children if c.suffix.lower() in VIDEO_EXTENSIONS)
    video_stems = {v.stem for v in videos}

    orphan_sidecars = sorted(
        c for c in children if c.suffix.lower() == ".yaml" and c.stem not in video_stems
    )
    if orphan_sidecars:
        names = ", ".join(o.name for o in orphan_sidecars)
        raise DiscoveryError(f"orphan sidecar(s) with no matching video: {names}")

    near_miss_thumbs = sorted(
        c
        for c in children
        if c.suffix.lower() in NEAR_MISS_THUMBNAIL_EXTENSIONS and c.stem in video_stems
    )
    if near_miss_thumbs:
        names = ", ".join(n.name for n in near_miss_thumbs)
        raise DiscoveryError(f"unsupported thumbnail format(s) (use .jpg or .png): {names}")

    return [_pair(v) for v in videos]


ProgressCallback = Callable[[int, int], None]


def upload_video(
    service: Any,
    job: UploadJob,
    *,
    on_progress: ProgressCallback,
    chunk_size: int = 4 * 1024 * 1024,
) -> str:
    """Resumable upload of one video. Returns the YouTube video id."""
    media = MediaFileUpload(
        str(job.video_path),
        chunksize=chunk_size,
        resumable=True,
        mimetype="video/*",
    )
    request = service.videos().insert(
        part="snippet,status",
        body=to_youtube_body(job.spec),
        media_body=media,
    )
    response: dict | None = None
    while response is None:
        status, response = request.next_chunk(num_retries=3)
        if status is not None:
            on_progress(status.resumable_progress, status.total_size)
    on_progress(response.get("size", 0) or 0, response.get("size", 0) or 0)
    return response["id"]


def set_thumbnail(service: Any, *, video_id: str, thumbnail_path: Path) -> None:
    media = MediaFileUpload(str(thumbnail_path), resumable=False)
    service.thumbnails().set(videoId=video_id, media_body=media).execute()
