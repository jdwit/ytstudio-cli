"""Pydantic v2 output models for MCP tools.

Returning a BaseModel from a FastMCP tool produces structured output for the
client. We keep these models close to the existing dataclasses but free of any
console/rich coupling.
"""

from typing import Any

from pydantic import BaseModel, Field

from ytstudio.commands.comments import Comment
from ytstudio.commands.livestreams import Broadcast, StreamIngest, _redact_key
from ytstudio.commands.videos import Video


class VideoOut(BaseModel):
    id: str
    title: str
    description: str = ""
    published_at: str = ""
    views: int = 0
    likes: int = 0
    comments: int = 0
    duration: str = ""
    privacy: str = ""
    tags: list[str] = Field(default_factory=list)
    category_id: str = ""
    default_language: str | None = None
    default_audio_language: str | None = None
    localizations: dict[str, Any] = Field(default_factory=dict)
    scheduled_publish_at: str | None = None


class VideoListOut(BaseModel):
    videos: list[VideoOut]
    next_page_token: str | None = None
    total_results: int | None = None


class CommentOut(BaseModel):
    id: str
    author: str
    text: str
    likes: int = 0
    published_at: str = ""
    video_id: str = ""


class CommentListOut(BaseModel):
    comments: list[CommentOut]


class BroadcastIngestOut(BaseModel):
    stream_id: str
    ingestion_address: str = ""
    backup_ingestion_address: str = ""
    rtmps_ingestion_address: str = ""
    rtmps_backup_ingestion_address: str = ""
    stream_name: str = ""  # always redacted before reaching this model
    format: str = ""
    frame_rate: str = ""
    resolution: str = ""


class BroadcastOut(BaseModel):
    id: str
    title: str
    lifecycle_status: str = ""
    scheduled_start: str = ""
    scheduled_end: str = ""
    description: str = ""
    privacy: str = "public"
    actual_start: str = ""
    actual_end: str = ""
    bound_stream_id: str = ""
    made_for_kids: bool = False
    ingest: BroadcastIngestOut | None = None


class BroadcastListOut(BaseModel):
    broadcasts: list[BroadcastOut]
    next_page_token: str | None = None


class PlaylistOut(BaseModel):
    id: str
    title: str
    description: str = ""
    privacy: str = "private"
    item_count: int = 0
    published_at: str = ""


class PlaylistListOut(BaseModel):
    playlists: list[PlaylistOut]
    next_page_token: str | None = None


class PlaylistItemOut(BaseModel):
    id: str  # the playlistItem id (used for delete)
    playlist_id: str
    video_id: str
    title: str = ""
    position: int = 0


class AnalyticsRowOut(BaseModel):
    headers: list[str]
    rows: list[list[Any]]


class AnalyticsOverviewOut(BaseModel):
    days: int
    views: int = 0
    estimated_minutes_watched: int = 0
    average_view_duration: int = 0
    subscribers_gained: int = 0
    subscribers_lost: int = 0
    likes: int = 0
    comments: int = 0


class UpdateResultOut(BaseModel):
    id: str
    updated_fields: list[str]


class ModerationResultOut(BaseModel):
    count: int
    status: str
    ban_author: bool = False


# --- helpers ---


def video_to_out(v: Video) -> VideoOut:
    return VideoOut(
        id=v.id,
        title=v.title,
        description=v.description,
        published_at=v.published_at,
        views=v.views,
        likes=v.likes,
        comments=v.comments,
        duration=v.duration,
        privacy=v.privacy,
        tags=list(v.tags),
        category_id=v.category_id,
        default_language=v.default_language,
        default_audio_language=v.default_audio_language,
        localizations=dict(v.localizations),
        scheduled_publish_at=v.scheduled_publish_at,
    )


def comment_to_out(c: Comment) -> CommentOut:
    return CommentOut(
        id=c.id,
        author=c.author,
        text=c.text,
        likes=c.likes,
        published_at=c.published_at,
        video_id=c.video_id,
    )


def broadcast_to_out(b: Broadcast, ingest: StreamIngest | None = None) -> BroadcastOut:
    ingest_out = None
    if ingest is not None:
        ingest_out = BroadcastIngestOut(
            stream_id=ingest.stream_id,
            ingestion_address=ingest.ingestion_address,
            backup_ingestion_address=ingest.backup_ingestion_address,
            rtmps_ingestion_address=ingest.rtmps_ingestion_address,
            rtmps_backup_ingestion_address=ingest.rtmps_backup_ingestion_address,
            # MCP never returns the raw stream key.
            stream_name=_redact_key(ingest.stream_name),
            format=ingest.format,
            frame_rate=ingest.frame_rate,
            resolution=ingest.resolution,
        )
    return BroadcastOut(
        id=b.id,
        title=b.title,
        lifecycle_status=b.lifecycle_status,
        scheduled_start=b.scheduled_start,
        scheduled_end=b.scheduled_end,
        description=b.description,
        privacy=b.privacy,
        actual_start=b.actual_start,
        actual_end=b.actual_end,
        bound_stream_id=b.bound_stream_id,
        made_for_kids=b.made_for_kids,
        ingest=ingest_out,
    )
