import pytest

from ytstudio import demo_service
from ytstudio.demo_service import (
    FakeAnalyticsService,
    FakeYouTubeService,
    _load_fixture,
    is_demo_mode,
)


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on"])
def test_is_demo_mode_truthy_values(monkeypatch, value):
    monkeypatch.setenv("YTSTUDIO_DEMO", value)
    assert is_demo_mode() is True


@pytest.mark.parametrize("value", ["", "0", "false", "no"])
def test_is_demo_mode_falsy_values(monkeypatch, value):
    monkeypatch.setenv("YTSTUDIO_DEMO", value)
    assert is_demo_mode() is False


def test_fake_youtube_channels_list_returns_fixture():
    response = FakeYouTubeService().channels().list(part="contentDetails", mine=True).execute()
    uploads = response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    assert uploads == "UU_demo_uploads"


def test_fake_youtube_videos_list_returns_requested_ids():
    response = (
        FakeYouTubeService().videos().list(part="snippet", id="demo_vid_001,demo_vid_002").execute()
    )
    items = response["items"]
    assert len(items) == 2
    assert {item["id"] for item in items} == {"demo_vid_001", "demo_vid_002"}


def test_fake_youtube_playlist_items_paginate_envelope():
    response = FakeYouTubeService().playlistItems().list().execute()
    fixture = _load_fixture("playlist_items.json")
    assert response["pageInfo"]["totalResults"] == len(fixture["items"])
    assert response["nextPageToken"] is None


def test_fake_analytics_query_returns_column_headers_and_rows():
    response = (
        FakeAnalyticsService()
        .reports()
        .query(
            ids="channel==X",
            startDate="2026-01-01",
            endDate="2026-01-31",
            metrics="views,likes",
        )
        .execute()
    )
    assert [h["name"] for h in response["columnHeaders"]] == ["views", "likes"]
    assert len(response["rows"]) == 1
    assert len(response["rows"][0]) == 2


def test_fixtures_load_via_importlib_resources():
    videos = _load_fixture("videos.json")
    assert isinstance(videos["items"], list)
    assert len(videos["items"]) > 0


def test_fake_videos_update_records_override():
    service = FakeYouTubeService()
    result = (
        service.videos()
        .update(part="snippet", body={"id": "demo_vid_001", "snippet": {"title": "Renamed"}})
        .execute()
    )
    assert result == {"id": "demo_vid_001"}

    listed = service.videos().list(part="snippet", id="demo_vid_001").execute()
    assert listed["items"][0]["snippet"]["title"] == "Renamed"


def test_fake_comments_set_moderation_status_returns_empty():
    response = (
        FakeYouTubeService().comments().setModerationStatus(id="x", moderationStatus="published")
    )
    assert response.execute() == {}


def test_print_demo_banner_once(capsys, monkeypatch):
    demo_service._reset_banner_for_tests()
    monkeypatch.setattr("sys.argv", ["ytstudio", "videos", "list"])
    demo_service.print_demo_banner_once()
    demo_service.print_demo_banner_once()
    captured = capsys.readouterr()
    assert captured.err.count("demo mode") == 1


def test_print_demo_banner_skipped_for_json(capsys, monkeypatch):
    demo_service._reset_banner_for_tests()
    monkeypatch.setattr("sys.argv", ["ytstudio", "videos", "list", "-o", "json"])
    demo_service.print_demo_banner_once()
    captured = capsys.readouterr()
    assert "demo mode" not in captured.err
