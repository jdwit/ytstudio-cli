import csv
import io
import json
from unittest.mock import MagicMock, patch

from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError
from typer.testing import CliRunner

from tests.conftest import MOCK_PLAYLIST, MOCK_PLAYLIST_ITEM_FULL
from ytstudio.main import app

runner = CliRunner()


def _set_playlists_list(mock_auth, payload):
    list_mock = MagicMock()
    list_mock.execute.return_value = payload
    mock_auth.playlists.return_value.list.return_value = list_mock


def _set_playlist_items_list(mock_auth, payload):
    list_mock = MagicMock()
    list_mock.execute.return_value = payload
    mock_auth.playlistItems.return_value.list.return_value = list_mock


def _set_playlist_items_list_side_effect(mock_auth, payloads):
    list_mock = MagicMock()
    list_mock.execute.side_effect = payloads
    mock_auth.playlistItems.return_value.list.return_value = list_mock


def _set_videos_list(mock_auth, payload):
    videos_mock = MagicMock()
    videos_mock.execute.return_value = payload
    mock_auth.videos.return_value.list.return_value = videos_mock


def _set_search_list(mock_auth, items):
    search_mock = MagicMock()
    search_mock.execute.return_value = {"items": items}
    mock_auth.search.return_value.list.return_value = search_mock


def _http_error(status: int, reason: str) -> HttpError:
    resp = MagicMock()
    resp.status = status
    err = HttpError(resp=resp, content=b"{}")
    err.error_details = [{"reason": reason}]
    return err


class TestPlaylistsList:
    def test_list_renders_table(self, mock_auth):
        result = runner.invoke(app, ["playlists", "list"])
        assert result.exit_code == 0
        assert "Test Playlist" in result.stdout
        assert "PL_test_123" in result.stdout

    def test_list_json_output(self, mock_auth):
        result = runner.invoke(app, ["playlists", "list", "-o", "json"])
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["playlists"][0]["id"] == "PL_test_123"

    def test_list_csv_output(self, mock_auth):
        result = runner.invoke(app, ["playlists", "list", "-o", "csv"])
        assert result.exit_code == 0
        lines = [ln for ln in result.stdout.strip().splitlines() if ln]
        assert lines[0] == "id,title,items,privacy,published_at"
        assert any("PL_test_123" in ln for ln in lines[1:])

    def test_list_sort_count_local(self, mock_auth):
        second = {
            **MOCK_PLAYLIST,
            "id": "PL_other",
            "snippet": {**MOCK_PLAYLIST["snippet"], "title": "Big Playlist"},
            "contentDetails": {"itemCount": 10},
        }
        _set_playlists_list(
            mock_auth,
            {
                "items": [MOCK_PLAYLIST, second],
                "nextPageToken": None,
                "pageInfo": {"totalResults": 2},
            },
        )

        result = runner.invoke(app, ["playlists", "list", "--sort", "count"])
        assert result.exit_code == 0
        out = result.stdout
        assert out.index("Big Playlist") < out.index("Test Playlist")

    def test_list_pagination_prints_token(self, mock_auth):
        _set_playlists_list(
            mock_auth,
            {
                "items": [MOCK_PLAYLIST],
                "nextPageToken": "next_tok",
                "pageInfo": {"totalResults": 1},
            },
        )
        result = runner.invoke(app, ["playlists", "list", "-n", "1"])
        assert result.exit_code == 0
        assert "--page-token next_tok" in result.stdout


