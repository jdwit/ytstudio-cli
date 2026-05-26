import json
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any

import typer
from googleapiclient.errors import HttpError

from ytstudio.api import api, handle_api_error
from ytstudio.services import get_data_service
from ytstudio.ui import (
    console,
    create_kv_table,
    create_table,
    dim,
    success_message,
    truncate,
)

app = typer.Typer(help="Live broadcast management (schedule, start, stop, update)")


class BroadcastStatus(StrEnum):
    all = "all"
    active = "active"
    completed = "completed"
    upcoming = "upcoming"


class PrivacyStatus(StrEnum):
    public = "public"
    private = "private"
    unlisted = "unlisted"


class ClosedCaptionsType(StrEnum):
    disabled = "closedCaptionsDisabled"
    http_post = "closedCaptionsHttpPost"
    embedded = "closedCaptionsEmbedded"


class LatencyPreference(StrEnum):
    normal = "normal"
    low = "low"
    ultra_low = "ultraLow"


class Projection(StrEnum):
    rectangular = "rectangular"
    three_sixty = "360"


class TransitionTarget(StrEnum):
    """The two states a user typically asks the CLI to drive into."""

    testing = "testing"
    live = "live"


class OutputFormat(StrEnum):
    table = "table"
    json = "json"


EMPTY = "-"


@dataclass
class Broadcast:
    id: str
    title: str
    lifecycle_status: str
    scheduled_start: str
    scheduled_end: str = ""
    description: str = ""
    privacy: str = "public"
    actual_start: str = ""
    actual_end: str = ""
    bound_stream_id: str = ""
    auto_start: bool = False
    auto_stop: bool = False
    dvr: bool = True
    embed: bool = True
    record_from_start: bool = True
    closed_captions_type: str = "closedCaptionsDisabled"
    latency_preference: str = "normal"
    projection: str = "rectangular"
    made_for_kids: bool = False
    # YouTube requires both of these whenever contentDetails is included in an
    # update, so we keep them on the parsed object and round-trip them.
    monitor_stream_enabled: bool = True
    broadcast_stream_delay_ms: int = 0


@dataclass
class StreamIngest:
    """Subset of liveStream.cdn.ingestionInfo we surface to the user."""

    stream_id: str
    ingestion_address: str = ""
    backup_ingestion_address: str = ""
    rtmps_ingestion_address: str = ""
    rtmps_backup_ingestion_address: str = ""
    stream_name: str = ""  # the actual stream key, redacted unless explicitly shown
    format: str = ""
    frame_rate: str = ""
    resolution: str = ""


_LIVESTREAM_ERRORS = {
    "invalidTransition": "Cannot perform this transition; broadcast may not be in the right state.",
    "redundantTransition": "Broadcast is already in the requested state.",
    "liveStreamingNotEnabled": (
        "Live streaming is not enabled for this channel. Enable it at youtube.com/features."
    ),
    "errorStreamInactive": (
        "No active stream is bound to this broadcast. Start your encoder (OBS, etc.) "
        "or bind a stream first."
    ),
    "liveBroadcastNotFound": "Broadcast not found.",
    "errorExecutingTransition": (
        "YouTube could not execute this transition. Check encoder health and try again."
    ),
    "livePermissionBlocked": (
        "Live streaming is blocked for this channel (account standing, age, or strikes)."
    ),
    "insufficientLivePermissions": (
        "This channel does not have permission for live streaming yet."
    ),
    "userRequestsExceedRateLimit": "Too many requests; wait a moment and retry.",
    "concurrentBroadcastsExceedLimit": (
        "You already have the maximum number of concurrent live broadcasts."
    ),
    "sharedIngestionBroadcastsExceedLimit": (
        "Too many broadcasts share this ingestion stream; stop one and try again."
    ),
}


def _handle_livestream_error(e: HttpError):
    detail = e.error_details[0] if getattr(e, "error_details", None) else {}
    reason = detail.get("reason", "") if isinstance(detail, dict) else ""
    if reason in _LIVESTREAM_ERRORS:
        console.print(f"[red]{_LIVESTREAM_ERRORS[reason]}[/red]")
        raise typer.Exit(1)
    handle_api_error(e)


