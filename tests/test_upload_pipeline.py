from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from ytstudio.upload_pipeline import Privacy, UploadSpec


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