class TestPlaylistsShow:
    def test_show_renders_kv_table(self, mock_auth):
        result = runner.invoke(app, ["playlists", "show", "PL_test_123"])
        assert result.exit_code == 0
        assert "Test Playlist" in result.stdout
        assert "private" in result.stdout

    def test_show_not_found_exits_1(self, mock_auth):
        _set_playlists_list(mock_auth, {"items": []})
        result = runner.invoke(app, ["playlists", "show", "PL_missing"])
        assert result.exit_code == 1
        assert "Playlist not found" in result.stdout

    def test_show_with_items_flag_renders_items(self, mock_auth):
        second_item = {
            **MOCK_PLAYLIST_ITEM_FULL,
            "id": "PLPLI_test_item_2",
            "snippet": {
                **MOCK_PLAYLIST_ITEM_FULL["snippet"],
                "title": "Second item",
                "position": 1,
                "resourceId": {"kind": "youtube#video", "videoId": "vid_2"},
            },
            "contentDetails": {"videoId": "vid_2", "note": ""},
        }
        _set_playlist_items_list(
            mock_auth,
            {
                "items": [MOCK_PLAYLIST_ITEM_FULL, second_item],
                "nextPageToken": None,
                "pageInfo": {"totalResults": 2},
            },
        )

        result = runner.invoke(app, ["playlists", "show", "PL_test_123", "--items"])
        assert result.exit_code == 0
        assert "Item title" in result.stdout
        assert "Second item" in result.stdout

    def test_show_json(self, mock_auth):
        result = runner.invoke(app, ["playlists", "show", "PL_test_123", "-o", "json"])
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["playlist"]["id"] == "PL_test_123"


class TestPlaylistsCreate:
    def test_create_dry_run_shows_preview(self, mock_auth):
        result = runner.invoke(app, ["playlists", "create", "-t", "Brand new"])
        assert result.exit_code == 0
        assert "Preview" in result.stdout
        mock_auth.playlists.return_value.insert.assert_not_called()

    def test_create_execute_calls_insert(self, mock_auth):
        result = runner.invoke(
            app,
            ["playlists", "create", "-t", "Brand new", "--execute"],
        )
        assert result.exit_code == 0
        call = mock_auth.playlists.return_value.insert.call_args
        assert call.kwargs["part"] == "snippet,status"
        assert call.kwargs["body"]["snippet"]["title"] == "Brand new"
        assert call.kwargs["body"]["status"]["privacyStatus"] == "private"

    def test_create_privacy_choice(self, mock_auth):
        result = runner.invoke(
            app,
            ["playlists", "create", "-t", "Brand new", "--execute"],
        )
        assert result.exit_code == 0
        call = mock_auth.playlists.return_value.insert.call_args
        assert call.kwargs["body"]["status"]["privacyStatus"] == "private"

    def test_create_requires_title(self, mock_auth):
        result = runner.invoke(app, ["playlists", "create"])
        assert result.exit_code == 2


class TestPlaylistsUpdate:
    def test_update_dry_run_diff_table(self, mock_auth):
        result = runner.invoke(
            app,
            [
                "playlists",
                "update",
                "PL_test_123",
                "-t",
                "Renamed",
                "--privacy",
                "public",
            ],
        )
        assert result.exit_code == 0
        assert "Renamed" in result.stdout
        assert "public" in result.stdout
        mock_auth.playlists.return_value.update.assert_not_called()

    def test_update_execute_merges_existing_fields(self, mock_auth):
        result = runner.invoke(
            app,
            ["playlists", "update", "PL_test_123", "-t", "New title", "--execute"],
        )
        assert result.exit_code == 0
        call = mock_auth.playlists.return_value.update.call_args
        body = call.kwargs["body"]
        assert body["snippet"]["title"] == "New title"
        # Re-spec rule: description from current GET is kept.
        assert body["snippet"]["description"] == MOCK_PLAYLIST["snippet"]["description"]

    def test_update_no_changes_exits_with_message(self, mock_auth):
        result = runner.invoke(app, ["playlists", "update", "PL_test_123"])
        assert result.exit_code == 1
        assert "Nothing to update" in result.stdout


