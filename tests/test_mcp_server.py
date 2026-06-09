from unittest.mock import MagicMock

import httplib2
import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError
from googleapiclient.errors import HttpError

from ytstudio.mcp.server import build_server


def _http_error(status: int, reason: str, message: str = "") -> HttpError:
    resp = httplib2.Response({"status": status})
    content = (
        b'{"error":{"errors":[{"reason":"'
        + reason.encode()
        + b'","message":"'
        + message.encode()
        + b'"}],"code":'
        + str(status).encode()
        + b',"message":"'
        + message.encode()
        + b'"}}'
    )
    return HttpError(resp, content, uri="https://example.com")


@pytest.fixture
def mcp_server_ro(mock_auth):
    return build_server(profile="default", allow_write=False)


@pytest.fixture
def mcp_server_rw(mock_auth):
    return build_server(profile="default", allow_write=True)


@pytest.fixture
async def mcp_client_ro(mcp_server_ro):
    async with Client(mcp_server_ro) as client:
        yield client


@pytest.fixture
async def mcp_client_rw(mcp_server_rw):
    async with Client(mcp_server_rw) as client:
        yield client


def _augment_for_broadcasts(mock_service):
    """Wire liveBroadcasts / liveStreams on the existing mock_service."""
    broadcast_item = {
        "id": "br1",
        "snippet": {
            "title": "Test Broadcast",
            "description": "Hello",
            "scheduledStartTime": "2026-07-01T18:00:00Z",
        },
        "status": {"lifeCycleStatus": "ready", "privacyStatus": "public"},
        "contentDetails": {"boundStreamId": "stream-1"},
    }
    bcast_list = MagicMock()
    bcast_list.execute.return_value = {"items": [broadcast_item], "nextPageToken": None}
    mock_service.liveBroadcasts.return_value.list.return_value = bcast_list

    bcast_insert = MagicMock()
    bcast_insert.execute.return_value = broadcast_item
    mock_service.liveBroadcasts.return_value.insert.return_value = bcast_insert

    bcast_update = MagicMock()
    bcast_update.execute.return_value = broadcast_item
    mock_service.liveBroadcasts.return_value.update.return_value = bcast_update

    bcast_transition = MagicMock()
    transitioned = {
        **broadcast_item,
        "status": {"lifeCycleStatus": "live", "privacyStatus": "public"},
    }
    bcast_transition.execute.return_value = transitioned
    mock_service.liveBroadcasts.return_value.transition.return_value = bcast_transition

    stream_item = {
        "id": "stream-1",
        "snippet": {"title": "Main Stream"},
        "cdn": {
            "format": "1080p",
            "frameRate": "30fps",
            "resolution": "1080p",
            "ingestionInfo": {
                "ingestionAddress": "rtmp://a.rtmp.youtube.com/live2",
                "streamName": "supersecretkey1234",
                "rtmpsIngestionAddress": "rtmps://a.rtmps.youtube.com/live2",
            },
        },
    }
    stream_list = MagicMock()
    stream_list.execute.return_value = {"items": [stream_item]}
    mock_service.liveStreams.return_value.list.return_value = stream_list


def _augment_for_playlists(mock_service):
    playlist_item = {
        "id": "PL1",
        "snippet": {
            "title": "Best Of",
            "description": "Top picks",
            "publishedAt": "2026-01-01T00:00:00Z",
        },
        "status": {"privacyStatus": "private"},
        "contentDetails": {"itemCount": 5},
    }
    pl_list = MagicMock()
    pl_list.execute.return_value = {"items": [playlist_item], "nextPageToken": None}
    mock_service.playlists.return_value.list.return_value = pl_list

    pl_insert = MagicMock()
    pl_insert.execute.return_value = playlist_item
    mock_service.playlists.return_value.insert.return_value = pl_insert

    pl_update = MagicMock()
    pl_update.execute.return_value = playlist_item
    mock_service.playlists.return_value.update.return_value = pl_update

    pl_delete = MagicMock()
    pl_delete.execute.return_value = {}
    mock_service.playlists.return_value.delete.return_value = pl_delete

    pli_insert = MagicMock()
    pli_insert.execute.return_value = {
        "id": "PLI1",
        "snippet": {"playlistId": "PL1", "title": "T", "position": 0},
        "contentDetails": {"videoId": "v1"},
    }
    mock_service.playlistItems.return_value.insert.return_value = pli_insert

    pli_delete = MagicMock()
    pli_delete.execute.return_value = {}
    mock_service.playlistItems.return_value.delete.return_value = pli_delete


