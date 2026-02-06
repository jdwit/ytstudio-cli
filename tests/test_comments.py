from datetime import UTC, datetime, timedelta

from typer.testing import CliRunner

from ytstudio.main import app
from ytstudio.ui import time_ago

runner = CliRunner()


class TestTimeAgo:
    def test_formats_correctly(self):
        now = datetime.now(UTC).isoformat()
        assert time_ago(now) == "recently"

        hours_ago = (datetime.now(UTC) - timedelta(hours=5)).isoformat()
        assert "5h ago" in time_ago(hours_ago)


class TestCommentsCommands:
    def test_list_channel_wide(self, mock_auth):
        result = runner.invoke(app, ["comments", "list"])
        assert result.exit_code == 0
        assert "Test User" in result.stdout
        assert "Published Comments" in result.stdout
        assert "channel" in result.stdout

    def test_list_with_video_filter(self, mock_auth):
        result = runner.invoke(app, ["comments", "list", "--video", "test_video_123"])
        assert result.exit_code == 0
        assert "Test User" in result.stdout
        assert "video test_video_123" in result.stdout

    def test_list_held_comments(self, mock_auth):
        result = runner.invoke(app, ["comments", "list", "--status", "held"])
        assert result.exit_code == 0
        assert "Held for Review" in result.stdout

    def test_list_spam_comments(self, mock_auth):
        result = runner.invoke(app, ["comments", "list", "--status", "spam"])
        assert result.exit_code == 0
        assert "Likely Spam" in result.stdout

    def test_list_comments_disabled(self, mock_auth):
        mock_auth.commentThreads.return_value.list.return_value.execute.side_effect = Exception(
            "Comments disabled"
        )
        result = runner.invoke(app, ["comments", "list", "--video", "test_video_123"])
        assert result.exit_code == 1
