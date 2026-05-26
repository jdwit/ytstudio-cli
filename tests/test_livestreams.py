import json
from unittest.mock import MagicMock, patch

import pytest
from googleapiclient.errors import HttpError
from typer.testing import CliRunner

from ytstudio.commands.livestreams import _redact_key, app

runner = CliRunner()


def _broadcast_item(
    *,
    broadcast_id: str = "abc123",
    title: str = "My Stream",
    lifecycle: str = "ready",
    privacy: str = "public",
    scheduled_start: str = "2026-06-01T19:00:00Z",
    scheduled_end: str = "2026-06-01T20:00:00Z",
    bound_stream_id: str = "",
    made_for_kids: bool = False,
    content_overrides: dict | None = None,
) -> dict:
    content = {
        "boundStreamId": bound_stream_id,
        "enableAutoStart": True,
        "enableAutoStop": False,
        "enableDvr": True,
        "enableEmbed": True,
        "recordFromStart": True,
        "closedCaptionsType": "closedCaptionsDisabled",
        "latencyPreference": "normal",
        "projection": "rectangular",
    }
    if content_overrides:
        content.update(content_overrides)
    return {
        "id": broadcast_id,
        "snippet": {
            "title": title,
            "description": "Demo",
            "scheduledStartTime": scheduled_start,
            "scheduledEndTime": scheduled_end,
        },
        "status": {
            "lifeCycleStatus": lifecycle,
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": made_for_kids,
        },
        "contentDetails": content,
    }


def _stream_item(stream_id: str = "s1", stream_name: str = "key-FULL-1234-ZXCV") -> dict:
    return {
        "id": stream_id,
        "snippet": {"title": "Stream"},
        "cdn": {
            "format": "1080p",
            "frameRate": "30fps",
            "resolution": "1080p",
            "ingestionInfo": {
                "ingestionAddress": "rtmp://primary",
                "backupIngestionAddress": "rtmp://backup",
                "rtmpsIngestionAddress": "rtmps://secure",
                "streamName": stream_name,
            },
        },
        "status": {"streamStatus": "active"},
    }


def _service(items=None, *, stream_items=None, transition_response=None, insert_response=None):
    service = MagicMock()

    list_request = MagicMock()
    list_request.execute.return_value = {"items": items or []}
    service.liveBroadcasts.return_value.list.return_value = list_request

    transition_request = MagicMock()
    transition_request.execute.return_value = transition_response or {
        "id": "abc123",
        "status": {"lifeCycleStatus": "live"},
    }
    service.liveBroadcasts.return_value.transition.return_value = transition_request

    insert_request = MagicMock()
    insert_request.execute.return_value = insert_response or {"id": "new-id"}
    service.liveBroadcasts.return_value.insert.return_value = insert_request

    update_request = MagicMock()
    update_request.execute.return_value = {}
    service.liveBroadcasts.return_value.update.return_value = update_request

    stream_list_request = MagicMock()
    stream_list_request.execute.return_value = {"items": stream_items or []}
    service.liveStreams.return_value.list.return_value = stream_list_request

    return service


def _http_error(reason: str, status: int = 400) -> HttpError:
    resp = MagicMock()
    resp.status = status
    err = HttpError(resp, b"{}")
    err.error_details = [{"reason": reason}]
    return err


# -------- redact helper --------


class TestRedactKey:
    @pytest.mark.parametrize(
        ("key", "expected"),
        [
            ("", ""),
            ("abcd", "****"),
            ("abcdef", "**cdef"),
            ("super-long-stream-key-XYZ9", "**********************XYZ9"),
        ],
    )
    def test_redact(self, key, expected):
        assert _redact_key(key) == expected


# -------- list --------


class TestList:
    def test_table_output(self):
        service = _service([_broadcast_item()])
        with patch("ytstudio.commands.livestreams.get_data_service", return_value=service):
            result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        assert "abc123" in result.stdout
        assert "My Stream" in result.stdout

    def test_json_output_includes_fields(self):
        service = _service([_broadcast_item(bound_stream_id="s1")])
        with patch("ytstudio.commands.livestreams.get_data_service", return_value=service):
            result = runner.invoke(app, ["list", "--output", "json"])
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["broadcasts"][0]["id"] == "abc123"
        assert payload["broadcasts"][0]["bound_stream_id"] == "s1"

    def test_empty_message(self):
        service = _service([])
        with patch("ytstudio.commands.livestreams.get_data_service", return_value=service):
            result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        assert "No broadcasts" in result.stdout

    def test_status_filter_passed_to_api(self):
        service = _service([])
        with patch("ytstudio.commands.livestreams.get_data_service", return_value=service):
            runner.invoke(app, ["list", "--status", "active"])
        service.liveBroadcasts.return_value.list.assert_called_with(
            part="snippet,status,contentDetails",
            broadcastStatus="active",
            maxResults=20,
            pageToken=None,
        )

    def test_limit_clamped_by_typer(self):
        service = _service([])
        with patch("ytstudio.commands.livestreams.get_data_service", return_value=service):
            result = runner.invoke(app, ["list", "--limit", "999"])
        # Typer's min/max=50 should reject this.
        assert result.exit_code != 0


