from unittest.mock import patch

from typer.testing import CliRunner

from ytstudio.main import app

runner = CliRunner()


class TestVideosCommands:
    def test_list(self, mock_auth):
        result = runner.invoke(app, ["videos", "list"])
        assert result.exit_code == 0
        assert "Test Video Title" in result.stdout

    def test_get(self, mock_auth):
        result = runner.invoke(app, ["videos", "show", "test_video_123"])
        assert result.exit_code == 0
        assert "Test Video Title" in result.stdout

    def test_get_not_found(self, mock_auth):
        mock_auth.videos.return_value.list.return_value.execute.return_value = {"items": []}
        result = runner.invoke(app, ["videos", "show", "nonexistent"])
        assert result.exit_code == 1

    def test_update_preview(self, mock_auth):
        result = runner.invoke(app, ["videos", "update", "test_video_123", "--title", "New Title"])
        assert result.exit_code == 0
        assert "Preview" in result.stdout
        mock_auth.videos.return_value.update.assert_not_called()

    def test_update_no_changes(self, mock_auth):
        result = runner.invoke(app, ["videos", "update", "test_video_123"])
        assert result.exit_code == 1

    def test_not_authenticated(self):
        with (
            patch("ytstudio.auth.get_authenticated_service", return_value=None),
            patch("ytstudio.commands.videos.is_demo_mode", return_value=False),
        ):
            result = runner.invoke(app, ["videos", "list"])
            assert result.exit_code == 1