def _parse_broadcast(item: dict[str, Any]) -> Broadcast:
    snippet = item.get("snippet") or {}
    status = item.get("status") or {}
    content = item.get("contentDetails") or {}
    monitor = content.get("monitorStream") or {}
    return Broadcast(
        id=str(item["id"]),
        title=snippet.get("title", ""),
        lifecycle_status=status.get("lifeCycleStatus", ""),
        scheduled_start=snippet.get("scheduledStartTime", ""),
        scheduled_end=snippet.get("scheduledEndTime", ""),
        description=snippet.get("description", ""),
        privacy=status.get("privacyStatus", "public"),
        actual_start=snippet.get("actualStartTime", ""),
        actual_end=snippet.get("actualEndTime", ""),
        bound_stream_id=content.get("boundStreamId", ""),
        auto_start=content.get("enableAutoStart", False),
        auto_stop=content.get("enableAutoStop", False),
        dvr=content.get("enableDvr", True),
        embed=content.get("enableEmbed", True),
        record_from_start=content.get("recordFromStart", True),
        closed_captions_type=content.get("closedCaptionsType", "closedCaptionsDisabled"),
        latency_preference=content.get("latencyPreference", "normal"),
        projection=content.get("projection", "rectangular"),
        made_for_kids=status.get("selfDeclaredMadeForKids", False),
        monitor_stream_enabled=monitor.get("enableMonitorStream", True),
        broadcast_stream_delay_ms=int(monitor.get("broadcastStreamDelayMs", 0) or 0),
    )


def _fetch_broadcast(service, broadcast_id: str) -> Broadcast | None:
    response = (
        api(service.liveBroadcasts().list(part="snippet,status,contentDetails", id=broadcast_id))
        or {}
    )
    for item in response.get("items", []):
        if item.get("id") == broadcast_id:
            return _parse_broadcast(item)
    return None


def _fetch_stream_ingest(service, stream_id: str) -> StreamIngest | None:
    response = api(service.liveStreams().list(part="snippet,cdn,status", id=stream_id)) or {}
    items = response.get("items", [])
    if not items:
        return None
    item = items[0]
    cdn = item.get("cdn") or {}
    ingestion_info = cdn.get("ingestionInfo") or {}
    return StreamIngest(
        stream_id=str(item.get("id", stream_id)),
        ingestion_address=ingestion_info.get("ingestionAddress", ""),
        backup_ingestion_address=ingestion_info.get("backupIngestionAddress", ""),
        rtmps_ingestion_address=ingestion_info.get("rtmpsIngestionAddress", ""),
        rtmps_backup_ingestion_address=ingestion_info.get("rtmpsBackupIngestionAddress", ""),
        stream_name=ingestion_info.get("streamName", ""),
        format=cdn.get("format", ""),
        frame_rate=cdn.get("frameRate", ""),
        resolution=cdn.get("resolution", ""),
    )


def _redact_key(stream_name: str) -> str:
    """Mask all but the last 4 chars of the stream key."""
    if not stream_name:
        return ""
    if len(stream_name) <= 4:
        return "*" * len(stream_name)
    return "*" * (len(stream_name) - 4) + stream_name[-4:]


