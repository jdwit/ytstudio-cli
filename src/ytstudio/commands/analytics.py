import csv
import io
import json
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta

import typer

from ytstudio.api import api
from ytstudio.registry import (
    DIMENSION_GROUPS,
    DIMENSIONS,
    METRIC_GROUPS,
    METRICS,
    DimensionName,
    MetricName,
    find_closest_dimension,
    validate_dimensions,
    validate_metrics,
)
from ytstudio.services import get_analytics_service, get_data_service
from ytstudio.ui import console, create_kv_table, create_table, dim, format_number, set_raw_output

app = typer.Typer(help="Analytics commands")


@dataclass
class VideoAnalytics:
    views: int
    watch_time_minutes: int
    avg_view_duration_secs: int
    avg_view_percentage: float
    likes: int
    comments: int


def get_channel_id(service) -> str:
    response = api(service.channels().list(part="id", mine=True))
    if not response.get("items"):
        console.print("[red]No channel found[/red]")
        raise typer.Exit(1)
    return response["items"][0]["id"]


def fetch_query(
    data_service,
    analytics_service,
    *,
    metric_names: list[str],
    dimension_names: list[str],
    start_date: str,
    end_date: str,
    days: int,
    filters_str: str | None = None,
    sort: str | None = None,
    max_results: int | None = None,
    currency: str | None = None,
) -> dict:
    channel_id = get_channel_id(data_service)

    query_params = {
        "ids": f"channel=={channel_id}",
        "startDate": start_date,
        "endDate": end_date,
        "metrics": ",".join(metric_names),
    }

    if dimension_names:
        query_params["dimensions"] = ",".join(dimension_names)
    if filters_str:
        query_params["filters"] = filters_str
    if sort:
        query_params["sort"] = sort
    if max_results:
        query_params["maxResults"] = max_results
    if currency:
        query_params["currency"] = currency

    return api(analytics_service.reports().query(**query_params))


# Metrics shown with a period-over-period delta in the overview.
OVERVIEW_COMPARE_METRICS = (
    "views",
    "estimatedMinutesWatched",
    "averageViewDuration",
    "likes",
    "comments",
)


def _pct_change(current: float, previous: float) -> float | None:
    """Percent change vs the previous window, or None when there is no baseline."""
    if previous == 0:
        return None
    return round((current - previous) / previous * 100, 1)


def _delta_suffix(metrics: dict, previous: dict | None, metric: str) -> str:
    """Coloured ' (+N%)' suffix comparing a metric to the previous window."""
    if previous is None:
        return ""
    current = float(metrics.get(metric, 0))
    pct = _pct_change(current, float(previous.get(metric, 0)))
    if pct is None:
        return dim(" (new)") if current else ""
    colour = "green" if pct >= 0 else "red"
    sign = "+" if pct >= 0 else ""
    return f" [{colour}]({sign}{pct:.0f}%)[/{colour}]"


