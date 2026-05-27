from pathlib import Path

import pytest
from pydantic import ValidationError

from ytstudio.upload_pipeline import (
    DiscoveryError,
    Privacy,
    UploadSpec,
    discover,
    to_youtube_body,
    validate_jobs,
)
from ytstudio.upload_pipeline import (
    ValidationError as JobValidationError,
)


def test_minimal_valid_spec():
    spec = UploadSpec(title="Hello", description="World")
    assert spec.title == "Hello"
    assert spec.description == "World"
    assert spec.privacy == "private"
    assert spec.category_id == "22"
    assert spec.made_for_kids is False
    assert spec.tags == []
    assert spec.video_id is None
    assert spec.uploaded_at is None


def test_publish_at_forces_privacy_to_private():
    spec = UploadSpec(
        title="x", description="x", privacy="public",
        publish_at="2099-01-01T10:00:00+02:00",
    )
    assert spec.privacy == Privacy.private


def test_publish_at_must_be_future():
    with pytest.raises(ValidationError, match="publish_at must be in the future"):
        UploadSpec(
            title="x", description="x",
            publish_at="2000-01-01T10:00:00+02:00",
        )


def test_publish_at_requires_timezone():
    with pytest.raises(ValidationError, match="timezone"):
        UploadSpec(
            title="x", description="x",
            publish_at="2099-01-01T10:00:00",  # naive
        )


def test_title_empty_rejected():
    with pytest.raises(ValidationError):
        UploadSpec(title="", description="x")


def test_unknown_field_rejected():
    with pytest.raises(ValidationError):
        UploadSpec(title="x", description="x", bogus="nope")


def test_privacy_invalid_rejected():
    with pytest.raises(ValidationError):
        UploadSpec(title="x", description="x", privacy="hidden")


def _write(p: Path, body: str = "") -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body)
    return p


SIDECAR_OK = """\
title: Sample
description: |
  Demo body
"""


def test_discover_single_pair(tmp_path):
    video = _write(tmp_path / "holiday.mp4")
    _write(tmp_path / "holiday.yaml", SIDECAR_OK)

    jobs = discover(tmp_path)

    assert len(jobs) == 1
    assert jobs[0].video_path == video
    assert jobs[0].thumbnail_path is None
    assert jobs[0].spec.title == "Sample"
    assert jobs[0].already_uploaded is False


def test_discover_picks_up_jpg_thumbnail(tmp_path):
    _write(tmp_path / "holiday.mp4")
    _write(tmp_path / "holiday.yaml", SIDECAR_OK)
    thumb = _write(tmp_path / "holiday.jpg", "fake")

    jobs = discover(tmp_path)

    assert jobs[0].thumbnail_path == thumb


def test_discover_picks_up_png_thumbnail(tmp_path):
    _write(tmp_path / "holiday.mp4")
    _write(tmp_path / "holiday.yaml", SIDECAR_OK)
    thumb = _write(tmp_path / "holiday.png", "fake")

    jobs = discover(tmp_path)

    assert jobs[0].thumbnail_path == thumb


def test_discover_single_file_argument(tmp_path):
    video = _write(tmp_path / "single.mov")
    _write(tmp_path / "single.yaml", SIDECAR_OK)

    jobs = discover(video)

    assert len(jobs) == 1
    assert jobs[0].video_path == video


def test_discover_video_without_sidecar_errors(tmp_path):
    _write(tmp_path / "orphan.mp4")

    with pytest.raises(DiscoveryError, match="no sidecar"):
        discover(tmp_path)


def test_discover_already_uploaded_flagged(tmp_path):
    _write(tmp_path / "done.mp4")
    _write(
        tmp_path / "done.yaml",
        "title: Done\ndescription: ok\nvideo_id: abc123\n",
    )

    jobs = discover(tmp_path)

    assert len(jobs) == 1
    assert jobs[0].already_uploaded is True


def test_discover_no_recursion(tmp_path):
    nested = tmp_path / "sub"
    _write(nested / "nested.mp4")
    _write(nested / "nested.yaml", SIDECAR_OK)

    jobs = discover(tmp_path)

    assert jobs == []


def test_validate_jobs_thumbnail_too_large(tmp_path):
    _write(tmp_path / "big.mp4")
    _write(tmp_path / "big.yaml", SIDECAR_OK)
    huge = tmp_path / "big.jpg"
    huge.write_bytes(b"x" * (2 * 1024 * 1024 + 1))

    jobs = discover(tmp_path)

    with pytest.raises(JobValidationError, match=r"thumbnail.*too large"):
        validate_jobs(jobs)


def test_validate_jobs_ok_with_small_thumbnail(tmp_path):
    _write(tmp_path / "ok.mp4")
    _write(tmp_path / "ok.yaml", SIDECAR_OK)
    (tmp_path / "ok.jpg").write_bytes(b"x" * 1024)

    jobs = discover(tmp_path)
    validate_jobs(jobs)  # no error


def test_validate_jobs_collects_all_errors(tmp_path):
    _write(tmp_path / "one.mp4")
    _write(tmp_path / "one.yaml", SIDECAR_OK)
    (tmp_path / "one.jpg").write_bytes(b"x" * (3 * 1024 * 1024))

    _write(tmp_path / "two.mp4")
    _write(tmp_path / "two.yaml", SIDECAR_OK)
    (tmp_path / "two.png").write_bytes(b"x" * (3 * 1024 * 1024))

    jobs = discover(tmp_path)

    with pytest.raises(JobValidationError) as ei:
        validate_jobs(jobs)

    msg = str(ei.value)
    assert "one.jpg" in msg
    assert "two.png" in msg


def test_body_minimal():
    spec = UploadSpec(title="Hi", description="Body")
    body = to_youtube_body(spec)

    assert body["snippet"]["title"] == "Hi"
    assert body["snippet"]["description"] == "Body"
    assert body["snippet"]["categoryId"] == "22"
    assert body["snippet"]["tags"] == []
    assert body["status"]["privacyStatus"] == "private"
    assert body["status"]["selfDeclaredMadeForKids"] is False
    assert "publishAt" not in body["status"]


def test_body_with_publish_at_uses_iso():
    spec = UploadSpec(
        title="Scheduled", description="x",
        publish_at="2099-06-01T19:00:00+02:00",
    )
    body = to_youtube_body(spec)

    assert body["status"]["privacyStatus"] == "private"
    assert body["status"]["publishAt"].startswith("2099-06-01T")
    assert body["status"]["publishAt"].endswith("+02:00") or body["status"]["publishAt"].endswith("Z")


def test_body_includes_languages_and_tags():
    spec = UploadSpec(
        title="Localised", description="x",
        tags=["a", "b"], default_language="nl", default_audio_language="nl",
    )
    body = to_youtube_body(spec)

    assert body["snippet"]["tags"] == ["a", "b"]
    assert body["snippet"]["defaultLanguage"] == "nl"
    assert body["snippet"]["defaultAudioLanguage"] == "nl"
