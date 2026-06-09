"""Playlist read helpers used by MCP playlist tools.

Mirrors the dataclass + fetch helper pattern of videos.py. There is intentionally
no Typer sub-app here; the playlists CLI is a separate PR.
"""

from dataclasses import dataclass, field

from ytstudio.api import api


@dataclass
class PlaylistRecord:
    id: str
    title: str
    description: str = ""
    privacy: str = "private"
    item_count: int = 0
    published_at: str = ""


@dataclass
class PlaylistItemRecord:
    id: str
    playlist_id: str
    video_id: str
    title: str = ""
    position: int = 0


@dataclass
class PlaylistPage:
    playlists: list[PlaylistRecord] = field(default_factory=list)
    next_page_token: str | None = None


def _parse_playlist(item: dict) -> PlaylistRecord:
    snippet = item.get("snippet") or {}
    status = item.get("status") or {}
    content = item.get("contentDetails") or {}
    return PlaylistRecord(
        id=str(item.get("id", "")),
        title=snippet.get("title", ""),
        description=snippet.get("description", ""),
        privacy=status.get("privacyStatus", "private"),
        item_count=int(content.get("itemCount", 0) or 0),
        published_at=snippet.get("publishedAt", ""),
    )


def fetch_playlists(data_service, limit: int = 25) -> PlaylistPage:
    response = (
        api(
            data_service.playlists().list(
                part="snippet,contentDetails,status",
                mine=True,
                maxResults=min(limit, 50),
            )
        )
        or {}
    )
    items = response.get("items", []) or []
    playlists = [_parse_playlist(item) for item in items[:limit]]
    return PlaylistPage(playlists=playlists, next_page_token=response.get("nextPageToken"))


def fetch_playlist(data_service, playlist_id: str) -> PlaylistRecord | None:
    response = (
        api(
            data_service.playlists().list(
                part="snippet,contentDetails,status",
                id=playlist_id,
            )
        )
        or {}
    )
    items = response.get("items", []) or []
    if not items:
        return None
    return _parse_playlist(items[0])


def fetch_playlist_items(
    data_service, playlist_id: str, limit: int = 50
) -> list[PlaylistItemRecord]:
    response = (
        api(
            data_service.playlistItems().list(
                part="snippet,contentDetails",
                playlistId=playlist_id,
                maxResults=min(limit, 50),
            )
        )
        or {}
    )
    items = response.get("items", []) or []
    out: list[PlaylistItemRecord] = []
    for item in items[:limit]:
        snippet = item.get("snippet") or {}
        content = item.get("contentDetails") or {}
        out.append(
            PlaylistItemRecord(
                id=str(item.get("id", "")),
                playlist_id=snippet.get("playlistId", playlist_id),
                video_id=content.get("videoId", "")
                or snippet.get("resourceId", {}).get("videoId", ""),
                title=snippet.get("title", ""),
                position=int(snippet.get("position", 0) or 0),
            )
        )
    return out
