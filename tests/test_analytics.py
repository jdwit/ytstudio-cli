from unittest.mock import patch

from typer.testing import CliRunner

from ytstudio.main import app
from ytstudio.ui import format_number

runner = CliRunner()


class TestFormatNumber:
    def test_formats_correctly(self):
        assert format_number(999) == "999"
        assert format_number(1500) == "1.5K"
        assert format_number(2500000) == "2.5M"


class TestAnalyticsCommands:
    def test_overview(self):
        with patch("ytstudio.commands.analytics.is_demo_mode", return_value=True):
            result = runner.invoke(app, ["analytics", "overview"])
            assert result.exit_code == 0

    def test_video_not_found(self, mock_auth):
        mock_auth.videos.return_value.list.return_value.execute.return_value = {"items": []}
        with patch("ytstudio.commands.analytics.get_services") as mock_get:
            mock_get.return_value = (mock_auth, mock_auth)
            result = runner.invoke(app, ["analytics", "video", "nonexistent"])
            assert result.exit_code == 1

    def test_not_authenticated(self):
        with patch("ytstudio.commands.analytics.get_authenticated_service", return_value=None):
            result = runner.invoke(app, ["analytics", "overview"])
            assert result.exit_code == 1
