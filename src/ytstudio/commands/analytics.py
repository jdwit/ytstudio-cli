import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta

import typer

from ytstudio.auth import api, get_authenticated_service
from ytstudio.demo import DEMO_ANALYTICS, is_demo_mode
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
        print(json.dumps({"video": video_data, "analytics": asdict(analytics) if analytics else None}, indent=2))
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