class TestPlaylistsDelete:
    def test_delete_dry_run_shows_count(self, mock_auth):
        result = runner.invoke(app, ["playlists", "delete", "PL_test_123"])
        assert result.exit_code == 0
        assert "Would delete" in result.stdout
        assert "3" in result.stdout

    def test_delete_execute_calls_delete(self, mock_auth):
        result = runner.invoke(app, ["playlists", "delete", "PL_test_123", "--execute", "--yes"])
        assert result.exit_code == 0
        mock_auth.playlists.return_value.delete.assert_called_with(id="PL_test_123")

    def test_delete_aborts_when_prompt_denied(self, mock_auth):
        with patch("ytstudio.commands.playlists.Confirm.ask", return_value=False):
            result = runner.invoke(app, ["playlists", "delete", "PL_test_123", "--execute"])
        assert result.exit_code == 0
        mock_auth.playlists.return_value.delete.assert_not_called()


class TestPlaylistsItems:
    def test_items_table_columns(self, mock_auth):
        _set_playlist_items_list(
            mock_auth,
            {
                "items": [MOCK_PLAYLIST_ITEM_FULL],
                "nextPageToken": None,
                "pageInfo": {"totalResults": 1},
            },
        )
        result = runner.invoke(app, ["playlists", "items", "PL_test_123"])
        assert result.exit_code == 0
        assert "Position" in result.stdout
        assert "Video ID" in result.stdout
        assert "Title" in result.stdout

    def test_items_pagination_prints_token(self, mock_auth):
        _set_playlist_items_list(
            mock_auth,
            {
                "items": [MOCK_PLAYLIST_ITEM_FULL],
                "nextPageToken": "next_tok",
                "pageInfo": {"totalResults": 1},
            },
        )
        result = runner.invoke(app, ["playlists", "items", "PL_test_123", "-n", "1"])
        assert result.exit_code == 0
        assert "--page-token next_tok" in result.stdout


class TestPlaylistsAdd:
    def test_add_video_dry_run_shows_preview(self, mock_auth):
        result = runner.invoke(
            app,
            [
                "playlists",
                "add",
                "PL_test_123",
                "-v",
                "vid_a",
                "-v",
                "vid_b",
            ],
        )
        assert result.exit_code == 0
        assert "vid_a" in result.stdout
        assert "vid_b" in result.stdout
        mock_auth.playlistItems.return_value.insert.assert_not_called()

    def test_add_video_execute_calls_insert_per_video(self, mock_auth):
        result = runner.invoke(
            app,
            [
                "playlists",
                "add",
                "PL_test_123",
                "-v",
                "vid_a",
                "-v",
                "vid_b",
                "--execute",
            ],
        )
        assert result.exit_code == 0
        calls = mock_auth.playlistItems.return_value.insert.call_args_list
        assert len(calls) == 2
        ids = [c.kwargs["body"]["snippet"]["resourceId"]["videoId"] for c in calls]
        assert ids == ["vid_a", "vid_b"]

    def test_add_from_search_uses_search_api(self, mock_auth):
        _set_search_list(
            mock_auth,
            [{"id": {"videoId": f"vid_{i}"}, "snippet": {"title": f"Hit {i}"}} for i in range(5)],
        )
        result = runner.invoke(
            app,
            [
                "playlists",
                "add",
                "PL_test_123",
                "--from-search",
                "test query",
                "-n",
                "3",
                "--execute",
            ],
        )
        assert result.exit_code == 0
        calls = mock_auth.playlistItems.return_value.insert.call_args_list
        assert len(calls) == 3

    def test_add_position_sets_snippet_position(self, mock_auth):
        result = runner.invoke(
            app,
            [
                "playlists",
                "add",
                "PL_test_123",
                "-v",
                "vid_a",
                "--position",
                "2",
                "--execute",
            ],
        )
        assert result.exit_code == 0
        call = mock_auth.playlistItems.return_value.insert.call_args
        assert call.kwargs["body"]["snippet"]["position"] == 2

    def test_add_quota_exceeded_stops_and_reports_partial(self, mock_auth):
        insert_mock = MagicMock()
        insert_mock.execute.side_effect = [
            MOCK_PLAYLIST_ITEM_FULL,
            _http_error(403, "quotaExceeded"),
        ]
        mock_auth.playlistItems.return_value.insert.return_value = insert_mock

        result = runner.invoke(
            app,
            [
                "playlists",
                "add",
                "PL_test_123",
                "-v",
                "vid_a",
                "-v",
                "vid_b",
                "--execute",
            ],
        )
        assert result.exit_code == 1
        assert "1 added" in result.stdout


