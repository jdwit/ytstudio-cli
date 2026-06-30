import json
from unittest.mock import MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner

from ytstudio.commands.analytics import (
    _align_date_range,
    _fetch_snippet_titles,
    _resolve_query_dimension_titles,
)
from ytstudio.main import app
from ytstudio.ui import format_number, set_raw_output

runner = CliRunner()

MOCK_QUERY_RESPONSE = {
    "columnHeaders": [
        {"name": "day", "columnType": "DIMENSION", "dataType": "STRING"},
        {"name": "views", "columnType": "METRIC", "dataType": "INTEGER"},
        {"name": "likes", "columnType": "METRIC", "dataType": "INTEGER"},
    ],
    "rows": [
        ["2026-01-01", 1500, 45],
        ["2026-01-02", 2300, 78],
        ["2026-01-03", 1800, 52],
    ],
}


class TestFormatNumber:
    def test_human_by_default(self):
        assert format_number(999) == "999"
        assert format_number(1500) == "1.5K"
        assert format_number(2500000) == "2.5M"

    def test_raw_mode(self):
        set_raw_output(True)
        assert format_number(999) == "999"
        assert format_number(1500) == "1500"
        assert format_number(2500000) == "2500000"
        set_raw_output(False)


class TestAnalyticsCommands:
    def _mock_overview_services(self):
        data_service = MagicMock()
        analytics_service = MagicMock()
        data_service.channels.return_value.list.return_value.execute.return_value = {
            "items": [{"id": "UC_test"}]
        }
        analytics_service.reports.return_value.query.return_value.execute.return_value = {
            "columnHeaders": [
                {"name": "views"},
                {"name": "estimatedMinutesWatched"},
                {"name": "averageViewDuration"},
                {"name": "subscribersGained"},
                {"name": "subscribersLost"},
                {"name": "likes"},
                {"name": "comments"},
            ],
            "rows": [[12345, 6000, 180, 42, 3, 789, 25]],
        }
        return data_service, analytics_service

    def test_overview_table(self):
        data_svc, analytics_svc = self._mock_overview_services()
        with (
            patch("ytstudio.commands.analytics.get_data_service", return_value=data_svc),
            patch("ytstudio.commands.analytics.get_analytics_service", return_value=analytics_svc),
        ):
            result = runner.invoke(app, ["analytics", "overview"])
            assert result.exit_code == 0
            assert "Channel Analytics" in result.output
            assert "12.3K" in result.output or "12345" in result.output
            assert "100 hours" in result.output

    def test_overview_json(self):
        data_svc, analytics_svc = self._mock_overview_services()
        with (
            patch("ytstudio.commands.analytics.get_data_service", return_value=data_svc),
            patch("ytstudio.commands.analytics.get_analytics_service", return_value=analytics_svc),
        ):
            result = runner.invoke(app, ["analytics", "overview", "-o", "json"])
            assert result.exit_code == 0
            payload = json.loads(result.output)
            assert payload["days"] == 28
            assert payload["analytics"]["views"] == 12345
            assert payload["analytics"]["likes"] == 789

    def test_overview_no_data(self):
        data_svc, analytics_svc = self._mock_overview_services()
        analytics_svc.reports.return_value.query.return_value.execute.return_value = {
            "columnHeaders": [{"name": "views"}],
            "rows": [],
        }
        with (
            patch("ytstudio.commands.analytics.get_data_service", return_value=data_svc),
            patch("ytstudio.commands.analytics.get_analytics_service", return_value=analytics_svc),
        ):
            result = runner.invoke(app, ["analytics", "overview"])
            assert result.exit_code == 0
            assert "No analytics data" in result.output

    @staticmethod
    def _overview_response(row):
        return {
            "columnHeaders": [
                {"name": "views"},
                {"name": "estimatedMinutesWatched"},
                {"name": "averageViewDuration"},
                {"name": "subscribersGained"},
                {"name": "subscribersLost"},
                {"name": "likes"},
                {"name": "comments"},
            ],
            "rows": [row],
        }

    def _two_window_services(self, current_row, previous_row):
        data_service = MagicMock()
        analytics_service = MagicMock()
        data_service.channels.return_value.list.return_value.execute.return_value = {
            "items": [{"id": "UC_test"}]
        }
        analytics_service.reports.return_value.query.return_value.execute.side_effect = [
            self._overview_response(current_row),
            self._overview_response(previous_row),
        ]
        return data_service, analytics_service

    def test_overview_compare_deltas_table(self):
        # views 12000 vs 10000 -> +20%, avg duration 180 vs 200 -> -10%
        data_svc, analytics_svc = self._two_window_services(
            [12000, 6000, 180, 42, 3, 770, 25],
            [10000, 6000, 200, 42, 3, 700, 25],
        )
        with (
            patch("ytstudio.commands.analytics.get_data_service", return_value=data_svc),
            patch("ytstudio.commands.analytics.get_analytics_service", return_value=analytics_svc),
        ):
            result = runner.invoke(app, ["analytics", "overview"])
            assert result.exit_code == 0
            assert "+20%" in result.output
            assert "-10%" in result.output

    def test_overview_compare_json(self):
        data_svc, analytics_svc = self._two_window_services(
            [12000, 6000, 180, 42, 3, 770, 25],
            [10000, 6000, 200, 42, 3, 700, 25],
        )
        with (
            patch("ytstudio.commands.analytics.get_data_service", return_value=data_svc),
            patch("ytstudio.commands.analytics.get_analytics_service", return_value=analytics_svc),
        ):
            result = runner.invoke(app, ["analytics", "overview", "-o", "json"])
            assert result.exit_code == 0
            payload = json.loads(result.output)
            assert payload["previous"]["views"] == 10000
            assert payload["pct_change"]["views"] == 20.0
            assert payload["pct_change"]["averageViewDuration"] == -10.0
            assert payload["pct_change"]["likes"] == 10.0

    def test_overview_compare_windows_do_not_overlap(self):
        # the previous window must end before the current window starts
        data_svc, analytics_svc = self._two_window_services(
            [12000, 6000, 180, 42, 3, 770, 25],
            [10000, 6000, 200, 42, 3, 700, 25],
        )
        with (
            patch("ytstudio.commands.analytics.get_data_service", return_value=data_svc),
            patch("ytstudio.commands.analytics.get_analytics_service", return_value=analytics_svc),
        ):
            result = runner.invoke(app, ["analytics", "overview", "--days", "7"])
            assert result.exit_code == 0

        calls = analytics_svc.reports.return_value.query.call_args_list
        current_start = calls[0].kwargs["startDate"]
        previous_end = calls[1].kwargs["endDate"]
        assert previous_end < current_start

    def test_overview_no_compare(self):
        data_svc, analytics_svc = self._mock_overview_services()
        with (
            patch("ytstudio.commands.analytics.get_data_service", return_value=data_svc),
            patch("ytstudio.commands.analytics.get_analytics_service", return_value=analytics_svc),
        ):
            result = runner.invoke(app, ["analytics", "overview", "--no-compare", "-o", "json"])
            assert result.exit_code == 0
            payload = json.loads(result.output)
            assert payload["previous"] is None
            assert payload["pct_change"] is None
            # only the current window is queried
            assert analytics_svc.reports.return_value.query.return_value.execute.call_count == 1

    def test_overview_compare_zero_previous(self):
        # previous window has no data -> guard against divide-by-zero
        data_svc, analytics_svc = self._two_window_services(
            [500, 6000, 180, 42, 3, 789, 25],
            [0, 0, 0, 0, 0, 0, 0],
        )
        with (
            patch("ytstudio.commands.analytics.get_data_service", return_value=data_svc),
            patch("ytstudio.commands.analytics.get_analytics_service", return_value=analytics_svc),
        ):
            result = runner.invoke(app, ["analytics", "overview", "-o", "json"])
            assert result.exit_code == 0
            payload = json.loads(result.output)
            assert payload["pct_change"]["views"] is None

    def test_video_not_found(self, mock_auth):
        mock_auth.videos.return_value.list.return_value.execute.return_value = {"items": []}
        with (
            patch("ytstudio.commands.analytics.get_data_service", return_value=mock_auth),
            patch("ytstudio.commands.analytics.get_analytics_service", return_value=mock_auth),
        ):
            result = runner.invoke(app, ["analytics", "video", "nonexistent"])
            assert result.exit_code == 1

    def test_not_authenticated(self):
        with patch(
            "ytstudio.commands.analytics.get_data_service",
            side_effect=typer.Exit(1),
        ):
            result = runner.invoke(app, ["analytics", "overview"])
            assert result.exit_code == 1


