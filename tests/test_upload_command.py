from pathlib import Path
from unittest.mock import MagicMock, patch

from googleapiclient.errors import HttpError
from typer.testing import CliRunner

from ytstudio.main import app

runner = CliRunner()


SIDECAR = """\
title: Dry Run Sample
description: |
  Hello
privacy: private
tags: [sample]
category_id: "22"
"""


def _stage(tmp_path: Path) -> Path:
    (tmp_path / "sample.mp4").write_bytes(b"fake-video")
    (tmp_path / "sample.yaml").write_text(SIDECAR)
    return tmp_path


def test_upload_dry_run_lists_jobs_and_does_not_call_api(tmp_path, mock_auth):
    _stage(tmp_path)

    result = runner.invoke(app, ["videos", "upload", str(tmp_path)])

    assert result.exit_code == 0
    assert "Dry Run Sample" in result.stdout
    assert "sample.mp4" in result.stdout
    assert "private" in result.stdout
    mock_auth.videos.return_value.insert.assert_not_called()


def test_upload_dry_run_validation_error_exits_nonzero(tmp_path, mock_auth):
    (tmp_path / "bad.mp4").write_bytes(b"x")
    (tmp_path / "bad.yaml").write_text("not-a-mapping\n")

    result = runner.invoke(app, ["videos", "upload", str(tmp_path)])

    assert result.exit_code != 0


def _mock_insert_success(mock_auth, video_id="vid1"):
    insert_request = MagicMock()
    insert_request.next_chunk.side_effect = [(None, {"id": video_id})]
    mock_auth.videos.return_value.insert.return_value = insert_request


def test_upload_execute_uploads_and_writes_back(tmp_path, mock_auth):
    _stage(tmp_path)
    _mock_insert_success(mock_auth, video_id="vid1")

    with patch("ytstudio.upload_pipeline.MediaFileUpload"):
        result = runner.invoke(app, ["videos", "upload", str(tmp_path), "--execute"])

    assert result.exit_code == 0
    mock_auth.videos.return_value.insert.assert_called_once()

    sidecar_text = (tmp_path / "sample.yaml").read_text()
    assert "video_id: vid1" in sidecar_text
    assert "uploaded_at:" in sidecar_text


def test_upload_execute_skips_already_uploaded(tmp_path, mock_auth):
    _stage(tmp_path)
    (tmp_path / "sample.yaml").write_text(SIDECAR + "\nvideo_id: already-there\n")

    with patch("ytstudio.upload_pipeline.MediaFileUpload"):
        result = runner.invoke(app, ["videos", "upload", str(tmp_path), "--execute"])

    assert result.exit_code == 0
    mock_auth.videos.return_value.insert.assert_not_called()


def test_upload_execute_surfaces_video_id_when_write_back_fails(tmp_path, mock_auth):
    # If write_back fails AFTER a successful upload, the user must still see the
    # video_id so they can patch the sidecar manually and avoid a duplicate re-upload.
    _stage(tmp_path)
    _mock_insert_success(mock_auth, video_id="vid-orphan")

    with (
        patch("ytstudio.upload_pipeline.MediaFileUpload"),
        patch(
            "ytstudio.commands.upload.write_back",
            side_effect=OSError("disk full"),
        ),
    ):
        result = runner.invoke(app, ["videos", "upload", str(tmp_path), "--execute"])

    assert "vid-orphan" in result.stdout
    assert "https://youtu.be/vid-orphan" in result.stdout
    # Warn user the sidecar was not patched.
    assert "write-back failed" in result.stdout.lower() or "not patched" in result.stdout.lower()


def test_upload_execute_stops_on_quota_exceeded(tmp_path, mock_auth):
    # Two jobs; first succeeds, second hits quotaExceeded.
    _stage(tmp_path)
    (tmp_path / "second.mp4").write_bytes(b"fake")
    (tmp_path / "second.yaml").write_text(SIDECAR.replace("Dry Run Sample", "Second"))

    insert_ok = MagicMock()
    insert_ok.next_chunk.side_effect = [(None, {"id": "v-ok"})]

    quota_resp = MagicMock(status=403, reason="quotaExceeded")
    quota_err = HttpError(
        quota_resp,
        b'{"error":{"message":"Quota exceeded","errors":[{"reason":"quotaExceeded"}]}}',
    )

    insert_fail = MagicMock()
    insert_fail.next_chunk.side_effect = quota_err

    mock_auth.videos.return_value.insert.side_effect = [insert_ok, insert_fail]

    with patch("ytstudio.upload_pipeline.MediaFileUpload"):
        result = runner.invoke(app, ["videos", "upload", str(tmp_path), "--execute"])

    assert "quota" in result.stdout.lower() or "quota" in result.stderr.lower()
    # First sidecar should be patched, second not.
    assert "video_id: v-ok" in (tmp_path / "sample.yaml").read_text()
    assert "video_id:" not in (tmp_path / "second.yaml").read_text()
    # Final summary must still print after quota stop (clean-stop behavior).
    assert "Done: 1/2 uploaded" in result.stdout
    # Quota exhaustion should surface as a non-zero exit code.
    assert result.exit_code != 0


def test_upload_execute_max_caps_uploads(tmp_path, mock_auth):
    _stage(tmp_path)
    (tmp_path / "second.mp4").write_bytes(b"fake")
    (tmp_path / "second.yaml").write_text(SIDECAR.replace("Dry Run Sample", "Second"))

    insert = MagicMock()
    insert.next_chunk.side_effect = [(None, {"id": "v1"})]
    mock_auth.videos.return_value.insert.return_value = insert

    with patch("ytstudio.upload_pipeline.MediaFileUpload"):
        result = runner.invoke(app, ["videos", "upload", str(tmp_path), "--execute", "--max", "1"])

    assert result.exit_code == 0
    assert mock_auth.videos.return_value.insert.call_count == 1