class TestPlaylistsRemove:
    def test_remove_by_item_id_execute(self, mock_auth):
        result = runner.invoke(
            app,
            ["playlists", "remove", "PL_test_123", "-i", "PLPLI_1", "--execute"],
        )
        assert result.exit_code == 0
        mock_auth.playlistItems.return_value.delete.assert_called_with(id="PLPLI_1")

    def test_remove_by_video_resolves_to_item_id(self, mock_auth):
        _set_playlist_items_list(
            mock_auth,
            {
                "items": [
                    {
                        "id": "PLPLI_resolved_1",
                        "snippet": {
                            "title": "x",
                            "publishedAt": "2026-01-02T00:00:00Z",
                            "position": 0,
                            "resourceId": {"kind": "youtube#video", "videoId": "VID_A"},
                        },
                        "contentDetails": {"videoId": "VID_A"},
                    },
                ],
                "nextPageToken": None,
            },
        )
        result = runner.invoke(
            app,
            ["playlists", "remove", "PL_test_123", "-v", "VID_A", "--execute"],
        )
        assert result.exit_code == 0
        list_call = mock_auth.playlistItems.return_value.list.call_args
        assert list_call.kwargs["videoId"] == "VID_A"
        mock_auth.playlistItems.return_value.delete.assert_called_with(id="PLPLI_resolved_1")

    def test_remove_dry_run_no_delete_calls(self, mock_auth):
        result = runner.invoke(app, ["playlists", "remove", "PL_test_123", "-i", "PLPLI_1"])
        assert result.exit_code == 0
        mock_auth.playlistItems.return_value.delete.assert_not_called()


def _make_item(item_id: str, video_id: str, position: int) -> dict:
    return {
        "id": item_id,
        "snippet": {
            "title": f"Title {video_id}",
            "publishedAt": "2026-01-02T00:00:00Z",
            "position": position,
            "resourceId": {"kind": "youtube#video", "videoId": video_id},
        },
        "contentDetails": {"videoId": video_id},
    }


def _make_video_stats(video_id: str, views: int) -> dict:
    return {
        "id": video_id,
        "snippet": {"title": f"Title {video_id}", "publishedAt": "2026-01-02T00:00:00Z"},
        "statistics": {"viewCount": str(views)},
    }


