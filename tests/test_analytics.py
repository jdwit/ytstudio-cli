import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from ytstudio.main import app
from ytstudio.ui import format_number

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
    def test_formats_correctly(self):
        assert format_number(999) == "999"
        assert format_number(1500) == "1.5K"
        assert format_number(2500000) == "2.5M"


class TestAnalyticsCommands:
    def test_overview(self):
        with patch("ytstudio.commands.analytics.is_demo_mode", return_value=True):
            result = runner.invoke(app, ["analytics", "overview"])
            assert result.exit_code == 0

    def test_video_not_found(self, mock_auth):
        mock_auth.videos.return_value.list.return_value.execute.return_value = {"items": []}
        with patch("ytstudio.commands.analytics.get_services") as mock_get:
            mock_get.return_value = (mock_auth, mock_auth)
            result = runner.invoke(app, ["analytics", "video", "nonexistent"])
            assert result.exit_code == 1

    def test_not_authenticated(self):
        with patch("ytstudio.commands.analytics.get_authenticated_service", return_value=None):
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
        with patch("ytstudio.commands.analytics.get_services") as mock_get:
            mock_get.return_value = (data_svc, analytics_svc)
            result = runner.invoke(
                app,
                ["analytics", "query", "-m", "views,likes", "-d", "day", "--days", "3"],
            )
            assert result.exit_code == 0
            assert "2026-01-01" in result.output

    def test_query_json_output(self):
        data_svc, analytics_svc = self._mock_services()
        with patch("ytstudio.commands.analytics.get_services") as mock_get:
            mock_get.return_value = (data_svc, analytics_svc)
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
        with patch("ytstudio.commands.analytics.get_services") as mock_get:
            mock_get.return_value = (data_svc, analytics_svc)
            result = runner.invoke(
                app,
                ["analytics", "query", "-m", "views,likes", "-d", "day", "-o", "csv"],
            )
            assert result.exit_code == 0
            lines = result.output.strip().split("\n")
            assert lines[0] == "day,views,likes"
            assert "2026-01-01" in lines[1]

    def test_query_with_filter(self):
        data_svc, analytics_svc = self._mock_services()
        with patch("ytstudio.commands.analytics.get_services") as mock_get:
            mock_get.return_value = (data_svc, analytics_svc)
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
        with patch("ytstudio.commands.analytics.get_services") as mock_get:
            mock_get.return_value = (data_svc, analytics_svc)
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

    def test_detail_view(self):
        result = runner.invoke(app, ["analytics", "metrics", "views"])
        assert result.exit_code == 0
        assert "Number of times" in result.output
        assert "core" in result.output

    def test_detail_unknown(self):
        result = runner.invoke(app, ["analytics", "metrics", "veiws"])
        assert result.exit_code == 1
        assert "views" in result.output  # suggestion

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