@app.command()
def overview(
    days: int = typer.Option(28, "--days", "-d", help="Number of days to analyze"),
    compare: bool = typer.Option(
        True,
        "--compare/--no-compare",
        help="Compare each metric to the previous equal-length window",
    ),
    output: str = typer.Option("table", "--output", "-o", help="Output format: table, json"),
):
    """Get channel overview analytics"""
    metric_names = [
        MetricName.VIEWS,
        MetricName.ESTIMATED_MINUTES_WATCHED,
        MetricName.AVERAGE_VIEW_DURATION,
        MetricName.SUBSCRIBERS_GAINED,
        MetricName.SUBSCRIBERS_LOST,
        MetricName.LIKES,
        MetricName.COMMENTS,
    ]

    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    data_service = get_data_service()
    analytics_service = get_analytics_service()
    response = fetch_query(
        data_service,
        analytics_service,
        metric_names=metric_names,
        dimension_names=[],
        start_date=start_date,
        end_date=end_date,
        days=days,
    )

    headers = [h["name"] for h in response.get("columnHeaders", [])]
    rows = response.get("rows", [])

    if not rows:
        console.print("[yellow]No analytics data available[/yellow]")
        return

    metrics = dict(zip(headers, rows[0], strict=False))

    # Previous equal-length window ending the day before the current one starts,
    # so the two windows do not share a boundary day.
    previous = None
    pct_change = None
    if compare:
        prev_end = (datetime.now() - timedelta(days=days + 1)).strftime("%Y-%m-%d")
        prev_start = (datetime.now() - timedelta(days=days * 2 + 1)).strftime("%Y-%m-%d")
        prev_response = fetch_query(
            data_service,
            analytics_service,
            metric_names=metric_names,
            dimension_names=[],
            start_date=prev_start,
            end_date=prev_end,
            days=days,
        )
        prev_rows = prev_response.get("rows", [])
        if prev_rows:
            prev_headers = [h["name"] for h in prev_response.get("columnHeaders", [])]
            previous = dict(zip(prev_headers, prev_rows[0], strict=False))
            pct_change = {
                m: _pct_change(float(metrics.get(m, 0)), float(previous.get(m, 0)))
                for m in OVERVIEW_COMPARE_METRICS
            }

    if output == "json":
        print(
            json.dumps(
                {
                    "analytics": metrics,
                    "days": days,
                    "previous": previous,
                    "pct_change": pct_change,
                },
                indent=2,
            )
        )
        return

    views = int(metrics.get("views", 0))
    watch_hours = int(metrics.get("estimatedMinutesWatched", 0)) // 60
    avg_secs = int(metrics.get("averageViewDuration", 0))
    subs_gained = int(metrics.get("subscribersGained", 0))
    subs_lost = int(metrics.get("subscribersLost", 0))
    likes = int(metrics.get("likes", 0))
    comments = int(metrics.get("comments", 0))

    subtitle = f"(last {days} days"
    subtitle += f" vs previous {days})" if previous is not None else ")"
    console.print(f"\n[bold]Channel Analytics[/bold] {dim(subtitle)}\n")
    table = create_kv_table()

    def d(metric: str) -> str:
        return _delta_suffix(metrics, previous, metric)

    table.add_row(dim("views"), format_number(views) + d("views"))
    table.add_row(dim("watch time"), f"{watch_hours} hours" + d("estimatedMinutesWatched"))
    table.add_row(
        dim("avg duration"), f"{avg_secs // 60}:{avg_secs % 60:02d}" + d("averageViewDuration")
    )
    table.add_row(dim("subscribers gained"), f"[green]+{subs_gained}[/green]")
    table.add_row(dim("subscribers lost"), f"[red]-{subs_lost}[/red]")
    table.add_row(dim("likes"), format_number(likes) + d("likes"))
    table.add_row(dim("comments"), format_number(comments) + d("comments"))

    console.print(table)


def fetch_video_analytics(
    data_service, analytics_service, video_id: str, days: int
) -> VideoAnalytics | None:
    channel_id = get_channel_id(data_service)
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    response = api(
        analytics_service.reports().query(
            ids=f"channel=={channel_id}",
            startDate=start_date,
            endDate=end_date,
            metrics=",".join(
                (
                    MetricName.VIEWS,
                    MetricName.ESTIMATED_MINUTES_WATCHED,
                    MetricName.AVERAGE_VIEW_DURATION,
                    MetricName.AVERAGE_VIEW_PERCENTAGE,
                    MetricName.LIKES,
                    MetricName.COMMENTS,
                )
            ),
            filters=f"video=={video_id}",
        )
    )

    if not response.get("rows"):
        return None

    row = response["rows"][0]
    metrics = {h["name"]: row[i] for i, h in enumerate(response["columnHeaders"])}

    return VideoAnalytics(
        views=int(metrics.get("views", 0)),
        watch_time_minutes=int(metrics.get("estimatedMinutesWatched", 0)),
        avg_view_duration_secs=int(metrics.get("averageViewDuration", 0)),
        avg_view_percentage=float(metrics.get("averageViewPercentage", 0)),
        likes=int(metrics.get("likes", 0)),
        comments=int(metrics.get("comments", 0)),
    )