class TestPlaylistsReorder:
    def test_reorder_by_views_descending_dry_run(self, mock_auth):
        items = [
            _make_item("PLPLI_a", "vid_a", 0),
            _make_item("PLPLI_b", "vid_b", 1),
            _make_item("PLPLI_c", "vid_c", 2),
        ]
        _set_playlist_items_list(
            mock_auth,
            {"items": items, "nextPageToken": None, "pageInfo": {"totalResults": 3}},
        )
        _set_videos_list(
            mock_auth,
            {
                "items": [
                    _make_video_stats("vid_a", 100),
                    _make_video_stats("vid_b", 500),
                    _make_video_stats("vid_c", 50),
                ]
            },
        )
        result = runner.invoke(app, ["playlists", "reorder", "PL_test_123", "--by", "views"])
        assert result.exit_code == 0
        # vid_b (PLPLI_b) was at position 1, should move to 0.
        assert "PLPLI_b" in result.stdout
        mock_auth.playlistItems.return_value.update.assert_not_called()

    def test_reorder_execute_calls_update_with_required_snippet_fields(self, mock_auth):
        items = [
            _make_item("PLPLI_a", "vid_a", 0),
            _make_item("PLPLI_b", "vid_b", 1),
        ]
        _set_playlist_items_list(
            mock_auth,
            {"items": items, "nextPageToken": None, "pageInfo": {"totalResults": 2}},
        )
        _set_videos_list(
            mock_auth,
            {
                "items": [
                    _make_video_stats("vid_a", 10),
                    _make_video_stats("vid_b", 500),
                ]
            },
        )
        result = runner.invoke(
            app, ["playlists", "reorder", "PL_test_123", "--by", "views", "--execute"]
        )
        assert result.exit_code == 0
        calls = mock_auth.playlistItems.return_value.update.call_args_list
        assert calls
        for call in calls:
            body = call.kwargs["body"]
            assert body["snippet"]["playlistId"] == "PL_test_123"
            assert body["snippet"]["resourceId"]["kind"] == "youtube#video"
            assert "videoId" in body["snippet"]["resourceId"]
            assert "position" in body["snippet"]

    def test_reorder_skips_unchanged_positions(self, mock_auth):
        items = [
            _make_item("PLPLI_a", "vid_a", 0),
            _make_item("PLPLI_b", "vid_b", 1),
        ]
        _set_playlist_items_list(
            mock_auth,
            {"items": items, "nextPageToken": None, "pageInfo": {"totalResults": 2}},
        )
        _set_videos_list(
            mock_auth,
            {
                "items": [
                    _make_video_stats("vid_a", 500),
                    _make_video_stats("vid_b", 100),
                ]
            },
        )
        result = runner.invoke(app, ["playlists", "reorder", "PL_test_123", "--by", "views"])
        assert result.exit_code == 0
        assert "No changes" in result.stdout
        mock_auth.playlistItems.return_value.update.assert_not_called()

    def test_reorder_handles_manual_sort_required_error(self, mock_auth):
        items = [
            _make_item("PLPLI_a", "vid_a", 0),
            _make_item("PLPLI_b", "vid_b", 1),
        ]
        _set_playlist_items_list(
            mock_auth,
            {"items": items, "nextPageToken": None, "pageInfo": {"totalResults": 2}},
        )
        _set_videos_list(
            mock_auth,
            {
                "items": [
                    _make_video_stats("vid_a", 10),
                    _make_video_stats("vid_b", 500),
                ]
            },
        )
        update_mock = MagicMock()
        update_mock.execute.side_effect = _http_error(400, "manualSortRequired")
        mock_auth.playlistItems.return_value.update.return_value = update_mock

        result = runner.invoke(
            app,
            ["playlists", "reorder", "PL_test_123", "--by", "views", "--execute"],
        )
        assert result.exit_code == 1
        assert "Manual sort" in result.stdout or "Manual" in result.stdout