# -------- show --------


class TestShow:
    def test_table(self):
        service = _service([_broadcast_item(bound_stream_id="s1")])
        with patch("ytstudio.commands.livestreams.get_data_service", return_value=service):
            result = runner.invoke(app, ["show", "abc123"])
        assert result.exit_code == 0
        assert "My Stream" in result.stdout
        assert "s1" in result.stdout

    def test_not_found(self):
        service = _service([])
        with patch("ytstudio.commands.livestreams.get_data_service", return_value=service):
            result = runner.invoke(app, ["show", "missing"])
        assert result.exit_code == 1
        assert "not found" in result.stdout.lower()

    def test_ingest_redacted_by_default(self):
        service = _service(
            [_broadcast_item(bound_stream_id="s1")],
            stream_items=[_stream_item("s1", "secret-key-ABCDEFGH")],
        )
        with patch("ytstudio.commands.livestreams.get_data_service", return_value=service):
            result = runner.invoke(app, ["show", "abc123", "--ingest"])
        assert result.exit_code == 0
        assert "secret-key-ABCDEFGH" not in result.stdout
        assert "EFGH" in result.stdout  # last four shown
        assert "rtmp://primary" in result.stdout

    def test_show_key_reveals(self):
        service = _service(
            [_broadcast_item(bound_stream_id="s1")],
            stream_items=[_stream_item("s1", "secret-key-ABCDEFGH")],
        )
        with patch("ytstudio.commands.livestreams.get_data_service", return_value=service):
            result = runner.invoke(app, ["show", "abc123", "--show-key"])
        assert result.exit_code == 0
        assert "secret-key-ABCDEFGH" in result.stdout

    def test_ingest_without_bound_stream(self):
        service = _service([_broadcast_item(bound_stream_id="")])
        with patch("ytstudio.commands.livestreams.get_data_service", return_value=service):
            result = runner.invoke(app, ["show", "abc123", "--ingest"])
        assert result.exit_code == 0
        assert "No stream bound" in result.stdout
        service.liveStreams.return_value.list.assert_not_called()

    def test_json_output_redacted(self):
        service = _service(
            [_broadcast_item(bound_stream_id="s1")],
            stream_items=[_stream_item("s1", "secret-key-ABCDEFGH")],
        )
        with patch("ytstudio.commands.livestreams.get_data_service", return_value=service):
            result = runner.invoke(app, ["show", "abc123", "--ingest", "--output", "json"])
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert "secret-key-ABCDEFGH" not in result.stdout
        assert payload["ingest"]["stream_name"].endswith("EFGH")


# -------- start / stop --------


class TestStartStop:
    def test_start_default_goes_live(self):
        service = _service()
        with patch("ytstudio.commands.livestreams.get_data_service", return_value=service):
            result = runner.invoke(app, ["start", "abc123"])
        assert result.exit_code == 0
        service.liveBroadcasts.return_value.transition.assert_called_with(
            broadcastStatus="live",
            id="abc123",
            part="id,snippet,status",
        )

    def test_start_to_testing(self):
        service = _service(transition_response={"status": {"lifeCycleStatus": "testing"}})
        with patch("ytstudio.commands.livestreams.get_data_service", return_value=service):
            result = runner.invoke(app, ["start", "abc123", "--to", "testing"])
        assert result.exit_code == 0
        assert "testing" in result.stdout
        service.liveBroadcasts.return_value.transition.assert_called_with(
            broadcastStatus="testing",
            id="abc123",
            part="id,snippet,status",
        )

    def test_stop_transitions_to_complete(self):
        service = _service(transition_response={"status": {"lifeCycleStatus": "complete"}})
        with patch("ytstudio.commands.livestreams.get_data_service", return_value=service):
            result = runner.invoke(app, ["stop", "abc123"])
        assert result.exit_code == 0
        service.liveBroadcasts.return_value.transition.assert_called_with(
            broadcastStatus="complete",
            id="abc123",
            part="id,snippet,status",
        )

    def test_known_error_reasons_map_to_friendly_message(self):
        service = _service()
        service.liveBroadcasts.return_value.transition.return_value.execute.side_effect = (
            _http_error("liveStreamingNotEnabled")
        )
        with patch("ytstudio.commands.livestreams.get_data_service", return_value=service):
            result = runner.invoke(app, ["start", "abc123"])
        assert result.exit_code == 1
        assert "not enabled" in result.stdout.lower()