@app.command()
def video(
    video_id: str = typer.Argument(..., help="Video ID"),
    days: int = typer.Option(28, "--days", "-d", help="Number of days to analyze"),
    output: str = typer.Option("table", "--output", "-o", help="Output format: table, json"),
):
    """Get analytics for a specific video"""
    data_service = get_data_service()
    analytics_service = get_analytics_service()

    video_response = api(data_service.videos().list(part="snippet,statistics", id=video_id))

    if not video_response.get("items"):
        console.print(f"[red]Video not found: {video_id}[/red]")
        raise typer.Exit(1)

    video_data = video_response["items"][0]
    snippet = video_data["snippet"]
    analytics = fetch_video_analytics(data_service, analytics_service, video_id, days)

    if output == "json":
        print(
            json.dumps(
                {"video": video_data, "analytics": asdict(analytics) if analytics else None},
                indent=2,
            )
        )
        return

    console.print(f"\n[bold]{snippet['title']}[/bold]")
    console.print(f"[cyan]https://youtu.be/{video_id}[/cyan]\n")

    if analytics:
        console.print(f"[bold]Analytics[/bold] {dim(f'(last {days} days)')}\n")
        table = create_kv_table()

        table.add_row(dim("views"), format_number(analytics.views))
        table.add_row(dim("watch time"), f"{analytics.watch_time_minutes} min")
        table.add_row(dim("avg duration"), f"{analytics.avg_view_duration_secs}s")
        table.add_row(dim("avg % viewed"), f"{analytics.avg_view_percentage:.1f}%")
        table.add_row(dim("likes"), format_number(analytics.likes))
        table.add_row(dim("comments"), format_number(analytics.comments))

        console.print(table)


# --- Raw query engine ---


def _parse_comma_list(value: str) -> list[str]:
    """Split a comma-separated string, stripping whitespace."""
    return [v.strip() for v in value.split(",") if v.strip()]


def _align_date_range(
    dimension_names: list[str], start_date: str, end_date: str
) -> tuple[str, str]:
    """Snap dates to the boundaries the YouTube Analytics API requires.

    month: both ends must be the first of a month. The API rejects other days,
    it does not snap. So snap both ends DOWN to the first of their month.
    week: API weeks begin on Sunday. Snap both ends back to their Sunday.
    See https://developers.google.com/youtube/analytics/dimensions (time periods).
    Other dimensions (day, country, ...) are returned unchanged.
    """
    if DimensionName.MONTH in dimension_names:
        return _snap_to_month_start(start_date), _snap_to_month_start(end_date)
    if "week" in dimension_names:
        return _snap_to_week_start(start_date), _snap_to_week_start(end_date)
    return start_date, end_date


def _snap_to_month_start(value: str) -> str:
    d = date.fromisoformat(value)
    return d.replace(day=1).isoformat()


def _snap_to_week_start(value: str) -> str:
    # weekday(): Mon=0 .. Sun=6; days back to the preceding Sunday.
    d = date.fromisoformat(value)
    return (d - timedelta(days=(d.weekday() + 1) % 7)).isoformat()


def _chunks(values: list[str], size: int) -> list[list[str]]:
    return [values[i : i + size] for i in range(0, len(values), size)]


def _fetch_snippet_titles(data_service, resource: str, ids: list[str]) -> dict[str, str]:
    """Fetch snippet titles for YouTube Data API resources by id."""
    if not ids:
        return {}

    titles: dict[str, str] = {}
    for batch in _chunks(ids, 50):
        if resource == "video":
            response = api(data_service.videos().list(part="snippet", id=",".join(batch)))
        elif resource == "playlist":
            response = api(data_service.playlists().list(part="snippet", id=",".join(batch)))
        else:
            raise ValueError(f"Unsupported resource for title resolution: {resource}")

        for item in response.get("items", []):
            item_id = item.get("id")
            title = item.get("snippet", {}).get("title")
            if item_id and title is not None:
                titles[item_id] = title
    return titles