class TestQueryCommand:
    def _mock_services(self):
        data_service = MagicMock()
        analytics_service = MagicMock()

        # channel id lookup
        data_service.channels.return_value.list.return_value.execute.return_value = {
            "items": [{"id": "UC_test"}]
        }

        # query response
        analytics_service.reports.return_value.query.return_value.execute.return_value = (
            MOCK_QUERY_RESPONSE
        )

        return data_service, analytics_service

    def test_query_table_output(self):
        data_svc, analytics_svc = self._mock_services()
        with (
            patch("ytstudio.commands.analytics.get_data_service", return_value=data_svc),
            patch("ytstudio.commands.analytics.get_analytics_service", return_value=analytics_svc),
        ):
            result = runner.invoke(
                app,
                ["analytics", "query", "-m", "views,likes", "-d", "day", "--days", "3"],
            )
            assert result.exit_code == 0
            assert "2026-01-01" in result.output

    def test_query_json_output(self):
        data_svc, analytics_svc = self._mock_services()
        with (
            patch("ytstudio.commands.analytics.get_data_service", return_value=data_svc),
            patch("ytstudio.commands.analytics.get_analytics_service", return_value=analytics_svc),
        ):
            result = runner.invoke(
                app,
                ["analytics", "query", "-m", "views,likes", "-d", "day", "-o", "json"],
            )
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert len(data) == 3
            assert data[0]["day"] == "2026-01-01"
            assert data[0]["views"] == 1500

    def test_query_csv_output(self):
        data_svc, analytics_svc = self._mock_services()
        with (
            patch("ytstudio.commands.analytics.get_data_service", return_value=data_svc),
            patch("ytstudio.commands.analytics.get_analytics_service", return_value=analytics_svc),
        ):
            result = runner.invoke(
                app,
                ["analytics", "query", "-m", "views,likes", "-d", "day", "-o", "csv"],
            )
            assert result.exit_code == 0
            lines = result.output.strip().split("\n")
            assert lines[0] == "day,views,likes"
            assert "2026-01-01" in lines[1]

    def test_query_resolve_video_titles_json(self):
        data_svc, analytics_svc = self._mock_services()
        analytics_svc.reports.return_value.query.return_value.execute.return_value = {
            "columnHeaders": [
                {"name": "video", "columnType": "DIMENSION", "dataType": "STRING"},
                {"name": "views", "columnType": "METRIC", "dataType": "INTEGER"},
            ],
            "rows": [["vid1", 100], ["vid2", 50]],
        }
        data_svc.videos.return_value.list.return_value.execute.return_value = {
            "items": [
                {"id": "vid1", "snippet": {"title": "First video"}},
                {"id": "vid2", "snippet": {"title": "Second video"}},
            ]
        }
        with (
            patch("ytstudio.commands.analytics.get_data_service", return_value=data_svc),
            patch("ytstudio.commands.analytics.get_analytics_service", return_value=analytics_svc),
        ):
            result = runner.invoke(
                app,
                [
                    "analytics",
                    "query",
                    "-m",
                    "views",
                    "-d",
                    "video",
                    "--sort",
                    "-views",
                    "-n",
                    "2",
                    "--resolve",
                    "-o",
                    "json",
                ],
            )
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data[0] == {"video": "vid1", "videoTitle": "First video", "views": 100}
            data_svc.videos.return_value.list.assert_called_once()
            assert data_svc.videos.return_value.list.call_args.kwargs["id"] == "vid1,vid2"

    def test_query_resolve_playlist_titles_csv(self):
        data_svc, analytics_svc = self._mock_services()
        analytics_svc.reports.return_value.query.return_value.execute.return_value = {
            "columnHeaders": [
                {"name": "playlist", "columnType": "DIMENSION", "dataType": "STRING"},
                {"name": "views", "columnType": "METRIC", "dataType": "INTEGER"},
            ],
            "rows": [["pl1", 100]],
        }
        data_svc.playlists.return_value.list.return_value.execute.return_value = {
            "items": [{"id": "pl1", "snippet": {"title": "My playlist"}}]
        }
        with (
            patch("ytstudio.commands.analytics.get_data_service", return_value=data_svc),
            patch("ytstudio.commands.analytics.get_analytics_service", return_value=analytics_svc),
        ):
            result = runner.invoke(
                app,
                ["analytics", "query", "-m", "views", "-d", "playlist", "--resolve", "-o", "csv"],
            )
            assert result.exit_code == 0
            assert result.output.strip().split("\n") == [
                "playlist,playlistTitle,views",
                "pl1,My playlist,100",
            ]

    def test_query_does_not_resolve_titles_without_flag(self):
        data_svc, analytics_svc = self._mock_services()
        analytics_svc.reports.return_value.query.return_value.execute.return_value = {
            "columnHeaders": [
                {"name": "video", "columnType": "DIMENSION", "dataType": "STRING"},
                {"name": "views", "columnType": "METRIC", "dataType": "INTEGER"},
            ],
            "rows": [["vid1", 100]],
        }
        with (
            patch("ytstudio.commands.analytics.get_data_service", return_value=data_svc),
            patch("ytstudio.commands.analytics.get_analytics_service", return_value=analytics_svc),
        ):
            result = runner.invoke(
                app,
                [
                    "analytics",
                    "query",
                    "-m",
                    "views",
                    "-d",
                    "video",
                    "--sort",
                    "-views",
                    "-n",
                    "1",
                    "-o",
                    "json",
                ],
            )
            assert result.exit_code == 0
            assert json.loads(result.output) == [{"video": "vid1", "views": 100}]
            data_svc.videos.return_value.list.assert_not_called()

    def test_fetch_snippet_titles_empty_ids_skips_api(self):
        data_svc = MagicMock()
        assert _fetch_snippet_titles(data_svc, "video", []) == {}
        data_svc.videos.assert_not_called()

    def test_fetch_snippet_titles_rejects_unknown_resource(self):
        with pytest.raises(ValueError, match="Unsupported resource"):
            _fetch_snippet_titles(MagicMock(), "channel", ["UC_test"])

    def test_fetch_snippet_titles_batches_large_video_lists(self):
        data_svc = MagicMock()
        responses = [
            {"items": [{"id": "v0", "snippet": {"title": "Video 0"}}]},
            {"items": [{"id": "v50", "snippet": {"title": "Video 50"}}]},
        ]
        data_svc.videos.return_value.list.return_value.execute.side_effect = responses

        titles = _fetch_snippet_titles(data_svc, "video", [f"v{i}" for i in range(51)])

        assert titles == {"v0": "Video 0", "v50": "Video 50"}
        calls = data_svc.videos.return_value.list.call_args_list
        assert len(calls) == 2
        assert calls[0].kwargs["id"] == ",".join(f"v{i}" for i in range(50))
        assert calls[1].kwargs["id"] == "v50"

    def test_resolve_query_dimension_titles_no_rows_returns_original_response(self):
        response = {
            "columnHeaders": [{"name": "video", "columnType": "DIMENSION"}],
            "rows": [],
        }
        assert _resolve_query_dimension_titles(MagicMock(), response) is response

    def test_resolve_query_dimension_titles_no_resolvable_dimension_returns_original_response(self):
        response = {
            "columnHeaders": [{"name": "country", "columnType": "DIMENSION"}],
            "rows": [["NL"]],
        }
        assert _resolve_query_dimension_titles(MagicMock(), response) is response

    def test_resolve_query_dimension_titles_multiple_dimensions_preserves_order(self):
        data_svc = MagicMock()
        data_svc.videos.return_value.list.return_value.execute.return_value = {
            "items": [{"id": "vid1", "snippet": {"title": "Video one"}}]
        }
        data_svc.playlists.return_value.list.return_value.execute.return_value = {
            "items": [{"id": "pl1", "snippet": {"title": "Playlist one"}}]
        }
        response = {
            "columnHeaders": [
                {"name": "playlist", "columnType": "DIMENSION"},
                {"name": "video", "columnType": "DIMENSION"},
                {"name": "views", "columnType": "METRIC"},
            ],
            "rows": [["pl1", "vid1", 10]],
        }

        resolved = _resolve_query_dimension_titles(data_svc, response)

        assert [h["name"] for h in resolved["columnHeaders"]] == [
            "playlist",
            "playlistTitle",
            "video",
            "videoTitle",
            "views",
        ]
        assert resolved["rows"] == [["pl1", "Playlist one", "vid1", "Video one", 10]]

    def test_query_with_filter(self):
        data_svc, analytics_svc = self._mock_services()
        with (
            patch("ytstudio.commands.analytics.get_data_service", return_value=data_svc),
            patch("ytstudio.commands.analytics.get_analytics_service", return_value=analytics_svc),
        ):
            result = runner.invoke(
                app,
                [
                    "analytics",
                    "query",
                    "-m",
                    "views",
                    "-f",
                    "video==abc123",
                    "-f",
                    "country==NL",
                ],
            )
            assert result.exit_code == 0
            # verify filters were passed
            call_kwargs = analytics_svc.reports.return_value.query.call_args
            assert "video==abc123;country==NL" in str(call_kwargs)

    def test_query_invalid_metric(self):
        result = runner.invoke(
            app,
            ["analytics", "query", "-m", "veiws"],
        )
        assert result.exit_code == 1
        assert "Unknown metric" in result.output
        assert "views" in result.output  # suggestion

    def test_query_invalid_dimension(self):
        result = runner.invoke(
            app,
            ["analytics", "query", "-m", "views", "-d", "contry"],
        )
        assert result.exit_code == 1
        assert "Unknown dimension" in result.output
        assert "country" in result.output  # suggestion

    def test_query_invalid_filter_format(self):
        data_svc, analytics_svc = self._mock_services()
        with (
            patch("ytstudio.commands.analytics.get_data_service", return_value=data_svc),
            patch("ytstudio.commands.analytics.get_analytics_service", return_value=analytics_svc),
        ):
            result = runner.invoke(
                app,
                ["analytics", "query", "-m", "views", "-f", "video=abc"],
            )
            assert result.exit_code == 1
            assert "Invalid filter" in result.output