@app.command("list")
def list_broadcasts(
    status: BroadcastStatus = typer.Option(
        BroadcastStatus.upcoming,
        "--status",
        "-s",
        help="Filter: all, upcoming, active, completed",
    ),
    limit: int = typer.Option(20, "--limit", "-n", min=1, max=50, help="Number of broadcasts"),
    page_token: str = typer.Option(None, "--page-token", "-p", help="Page token for pagination"),
    output: OutputFormat = typer.Option(
        OutputFormat.table, "--output", "-o", help="Output format: table or json"
    ),
):
    """List your YouTube live broadcasts."""
    service = get_data_service()
    response = (
        api(
            service.liveBroadcasts().list(
                part="snippet,status,contentDetails",
                broadcastStatus=status.value,
                maxResults=limit,
                pageToken=page_token,
            )
        )
        or {}
    )
    broadcasts = [_parse_broadcast(item) for item in response.get("items", [])]
    broadcasts.sort(key=lambda b: b.scheduled_start or "", reverse=True)

    if not broadcasts:
        console.print("[yellow]No broadcasts found[/yellow]")
        return

    if output is OutputFormat.json:
        print(
            json.dumps(
                {
                    "broadcasts": [asdict(b) for b in broadcasts],
                    "next_page_token": response.get("nextPageToken"),
                    "total_results": (response.get("pageInfo") or {}).get("totalResults", 0),
                },
                indent=2,
            )
        )
        return

    table = create_table()
    table.add_column("ID", style="yellow")
    table.add_column("Title", style="cyan")
    table.add_column("Status")
    table.add_column("Scheduled Start")
    table.add_column("Privacy")

    for broadcast in broadcasts:
        scheduled = (
            broadcast.scheduled_start[:16].replace("T", " ") if broadcast.scheduled_start else EMPTY
        )
        table.add_row(
            broadcast.id,
            truncate(broadcast.title),
            broadcast.lifecycle_status or EMPTY,
            scheduled,
            broadcast.privacy,
        )

    console.print(table)

    if response.get("nextPageToken"):
        console.print(f"\nNext page: --page-token {response['nextPageToken']}")


@app.command()
def show(
    broadcast_id: str = typer.Argument(..., help="Broadcast ID"),
    ingest: bool = typer.Option(
        False,
        "--ingest",
        help="Also fetch and display the bound stream's ingest URL (key is redacted by default)",
    ),
    show_key: bool = typer.Option(
        False,
        "--show-key",
        help="Reveal the bound stream key (implies --ingest). Treat output as a secret.",
    ),
    output: OutputFormat = typer.Option(
        OutputFormat.table, "--output", "-o", help="Output format: table or json"
    ),
):
    """Show details for a specific broadcast."""
    service = get_data_service()
    broadcast = _fetch_broadcast(service, broadcast_id)

    if not broadcast:
        console.print(f"[red]Broadcast not found: {broadcast_id}[/red]")
        raise typer.Exit(1)

    stream: StreamIngest | None = None
    if (ingest or show_key) and broadcast.bound_stream_id:
        stream = _fetch_stream_ingest(service, broadcast.bound_stream_id)

    if output is OutputFormat.json:
        payload: dict[str, Any] = {"broadcast": asdict(broadcast)}
        if stream:
            ingest_dump = asdict(stream)
            if not show_key:
                ingest_dump["stream_name"] = _redact_key(ingest_dump["stream_name"])
            payload["ingest"] = ingest_dump
        print(json.dumps(payload, indent=2))
        return

    console.print(f"\n[bold]{broadcast.title}[/bold]\n")

    table = create_kv_table()
    table.add_column("field", style="dim")
    table.add_column("value")
    table.add_row("status", broadcast.lifecycle_status or EMPTY)
    table.add_row("privacy", broadcast.privacy)
    table.add_row("scheduled start", broadcast.scheduled_start or EMPTY)
    table.add_row("scheduled end", broadcast.scheduled_end or EMPTY)
    table.add_row("actual start", broadcast.actual_start or EMPTY)
    table.add_row("actual end", broadcast.actual_end or EMPTY)
    table.add_row("stream bound", broadcast.bound_stream_id or "No")
    table.add_row("auto start", "Yes" if broadcast.auto_start else "No")
    table.add_row("auto stop", "Yes" if broadcast.auto_stop else "No")
    table.add_row("dvr", "Yes" if broadcast.dvr else "No")
    table.add_row("embed", "Yes" if broadcast.embed else "No")
    table.add_row("record from start", "Yes" if broadcast.record_from_start else "No")
    table.add_row("closed captions", broadcast.closed_captions_type)
    table.add_row("latency", broadcast.latency_preference)
    table.add_row("projection", broadcast.projection)
    table.add_row("made for kids", "Yes" if broadcast.made_for_kids else "No")
    table.add_row("description", broadcast.description or EMPTY)
    console.print(table)

    if (ingest or show_key) and not broadcast.bound_stream_id:
        console.print(dim("\nNo stream bound; nothing to fetch."))
        return

    if stream:
        console.print()
        console.print("[bold]Ingest[/bold]")
        ingest_table = create_kv_table()
        ingest_table.add_column("field", style="dim")
        ingest_table.add_column("value")
        ingest_table.add_row("stream id", stream.stream_id)
        ingest_table.add_row(
            "format", f"{stream.resolution or '?'} {stream.frame_rate or ''}".strip()
        )
        ingest_table.add_row("rtmp", stream.ingestion_address or EMPTY)
        if stream.backup_ingestion_address:
            ingest_table.add_row("rtmp (backup)", stream.backup_ingestion_address)
        if stream.rtmps_ingestion_address:
            ingest_table.add_row("rtmps", stream.rtmps_ingestion_address)
        if stream.rtmps_backup_ingestion_address:
            ingest_table.add_row("rtmps (backup)", stream.rtmps_backup_ingestion_address)
        key_display = stream.stream_name if show_key else _redact_key(stream.stream_name)
        ingest_table.add_row("stream key", key_display or EMPTY)
        console.print(ingest_table)
        if show_key:
            console.print(dim("\nstream key revealed; treat the line above as a secret."))