def _resolve_query_dimension_titles(data_service, response: dict) -> dict:
    """Add title columns for video/playlist dimensions in an analytics query response."""
    headers = list(response.get("columnHeaders", []))
    rows = [list(row) for row in response.get("rows", [])]
    header_names = [h.get("name") for h in headers]

    resolvable = sorted(
        (name for name in (DimensionName.VIDEO, DimensionName.PLAYLIST) if name in header_names),
        key=header_names.index,
    )
    if not resolvable or not rows:
        return response

    title_maps: dict[str, dict[str, str]] = {}
    for name in resolvable:
        idx = header_names.index(name)
        ids = list(dict.fromkeys(str(row[idx]) for row in rows if idx < len(row) and row[idx]))
        title_maps[name] = _fetch_snippet_titles(data_service, name, ids)

    # Insert title columns immediately after each resolved dimension. Iterate in
    # reverse so earlier indices remain valid while mutating rows/headers.
    for name in reversed(resolvable):
        idx = header_names.index(name)
        title_header = f"{name}Title"
        headers.insert(
            idx + 1,
            {"name": title_header, "columnType": "DIMENSION", "dataType": "STRING"},
        )
        for row in rows:
            resource_id = str(row[idx]) if idx < len(row) and row[idx] is not None else ""
            row.insert(idx + 1, title_maps[name].get(resource_id))

    return {**response, "columnHeaders": headers, "rows": rows}


def _format_query_response(response: dict, output: str) -> None:
    headers = [h["name"] for h in response.get("columnHeaders", [])]
    rows = response.get("rows", [])

    if output == "json":
        records = [dict(zip(headers, row, strict=False)) for row in rows]
        print(json.dumps(records, indent=2))
        return

    if output == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(headers)
        writer.writerows(rows)
        print(buf.getvalue(), end="")
        return

    # table output
    if not rows:
        console.print("[yellow]No data returned[/yellow]")
        return

    table = create_table()
    for header in headers:
        is_numeric = header in METRICS
        table.add_column(
            header,
            justify="right" if is_numeric else "left",
            style="yellow" if header in DIMENSIONS else None,
        )

    for row in rows:
        table.add_row(*[_format_cell(headers[i], v) for i, v in enumerate(row)])

    console.print(table)


def _format_cell(header: str, value) -> str:
    if isinstance(value, int):
        return format_number(value)
    if isinstance(value, float):
        if "rate" in header.lower() or "percentage" in header.lower() or "ctr" in header.lower():
            return f"{value:.2f}%"
        if "cpm" in header.lower():
            return f"${value:.2f}"
        if value == int(value):
            return format_number(int(value))
        return f"{value:.1f}"
    return str(value)


