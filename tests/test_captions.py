import json
from unittest.mock import Mock

from googleapiclient.errors import HttpError
from typer.testing import CliRunner

from tests.conftest import MOCK_CAPTION_ASR, MOCK_CAPTION_STANDARD
from ytstudio.commands.videos import srt_to_text
from ytstudio.main import app

runner = CliRunner()


def _set_srt(mock_auth, body: bytes):
    mock_auth.captions.return_value.download.return_value.execute.return_value = body


class TestCaptions:
    def test_captions_table(self, mock_auth):
        result = runner.invoke(app, ["videos", "captions", "test_video_123"])
        assert result.exit_code == 0
        assert "nl" in result.stdout
        assert "standard" in result.stdout
        assert "ASR" in result.stdout

    def test_captions_json(self, mock_auth):
        result = runner.invoke(app, ["videos", "captions", "test_video_123", "-o", "json"])
        assert result.exit_code == 0
        tracks = json.loads(result.stdout)
        assert len(tracks) == 2
        assert {t["language"] for t in tracks} == {"nl", "en"}
        assert set(tracks[0]) == {
            "id",
            "language",
            "name",
            "track_kind",
            "is_draft",
            "last_updated",
        }

    def test_captions_none(self, mock_auth):
        mock_auth.captions.return_value.list.return_value.execute.return_value = {"items": []}
        result = runner.invoke(app, ["videos", "captions", "test_video_123"])
        assert result.exit_code == 0
        assert "No caption tracks" in result.stdout


class TestTranscript:
    def test_default_text_is_clean(self, mock_auth):
        result = runner.invoke(app, ["videos", "transcript", "test_video_123"])
        assert result.exit_code == 0
        assert result.stdout.strip() == "Hello world\nThis is the video"

    def test_default_selects_standard_track(self, mock_auth):
        runner.invoke(app, ["videos", "transcript", "test_video_123"])
        mock_auth.captions.return_value.download.assert_called_with(id="cap_std_nl", tfmt="srt")

    def test_prefers_standard_even_when_asr_listed_first(self, mock_auth):
        # ASR first in the list: candidates[0] would be ASR, so this only passes
        # if the standard-over-ASR preference actually runs.
        mock_auth.captions.return_value.list.return_value.execute.return_value = {
            "items": [MOCK_CAPTION_ASR, MOCK_CAPTION_STANDARD]
        }
        runner.invoke(app, ["videos", "transcript", "test_video_123"])
        mock_auth.captions.return_value.download.assert_called_with(id="cap_std_nl", tfmt="srt")

    def test_lang_selects_matching_track(self, mock_auth):
        result = runner.invoke(app, ["videos", "transcript", "test_video_123", "--lang", "en"])
        assert result.exit_code == 0
        mock_auth.captions.return_value.download.assert_called_with(id="cap_asr_en", tfmt="srt")

    def test_lang_missing(self, mock_auth):
        result = runner.invoke(app, ["videos", "transcript", "test_video_123", "--lang", "fr"])
        assert result.exit_code == 1
        assert "Available: en, nl" in result.stdout

    def test_numeric_cue_text_preserved(self, mock_auth):
        _set_srt(
            mock_auth,
            b"1\n00:00:00,000 --> 00:00:01,000\n2026\n\n"
            b"2\n00:00:01,000 --> 00:00:02,000\nhappy new year\n",
        )
        result = runner.invoke(app, ["videos", "transcript", "test_video_123"])
        assert result.exit_code == 0
        assert result.stdout.strip() == "2026\nhappy new year"

    def test_standard_track_keeps_repeated_lines(self, mock_auth):
        # Human track: a legitimately repeated cue must not be collapsed.
        _set_srt(
            mock_auth,
            b"1\n00:00:00,000 --> 00:00:01,000\nRun!\n\n2\n00:00:01,000 --> 00:00:02,000\nRun!\n",
        )
        result = runner.invoke(app, ["videos", "transcript", "test_video_123"])
        assert result.exit_code == 0
        assert result.stdout.strip() == "Run!\nRun!"

    def test_asr_track_dedupes_consecutive(self, mock_auth):
        # ASR track (--lang en): rolling-caption duplicates collapse.
        _set_srt(
            mock_auth,
            b"1\n00:00:00,000 --> 00:00:01,000\nrolling\n\n"
            b"2\n00:00:01,000 --> 00:00:02,000\nrolling\n",
        )
        result = runner.invoke(app, ["videos", "transcript", "test_video_123", "--lang", "en"])
        assert result.exit_code == 0
        assert result.stdout.strip() == "rolling"

    def test_json_payload(self, mock_auth):
        result = runner.invoke(app, ["videos", "transcript", "test_video_123", "-o", "json"])
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["track_kind"] == "standard"
        assert payload["transcript"] == "Hello world\nThis is the video"

    def test_no_tracks(self, mock_auth):
        mock_auth.captions.return_value.list.return_value.execute.return_value = {"items": []}
        result = runner.invoke(app, ["videos", "transcript", "test_video_123"])
        assert result.exit_code == 1
        assert "No caption tracks" in result.stdout

    def test_not_downloadable(self, mock_auth):
        err = HttpError(resp=Mock(status=403, reason="Forbidden"), content=b"{}")
        mock_auth.captions.return_value.download.return_value.execute.side_effect = err
        result = runner.invoke(app, ["videos", "transcript", "test_video_123"])
        assert result.exit_code == 1
        assert "not downloadable" in result.stdout

    def test_quota_exceeded_is_not_misreported(self, mock_auth):
        # Quota is also a 403; it must reach the quota handler, not "not downloadable".
        err = HttpError(resp=Mock(status=403, reason="Forbidden"), content=b"{}")
        err.error_details = [{"reason": "quotaExceeded"}]
        mock_auth.captions.return_value.download.return_value.execute.side_effect = err
        result = runner.invoke(app, ["videos", "transcript", "test_video_123"])
        assert result.exit_code == 1
        assert "quota" in result.stdout.lower()
        assert "not downloadable" not in result.stdout


class TestSrtToText:
    def test_dedup_off_keeps_duplicates(self):
        srt = "1\n00:00:00,000 --> 00:00:01,000\nhi\n\n2\n00:00:01,000 --> 00:00:02,000\nhi\n"
        assert srt_to_text(srt) == "hi\nhi"

    def test_dedup_on_collapses(self):
        srt = "1\n00:00:00,000 --> 00:00:01,000\nhi\n\n2\n00:00:01,000 --> 00:00:02,000\nhi\n"
        assert srt_to_text(srt, dedup_consecutive=True) == "hi"

    def test_multiline_cue_joined(self):
        srt = "1\n00:00:00,000 --> 00:00:02,000\nfirst line\nsecond line\n"
        assert srt_to_text(srt) == "first line second line"

    def test_strips_inline_tags(self):
        srt = "1\n00:00:00,000 --> 00:00:02,000\n<c>tag</c>ged text\n"
        assert srt_to_text(srt) == "tagged text"

    def test_empty(self):
        assert srt_to_text("") == ""
