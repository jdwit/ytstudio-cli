"""Fake YouTube Data + Analytics services for offline demo mode.

The fake services mimic the small surface of `googleapiclient` resources that
the real ytstudio commands exercise. They are fed by JSON fixtures bundled in
`ytstudio/fixtures/`. No network calls are made.
"""

from __future__ import annotations

import functools
import hashlib
import json
import os
import sys
from importlib import resources
from typing import Any, ClassVar

from rich.console import Console

_DEMO_ENV = "YTSTUDIO_DEMO"
_TRUTHY = {"1", "true", "yes", "on"}


def is_demo_mode() -> bool:
    return os.getenv(_DEMO_ENV, "").lower() in _TRUTHY


def _wants_json_output() -> bool:
    argv = sys.argv[1:]
    for i, arg in enumerate(argv):
        if arg in {"-o", "--output"} and i + 1 < len(argv) and argv[i + 1] == "json":
            return True
        if arg in {"-o=json", "--output=json"}:
            return True
    return False


class _BannerState:
    """Per-process flag for the demo banner. Module-level mutables trip PLW0603."""

    printed = False


def print_demo_banner_once() -> None:
    """Print the demo banner at most once per process, on stderr."""
    if _BannerState.printed or _wants_json_output():
        return
    _BannerState.printed = True
    Console(stderr=True).print("[dim]demo mode: using built-in fake channel (no network)[/dim]")


def _reset_banner_for_tests() -> None:
    _BannerState.printed = False


@functools.cache
def _load_fixture(name: str) -> Any:
    path = resources.files("ytstudio").joinpath("fixtures", name)
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


class _FakeRequest:
    def __init__(self, result: dict):
        self._result = result

    def execute(self) -> dict:
        return self._result


class FakeYouTubeService:
    """Fake `youtube` v3 Data API service."""

    def __init__(self) -> None:
        # In-process edits so search-replace --execute renders coherently.
        self._video_overrides: dict[str, dict] = {}

    def channels(self) -> _FakeChannels:
        return _FakeChannels()

    def playlistItems(self) -> _FakePlaylistItems:
        return _FakePlaylistItems()

    def videos(self) -> _FakeVideos:
        return _FakeVideos(self._video_overrides)

    def videoCategories(self) -> _FakeVideoCategories:
        return _FakeVideoCategories()

    def commentThreads(self) -> _FakeCommentThreads:
        return _FakeCommentThreads()

    def comments(self) -> _FakeComments:
        return _FakeComments()

    def search(self) -> _FakeSearch:
        return _FakeSearch()


class _FakeChannels:
    def list(self, **_kwargs) -> _FakeRequest:
        return _FakeRequest(_load_fixture("channel.json"))


class _FakePlaylistItems:
    def list(self, **_kwargs) -> _FakeRequest:
        return _FakeRequest(_load_fixture("playlist_items.json"))


class _FakeVideos:
    def __init__(self, overrides: dict[str, dict]):
        self._overrides = overrides

    def list(self, **kwargs) -> _FakeRequest:
        videos = _load_fixture("videos.json")["items"]
        wanted_ids = kwargs.get("id")
        if wanted_ids:
            ids = [i.strip() for i in wanted_ids.split(",") if i.strip()]
            by_id = {v["id"]: v for v in videos}
            picked = [by_id[i] for i in ids if i in by_id]
        else:
            picked = list(videos)

        merged = []
        for item in picked:
            override = self._overrides.get(item["id"])
            if override:
                copy = json.loads(json.dumps(item))
                copy["snippet"].update(override.get("snippet", {}))
                merged.append(copy)
            else:
                merged.append(item)
        return _FakeRequest({"items": merged})

    def update(self, **kwargs) -> _FakeRequest:
        body = kwargs.get("body", {})
        vid = body.get("id", "demo_vid_unknown")
        if "snippet" in body:
            self._overrides[vid] = {"snippet": body["snippet"]}
        return _FakeRequest({"id": vid})


class _FakeVideoCategories:
    def list(self, **_kwargs) -> _FakeRequest:
        items = [
            {"id": "22", "snippet": {"title": "People & Blogs", "assignable": True}},
            {"id": "26", "snippet": {"title": "Howto & Style", "assignable": True}},
            {"id": "27", "snippet": {"title": "Education", "assignable": True}},
            {"id": "28", "snippet": {"title": "Science & Technology", "assignable": True}},
        ]
        return _FakeRequest({"items": items})


class _FakeCommentThreads:
    def list(self, **_kwargs) -> _FakeRequest:
        return _FakeRequest(_load_fixture("comments.json"))


class _FakeComments:
    def setModerationStatus(self, **_kwargs) -> _FakeRequest:
        return _FakeRequest({})


class _FakeSearch:
    def list(self, **_kwargs) -> _FakeRequest:
        videos = _load_fixture("videos.json")["items"]
        items = [{"id": {"videoId": v["id"]}} for v in videos]
        return _FakeRequest({"items": items, "nextPageToken": None})


class FakeAnalyticsService:
    """Fake `youtubeAnalytics` v2 service."""

    def reports(self) -> _FakeReports:
        return _FakeReports()


class _FakeReports:
    _OVERVIEW_METRICS: ClassVar[set[str]] = {
        "views",
        "estimatedMinutesWatched",
        "averageViewDuration",
        "subscribersGained",
        "subscribersLost",
        "likes",
        "comments",
    }

    def query(self, **kwargs) -> _FakeRequest:
        metrics = [m.strip() for m in kwargs.get("metrics", "").split(",") if m.strip()]
        if set(metrics) == self._OVERVIEW_METRICS:
            return _FakeRequest(_load_fixture("analytics_overview.json"))
        # Stable-seeded synthetic response for any other metric combo.
        row = [_pseudo_value(m) for m in metrics]
        return _FakeRequest(
            {"columnHeaders": [{"name": m} for m in metrics], "rows": [row] if row else []}
        )


def _pseudo_value(metric: str) -> int:
    digest = hashlib.md5(metric.encode()).hexdigest()
    return int(digest[:8], 16) % 100_000