# -------- schedule --------


class TestSchedule:
    def test_dry_run_does_not_call_insert(self):
        service = _service()
        with patch("ytstudio.commands.livestreams.get_data_service", return_value=service):
            result = runner.invoke(
                app,
                [
                    "schedule",
                    "--title",
                    "Hello",
                    "--scheduled-start",
                    "2026-06-01T19:00:00+02:00",
                ],
            )
        assert result.exit_code == 0
        assert "Preview" in result.stdout
        service.liveBroadcasts.return_value.insert.assert_not_called()

    def test_execute_creates_broadcast(self):
        service = _service(insert_response={"id": "freshly-made"})
        with patch("ytstudio.commands.livestreams.get_data_service", return_value=service):
            result = runner.invoke(
                app,
                [
                    "schedule",
                    "--title",
                    "Hello",
                    "--scheduled-start",
                    "2026-06-01T19:00:00+02:00",
                    "--scheduled-end",
                    "2026-06-01T20:00:00+02:00",
                    "--privacy",
                    "unlisted",
                    "--made-for-kids",
                    "--execute",
                ],
            )
        assert result.exit_code == 0
        assert "freshly-made" in result.stdout
        call_kwargs = service.liveBroadcasts.return_value.insert.call_args.kwargs
        body = call_kwargs["body"]
        assert body["snippet"]["title"] == "Hello"
        assert body["snippet"]["scheduledStartTime"] == "2026-06-01T19:00:00+02:00"
        assert body["snippet"]["scheduledEndTime"] == "2026-06-01T20:00:00+02:00"
        assert body["status"]["privacyStatus"] == "unlisted"
        assert body["status"]["selfDeclaredMadeForKids"] is True


# -------- update --------


class TestUpdate:
    def test_no_change_flags_exits(self):
        service = _service([_broadcast_item()])
        with patch("ytstudio.commands.livestreams.get_data_service", return_value=service):
            result = runner.invoke(app, ["update", "abc123"])
        assert result.exit_code == 1
        service.liveBroadcasts.return_value.update.assert_not_called()

    def test_not_found(self):
        service = _service([])
        with patch("ytstudio.commands.livestreams.get_data_service", return_value=service):
            result = runner.invoke(app, ["update", "missing", "--title", "x"])
        assert result.exit_code == 1
        assert "not found" in result.stdout.lower()

    def test_dry_run_shows_diff_only(self):
        service = _service([_broadcast_item()])
        with patch("ytstudio.commands.livestreams.get_data_service", return_value=service):
            result = runner.invoke(app, ["update", "abc123", "--title", "Renamed"])
        assert result.exit_code == 0
        assert "Renamed" in result.stdout
        service.liveBroadcasts.return_value.update.assert_not_called()

    def test_partial_update_keeps_other_fields(self):
        service = _service(
            [_broadcast_item(bound_stream_id="s1", content_overrides={"enableDvr": True})]
        )
        with patch("ytstudio.commands.livestreams.get_data_service", return_value=service):
            result = runner.invoke(
                app,
                ["update", "abc123", "--no-dvr", "--execute"],
            )
        assert result.exit_code == 0
        update = service.liveBroadcasts.return_value.update
        update.assert_called_once()
        kwargs = update.call_args.kwargs
        assert "contentDetails" in kwargs["part"]
        body = kwargs["body"]
        assert body["contentDetails"]["enableDvr"] is False
        # Other content fields keep their fetched-current values.
        assert body["contentDetails"]["enableAutoStart"] is True
        # Snippet must still have title/start/end to avoid clearing them via PUT.
        assert body["snippet"]["title"] == "My Stream"
        assert body["snippet"]["scheduledStartTime"] == "2026-06-01T19:00:00Z"

    def test_metadata_only_update_skips_content_part(self):
        service = _service([_broadcast_item()])
        with patch("ytstudio.commands.livestreams.get_data_service", return_value=service):
            result = runner.invoke(
                app,
                ["update", "abc123", "--title", "Renamed", "--execute"],
            )
        assert result.exit_code == 0
        kwargs = service.liveBroadcasts.return_value.update.call_args.kwargs
        assert "contentDetails" not in kwargs["part"]
        assert "snippet" in kwargs["part"]
        assert kwargs["body"]["snippet"]["title"] == "Renamed"