def _augment_for_comments_moderation(mock_service):
    mod = MagicMock()
    mod.execute.return_value = {}
    mock_service.comments.return_value.setModerationStatus.return_value = mod


class TestReadTools:
    async def test_list_videos_returns_structured_output(self, mcp_client_ro):
        result = await mcp_client_ro.call_tool("list_videos", {"limit": 5})
        assert result.data is not None
        # Structured payload exposes attributes via the dynamic Root model.
        videos = result.data.videos
        assert videos
        assert videos[0].id == "test_video_123"
        assert videos[0].title == "Test Video Title"

    async def test_get_video_not_found_raises_tool_error(self, mock_auth, mcp_client_ro):
        empty_list = MagicMock()
        empty_list.execute.return_value = {"items": []}
        mock_auth.videos.return_value.list.return_value = empty_list

        with pytest.raises(ToolError) as excinfo:
            await mcp_client_ro.call_tool("get_video", {"video_id": "missing"})
        assert "not found" in str(excinfo.value).lower()

    async def test_quota_exceeded_becomes_tool_error(self, mock_auth, mcp_client_ro):
        boom = MagicMock()
        boom.execute.side_effect = _http_error(403, "quotaExceeded", "Quota exceeded")
        mock_auth.videos.return_value.list.return_value = boom

        with pytest.raises(ToolError) as excinfo:
            await mcp_client_ro.call_tool("get_video", {"video_id": "anything"})
        assert "quota" in str(excinfo.value).lower()

    async def test_whoami_returns_channel(self, mcp_client_ro):
        result = await mcp_client_ro.call_tool("whoami", {})
        data = result.data if isinstance(result.data, dict) else result.data.model_dump()
        assert data["id"] == "UC_test_channel_id"
        assert data["title"] == "Test Channel"
        assert data["subscriber_count"] == 125000

    async def test_list_comments_filters_by_status(self, mcp_client_ro):
        result = await mcp_client_ro.call_tool("list_comments", {"video_id": "test_video_123"})
        comments = result.data.comments
        assert comments
        assert comments[0].author == "Test User"

    async def test_analytics_overview_returns_metrics(self, mock_auth, mcp_client_ro):
        reports_query = MagicMock()
        reports_query.execute.return_value = {
            "columnHeaders": [
                {"name": "views"},
                {"name": "estimatedMinutesWatched"},
                {"name": "averageViewDuration"},
                {"name": "subscribersGained"},
                {"name": "subscribersLost"},
                {"name": "likes"},
                {"name": "comments"},
            ],
            "rows": [[100, 250, 30, 5, 1, 10, 4]],
        }
        # mock_auth is shared between data + analytics service.
        mock_auth.reports.return_value.query.return_value = reports_query

        result = await mcp_client_ro.call_tool("analytics_overview", {"days": 7})
        assert result.data.views == 100
        assert result.data.likes == 10

    async def test_list_broadcasts_returns_broadcasts(self, mock_auth, mcp_client_ro):
        _augment_for_broadcasts(mock_auth)
        result = await mcp_client_ro.call_tool("list_broadcasts", {"limit": 5})
        bcasts = result.data.broadcasts
        assert bcasts
        assert bcasts[0].id == "br1"

    async def test_get_broadcast_redacts_stream_key(self, mock_auth, mcp_server_rw):
        _augment_for_broadcasts(mock_auth)
        async with Client(mcp_server_rw) as client:
            result = await client.call_tool(
                "get_broadcast", {"broadcast_id": "br1", "include_ingest": True}
            )
        ingest = result.data.ingest
        assert ingest is not None
        # Last 4 chars preserved; everything else masked.
        assert ingest.stream_name.endswith("1234")
        assert ingest.stream_name != "supersecretkey1234"
        assert "*" in ingest.stream_name

    async def test_list_playlists_returns_playlists(self, mock_auth, mcp_client_ro):
        _augment_for_playlists(mock_auth)
        result = await mcp_client_ro.call_tool("list_playlists", {"limit": 10})
        playlists = result.data.playlists
        assert playlists
        assert playlists[0].id == "PL1"
        assert playlists[0].title == "Best Of"


