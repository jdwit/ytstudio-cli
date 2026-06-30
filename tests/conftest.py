from unittest.mock import MagicMock, patch

import pytest

from ytstudio.commands import playlists as _playlists_module

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
        "tags": ["test", "video", "youtube", "cli"],
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

MOCK_CAPTION_STANDARD = {
    "id": "cap_std_nl",
    "snippet": {
        "videoId": "test_video_123",
        "language": "nl",
        "name": "Nederlands",
        "trackKind": "standard",
        "isDraft": False,
        "lastUpdated": "2026-01-20T00:00:00Z",
    },
}

MOCK_CAPTION_ASR = {
    "id": "cap_asr_en",
    "snippet": {
        "videoId": "test_video_123",
        "language": "en",
        "name": "",
        "trackKind": "ASR",
        "isDraft": False,
        "lastUpdated": "2026-01-21T00:00:00Z",
    },
}

MOCK_SRT = (
    b"1\n00:00:00,000 --> 00:00:02,000\nHello world\n\n"
    b"2\n00:00:02,000 --> 00:00:04,000\nThis is the video\n"
)

MOCK_COMMENT = {
    "id": "UgwComment123",
    "snippet": {
        "topLevelComment": {
            "snippet": {
                "authorDisplayName": "Test User",
                "textOriginal": "Great video! Love it!",
                "textDisplay": "Great video! Love it!",
                "likeCount": 5,
                "publishedAt": "2026-01-20T15:00:00Z",
                "videoId": "test_video_123",
            },
        },
    },
}

MOCK_NEGATIVE_COMMENT = {
    "id": "UgwComment456",
    "snippet": {
        "topLevelComment": {
            "snippet": {
                "authorDisplayName": "Angry User",
                "textOriginal": "This is terrible and boring",
                "textDisplay": "This is terrible and boring",
                "likeCount": 0,
                "publishedAt": "2026-01-20T16:00:00Z",
                "videoId": "test_video_123",
            },
        },
    },
}

MOCK_PLAYLIST = {
    "id": "PL_test_123",
    "snippet": {
        "title": "Test Playlist",
        "description": "desc",
        "publishedAt": "2026-01-01T00:00:00Z",
        "defaultLanguage": "en",
    },
    "contentDetails": {"itemCount": 3},
    "status": {"privacyStatus": "private"},
}

MOCK_PLAYLIST_ITEM_FULL = {
    "id": "PLPLI_test_item_1",
    "snippet": {
        "title": "Item title",
        "publishedAt": "2026-01-02T00:00:00Z",
        "position": 0,
        "resourceId": {"kind": "youtube#video", "videoId": "test_video_123"},
    },
    "contentDetails": {"videoId": "test_video_123", "note": ""},
}


def create_mock_service():
    service = MagicMock()

    channels_list = MagicMock()
    channels_list.execute.return_value = {"items": [MOCK_CHANNEL]}
    service.channels.return_value.list.return_value = channels_list

    playlist_list = MagicMock()
    playlist_list.execute.return_value = {
        "items": [MOCK_PLAYLIST_ITEM],
        "nextPageToken": None,
        "pageInfo": {"totalResults": 1},
    }
    service.playlistItems.return_value.list.return_value = playlist_list

    videos_list = MagicMock()
    videos_list.execute.return_value = {"items": [MOCK_VIDEO]}
    service.videos.return_value.list.return_value = videos_list

    videos_update = MagicMock()
    videos_update.execute.return_value = MOCK_VIDEO
    service.videos.return_value.update.return_value = videos_update

    captions_list = MagicMock()
    captions_list.execute.return_value = {"items": [MOCK_CAPTION_STANDARD, MOCK_CAPTION_ASR]}
    service.captions.return_value.list.return_value = captions_list

    captions_download = MagicMock()
    captions_download.execute.return_value = MOCK_SRT
    service.captions.return_value.download.return_value = captions_download

    comments_list = MagicMock()
    comments_list.execute.return_value = {
        "items": [MOCK_COMMENT, MOCK_NEGATIVE_COMMENT],
        "nextPageToken": None,
    }
    service.commentThreads.return_value.list.return_value = comments_list

    comments_insert = MagicMock()
    comments_insert.execute.return_value = {
        "id": "UgwReply789",
        "snippet": {"parentId": MOCK_COMMENT["id"], "textOriginal": "Thanks for watching!"},
    }
    service.comments.return_value.insert.return_value = comments_insert

    search_list = MagicMock()
    search_list.execute.return_value = {
        "items": [{"id": {"videoId": MOCK_VIDEO["id"]}}],
    }
    service.search.return_value.list.return_value = search_list

    playlists_list = MagicMock()
    playlists_list.execute.return_value = {
        "items": [MOCK_PLAYLIST],
        "nextPageToken": None,
        "pageInfo": {"totalResults": 1},
    }
    service.playlists.return_value.list.return_value = playlists_list

    playlists_insert = MagicMock()
    playlists_insert.execute.return_value = MOCK_PLAYLIST
    service.playlists.return_value.insert.return_value = playlists_insert

    playlists_update = MagicMock()
    playlists_update.execute.return_value = MOCK_PLAYLIST
    service.playlists.return_value.update.return_value = playlists_update

    playlists_delete = MagicMock()
    playlists_delete.execute.return_value = ""
    service.playlists.return_value.delete.return_value = playlists_delete

    playlist_items_insert = MagicMock()
    playlist_items_insert.execute.return_value = MOCK_PLAYLIST_ITEM_FULL
    service.playlistItems.return_value.insert.return_value = playlist_items_insert

    playlist_items_update = MagicMock()
    playlist_items_update.execute.return_value = MOCK_PLAYLIST_ITEM_FULL
    service.playlistItems.return_value.update.return_value = playlist_items_update

    playlist_items_delete = MagicMock()
    playlist_items_delete.execute.return_value = ""
    service.playlistItems.return_value.delete.return_value = playlist_items_delete

    return service


@pytest.fixture
def mock_service():
    return create_mock_service()


@pytest.fixture(autouse=True)
def _clear_playlists_caches():
    _playlists_module._uploads_id_cache.clear()
    yield
    _playlists_module._uploads_id_cache.clear()


@pytest.fixture
def mock_auth(mock_service):
    mock_creds = MagicMock()
    with (
        patch("ytstudio.api.get_credentials", return_value=mock_creds),
        patch("ytstudio.api.build", return_value=mock_service),
    ):
        yield mock_service


@pytest.fixture
def mock_credentials():
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
