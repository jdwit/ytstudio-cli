"""Tests for analytics commands."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from ytcli.commands.analytics import format_number
from ytcli.main import app

runner = CliRunner()


class TestFormatNumber:
    """Test number formatting."""

    def test_small_numbers(self):
        assert format_number(0) == "0"
        assert format_number(999) == "999"

    def test_thousands(self):
        assert format_number(1000) == "1.0K"
        assert format_number(15000) == "15.0K"

    def test_millions(self):
        assert format_number(1000000) == "1.0M"
        assert format_number(2500000) == "2.5M"


class TestAnalyticsOverviewCommand:
    """Test yt analytics overview command."""

    def test_overview_basic_stats(self, mock_auth):
        """Test overview shows channel stats when analytics API unavailable."""
        # Mock analytics service as None (unavailable)
        with patch("ytcli.commands.analytics.get_services") as mock_get:
            mock_get.return_value = (mock_auth, None)

            result = runner.invoke(app, ["analytics", "overview"])

            assert result.exit_code == 0
            assert "Test Channel" in result.stdout or "Subscribers" in result.stdout

    def test_overview_json(self, mock_auth):
        """Test overview in JSON format."""
        with patch("ytcli.commands.analytics.get_services") as mock_get:
            mock_get.return_value = (mock_auth, None)

            result = runner.invoke(app, ["analytics", "overview", "-o", "json"])

            assert result.exit_code == 0


class TestAnalyticsVideoCommand:
    """Test yt analytics video command."""

    def test_video_stats(self, mock_auth):
        """Test video analytics shows stats."""
        with patch("ytcli.commands.analytics.get_services") as mock_get:
            mock_get.return_value = (mock_auth, None)

            result = runner.invoke(app, ["analytics", "video", "test_video_123"])

            assert result.exit_code == 0
            assert "Test Video Title" in result.stdout

    def test_video_not_found(self, mock_auth):
        """Test error when video not found."""
        mock_auth.videos.return_value.list.return_value.execute.return_value = {"items": []}

        with patch("ytcli.commands.analytics.get_services") as mock_get:
            mock_get.return_value = (mock_auth, None)

            result = runner.invoke(app, ["analytics", "video", "nonexistent"])

            assert result.exit_code == 1
            assert "not found" in result.stdout


class TestAnalyticsTopCommand:
    """Test yt analytics top command."""

    def test_top_videos(self, mock_auth):
        """Test top videos command."""
        with patch("ytcli.commands.analytics.get_services") as mock_get:
            mock_get.return_value = (mock_auth, None)

            result = runner.invoke(app, ["analytics", "top"])

            assert result.exit_code == 0
            assert "Top" in result.stdout or "Video" in result.stdout


class TestAnalyticsWithFullAPI:
    """Test analytics with full YouTube Analytics API."""

    def test_overview_with_analytics_api(self, mock_auth):
        """Test overview when analytics API is available."""
        mock_analytics = MagicMock()
        mock_analytics.reports.return_value.query.return_value.execute.return_value = {
            "columnHeaders": [
                {"name": "views"},
                {"name": "estimatedMinutesWatched"},
                {"name": "averageViewDuration"},
                {"name": "subscribersGained"},
                {"name": "subscribersLost"},
                {"name": "likes"},
                {"name": "comments"},
            ],
            "rows": [[10000, 50000, 180, 100, 10, 500, 50]],
        }

        with patch("ytcli.commands.analytics.get_services") as mock_get:
            mock_get.return_value = (mock_auth, mock_analytics)

            result = runner.invoke(app, ["analytics", "overview"])

            assert result.exit_code == 0
            # Should show formatted metrics
            assert "views" in result.stdout.lower() or "Views" in result.stdout

    def test_traffic_requires_analytics_api(self, mock_auth):
        """Test traffic command requires analytics API."""
        with patch("ytcli.commands.analytics.get_services") as mock_get:
            mock_get.return_value = (mock_auth, None)

            result = runner.invoke(app, ["analytics", "traffic", "test_video_123"])

            assert result.exit_code == 1
            assert "Analytics API required" in result.stdout