class TestMetricsCommand:
    def test_list_all(self):
        result = runner.invoke(app, ["analytics", "metrics"])
        assert result.exit_code == 0
        assert "views" in result.output
        assert "likes" in result.output

    def test_list_by_group(self):
        result = runner.invoke(app, ["analytics", "metrics", "--group", "engagement"])
        assert result.exit_code == 0
        assert "likes" in result.output
        assert "shares" in result.output

    def test_list_invalid_group(self):
        result = runner.invoke(app, ["analytics", "metrics", "--group", "nonexistent"])
        assert result.exit_code == 1
        assert "Unknown group" in result.output

    def test_json_output(self):
        result = runner.invoke(app, ["analytics", "metrics", "-o", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert any(m["name"] == "views" for m in data)


class TestDimensionsCommand:
    def test_list_all(self):
        result = runner.invoke(app, ["analytics", "dimensions"])
        assert result.exit_code == 0
        assert "country" in result.output
        assert "day" in result.output

    def test_list_by_group(self):
        result = runner.invoke(app, ["analytics", "dimensions", "--group", "geographic"])
        assert result.exit_code == 0
        assert "country" in result.output

    def test_detail_view(self):
        result = runner.invoke(app, ["analytics", "dimensions", "country"])
        assert result.exit_code == 0
        assert "ISO 3166-1" in result.output

    def test_filter_only_shown(self):
        result = runner.invoke(app, ["analytics", "dimensions", "continent"])
        assert result.exit_code == 0
        assert "filter only" in result.output

    def test_json_output(self):
        result = runner.invoke(app, ["analytics", "dimensions", "-o", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert any(d["name"] == "country" for d in data)


class TestAlignDateRange:
    def test_month_snaps_start_down(self):
        assert _align_date_range(["month"], "2026-04-17", "2026-06-01") == (
            "2026-04-01",
            "2026-06-01",
        )

    def test_month_snaps_end_down(self):
        assert _align_date_range(["month"], "2026-04-01", "2026-06-23") == (
            "2026-04-01",
            "2026-06-01",
        )

    def test_month_days_derived_non_aligned(self):
        # --days 365 from a mid-month "today" yields two arbitrary days.
        assert _align_date_range(["month"], "2025-06-18", "2026-06-18") == (
            "2025-06-01",
            "2026-06-01",
        )

    def test_month_already_aligned_unchanged(self):
        assert _align_date_range(["month"], "2026-04-01", "2026-06-01") == (
            "2026-04-01",
            "2026-06-01",
        )

    def test_month_same_month_range(self):
        assert _align_date_range(["month"], "2026-04-10", "2026-04-25") == (
            "2026-04-01",
            "2026-04-01",
        )

    def test_day_untouched(self):
        assert _align_date_range(["day"], "2026-04-17", "2026-06-23") == (
            "2026-04-17",
            "2026-06-23",
        )

    def test_no_dimension_untouched(self):
        assert _align_date_range([], "2026-04-17", "2026-06-23") == (
            "2026-04-17",
            "2026-06-23",
        )

    def test_week_snaps_back_to_sunday(self):
        # 2026-06-18 is a Thursday; preceding Sunday is 2026-06-14.
        assert _align_date_range(["week"], "2026-06-18", "2026-06-18") == (
            "2026-06-14",
            "2026-06-14",
        )

    def test_week_sunday_unchanged(self):
        # 2026-06-14 is a Sunday; stays put.
        assert _align_date_range(["week"], "2026-06-14", "2026-06-21") == (
            "2026-06-14",
            "2026-06-21",
        )