@app.command()
def start(
    broadcast_id: str = typer.Argument(..., help="Broadcast ID"),
    to: TransitionTarget = typer.Option(
        TransitionTarget.live,
        "--to",
        help="Target state: testing (monitor only) or live (publish to viewers).",
    ),
):
    """Transition a broadcast to testing or live."""
    service = get_data_service()
    try:
        response = api(
            service.liveBroadcasts().transition(
                broadcastStatus=to.value,
                id=broadcast_id,
                part="id,snippet,status",
            )
        )
    except HttpError as e:
        _handle_livestream_error(e)
        return

    new_status = (response or {}).get("status", {}).get("lifeCycleStatus", to.value)
    success_message(f"Broadcast transitioning to {to.value}: {broadcast_id}")
    console.print(f"Current status: {new_status}")
    console.print(dim("Note: transitions are asynchronous; status may take a moment to update."))


@app.command()
def stop(broadcast_id: str = typer.Argument(..., help="Broadcast ID")):
    """Stop a live broadcast (transition to complete)."""
    service = get_data_service()
    try:
        response = api(
            service.liveBroadcasts().transition(
                broadcastStatus="complete",
                id=broadcast_id,
                part="id,snippet,status",
            )
        )
    except HttpError as e:
        _handle_livestream_error(e)
        return

    new_status = (response or {}).get("status", {}).get("lifeCycleStatus", "complete")
    success_message(f"Broadcast stopped: {broadcast_id}")
    console.print(f"Current status: {new_status}")


@app.command()
def schedule(
    title: str = typer.Option(..., "--title", "-t", help="Broadcast title"),
    scheduled_start: str = typer.Option(
        ...,
        "--scheduled-start",
        help="Scheduled start time, ISO 8601 (e.g. 2026-06-01T19:00:00+02:00)",
    ),
    scheduled_end: str = typer.Option(
        "",
        "--scheduled-end",
        help="Scheduled end time, ISO 8601",
    ),
    description: str = typer.Option("", "--description", "-d", help="Broadcast description"),
    privacy: PrivacyStatus = typer.Option(
        PrivacyStatus.public, "--privacy", help="public, private, or unlisted"
    ),
    made_for_kids: bool = typer.Option(
        False,
        "--made-for-kids/--not-made-for-kids",
        help="COPPA self-declaration; required by YouTube on every broadcast.",
    ),
    execute: bool = typer.Option(
        False, "--execute", help="Create the broadcast (default is dry-run preview)"
    ),
):
    """Schedule a new live broadcast."""
    snippet_body: dict[str, Any] = {
        "title": title,
        "description": description,
        "scheduledStartTime": scheduled_start,
    }
    if scheduled_end:
        snippet_body["scheduledEndTime"] = scheduled_end
    status_body = {
        "privacyStatus": privacy.value,
        "selfDeclaredMadeForKids": made_for_kids,
    }
    body = {"snippet": snippet_body, "status": status_body}

    if not execute:
        console.print("[bold]Preview new broadcast:[/bold]\n")
        preview = create_kv_table()
        preview.add_column("field", style="dim")
        preview.add_column("value")
        preview.add_row("title", title)
        preview.add_row("scheduled start", scheduled_start)
        if scheduled_end:
            preview.add_row("scheduled end", scheduled_end)
        if description:
            preview.add_row("description", description)
        preview.add_row("privacy", privacy.value)
        preview.add_row("made for kids", "Yes" if made_for_kids else "No")
        console.print(preview)
        console.print("\nRun with --execute to create.")
        console.print(dim("Quota: liveBroadcasts.insert costs ~50 units against your daily quota."))
        return

    service = get_data_service()
    try:
        response = (
            api(service.liveBroadcasts().insert(part="snippet,status,contentDetails", body=body))
            or {}
        )
    except HttpError as e:
        _handle_livestream_error(e)
        return

    broadcast_id = response.get("id", "unknown")
    success_message(f"Broadcast created: {broadcast_id}")
    console.print(f"Title: {title}")
    console.print(dim("Next: bind a stream in YouTube Studio or start your encoder."))


