from pathlib import Path

from typer.testing import CliRunner

from ytstudio.main import app

runner = CliRunner()


SIDECAR = """\
title: Dry Run Sample
description: |
  Hello
privacy: private
tags: [demo]
"""


def _stage(tmp_path: Path) -> Path:
    (tmp_path / "demo.mp4").write_bytes(b"fake-video")
    (tmp_path / "demo.yaml").write_text(SIDECAR)
    return tmp_path


def test_upload_dry_run_lists_jobs_and_does_not_call_api(tmp_path, mock_auth):
    _stage(tmp_path)

    result = runner.invoke(app, ["videos", "upload", str(tmp_path)])

    assert result.exit_code == 0
    assert "Dry Run Sample" in result.stdout
    assert "demo.mp4" in result.stdout
    assert "private" in result.stdout
    mock_auth.videos.return_value.insert.assert_not_called()


def test_upload_dry_run_validation_error_exits_nonzero(tmp_path, mock_auth):
    (tmp_path / "bad.mp4").write_bytes(b"x")
    (tmp_path / "bad.yaml").write_text("not-a-mapping\n")

    result = runner.invoke(app, ["videos", "upload", str(tmp_path)])

    assert result.exit_code != 0
