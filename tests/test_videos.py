from unittest.mock import MagicMock, patch

import typer
from typer.testing import CliRunner

from ytstudio.main import app

runner = CliRunner()


def make_search_video(video_id, title, description=""):
    return {
        "id": video_id,
        "snippet": {
            "title": title,
            "description": description,
            "publishedAt": "2020-01-01T00:00:00Z",
            "tags": [],
            "categoryId": "22",
        },
        "statistics": {"viewCount": "0", "likeCount": "0", "commentCount": "0"},
        "contentDetails": {"duration": "PT1M"},
        "status": {"privacyStatus": "public"},
    }


def setup_search_mock(mock_service, videos):
    """Configure the search and videos.list mocks for search-replace tests"""
    search_list = MagicMock()
    search_list.execute.return_value = {
        "items": [{"id": {"videoId": v["id"]}} for v in videos],
    }
    mock_service.search.return_value.list.return_value = search_list

    videos_list = MagicMock()
    videos_list.execute.return_value = {"items": videos}
    mock_service.videos.return_value.list.return_value = videos_list


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
        with patch(
            "ytstudio.commands.videos.get_data_service",
            side_effect=typer.Exit(1),
        ):
            result = runner.invoke(app, ["videos", "list"])
            assert result.exit_code == 1


class TestSearchReplace:
    def test_dry_run_shows_preview(self, mock_auth):
        videos = [make_search_video("vid1", "OLDNAME Episode 1")]
        setup_search_mock(mock_auth, videos)

        result = runner.invoke(
            app,
            [
                "videos",
                "search-replace",
                "-s",
                "OLDNAME",
                "-r",
                "NewName",
                "-f",
                "title",
            ],
        )
        assert result.exit_code == 0
        assert "NewName Episode 1" in result.stdout
        assert "Pending" in result.stdout
        assert "--execute" in result.stdout
        mock_auth.videos.return_value.update.assert_not_called()

    def test_execute_applies_changes(self, mock_auth):
        videos = [make_search_video("vid1", "OLDNAME Episode 1")]
        setup_search_mock(mock_auth, videos)

        result = runner.invoke(
            app,
            [
                "videos",
                "search-replace",
                "-s",
                "OLDNAME",
                "-r",
                "NewName",
                "-f",
                "title",
                "--execute",
            ],
        )
        assert result.exit_code == 0
        assert "1 updated" in result.stdout
        mock_auth.videos.return_value.update.assert_called_once()

    def test_no_matches(self, mock_auth):
        videos = [make_search_video("vid1", "Some Other Title")]
        setup_search_mock(mock_auth, videos)

        result = runner.invoke(
            app,
            [
                "videos",
                "search-replace",
                "-s",
                "OLDNAME",
                "-r",
                "NewName",
                "-f",
                "title",
            ],
        )
        assert result.exit_code == 0
        assert "No matches found" in result.stdout

    def test_regex_replace(self, mock_auth):
        videos = [make_search_video("vid1", "Episode 01 - Test")]
        setup_search_mock(mock_auth, videos)

        result = runner.invoke(
            app,
            [
                "videos",
                "search-replace",
                "-s",
                r"Episode (\d+)",
                "-r",
                r"Ep.\1",
                "-f",
                "title",
                "--regex",
            ],
        )
        assert result.exit_code == 0
        assert "Ep.01" in result.stdout

    def test_limit_caps_matches(self, mock_auth):
        videos = [make_search_video(f"vid{i}", f"OLDNAME Episode {i}") for i in range(5)]
        setup_search_mock(mock_auth, videos)

        result = runner.invoke(
            app,
            [
                "videos",
                "search-replace",
                "-s",
                "OLDNAME",
                "-r",
                "NewName",
                "-f",
                "title",
                "-n",
                "2",
            ],
        )
        assert result.exit_code == 0
        assert "2 changes" in result.stdout

    def test_description_field(self, mock_auth):
        videos = [make_search_video("vid1", "Title", description="Visit OLDSITE.com")]
        setup_search_mock(mock_auth, videos)

        result = runner.invoke(
            app,
            [
                "videos",
                "search-replace",
                "-s",
                "OLDSITE.com",
                "-r",
                "newsite.com",
                "-f",
                "description",
            ],
        )
        assert result.exit_code == 0
        assert "newsite.com" in result.stdout

    def test_pagination_reaches_all_videos(self, mock_auth):
        page1_videos = [make_search_video("vid1", "No Match Here")]
        page2_videos = [make_search_video("vid2", "OLDNAME Old Video")]

        call_count = 0

        def search_side_effect():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {
                    "items": [{"id": {"videoId": "vid1"}}],
                    "nextPageToken": "page2token",
                }
            return {
                "items": [{"id": {"videoId": "vid2"}}],
            }

        mock_auth.search.return_value.list.return_value.execute.side_effect = search_side_effect

        videos_call_count = 0

        def videos_side_effect():
            nonlocal videos_call_count
            videos_call_count += 1
            if videos_call_count == 1:
                return {"items": page1_videos}
            return {"items": page2_videos}

        mock_auth.videos.return_value.list.return_value.execute.side_effect = videos_side_effect

        result = runner.invoke(
            app,
            [
                "videos",
                "search-replace",
                "-s",
                "OLDNAME",
                "-r",
                "NewName",
                "-f",
                "title",
            ],
        )
        assert result.exit_code == 0
        assert "NewName Old Video" in result.stdout