@app.command()
def update(
    broadcast_id: str = typer.Argument(..., help="Broadcast ID"),
    title: str = typer.Option(None, "--title", "-t", help="New title"),
    description: str = typer.Option(None, "--description", "-d", help="New description"),
    privacy: PrivacyStatus = typer.Option(None, "--privacy", help="New privacy status"),
    scheduled_start: str = typer.Option(
        None, "--scheduled-start", help="New scheduled start, ISO 8601"
    ),
    scheduled_end: str = typer.Option(None, "--scheduled-end", help="New scheduled end, ISO 8601"),
    auto_start: bool | None = typer.Option(
        None, "--auto-start/--no-auto-start", help="Auto-start when stream begins"
    ),
    auto_stop: bool | None = typer.Option(
        None, "--auto-stop/--no-auto-stop", help="Auto-stop when stream ends"
    ),
    dvr: bool | None = typer.Option(None, "--dvr/--no-dvr", help="Enable DVR controls"),
    embed: bool | None = typer.Option(None, "--embed/--no-embed", help="Allow embedding"),
    record_from_start: bool | None = typer.Option(
        None,
        "--record-from-start/--no-record-from-start",
        help="Record broadcast for archive",
    ),
    closed_captions: ClosedCaptionsType = typer.Option(
        None, "--closed-captions", help="Closed-caption mode"
    ),
    latency: LatencyPreference = typer.Option(
        None, "--latency", help="Latency: normal, low, ultraLow"
    ),
    projection: Projection = typer.Option(
        None, "--projection", help="Projection: rectangular or 360"
    ),
    execute: bool = typer.Option(False, "--execute", help="Apply changes (default is dry-run)"),
):
    """Update a broadcast's metadata or settings (partial update).

    Note: liveBroadcasts.update only accepts privacyStatus under status; the
    made-for-kids designation is set at schedule time and managed on the
    resulting video resource afterwards.
    """
    snippet_changes: dict[str, Any] = {}
    if title is not None:
        snippet_changes["title"] = title
    if description is not None:
        snippet_changes["description"] = description
    if scheduled_start is not None:
        snippet_changes["scheduledStartTime"] = scheduled_start
    if scheduled_end is not None:
        snippet_changes["scheduledEndTime"] = scheduled_end

    status_changes: dict[str, Any] = {}
    if privacy is not None:
        status_changes["privacyStatus"] = privacy.value

    content_changes: dict[str, Any] = {}
    if auto_start is not None:
        content_changes["enableAutoStart"] = auto_start
    if auto_stop is not None:
        content_changes["enableAutoStop"] = auto_stop
    if dvr is not None:
        content_changes["enableDvr"] = dvr
    if embed is not None:
        content_changes["enableEmbed"] = embed
    if record_from_start is not None:
        content_changes["recordFromStart"] = record_from_start
    if closed_captions is not None:
        content_changes["closedCaptionsType"] = closed_captions.value
    if latency is not None:
        content_changes["latencyPreference"] = latency.value
    if projection is not None:
        content_changes["projection"] = projection.value

    if not snippet_changes and not status_changes and not content_changes:
        console.print(
            "[yellow]Nothing to update. Pass at least one of --title, --description, "
            "--privacy, --scheduled-start, --scheduled-end, --auto-start, --auto-stop, "
            "--dvr, --embed, --record-from-start, --closed-captions, --latency, "
            "or --projection.[/yellow]"
        )
        raise typer.Exit(1)

    service = get_data_service()
    current = _fetch_broadcast(service, broadcast_id)
    if not current:
        console.print(f"[red]Broadcast not found: {broadcast_id}[/red]")
        raise typer.Exit(1)

    # Snippet/status PUTs replace the whole part, so we merge changes onto the current
    # values from a fresh read. contentDetails accepts the same pattern.
    snippet_body: dict[str, Any] = {
        "title": current.title,
        "description": current.description,
        "scheduledStartTime": current.scheduled_start,
    }
    if current.scheduled_end:
        snippet_body["scheduledEndTime"] = current.scheduled_end
    snippet_body.update(snippet_changes)

    # liveBroadcasts.update only accepts privacyStatus under status (per the API
    # reference), so we deliberately omit selfDeclaredMadeForKids here.
    status_body: dict[str, Any] = {"privacyStatus": current.privacy}
    status_body.update(status_changes)

    parts = ["snippet", "status"]
    body: dict[str, Any] = {
        "id": broadcast_id,
        "snippet": snippet_body,
        "status": status_body,
    }

    if content_changes:
        parts.append("contentDetails")
        # contentDetails is replace-on-update. Include both monitorStream fields
        # (YouTube rejects the request otherwise) and round-trip the rest from
        # the freshly-read broadcast so unchanged fields are preserved.
        content_body: dict[str, Any] = {
            "monitorStream": {
                "enableMonitorStream": current.monitor_stream_enabled,
                "broadcastStreamDelayMs": current.broadcast_stream_delay_ms,
            },
            "enableAutoStart": current.auto_start,
            "enableAutoStop": current.auto_stop,
            "enableDvr": current.dvr,
            "enableEmbed": current.embed,
            "recordFromStart": current.record_from_start,
            "closedCaptionsType": current.closed_captions_type,
            "latencyPreference": current.latency_preference,
            "projection": current.projection,
        }
        content_body.update(content_changes)
        body["contentDetails"] = content_body

    if not execute:
        _print_update_preview(current, snippet_changes, status_changes, content_changes)
        return

    try:
        api(service.liveBroadcasts().update(part=",".join(parts), body=body))
    except HttpError as e:
        _handle_livestream_error(e)
        return
    success_message(f"Updated: {snippet_body['title']}")