class TestPlaylistsReviewFixes:
    """Regression tests for the fixes applied after PR review."""

    def test_add_position_increments_per_insert(self, mock_auth):
        result = runner.invoke(
            app,
            [
                "playlists",
                "add",
                "PL_test_123",
                "-v",
                "vid_a",
                "-v",
                "vid_b",
                "-v",
                "vid_c",
                "--position",
                "5",
                "--execute",
            ],
        )
        assert result.exit_code == 0
        calls = mock_auth.playlistItems.return_value.insert.call_args_list
        positions = [c.kwargs["body"]["snippet"]["position"] for c in calls]
        assert positions == [5, 6, 7]

    def test_add_combines_video_and_search_respects_limit(self, mock_auth):
        _set_search_list(
            mock_auth,
            [{"id": {"videoId": f"hit_{i}"}, "snippet": {"title": f"Hit {i}"}} for i in range(5)],
        )
        result = runner.invoke(
            app,
            [
                "playlists",
                "add",
                "PL_test_123",
                "-v",
                "vid_a",
                "-v",
                "vid_b",
                "--from-search",
                "topic",
                "-n",
                "3",
                "--execute",
            ],
        )
        assert result.exit_code == 0
        calls = mock_auth.playlistItems.return_value.insert.call_args_list
        # 2 explicit videos + 1 search hit = 3, capped by --limit/-n
        assert len(calls) == 3

    def test_uploads_check_refuses_canonical_channel_uploads_id(self, mock_auth):
        result = runner.invoke(
            app,
            [
                "playlists",
                "add",
                "UU_test_uploads_playlist",
                "-v",
                "vid_a",
                "--execute",
            ],
        )
        assert result.exit_code == 1
        assert "uploads playlist" in result.stdout
        mock_auth.playlistItems.return_value.insert.assert_not_called()

    def test_uploads_check_allows_non_uploads_uu_prefix(self, mock_auth):
        result = runner.invoke(
            app,
            [
                "playlists",
                "add",
                "UU_unrelated_id_starting_with_UU",
                "-v",
                "vid_a",
                "--execute",
            ],
        )
        # Canonical check resolves uploads to "UU_test_uploads_playlist"; a
        # different UU-prefixed id is not refused.
        assert result.exit_code == 0
        mock_auth.playlistItems.return_value.insert.assert_called()

    def test_reorder_skips_writes_that_become_no_ops_after_prior_moves(self, mock_auth):
        # Full reverse on 4 items: targets become [0, 1, 2, 3] for the new order
        # [d, c, b, a]. Applied in target-ascending order, the last write would
        # land on the position the item already occupies after prior shifts.
        items = [
            _make_item("PLPLI_a", "vid_a", 0),
            _make_item("PLPLI_b", "vid_b", 1),
            _make_item("PLPLI_c", "vid_c", 2),
            _make_item("PLPLI_d", "vid_d", 3),
        ]
        _set_playlist_items_list(
            mock_auth,
            {"items": items, "nextPageToken": None, "pageInfo": {"totalResults": 4}},
        )
        _set_videos_list(
            mock_auth,
            {
                "items": [
                    _make_video_stats("vid_a", 1),
                    _make_video_stats("vid_b", 2),
                    _make_video_stats("vid_c", 3),
                    _make_video_stats("vid_d", 4),
                ]
            },
        )
        result = runner.invoke(
            app,
            ["playlists", "reorder", "PL_test_123", "--by", "views", "--execute"],
        )
        assert result.exit_code == 0
        # 4 logical moves planned, but the last one is a no-op after prior shifts.
        calls = mock_auth.playlistItems.return_value.update.call_args_list
        assert len(calls) == 3
        assert "already in place" in result.stdout

    def test_list_csv_quotes_titles_with_special_chars(self, mock_auth):
        nasty = {
            **MOCK_PLAYLIST,
            "id": "PL_nasty",
            "snippet": {
                **MOCK_PLAYLIST["snippet"],
                "title": 'has, a comma and a "quote" and a\nnewline',
            },
        }
        _set_playlists_list(
            mock_auth,
            {"items": [nasty], "nextPageToken": None, "pageInfo": {"totalResults": 1}},
        )
        result = runner.invoke(app, ["playlists", "list", "-o", "csv"])
        assert result.exit_code == 0
        rows = list(csv.reader(io.StringIO(result.stdout)))
        # Header + one data row, even with embedded comma/newline in the title.
        assert rows[0] == ["id", "title", "items", "privacy", "published_at"]
        assert rows[1][0] == "PL_nasty"
        assert rows[1][1] == 'has, a comma and a "quote" and a\nnewline'

    def test_add_session_expired_exits_friendly(self, mock_auth):
        insert_mock = MagicMock()
        insert_mock.execute.side_effect = RefreshError("revoked")
        mock_auth.playlistItems.return_value.insert.return_value = insert_mock

        result = runner.invoke(
            app,
            ["playlists", "add", "PL_test_123", "-v", "vid_a", "--execute"],
        )
        assert result.exit_code == 1
        assert "Session expired" in result.stdout
        assert "ytstudio login" in result.stdout
