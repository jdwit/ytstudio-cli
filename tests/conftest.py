"""Shared test fixtures and mock data."""

from unittest.mock import MagicMock, patch

import pytest

# Sample API response data
MOCK_CHANNEL = {
    "id": "UC_test_channel_id",
    "snippet": {
        "title": "Test Channel",
        "description": "A test channel",
        "customUrl": "@testchannel",
    },
    "statistics": {
        "subscriberCount": "125000",
        "viewCount": "5000000",
        "videoCount": "50",
    },
    "contentDetails": {
        "relatedPlaylists": {
            "uploads": "UU_test_uploads_playlist",
        },
    },
}

MOCK_VIDEO = {
    "id": "test_video_123",
    "snippet": {
        "title": "Test Video Title",
        "description": "This is a test video description that is long enough.",
        "publishedAt": "2026-01-15T10:00:00Z",
        "tags": ["test", "video", "youtube", "cli", "demo"],
        "categoryId": "22",
    },
    "statistics": {
        "viewCount": "10000",
        "likeCount": "500",
        "commentCount": "50",
    },
    "contentDetails": {
        "duration": "PT5M30S",
    },
    "status": {
        "privacyStatus": "public",
    },
}

MOCK_VIDEO_SHORT_TITLE = {
    **MOCK_VIDEO,
    "id": "short_title_vid",
    "snippet": {
        **MOCK_VIDEO["snippet"],
        "title": "Short",
        "description": "",
        "tags": [],
    },
}

MOCK_PLAYLIST_ITEM = {
    "snippet": {
        "title": MOCK_VIDEO["snippet"]["title"],
        "publishedAt": MOCK_VIDEO["snippet"]["publishedAt"],
    },
    "contentDetails": {
        "videoId": MOCK_VIDEO["id"],
    },
}

MOCK_COMMENT = {
    "snippet": {
        "topLevelComment": {
            "snippet": {
                "authorDisplayName": "Test User",
                "textOriginal": "Great video! Love it!",
                "textDisplay": "Great video! Love it!",
                "likeCount": 5,
                "publishedAt": "2026-01-20T15:00:00Z",
            },
        },
    },
}

MOCK_NEGATIVE_COMMENT = {
    "snippet": {
        "topLevelComment": {
            "snippet": {
                "authorDisplayName": "Angry User",
                "textOriginal": "This is terrible and boring",
                "textDisplay": "This is terrible and boring",
                "likeCount": 0,
                "publishedAt": "2026-01-20T16:00:00Z",
            },
        },
    },
}


def create_mock_service():
    """Create a mock YouTube API service."""
    service = MagicMock()

    # channels().list()
    channels_list = MagicMock()
    channels_list.execute.return_value = {"items": [MOCK_CHANNEL]}
    service.channels.return_value.list.return_value = channels_list

    # playlistItems().list()
    playlist_list = MagicMock()
    playlist_list.execute.return_value = {
        "items": [MOCK_PLAYLIST_ITEM],
        "nextPageToken": None,
        "pageInfo": {"totalResults": 1},
    }
    service.playlistItems.return_value.list.return_value = playlist_list

    # videos().list()
    videos_list = MagicMock()
    videos_list.execute.return_value = {"items": [MOCK_VIDEO]}
    service.videos.return_value.list.return_value = videos_list

    # videos().update()
    videos_update = MagicMock()
    videos_update.execute.return_value = MOCK_VIDEO
    service.videos.return_value.update.return_value = videos_update

    # commentThreads().list()
    comments_list = MagicMock()
    comments_list.execute.return_value = {
        "items": [MOCK_COMMENT, MOCK_NEGATIVE_COMMENT],
        "nextPageToken": None,
    }
    service.commentThreads.return_value.list.return_value = comments_list

    return service


@pytest.fixture
def mock_service():
    """Fixture that provides a mocked YouTube service."""
    return create_mock_service()


@pytest.fixture
def mock_auth(mock_service):
    """Fixture that patches authentication to return mock service in all modules."""
    with (
        patch("ytstudio.commands.videos.get_authenticated_service", return_value=mock_service),
        patch("ytstudio.commands.comments.get_authenticated_service", return_value=mock_service),
        patch("ytstudio.commands.seo.get_authenticated_service", return_value=mock_service),
        patch("ytstudio.commands.analytics.get_authenticated_service", return_value=mock_service),
    ):
        yield mock_service


@pytest.fixture
def mock_credentials():
    """Fixture that patches credential loading."""
    mock_creds = {
        "token": "fake_token",
        "refresh_token": "fake_refresh",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "fake_client_id",
        "client_secret": "fake_secret",
        "scopes": ["https://www.googleapis.com/auth/youtube.readonly"],
    }
    with patch("ytstudio.config.load_credentials", return_value=mock_creds):
        yield mock_creds
