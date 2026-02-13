import functools
import json
import os
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

DEMO_MODE = os.environ.get("YTSTUDIO_DEMO", "").lower() in ("1", "true", "yes")

_DATA_DIR = Path(__file__).parent / "demo_data"


@functools.cache
def _load(name: str) -> dict:
    return json.loads((_DATA_DIR / name).read_text())


class DemoRequest:
    def __init__(self, response: dict, delay: float = 0):
        self._response = response
        self._delay = delay

    def execute(self) -> dict:
        if self._delay:
            time.sleep(self._delay)
        return self._response


class _DemoChannels:
    def list(self, **kwargs):
        return DemoRequest(_load("channel.json"))


class _DemoVideos:
    def list(self, **kwargs):
        id_param = kwargs.get("id", "")
        requested_ids = [i.strip() for i in id_param.split(",") if i.strip()]

        if not requested_ids:
            return DemoRequest(_load("videos.json"))

        matched = [v for v in _load("videos.json")["items"] if v["id"] in requested_ids]
        return DemoRequest({"items": matched})

    def update(self, **kwargs):
        body = kwargs.get("body", {})
        return DemoRequest(body, delay=0.3)


class _DemoPlaylistItems:
    def list(self, **kwargs):
        max_results = kwargs.get("maxResults", 50)
        data = _load("playlist_items.json")
        items = data["items"][:max_results]
        return DemoRequest(
            {
                "items": items,
                "pageInfo": {"totalResults": len(data["items"])},
            }
        )


class _DemoCommentThreads:
    def list(self, **kwargs):
        max_results = kwargs.get("maxResults", 100)
        video_id = kwargs.get("videoId")

        items = _load("comments.json")["items"]
        if video_id:
            items = [
                c
                for c in items
                if c["snippet"]["topLevelComment"]["snippet"].get("videoId") == video_id
            ]

        return DemoRequest({"items": items[:max_results]})


class _DemoComments:
    def setModerationStatus(self, **kwargs):
        return DemoRequest({})


class DemoDataService:
    def channels(self):
        return _DemoChannels()

    def videos(self):
        return _DemoVideos()

    def playlistItems(self):
        return _DemoPlaylistItems()

    def comments(self):
        return _DemoComments()

    def commentThreads(self):
        return _DemoCommentThreads()


class _DemoReports:
    def query(self, **params):
        metrics = [m.strip() for m in params.get("metrics", "").split(",") if m.strip()]
        dimensions = [d.strip() for d in params.get("dimensions", "").split(",") if d.strip()]
        filters = params.get("filters", "")
        sort = params.get("sort", "")
        max_results = params.get("maxResults")

        analytics = _load("analytics_metrics.json")
        video_metrics = {k: v for k, v in analytics.items() if k != "countries"}
        countries = analytics.get("countries", ["US", "IN", "GB", "DE", "BR"])

        headers = _make_column_headers(dimensions, metrics)

        def _metric_vals(base: dict) -> list:
            return [base.get(m, 0) for m in metrics]

        rows = []

        # Single video filter
        filter_video_id = None
        if filters:
            for part in filters.split(";"):
                if part.startswith("video=="):
                    filter_video_id = part.split("==", 1)[1]

        if not dimensions:
            totals = {m: 0 for m in metrics}
            sources = video_metrics
            if filter_video_id and filter_video_id in video_metrics:
                sources = {filter_video_id: video_metrics[filter_video_id]}
            for base in sources.values():
                for m in metrics:
                    totals[m] += base.get(m, 0)
            rows.append([totals[m] for m in metrics])

        elif dimensions == ["day"]:
            today = datetime.now(UTC).date()
            n_days = 7
            for i in range(n_days, 0, -1):
                date_str = (today - timedelta(days=i)).strftime("%Y-%m-%d")
                vid = list(video_metrics.values())[i % len(video_metrics)]
                rows.append([date_str, *_metric_vals(vid)])

        elif dimensions == ["country"]:
            for j, country in enumerate(countries):
                vid = list(video_metrics.values())[j % len(video_metrics)]
                rows.append([country, *_metric_vals(vid)])

        elif "video" in dimensions:
            for vid_id, base in video_metrics.items():
                rows.append([vid_id, *_metric_vals(base)])

        else:
            totals = {m: 0 for m in metrics}
            for base in video_metrics.values():
                for m in metrics:
                    totals[m] += base.get(m, 0)
            dim_vals = ["unknown"] * len(dimensions)
            rows.append([*dim_vals, *[totals[m] for m in metrics]])

        # Apply sort
        if sort and rows and dimensions:
            sort_desc = sort.startswith("-")
            sort_field = sort.lstrip("-")
            all_names = dimensions + metrics
            if sort_field in all_names:
                idx = all_names.index(sort_field)
                rows.sort(key=lambda r: r[idx], reverse=sort_desc)

        if max_results and len(rows) > max_results:
            rows = rows[:max_results]

        return DemoRequest({"columnHeaders": headers, "rows": rows})


def _make_column_headers(dimensions: list[str], metrics: list[str]) -> list[dict]:
    return [{"name": d, "columnType": "DIMENSION", "dataType": "STRING"} for d in dimensions] + [
        {"name": m, "columnType": "METRIC", "dataType": "INTEGER"} for m in metrics
    ]


class DemoAnalyticsService:
    def reports(self):
        return _DemoReports()


def is_demo_mode() -> bool:
    return DEMO_MODE
