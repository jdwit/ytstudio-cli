import csv
import io
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta

import typer

from ytstudio.auth import api, get_authenticated_service
from ytstudio.demo import DEMO_ANALYTICS, is_demo_mode
from ytstudio.registry import (
    DIMENSION_GROUPS,
    DIMENSIONS,
    METRIC_GROUPS,
    METRICS,
    find_closest_dimension,
    find_closest_metric,
    validate_dimensions,
    validate_metrics,
)
from ytstudio.ui import console, create_kv_table, create_table, dim, format_number

app = typer.Typer(help="Analytics commands")


@dataclass
class ChannelAnalytics:
    views: int
    watch_time_hours: int
    avg_view_duration: str
    subscribers_gained: int
    subscribers_lost: int
    likes: int
    comments: int
    impressions: int | None = None
    ctr: float | None = None


@dataclass
class VideoAnalytics:
    views: int
    watch_time_minutes: int
    avg_view_duration_secs: int
    avg_view_percentage: float
    likes: int
    comments: int


# Available metrics: https://developers.google.com/youtube/analytics/metrics

CHANNEL_METRICS = (
    "views",
    "estimatedMinutesWatched",
    "averageViewDuration",
    "subscribersGained",
    "subscribersLost",
    "likes",
    "comments",
)

VIDEO_METRICS = (
    "views",
    "estimatedMinutesWatched",
    "averageViewDuration",
    "averageViewPercentage",
    "likes",
    "comments",
)

TOP_VIDEO_METRICS = (
    "views",
    "estimatedMinutesWatched",
    "likes",
)


def get_services():
    if is_demo_mode():
        return None, None

    data_service = get_authenticated_service("youtube", "v3")
    analytics_service = get_authenticated_service("youtubeAnalytics", "v2")

    return data_service, analytics_service


def get_channel_id(service) -> str:
    response = api(service.channels().list(part="id", mine=True))
    if not response.get("items"):
        console.print("[red]No channel found[/red]")
        raise typer.Exit(1)
    return response["items"][0]["id"]


def fetch_channel_analytics(data_service, analytics_service, days: int) -> ChannelAnalytics | None:
    if is_demo_mode():
        return ChannelAnalytics(
            views=DEMO_ANALYTICS["views"],
            watch_time_hours=DEMO_ANALYTICS["watch_time_hours"],
            avg_view_duration=DEMO_ANALYTICS["avg_view_duration"],
            subscribers_gained=DEMO_ANALYTICS["subscribers_gained"],
            subscribers_lost=DEMO_ANALYTICS["subscribers_lost"],
            likes=DEMO_ANALYTICS["likes"],
            comments=DEMO_ANALYTICS["comments"],
            impressions=DEMO_ANALYTICS.get("impressions"),
            ctr=DEMO_ANALYTICS.get("ctr"),
        )

    if not analytics_service:
        return None

    channel_id = get_channel_id(data_service)
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    response = api(
        analytics_service.reports().query(
            ids=f"channel=={channel_id}",
            startDate=start_date,
            endDate=end_date,
            metrics=",".join(CHANNEL_METRICS),
        )
    )

    if not response.get("rows"):
        return None

    row = response["rows"][0]
    metrics = {h["name"]: row[i] for i, h in enumerate(response["columnHeaders"])}
    avg_duration_secs = int(metrics.get("averageViewDuration", 0))

    return ChannelAnalytics(
        views=int(metrics.get("views", 0)),
        watch_time_hours=int(metrics.get("estimatedMinutesWatched", 0) / 60),
        avg_view_duration=f"{avg_duration_secs // 60}:{avg_duration_secs % 60:02d}",
        subscribers_gained=int(metrics.get("subscribersGained", 0)),
        subscribers_lost=int(metrics.get("subscribersLost", 0)),
        likes=int(metrics.get("likes", 0)),
        comments=int(metrics.get("comments", 0)),
    )


