"""FastMCP server exposing the ytstudio CLI surface as MCP tools.

Read tools are always registered; write tools are only registered when the
caller passes allow_write=True. Every tool resolves a single explicit profile
captured at startup so a profile switch mid-session cannot affect an in-flight
tool call.
"""

from __future__ import annotations

import functools
import inspect
import sys
from datetime import datetime, timedelta
from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError
from pydantic import Field

from ytstudio import api as _api_module
from ytstudio.commands.comments import (
    Comment,
    ModerationStatus,
    SortOrder,
    fetch_comments,
)
from ytstudio.commands.livestreams import (
    _fetch_broadcast,
    _fetch_stream_ingest,
    _parse_broadcast,
)
from ytstudio.commands.videos import fetch_video, fetch_videos
from ytstudio.mcp.models import (
    AnalyticsOverviewOut,
    AnalyticsRowOut,
    BroadcastListOut,
    BroadcastOut,
    CommentListOut,
    ModerationResultOut,
    PlaylistItemOut,
    PlaylistListOut,
    PlaylistOut,
    UpdateResultOut,
    VideoListOut,
    VideoOut,
    broadcast_to_out,
    comment_to_out,
    video_to_out,
)
from ytstudio.mcp.playlists import (
    PlaylistRecord,
    fetch_playlist,
    fetch_playlist_items,
    fetch_playlists,
)
from ytstudio.registry import validate_dimensions, validate_metrics
from ytstudio.services import get_analytics_service, get_data_service

INSTRUCTIONS = (
    "YouTube channel management for AI agents. Read tools are always available; "
    "write tools require the server to be started with --allow-write or with "
    "YTSTUDIO_MCP_ALLOW_WRITE=1."
)


def _explain(error: HttpError) -> str:
    """Translate an HttpError into a short, human-readable message for ToolError."""
    detail: dict[str, Any] = {}
    if getattr(error, "error_details", None):
        first = error.error_details[0]
        if isinstance(first, dict):
            detail = first
    reason = detail.get("reason", "")
    if error.resp.status == 403:
        if reason == "quotaExceeded":
            return (
                "Daily YouTube API quota exceeded. Quota resets at midnight Pacific Time. "
                "See https://developers.google.com/youtube/v3/guides/quota_and_compliance_audits"
            )
        if reason == "commentsDisabled":
            return "Comments are disabled for this video."
        if reason == "forbidden":
            return "Access denied. Your account may not have permission for this action."
    if error.resp.status == 404:
        return "The requested resource was not found."
    return f"YouTube API error ({error.resp.status}): {reason or 'unknown'}"


def _reraise_http(error: HttpError) -> None:
    """Replacement for ``ytstudio.api.handle_api_error`` while a tool runs.

    The CLI helper raises ``SystemExit`` on quota/forbidden which would kill
    the MCP server; here we let the original ``HttpError`` propagate so the
    tool wrapper can translate it into a ``ToolError``.
    """
    raise error


def _wrap(callable_):
    """Decorator that converts HttpError/RefreshError into ToolError.

    Preserves the wrapped function's signature so FastMCP can introspect it.
    Patches ``ytstudio.api.handle_api_error`` to re-raise during the call so
    the shared CLI helpers can be reused without taking down the server.
    """

    @functools.wraps(callable_)
    def wrapper(**kwargs):
        # Local import keeps the rebinding tightly scoped to each call.
        from ytstudio import api as api_module  # noqa: PLC0415

        original_handler = api_module.handle_api_error
        api_module.handle_api_error = _reraise_http
        try:
            return callable_(**kwargs)
        except RefreshError as exc:
            raise ToolError(
                "Session expired or revoked. Run 'ytstudio login' and restart the MCP server."
            ) from exc
        except HttpError as exc:
            raise ToolError(_explain(exc)) from exc
        finally:
            api_module.handle_api_error = original_handler

    wrapper.__signature__ = inspect.signature(callable_)  # type: ignore[attr-defined]
    return wrapper