_SNIPPET_LABELS: dict[str, tuple[str, str]] = {
    "title": ("title", "title"),
    "description": ("description", "description"),
    "scheduledStartTime": ("scheduled start", "scheduled_start"),
    "scheduledEndTime": ("scheduled end", "scheduled_end"),
}
_STATUS_LABELS: dict[str, tuple[str, str]] = {
    "privacyStatus": ("privacy", "privacy"),
}
_CONTENT_LABELS: dict[str, tuple[str, str]] = {
    "enableAutoStart": ("auto start", "auto_start"),
    "enableAutoStop": ("auto stop", "auto_stop"),
    "enableDvr": ("dvr", "dvr"),
    "enableEmbed": ("embed", "embed"),
    "recordFromStart": ("record from start", "record_from_start"),
    "closedCaptionsType": ("closed captions", "closed_captions_type"),
    "latencyPreference": ("latency", "latency_preference"),
    "projection": ("projection", "projection"),
}


def _print_update_preview(
    current: Broadcast,
    snippet_changes: dict[str, Any],
    status_changes: dict[str, Any],
    content_changes: dict[str, Any],
) -> None:
    console.print("[bold]Preview changes:[/bold]\n")
    table = create_kv_table()
    table.add_column("field", style="dim")
    table.add_column("old")
    table.add_column("new", style="green")
    for changes, label_map in (
        (snippet_changes, _SNIPPET_LABELS),
        (status_changes, _STATUS_LABELS),
        (content_changes, _CONTENT_LABELS),
    ):
        for api_key, new_value in changes.items():
            label, attr = label_map.get(api_key, (api_key, api_key))
            old_value = getattr(current, attr, "")
            old_display = str(old_value) if old_value not in ("", None) else EMPTY
            table.add_row(label, old_display, str(new_value))
    console.print(table)
    console.print("\nRun with --execute to apply.")