@app.command()
def overview(
    days: int = typer.Option(28, "--days", "-d", help="Number of days to analyze"),
    output: str = typer.Option("table", "--output", "-o", help="Output format: table, json"),
):
    """Get channel overview analytics"""
    data_service, analytics_service = get_services()
    analytics = fetch_channel_analytics(data_service, analytics_service, days)

    if output == "json":
        print(json.dumps({"analytics": asdict(analytics), "days": days}, indent=2))
        return

    console.print(f"\n[bold]Channel Analytics[/bold] {dim(f'(last {days} days)')}\n")
    table = create_kv_table()

    table.add_row(dim("views"), format_number(analytics.views))
    table.add_row(dim("watch time"), f"{analytics.watch_time_hours} hours")
    table.add_row(dim("avg duration"), analytics.avg_view_duration)
    table.add_row(dim("subscribers gained"), f"[green]+{analytics.subscribers_gained}[/green]")
    table.add_row(dim("subscribers lost"), f"[red]-{analytics.subscribers_lost}[/red]")
    table.add_row(dim("likes"), format_number(analytics.likes))
    table.add_row(dim("comments"), format_number(analytics.comments))

    if analytics.impressions:
        table.add_row(dim("impressions"), format_number(analytics.impressions))
    if analytics.ctr:
        table.add_row(dim("CTR"), f"{analytics.ctr}%")

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
            metrics=",".join(VIDEO_METRICS),
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
    data_service, analytics_service = get_services()

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


@app.command()
def traffic(
    video_id: str = typer.Argument(..., help="Video ID"),
    days: int = typer.Option(28, "--days", "-d", help="Number of days to analyze"),
    output: str = typer.Option("table", "--output", "-o", help="Output format: table, json"),
):
    """Get traffic source data for a video"""
    data_service, analytics_service = get_services()
    channel_id = get_channel_id(data_service)
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    response = api(
        analytics_service.reports().query(
            ids=f"channel=={channel_id}",
            startDate=start_date,
            endDate=end_date,
            metrics="views",
            dimensions="insightTrafficSourceType",
            filters=f"video=={video_id}",
            sort="-views",
        )
    )

    if output == "json":
        print(json.dumps(response, indent=2))
        return

    if response.get("rows"):
        console.print(f"\n[bold]Traffic Sources[/bold] {dim(f'(last {days} days)')}\n")
        table = create_table()
        table.add_column("Source", style="dim")
        table.add_column("Views", justify="right")

        for row in response["rows"]:
            table.add_row(row[0], format_number(int(row[1])))

        console.print(table)
    else:
        console.print("[yellow]No traffic data available[/yellow]")


@app.command()
def top(
    days: int = typer.Option(28, "--days", "-d", help="Number of days to analyze"),
    limit: int = typer.Option(10, "--limit", "-n", help="Number of videos"),
    output: str = typer.Option("table", "--output", "-o", help="Output format: table, json"),
):
    """Show top performing videos"""
    data_service, analytics_service = get_services()
    channel_id = get_channel_id(data_service)
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    response = api(
        analytics_service.reports().query(
            ids=f"channel=={channel_id}",
            startDate=start_date,
            endDate=end_date,
            metrics=",".join(TOP_VIDEO_METRICS),
            dimensions="video",
            sort="-views",
            maxResults=limit,
        )
    )

    if output == "json":
        print(json.dumps(response, indent=2))
        return

    if response.get("rows"):
        video_ids = [row[0] for row in response["rows"]]
        videos_response = api(data_service.videos().list(part="snippet", id=",".join(video_ids)))

        title_map = {v["id"]: v["snippet"]["title"] for v in videos_response.get("items", [])}

        console.print(f"\n[bold]Top {limit} Videos[/bold] {dim(f'(last {days} days)')}\n")
        table = create_table()
        table.add_column("Title", max_width=40)
        table.add_column("Views", justify="right")
        table.add_column("Watch time", justify="right", style="dim")

        for row in response["rows"]:
            video_id, views, watch_time, _likes = row[0], row[1], row[2], row[3]
            title = title_map.get(video_id, video_id)

            table.add_row(
                title[:40],
                format_number(int(views)),
                f"{int(watch_time / 60)}h",
            )

        console.print(table)