def build_server(
    profile: str | None = None,
    allow_write: bool = False,
) -> FastMCP:
    """Construct and return a FastMCP server bound to the given profile."""

    credentials = _api_module.get_credentials(profile)
    if credentials is None:
        print(
            "ytstudio MCP: no credentials found for the active profile. "
            "Run 'ytstudio login' first.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    mcp = FastMCP(name="ytstudio", instructions=INSTRUCTIONS)

    # Bound service factories so every tool uses the resolved profile.
    def data():
        return get_data_service(profile=profile)

    def analytics():
        return get_analytics_service(profile=profile)

    # --- Read-only tools ---

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    @_wrap
    def whoami() -> dict[str, Any]:
        """Return the authenticated channel id, title, subscriber count, and video count."""
        service = data()
        response = service.channels().list(part="snippet,statistics", mine=True).execute()
        items = response.get("items") or []
        if not items:
            raise ToolError("No channel found for the current profile.")
        item = items[0]
        snippet = item.get("snippet", {})
        stats = item.get("statistics", {})
        return {
            "id": item.get("id", ""),
            "title": snippet.get("title", ""),
            "custom_url": snippet.get("customUrl", ""),
            "subscriber_count": int(stats.get("subscriberCount", 0) or 0),
            "video_count": int(stats.get("videoCount", 0) or 0),
            "view_count": int(stats.get("viewCount", 0) or 0),
        }

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    @_wrap
    def list_videos(
        limit: Annotated[int, Field(ge=1, le=200)] = 20,
        page_token: str | None = None,
        sort: Literal["date", "views", "likes"] = "date",
    ) -> VideoListOut:
        """List videos on the authenticated channel."""
        result = fetch_videos(data(), limit=limit, page_token=page_token)
        videos = list(result["videos"])
        if sort == "views":
            videos.sort(key=lambda v: v.views, reverse=True)
        elif sort == "likes":
            videos.sort(key=lambda v: v.likes, reverse=True)
        return VideoListOut(
            videos=[video_to_out(v) for v in videos],
            next_page_token=result.get("next_page_token"),
            total_results=result.get("total_results"),
        )

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    @_wrap
    def get_video(video_id: str) -> VideoOut:
        """Fetch a single video by id."""
        video = fetch_video(data(), video_id)
        if video is None:
            raise ToolError(f"Video not found: {video_id}")
        return video_to_out(video)

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    @_wrap
    def list_categories(region: str = "US") -> list[dict[str, str]]:
        """List YouTube video categories assignable to uploads in the given region."""
        service = data()
        response = (
            service.videoCategories().list(part="snippet", regionCode=region.upper()).execute()
        )
        items = [
            {"id": item["id"], "title": item["snippet"]["title"]}
            for item in response.get("items", []) or []
            if (item.get("snippet") or {}).get("assignable", False)
        ]
        items.sort(key=lambda c: int(c["id"]))
        return items

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    @_wrap
    def analytics_overview(
        days: Annotated[int, Field(ge=1, le=365)] = 28,
    ) -> AnalyticsOverviewOut:
        """Return channel-level metrics for the trailing `days` window."""
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        d_service = data()
        a_service = analytics()
        channel_response = d_service.channels().list(part="id", mine=True).execute()
        items = channel_response.get("items") or []
        if not items:
            raise ToolError("No channel found for the current profile.")
        channel_id = items[0]["id"]
        response = (
            a_service.reports()
            .query(
                ids=f"channel=={channel_id}",
                startDate=start_date,
                endDate=end_date,
                metrics=(
                    "views,estimatedMinutesWatched,averageViewDuration,"
                    "subscribersGained,subscribersLost,likes,comments"
                ),
            )
            .execute()
        )
        headers = [h["name"] for h in response.get("columnHeaders", []) or []]
        rows = response.get("rows", []) or []
        metrics = dict(zip(headers, rows[0], strict=False)) if rows else {}
        return AnalyticsOverviewOut(
            days=days,
            views=int(metrics.get("views", 0) or 0),
            estimated_minutes_watched=int(metrics.get("estimatedMinutesWatched", 0) or 0),
            average_view_duration=int(metrics.get("averageViewDuration", 0) or 0),
            subscribers_gained=int(metrics.get("subscribersGained", 0) or 0),
            subscribers_lost=int(metrics.get("subscribersLost", 0) or 0),
            likes=int(metrics.get("likes", 0) or 0),
            comments=int(metrics.get("comments", 0) or 0),
        )

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    @_wrap
    def analytics_query(
        metrics: Annotated[list[str], Field(min_length=1)],
        dimensions: list[str] | None = None,
        filters: str | None = None,
        start: str | None = None,
        end: str | None = None,
        days: Annotated[int, Field(ge=1, le=365)] = 28,
        sort: str | None = None,
        limit: Annotated[int | None, Field(ge=1, le=200)] = None,
        currency: str | None = None,
    ) -> AnalyticsRowOut:
        """Run a raw YouTube Analytics query. Returns headers + rows."""
        metric_errors = validate_metrics(metrics)
        if metric_errors:
            raise ToolError("; ".join(metric_errors))
        if dimensions:
            dim_errors = validate_dimensions(dimensions)
            if dim_errors:
                raise ToolError("; ".join(dim_errors))
        end_date = end or datetime.now().strftime("%Y-%m-%d")
        start_date = start or (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        d_service = data()
        a_service = analytics()
        channel_response = d_service.channels().list(part="id", mine=True).execute()
        items = channel_response.get("items") or []
        if not items:
            raise ToolError("No channel found for the current profile.")
        channel_id = items[0]["id"]
        params: dict[str, Any] = {
            "ids": f"channel=={channel_id}",
            "startDate": start_date,
            "endDate": end_date,
            "metrics": ",".join(metrics),
        }
        if dimensions:
            params["dimensions"] = ",".join(dimensions)
        if filters:
            params["filters"] = filters
        if sort:
            params["sort"] = sort
        if limit:
            params["maxResults"] = limit
        if currency:
            params["currency"] = currency
        response = a_service.reports().query(**params).execute()
        headers = [h["name"] for h in response.get("columnHeaders", []) or []]
        rows = response.get("rows", []) or []
        return AnalyticsRowOut(headers=headers, rows=rows)

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    @_wrap
    def list_comments(
        video_id: str | None = None,
        status: Literal["published", "held", "spam"] = "published",
        limit: Annotated[int, Field(ge=1, le=200)] = 20,
        sort: Literal["time", "relevance"] = "time",
    ) -> CommentListOut:
        """List comments across the channel or for a specific video."""
        if sort == "relevance" and not video_id:
            raise ToolError("Relevance sort requires a video_id (YouTube API limitation).")
        try:
            comments: list[Comment] = fetch_comments(
                data(),
                video_id=video_id,
                limit=limit,
                order=SortOrder(sort),
                moderation_status=ModerationStatus(status),
            )
        except SystemExit as exc:
            raise ToolError("Could not fetch comments (may be disabled).") from exc
        return CommentListOut(comments=[comment_to_out(c) for c in comments])

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    @_wrap
    def list_broadcasts(
        status: Literal["all", "upcoming", "active", "completed"] = "upcoming",
        limit: Annotated[int, Field(ge=1, le=50)] = 20,
    ) -> BroadcastListOut:
        """List live broadcasts for the channel."""
        service = data()
        response = (
            service.liveBroadcasts()
            .list(
                part="snippet,status,contentDetails",
                broadcastStatus=status,
                maxResults=limit,
            )
            .execute()
            or {}
        )
        broadcasts = [_parse_broadcast(item) for item in response.get("items", []) or []]
        broadcasts.sort(key=lambda b: b.scheduled_start or "", reverse=True)
        return BroadcastListOut(
            broadcasts=[broadcast_to_out(b) for b in broadcasts],
            next_page_token=response.get("nextPageToken"),
        )

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    @_wrap
    def get_broadcast(broadcast_id: str, include_ingest: bool = False) -> BroadcastOut:
        """Fetch a broadcast; stream key is always redacted."""
        service = data()
        broadcast = _fetch_broadcast(service, broadcast_id)
        if broadcast is None:
            raise ToolError(f"Broadcast not found: {broadcast_id}")
        ingest = None
        if include_ingest and broadcast.bound_stream_id:
            ingest = _fetch_stream_ingest(service, broadcast.bound_stream_id)
        return broadcast_to_out(broadcast, ingest=ingest)

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    @_wrap
    def list_playlists(
        limit: Annotated[int, Field(ge=1, le=200)] = 25,
    ) -> PlaylistListOut:
        """List playlists owned by the channel."""
        page = fetch_playlists(data(), limit=limit)
        return PlaylistListOut(
            playlists=[_playlist_to_out(p) for p in page.playlists],
            next_page_token=page.next_page_token,
        )

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    @_wrap
    def get_playlist(playlist_id: str) -> PlaylistOut:
        """Fetch a single playlist by id."""
        record = fetch_playlist(data(), playlist_id)
        if record is None:
            raise ToolError(f"Playlist not found: {playlist_id}")
        return _playlist_to_out(record)

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    @_wrap
    def list_playlist_items(
        playlist_id: str,
        limit: Annotated[int, Field(ge=1, le=200)] = 50,
    ) -> list[PlaylistItemOut]:
        """List items in a playlist."""
        records = fetch_playlist_items(data(), playlist_id, limit=limit)
        return [
            PlaylistItemOut(
                id=r.id,
                playlist_id=r.playlist_id,
                video_id=r.video_id,
                title=r.title,
                position=r.position,
            )
            for r in records
        ]

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    @_wrap
    def list_captions(video_id: str) -> list[dict[str, Any]]:
        """List caption tracks for a video."""
        service = data()
        response = service.captions().list(part="snippet", videoId=video_id).execute() or {}
        out: list[dict[str, Any]] = []
        for item in response.get("items", []) or []:
            snippet = item.get("snippet") or {}
            out.append(
                {
                    "id": item.get("id", ""),
                    "language": snippet.get("language", ""),
                    "name": snippet.get("name", ""),
                    "track_kind": snippet.get("trackKind", ""),
                    "is_draft": bool(snippet.get("isDraft", False)),
                    "last_updated": snippet.get("lastUpdated", ""),
                }
            )
        return out

    # --- Write tools (gated) ---

    if allow_write:
        _register_write_tools(mcp, data)

    return mcp


def _playlist_to_out(record: PlaylistRecord) -> PlaylistOut:
    return PlaylistOut(
        id=record.id,
        title=record.title,
        description=record.description,
        privacy=record.privacy,
        item_count=record.item_count,
        published_at=record.published_at,
    )


def _register_write_tools(mcp: FastMCP, data) -> None:
    @mcp.tool(annotations={"destructiveHint": False})
    @_wrap
    def update_video(
        video_id: str,
        title: str | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
    ) -> UpdateResultOut:
        """Update title, description, and/or tags on a video."""
        if title is None and description is None and tags is None:
            raise ToolError("Provide at least one of title, description, or tags.")
        service = data()
        response = service.videos().list(part="snippet", id=video_id).execute()
        items = response.get("items") or []
        if not items:
            raise ToolError(f"Video not found: {video_id}")
        current = items[0]["snippet"]
        new_snippet = {
            "title": title if title is not None else current.get("title", ""),
            "description": (
                description if description is not None else current.get("description", "")
            ),
            "tags": tags if tags is not None else current.get("tags", []),
            "categoryId": current.get("categoryId", ""),
        }
        service.videos().update(
            part="snippet", body={"id": video_id, "snippet": new_snippet}
        ).execute()
        updated = [
            name
            for name, value in (("title", title), ("description", description), ("tags", tags))
            if value is not None
        ]
        return UpdateResultOut(id=video_id, updated_fields=updated)

    @mcp.tool(annotations={"destructiveHint": False})
    @_wrap
    def publish_comments(comment_ids: list[str]) -> ModerationResultOut:
        """Publish (approve) held comments."""
        if not comment_ids:
            raise ToolError("comment_ids must not be empty.")
        service = data()
        service.comments().setModerationStatus(
            id=",".join(comment_ids), moderationStatus="published"
        ).execute()
        return ModerationResultOut(count=len(comment_ids), status="published")

    @mcp.tool(annotations={"destructiveHint": True})
    @_wrap
    def reject_comments(comment_ids: list[str], ban_author: bool = False) -> ModerationResultOut:
        """Reject comments; optionally ban the author."""
        if not comment_ids:
            raise ToolError("comment_ids must not be empty.")
        service = data()
        params: dict[str, Any] = {
            "id": ",".join(comment_ids),
            "moderationStatus": "rejected",
        }
        if ban_author:
            params["banAuthor"] = True
        service.comments().setModerationStatus(**params).execute()
        return ModerationResultOut(count=len(comment_ids), status="rejected", ban_author=ban_author)

    @mcp.tool(annotations={"destructiveHint": False})
    @_wrap
    def schedule_broadcast(
        title: str,
        scheduled_start: str,
        made_for_kids: bool,
        scheduled_end: str = "",
        description: str = "",
        privacy: Literal["public", "private", "unlisted"] = "public",
    ) -> BroadcastOut:
        """Create a new live broadcast."""
        snippet_body: dict[str, Any] = {
            "title": title,
            "description": description,
            "scheduledStartTime": scheduled_start,
        }
        if scheduled_end:
            snippet_body["scheduledEndTime"] = scheduled_end
        body = {
            "snippet": snippet_body,
            "status": {
                "privacyStatus": privacy,
                "selfDeclaredMadeForKids": made_for_kids,
            },
        }
        service = data()
        response = (
            service.liveBroadcasts()
            .insert(part="snippet,status,contentDetails", body=body)
            .execute()
            or {}
        )
        return broadcast_to_out(_parse_broadcast(response))

    @mcp.tool(annotations={"destructiveHint": False})
    @_wrap
    def transition_broadcast(
        broadcast_id: str,
        to: Literal["testing", "live", "complete"],
    ) -> BroadcastOut:
        """Transition a broadcast to testing, live, or complete."""
        service = data()
        response = (
            service.liveBroadcasts()
            .transition(broadcastStatus=to, id=broadcast_id, part="id,snippet,status")
            .execute()
            or {}
        )
        return broadcast_to_out(_parse_broadcast(response))

    @mcp.tool(annotations={"destructiveHint": False})
    @_wrap
    def update_broadcast(
        broadcast_id: str,
        title: str | None = None,
        description: str | None = None,
        privacy: Literal["public", "private", "unlisted"] | None = None,
        scheduled_start: str | None = None,
        scheduled_end: str | None = None,
    ) -> BroadcastOut:
        """Update fields on an existing broadcast (merges over current values)."""
        if all(v is None for v in (title, description, privacy, scheduled_start, scheduled_end)):
            raise ToolError("Provide at least one field to update.")
        service = data()
        current = _fetch_broadcast(service, broadcast_id)
        if current is None:
            raise ToolError(f"Broadcast not found: {broadcast_id}")
        snippet_body: dict[str, Any] = {
            "title": title if title is not None else current.title,
            "description": description if description is not None else current.description,
            "scheduledStartTime": (
                scheduled_start if scheduled_start is not None else current.scheduled_start
            ),
        }
        end_value = scheduled_end if scheduled_end is not None else current.scheduled_end
        if end_value:
            snippet_body["scheduledEndTime"] = end_value
        status_body = {
            "privacyStatus": privacy if privacy is not None else current.privacy,
        }
        response = (
            service.liveBroadcasts()
            .update(
                part="snippet,status",
                body={
                    "id": broadcast_id,
                    "snippet": snippet_body,
                    "status": status_body,
                },
            )
            .execute()
            or {}
        )
        return broadcast_to_out(_parse_broadcast(response))

    @mcp.tool(annotations={"destructiveHint": False})
    @_wrap
    def create_playlist(
        title: str,
        description: str = "",
        privacy: Literal["public", "private", "unlisted"] = "private",
    ) -> PlaylistOut:
        """Create a new playlist."""
        service = data()
        response = (
            service.playlists()
            .insert(
                part="snippet,status",
                body={
                    "snippet": {"title": title, "description": description},
                    "status": {"privacyStatus": privacy},
                },
            )
            .execute()
            or {}
        )
        snippet = response.get("snippet") or {}
        status = response.get("status") or {}
        return PlaylistOut(
            id=str(response.get("id", "")),
            title=snippet.get("title", title),
            description=snippet.get("description", description),
            privacy=status.get("privacyStatus", privacy),
            item_count=0,
            published_at=snippet.get("publishedAt", ""),
        )

    @mcp.tool(annotations={"destructiveHint": False})
    @_wrap
    def update_playlist(
        playlist_id: str,
        title: str | None = None,
        description: str | None = None,
        privacy: Literal["public", "private", "unlisted"] | None = None,
    ) -> PlaylistOut:
        """Update a playlist (merges over current snippet/status)."""
        if title is None and description is None and privacy is None:
            raise ToolError("Provide at least one of title, description, or privacy.")
        service = data()
        current = fetch_playlist(service, playlist_id)
        if current is None:
            raise ToolError(f"Playlist not found: {playlist_id}")
        body = {
            "id": playlist_id,
            "snippet": {
                "title": title if title is not None else current.title,
                "description": description if description is not None else current.description,
            },
            "status": {
                "privacyStatus": privacy if privacy is not None else current.privacy,
            },
        }
        response = service.playlists().update(part="snippet,status", body=body).execute() or {}
        snippet = response.get("snippet") or {}
        status = response.get("status") or {}
        return PlaylistOut(
            id=str(response.get("id", playlist_id)),
            title=snippet.get("title", body["snippet"]["title"]),
            description=snippet.get("description", body["snippet"]["description"]),
            privacy=status.get("privacyStatus", body["status"]["privacyStatus"]),
            item_count=current.item_count,
            published_at=snippet.get("publishedAt", current.published_at),
        )

    @mcp.tool(annotations={"destructiveHint": True})
    @_wrap
    def delete_playlist(playlist_id: str) -> dict[str, str]:
        """Delete a playlist."""
        service = data()
        service.playlists().delete(id=playlist_id).execute()
        return {"deleted": playlist_id}

    @mcp.tool(annotations={"destructiveHint": False})
    @_wrap
    def add_to_playlist(
        playlist_id: str,
        video_id: str,
        position: int | None = None,
    ) -> PlaylistItemOut:
        """Add a video to a playlist."""
        snippet: dict[str, Any] = {
            "playlistId": playlist_id,
            "resourceId": {"kind": "youtube#video", "videoId": video_id},
        }
        if position is not None:
            snippet["position"] = position
        service = data()
        response = (
            service.playlistItems()
            .insert(part="snippet,contentDetails", body={"snippet": snippet})
            .execute()
            or {}
        )
        item_snippet = response.get("snippet") or {}
        content = response.get("contentDetails") or {}
        return PlaylistItemOut(
            id=str(response.get("id", "")),
            playlist_id=item_snippet.get("playlistId", playlist_id),
            video_id=content.get("videoId", video_id),
            title=item_snippet.get("title", ""),
            position=int(item_snippet.get("position", position or 0) or 0),
        )

    @mcp.tool(annotations={"destructiveHint": True})
    @_wrap
    def remove_from_playlist(playlist_item_id: str) -> dict[str, str]:
        """Remove an item from a playlist by playlistItem id."""
        service = data()
        service.playlistItems().delete(id=playlist_item_id).execute()
        return {"deleted": playlist_item_id}
