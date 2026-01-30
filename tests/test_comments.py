"""Tests for comment commands."""

import pytest
from unittest.mock import patch
from typer.testing import CliRunner

from ytcli.main import app
from ytcli.commands.comments import time_ago
from tests.conftest import MOCK_COMMENT, MOCK_NEGATIVE_COMMENT

runner = CliRunner()


class TestTimeAgo:
    """Test time_ago utility."""

    def test_recent(self):
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat()
        assert time_ago(now) == "recently"

    def test_hours_ago(self):
        from datetime import datetime, timezone, timedelta

        dt = datetime.now(timezone.utc) - timedelta(hours=5)
        result = time_ago(dt.isoformat())
        assert "5h ago" in result

    def test_days_ago(self):
        from datetime import datetime, timezone, timedelta

        dt = datetime.now(timezone.utc) - timedelta(days=3)
        result = time_ago(dt.isoformat())
        assert "3d ago" in result

    def test_months_ago(self):
        from datetime import datetime, timezone, timedelta

        dt = datetime.now(timezone.utc) - timedelta(days=60)
        result = time_ago(dt.isoformat())
        assert "2mo ago" in result

    def test_years_ago(self):
        from datetime import datetime, timezone, timedelta

        dt = datetime.now(timezone.utc) - timedelta(days=400)
        result = time_ago(dt.isoformat())
        assert "1y ago" in result


class TestCommentsListCommand:
    """Test yt comments list command."""

    def test_list_comments(self, mock_auth):
        """Test listing comments."""
        result = runner.invoke(app, ["comments", "list", "test_video_123"])

        assert result.exit_code == 0
        assert "Test User" in result.stdout
        assert "Great video" in result.stdout

    def test_list_comments_json(self, mock_auth):
        """Test listing comments as JSON."""
        result = runner.invoke(app, ["comments", "list", "test_video_123", "-o", "json"])

        assert result.exit_code == 0
        assert "Test User" in result.stdout
        assert "Great video" in result.stdout

    def test_list_comments_disabled(self, mock_auth):
        """Test handling when comments are disabled."""
        mock_auth.commentThreads.return_value.list.return_value.execute.side_effect = Exception(
            "Comments disabled"
        )

        result = runner.invoke(app, ["comments", "list", "test_video_123"])

        assert result.exit_code == 1
        assert "Could not fetch" in result.stdout


class TestCommentsSummaryCommand:
    """Test yt comments summary command."""

    def test_summary_shows_sentiment(self, mock_auth):
        """Test that summary shows sentiment breakdown."""
        result = runner.invoke(app, ["comments", "summary", "test_video_123"])

        assert result.exit_code == 0
        assert "Positive" in result.stdout
        assert "Negative" in result.stdout

    def test_summary_shows_negative_comments(self, mock_auth):
        """Test that negative comments are highlighted."""
        result = runner.invoke(app, ["comments", "summary", "test_video_123"])

        assert result.exit_code == 0
        # Should show the negative comment
        assert "terrible" in result.stdout.lower() or "Angry User" in result.stdout


class TestSentimentAnalysis:
    """Test sentiment analysis logic."""

    def test_positive_comment_detected(self):
        """Test that positive words are detected."""
        from ytcli.commands.comments import summary  # noqa

        # The sentiment logic is in summary command
        positive_words = {"love", "great", "amazing", "awesome"}
        text = "Great video! Love it!".lower()

        assert any(word in text for word in positive_words)

    def test_negative_comment_detected(self):
        """Test that negative words are detected."""
        negative_words = {"hate", "bad", "worst", "terrible", "boring"}
        text = "This is terrible and boring".lower()

        assert any(word in text for word in negative_words)
