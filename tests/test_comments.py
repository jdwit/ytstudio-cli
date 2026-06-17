from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from googleapiclient.errors import HttpError
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

    def test_list_json_output(self, mock_auth):
        result = runner.invoke(app, ["comments", "list", "-o", "json"])
        assert result.exit_code == 0
        assert '"id": "UgwComment123"' in result.stdout
        assert '"author": "Test User"' in result.stdout

    def test_publish_comments(self, mock_auth):
        result = runner.invoke(app, ["comments", "publish", "UgwComment123", "UgwComment456"])
        assert result.exit_code == 0
        assert "2 comment(s) published" in result.stdout
        mock_auth.comments.return_value.setModerationStatus.assert_called_once_with(
            id="UgwComment123,UgwComment456",
            moderationStatus="published",
        )

    def test_reject_comments_with_ban(self, mock_auth):
        result = runner.invoke(app, ["comments", "reject", "UgwComment123", "--ban"])
        assert result.exit_code == 0
        assert "1 comment(s) rejected" in result.stdout
        mock_auth.comments.return_value.setModerationStatus.assert_called_once_with(
            id="UgwComment123",
            moderationStatus="rejected",
            banAuthor=True,
        )

    def test_list_comments_disabled(self, mock_auth):
        mock_auth.commentThreads.return_value.list.return_value.execute.side_effect = Exception(
            "Comments disabled"
        )
        result = runner.invoke(app, ["comments", "list", "--video", "test_video_123"])
        assert result.exit_code == 1

    def test_reply(self, mock_auth):
        result = runner.invoke(
            app, ["comments", "reply", "UgwComment123", "--text", "Thanks for watching!"]
        )
        assert result.exit_code == 0
        assert "UgwReply789" in result.stdout
        insert = mock_auth.comments.return_value.insert
        body = insert.call_args.kwargs["body"]
        assert body["snippet"]["parentId"] == "UgwComment123"
        assert body["snippet"]["textOriginal"] == "Thanks for watching!"

    def test_reply_requires_text(self, mock_auth):
        result = runner.invoke(app, ["comments", "reply", "UgwComment123"])
        assert result.exit_code != 0

    def test_reply_invalid_parent(self, mock_auth):
        resp = MagicMock()
        resp.status = 400
        mock_auth.comments.return_value.insert.return_value.execute.side_effect = HttpError(
            resp, b'{"error": {"message": "invalid"}}'
        )
        result = runner.invoke(app, ["comments", "reply", "not_a_top_level_id", "--text", "hi"])
        assert result.exit_code == 1
        assert "top-level comment id" in result.stdout