class TestWriteGating:
    async def test_update_video_not_available_in_readonly_mode(self, mcp_server_ro):
        tools = await mcp_server_ro.list_tools()
        names = {t.name for t in tools}
        assert "update_video" not in names
        assert "create_playlist" not in names

    async def test_update_video_calls_youtube_api(self, mock_auth, mcp_client_rw):
        result = await mcp_client_rw.call_tool(
            "update_video",
            {"video_id": "test_video_123", "title": "Brand New Title"},
        )
        assert result.data.id == "test_video_123"
        assert "title" in result.data.updated_fields
        mock_auth.videos.return_value.update.assert_called_once()
        called_body = mock_auth.videos.return_value.update.call_args.kwargs["body"]
        assert called_body["snippet"]["title"] == "Brand New Title"
        # description preserved from existing snippet
        assert called_body["snippet"]["description"]

    async def test_publish_comments_calls_set_moderation(self, mock_auth, mcp_client_rw):
        _augment_for_comments_moderation(mock_auth)
        await mcp_client_rw.call_tool("publish_comments", {"comment_ids": ["c1", "c2"]})
        mock_auth.comments.return_value.setModerationStatus.assert_called_once()
        kwargs = mock_auth.comments.return_value.setModerationStatus.call_args.kwargs
        assert kwargs["id"] == "c1,c2"
        assert kwargs["moderationStatus"] == "published"

    async def test_reject_comments_with_ban_passes_banAuthor(self, mock_auth, mcp_client_rw):
        _augment_for_comments_moderation(mock_auth)
        await mcp_client_rw.call_tool(
            "reject_comments", {"comment_ids": ["c1"], "ban_author": True}
        )
        kwargs = mock_auth.comments.return_value.setModerationStatus.call_args.kwargs
        assert kwargs["banAuthor"] is True
        assert kwargs["moderationStatus"] == "rejected"

    async def test_create_playlist_inserts_with_correct_body(self, mock_auth, mcp_client_rw):
        _augment_for_playlists(mock_auth)
        await mcp_client_rw.call_tool(
            "create_playlist",
            {"title": "New PL", "description": "d", "privacy": "unlisted"},
        )
        kwargs = mock_auth.playlists.return_value.insert.call_args.kwargs
        body = kwargs["body"]
        assert body["snippet"]["title"] == "New PL"
        assert body["status"]["privacyStatus"] == "unlisted"

    async def test_add_to_playlist_builds_resourceId(self, mock_auth, mcp_client_rw):
        _augment_for_playlists(mock_auth)
        await mcp_client_rw.call_tool("add_to_playlist", {"playlist_id": "PL1", "video_id": "v1"})
        kwargs = mock_auth.playlistItems.return_value.insert.call_args.kwargs
        snippet = kwargs["body"]["snippet"]
        assert snippet["playlistId"] == "PL1"
        assert snippet["resourceId"] == {"kind": "youtube#video", "videoId": "v1"}

    async def test_delete_playlist_calls_api(self, mock_auth, mcp_client_rw):
        _augment_for_playlists(mock_auth)
        result = await mcp_client_rw.call_tool("delete_playlist", {"playlist_id": "PL1"})
        data = result.data if isinstance(result.data, dict) else result.data.model_dump()
        assert data["deleted"] == "PL1"
        mock_auth.playlists.return_value.delete.assert_called_once_with(id="PL1")

    async def test_transition_broadcast_to_live(self, mock_auth, mcp_client_rw):
        _augment_for_broadcasts(mock_auth)
        result = await mcp_client_rw.call_tool(
            "transition_broadcast", {"broadcast_id": "br1", "to": "live"}
        )
        assert result.data.id == "br1"
        kwargs = mock_auth.liveBroadcasts.return_value.transition.call_args.kwargs
        assert kwargs["broadcastStatus"] == "live"
