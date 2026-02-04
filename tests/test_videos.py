"""Tests for video commands."""

from unittest.mock import patch

from typer.testing import CliRunner

from tests.conftest import MOCK_VIDEO
from ytstudio.commands.videos import fetch_videos, format_number
from ytstudio.main import app

runner = CliRunner()


class TestFormatNumber:
    """Test number formatting utility."""

    def test_small_number(self):
        assert format_number(500) == "500"

    def test_thousands(self):
        assert format_number(1500) == "1.5K"
        assert format_number(10000) == "10.0K"

    def test_millions(self):
        assert format_number(1500000) == "1.5M"
        assert format_number(5000000) == "5.0M"


class TestFetchVideos:
    """Test video fetching logic."""

    def test_fetch_videos_returns_data(self, mock_service):
        """Test that fetch_videos returns video data with stats."""
        result = fetch_videos(mock_service, limit=10)

        assert "videos" in result
        assert "next_page_token" in result
        assert "total_results" in result
        assert len(result["videos"]) == 1

        video = result["videos"][0]
        assert video["id"] == MOCK_VIDEO["id"]
        assert video["title"] == MOCK_VIDEO["snippet"]["title"]
        assert video["views"] == 10000
        assert video["likes"] == 500

    def test_fetch_videos_calls_api(self, mock_service):
        """Test that correct API calls are made."""
        fetch_videos(mock_service, limit=20)

        # Should call channels to get uploads playlist
        mock_service.channels.return_value.list.assert_called()

        # Should call playlistItems to get video list
        mock_service.playlistItems.return_value.list.assert_called()

        # Should call videos to get stats
        mock_service.videos.return_value.list.assert_called()


class TestVideosListCommand:
    """Test yt videos list command."""

    def test_list_videos_table(self, mock_auth):
        """Test listing videos in table format."""
        result = runner.invoke(app, ["videos", "list"])

        assert result.exit_code == 0
        assert "Test Video Title" in result.stdout

    def test_list_videos_json(self, mock_auth):
        """Test listing videos in JSON format."""
        result = runner.invoke(app, ["videos", "list", "--output", "json"])

        assert result.exit_code == 0
        assert "test_video_123" in result.stdout

    def test_list_videos_not_authenticated(self):
        """Test error when not authenticated."""
        with (
            patch("ytstudio.commands.videos.get_authenticated_service", return_value=None),
            patch("ytstudio.commands.videos.is_demo_mode", return_value=False),
        ):
            result = runner.invoke(app, ["videos", "list"])

            assert result.exit_code == 1
            assert "Not authenticated" in result.stdout


class TestVideosGetCommand:
    """Test yt videos get command."""

    def test_get_video_details(self, mock_auth):
        """Test getting video details."""
        result = runner.invoke(app, ["videos", "get", "test_video_123"])

        assert result.exit_code == 0
        assert "Test Video Title" in result.stdout
        assert "youtu.be" in result.stdout

    def test_get_video_json(self, mock_auth):
        """Test getting video details as JSON."""
        result = runner.invoke(app, ["videos", "get", "test_video_123", "-o", "json"])

        assert result.exit_code == 0
        assert '"id": "test_video_123"' in result.stdout

    def test_get_video_not_found(self, mock_auth):
        """Test error when video not found."""
        mock_auth.videos.return_value.list.return_value.execute.return_value = {"items": []}

        result = runner.invoke(app, ["videos", "get", "nonexistent"])

        assert result.exit_code == 1
        assert "not found" in result.stdout


class TestVideosUpdateCommand:
    """Test yt videos update command."""

    def test_update_video_dry_run(self, mock_auth):
        """Test update with dry-run flag."""
        result = runner.invoke(
            app, ["videos", "update", "test_video_123", "--title", "New Title", "--dry-run"]
        )

        assert result.exit_code == 0
        assert "Dry run" in result.stdout
        assert "New Title" in result.stdout

        # Should not call update API
        mock_auth.videos.return_value.update.assert_not_called()

    def test_update_video_apply(self, mock_auth):
        """Test applying update."""
        result = runner.invoke(app, ["videos", "update", "test_video_123", "--title", "New Title"])

        assert result.exit_code == 0
        assert "Updated" in result.stdout

        # Should call update API
        mock_auth.videos.return_value.update.assert_called()

    def test_update_no_changes(self, mock_auth):
        """Test error when no changes provided."""
        result = runner.invoke(app, ["videos", "update", "test_video_123"])

        assert result.exit_code == 1
        assert "Nothing to update" in result.stdout


class TestSearchReplaceCommand:
    """Test yt videos search-replace command."""

    def test_search_replace_no_matches(self, mock_auth):
        """Test search-replace with no matches."""
        result = runner.invoke(
            app, ["videos", "search-replace", "-s", "nonexistent_text", "-r", "new", "-f", "title"]
        )

        assert result.exit_code == 0
        assert "No matches" in result.stdout

    def test_search_replace_missing_args(self):
        """Test search-replace requires search and replace."""
        result = runner.invoke(app, ["videos", "search-replace"])

        assert result.exit_code != 0