@app.command()
def query(
    metrics_str: str = typer.Option(
        ..., "--metrics", "-m", help="Comma-separated metrics (e.g. views,likes,shares)"
    ),
    dimensions_str: str = typer.Option(
        None, "--dimensions", "-d", help="Comma-separated dimensions (e.g. day,country)"
    ),
    filter_list: list[str] = typer.Option(
        None,
        "--filter",
        "-f",
        help="Filter in key==value format (repeatable, e.g. -f video==ID -f country==NL)",
    ),
    start: str = typer.Option(
        None, "--start", "-s", help="Start date (YYYY-MM-DD). Defaults to --days ago"
    ),
    end: str = typer.Option(None, "--end", "-e", help="End date (YYYY-MM-DD). Defaults to today"),
    days: int = typer.Option(28, "--days", help="Number of days (used if --start not set)"),
    sort: str = typer.Option(None, "--sort", help="Sort field (prefix with - for descending)"),
    limit: int = typer.Option(None, "--limit", "-n", help="Maximum number of rows"),
    currency: str = typer.Option(None, "--currency", help="Currency code for revenue (e.g. EUR)"),
    output: str = typer.Option("table", "--output", "-o", help="Output format: table, json, csv"),
    raw: bool = typer.Option(False, "--raw", help="Show raw numbers instead of human-readable"),
    resolve: bool = typer.Option(
        False,
        "--resolve",
        help="Resolve video/playlist dimension IDs to title columns",
    ),
):
    """Run a custom analytics query with any metrics and dimensions.

    Direct access to the YouTube Analytics API reports.query endpoint.
    Supports all available metrics and dimensions.

    Examples:

        ytstudio analytics query -m views,likes --dimensions day --days 7

        ytstudio analytics query -m views,shares -d country --sort -views -n 10

        ytstudio analytics query -m views,estimatedMinutesWatched -d video \\
            --sort -views -n 5 --resolve -o json

        ytstudio analytics query -m videoThumbnailImpressions,videoThumbnailImpressionsClickRate \\
            -d video --sort -videoThumbnailImpressions -n 10

        ytstudio analytics query -m views -d insightTrafficSourceType \\
            -f video==dMH0bHeiRNg --sort -views
    """
    set_raw_output(raw)

    # Parse and validate
    metric_names = _parse_comma_list(metrics_str)
    if not metric_names:
        console.print("[red]At least one metric is required[/red]")
        raise typer.Exit(1)

    errors = validate_metrics(metric_names)
    if errors:
        for err in errors:
            console.print(f"[red]{err}[/red]")
        console.print("\nRun [bold]ytstudio analytics metrics[/bold] to see available metrics.")
        raise typer.Exit(1)

    dimension_names = _parse_comma_list(dimensions_str) if dimensions_str else []
    if dimension_names:
        errors = validate_dimensions(dimension_names)
        if errors:
            for err in errors:
                console.print(f"[red]{err}[/red]")
            console.print(
                "\nRun [bold]ytstudio analytics dimensions[/bold] to see available dimensions."
            )
            raise typer.Exit(1)

    # Build filters string
    filters_str = None
    if filter_list:
        for f in filter_list:
            if "==" not in f:
                console.print(f"[red]Invalid filter format: '{f}'. Use key==value[/red]")
                raise typer.Exit(1)
        filters_str = ";".join(filter_list)

    # Build dates, then snap to dimension-required boundaries (month, week).
    end_date = end or datetime.now().strftime("%Y-%m-%d")
    start_date = start or (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    start_date, end_date = _align_date_range(dimension_names, start_date, end_date)

    # The video dimension requires sort + maxResults per YouTube API docs
    if DimensionName.VIDEO in dimension_names and (not sort or not limit):
        missing = [x for x, v in [("--sort", sort), ("--limit", limit)] if not v]
        console.print(f"[red]The 'video' dimension requires {' and '.join(missing)}[/red]")
        console.print(f"Example: -d video --sort -{metric_names[0]} -n 10")
        raise typer.Exit(1)

    # Execute query
    data_service = get_data_service()
    analytics_service = get_analytics_service()
    response = fetch_query(
        data_service,
        analytics_service,
        metric_names=metric_names,
        dimension_names=dimension_names,
        start_date=start_date,
        end_date=end_date,
        days=days,
        filters_str=filters_str,
        sort=sort,
        max_results=limit,
        currency=currency,
    )

    if resolve:
        response = _resolve_query_dimension_titles(data_service, response)

    _format_query_response(response, output)


# --- Discovery commands ---


@app.command("metrics")
def list_metrics(
    group: str = typer.Option(None, "--group", "-g", help="Filter by group"),
    output: str = typer.Option("table", "--output", "-o", help="Output format: table, json"),
):
    """List available analytics metrics.

    Examples:

        ytstudio analytics metrics

        ytstudio analytics metrics --group engagement
    """
    filtered = METRICS.values()
    if group:
        if group not in METRIC_GROUPS:
            console.print(
                f"[red]Unknown group '{group}'. Available: {', '.join(METRIC_GROUPS)}[/red]"
            )
            raise typer.Exit(1)
        filtered = [m for m in filtered if m.group == group]

    if output == "json":
        print(
            json.dumps(
                [
                    {
                        "name": m.name,
                        "description": m.description,
                        "group": m.group,
                        "core": m.core,
                        "monetary": m.monetary,
                    }
                    for m in filtered
                ],
                indent=2,
            )
        )
        return

    title = "Available Metrics"
    if group:
        title += f" ({group})"
    console.print(f"\n[bold]{title}[/bold]\n")

    table = create_table()
    table.add_column("Metric", style="bold")
    table.add_column("Description")
    table.add_column("Group", style="dim")
    table.add_column("", justify="right")  # tags

    for m in filtered:
        tags = []
        if m.core:
            tags.append("[cyan]core[/cyan]")
        if m.monetary:
            tags.append("[yellow]$[/yellow]")
        table.add_row(m.name, m.description, m.group, " ".join(tags))

    console.print(table)

    if not group:
        console.print(f"\n{dim(f'Groups: {", ".join(METRIC_GROUPS)}')}")
        console.print(dim("Filter with --group <name>"))
    console.print()


@app.command("dimensions")
def list_dimensions(
    group: str = typer.Option(None, "--group", "-g", help="Filter by group"),
    name: str = typer.Argument(None, help="Show details for a specific dimension"),
    output: str = typer.Option("table", "--output", "-o", help="Output format: table, json"),
):
    """List available analytics dimensions.

    Examples:

        ytstudio analytics dimensions

        ytstudio analytics dimensions --group geographic

        ytstudio analytics dimensions country
    """
    if name:
        if name not in DIMENSIONS:
            console.print(f"[red]Unknown dimension '{name}'[/red]")
            suggestion = find_closest_dimension(name)
            if suggestion:
                console.print(f"Did you mean [bold]{suggestion}[/bold]?")
            raise typer.Exit(1)

        d = DIMENSIONS[name]
        if output == "json":
            print(
                json.dumps(
                    {
                        "name": d.name,
                        "description": d.description,
                        "group": d.group,
                        "filter_only": d.filter_only,
                    },
                    indent=2,
                )
            )
            return

        console.print(f"\n[bold]{d.name}[/bold]")
        console.print(f"  {d.description}")
        console.print(f"  group: {dim(d.group)}")
        if d.filter_only:
            console.print("  [yellow]filter only[/yellow] (cannot be used as a dimension)")
        console.print()
        return

    # List dimensions
    filtered = DIMENSIONS.values()
    if group:
        if group not in DIMENSION_GROUPS:
            console.print(
                f"[red]Unknown group '{group}'. Available: {', '.join(DIMENSION_GROUPS)}[/red]"
            )
            raise typer.Exit(1)
        filtered = [d for d in filtered if d.group == group]

    if output == "json":
        print(
            json.dumps(
                [
                    {
                        "name": d.name,
                        "description": d.description,
                        "group": d.group,
                        "filter_only": d.filter_only,
                    }
                    for d in filtered
                ],
                indent=2,
            )
        )
        return

    title = "Available Dimensions"
    if group:
        title += f" ({group})"
    console.print(f"\n[bold]{title}[/bold]\n")

    table = create_table()
    table.add_column("Dimension", style="bold")
    table.add_column("Description")
    table.add_column("Group", style="dim")
    table.add_column("", justify="right")

    for d in filtered:
        tag = "[yellow]filter[/yellow]" if d.filter_only else ""
        table.add_row(d.name, d.description, d.group, tag)

    console.print(table)

    if not group:
        console.print(f"\n{dim(f'Groups: {", ".join(DIMENSION_GROUPS)}')}")
        console.print(dim("Filter with --group <name>"))
    console.print()