# --- Raw query engine ---


def _parse_comma_list(value: str) -> list[str]:
    """Split a comma-separated string, stripping whitespace."""
    return [v.strip() for v in value.split(",") if v.strip()]


def _format_query_response(response: dict, output: str) -> None:
    """Format and print a raw API response in the requested format."""
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
            style="dim" if header in DIMENSIONS else None,
        )

    for row in rows:
        table.add_row(*[_format_cell(headers[i], v) for i, v in enumerate(row)])

    console.print(table)


def _format_cell(header: str, value) -> str:
    """Format a cell value for table display."""
    if isinstance(value, float):
        if "rate" in header.lower() or "percentage" in header.lower() or "ctr" in header.lower():
            return f"{value:.2f}%"
        if "cpm" in header.lower():
            return f"${value:.2f}"
        return f"{value:.1f}"
    if isinstance(value, int) or (isinstance(value, float) and value == int(value)):
        return format_number(int(value))
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
):
    """Run a custom analytics query with any metrics and dimensions.

    Direct access to the YouTube Analytics API reports.query endpoint.
    Supports all available metrics and dimensions.

    Examples:

        ytstudio analytics query -m views,likes --dimensions day --days 7

        ytstudio analytics query -m views,shares -d country --sort -views -n 10

        ytstudio analytics query -m views,estimatedMinutesWatched -d video \\
            --sort -views -n 5 -o json

        ytstudio analytics query -m videoThumbnailImpressions,videoThumbnailImpressionsClickRate \\
            -d video --sort -videoThumbnailImpressions -n 10

        ytstudio analytics query -m views -d insightTrafficSourceType \\
            -f video==dMH0bHeiRNg --sort -views
    """
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

    # Build dates
    end_date = end or datetime.now().strftime("%Y-%m-%d")
    start_date = start or (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    # Execute query
    data_service, analytics_service = get_services()
    if not analytics_service:
        console.print("[red]Analytics service not available[/red]")
        raise typer.Exit(1)

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
    if limit:
        query_params["maxResults"] = limit
    if currency:
        query_params["currency"] = currency

    response = api(analytics_service.reports().query(**query_params))

    _format_query_response(response, output)


# --- Discovery commands ---


@app.command("metrics")
def list_metrics(
    group: str = typer.Option(None, "--group", "-g", help="Filter by group"),
    name: str = typer.Argument(None, help="Show details for a specific metric"),
    output: str = typer.Option("table", "--output", "-o", help="Output format: table, json"),
):
    """List available analytics metrics.

    Examples:

        ytstudio analytics metrics

        ytstudio analytics metrics --group engagement

        ytstudio analytics metrics views
    """
    if name:
        # Show detail for a single metric
        if name not in METRICS:
            console.print(f"[red]Unknown metric '{name}'[/red]")
            suggestion = find_closest_metric(name)
            if suggestion:
                console.print(f"Did you mean [bold]{suggestion}[/bold]?")
            raise typer.Exit(1)

        m = METRICS[name]
        if output == "json":
            print(
                json.dumps(
                    {
                        "name": m.name,
                        "description": m.description,
                        "group": m.group,
                        "core": m.core,
                        "monetary": m.monetary,
                    },
                    indent=2,
                )
            )
            return

        console.print(f"\n[bold]{m.name}[/bold]")
        console.print(f"  {m.description}")
        console.print(f"  group: {dim(m.group)}")
        tags = []
        if m.core:
            tags.append("[cyan]core[/cyan]")
        if m.monetary:
            tags.append("[yellow]monetary[/yellow]")
        if tags:
            console.print(f"  {' '.join(tags)}")
        console.print()
        return

    # List metrics
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
