"""Analytics commands."""

import json
from datetime import datetime, timedelta

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ytcli.auth import get_authenticated_service
from ytcli.commands.videos import fetch_videos

app = typer.Typer(help="Analytics commands")
console = Console()


def format_number(n: int) -> str:
    """Format large numbers."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def get_services():
    """Get YouTube Data API and Analytics API services."""
    data_service = get_authenticated_service("youtube", "v3")
    analytics_service = get_authenticated_service("youtubeAnalytics", "v2")

    if not data_service:
        console.print("[red]Not authenticated. Run 'yt login' first.[/red]")
        raise typer.Exit(1)

    return data_service, analytics_service


def get_channel_id(service) -> str:
    """Get the authenticated user's channel ID."""
    response = service.channels().list(part="id", mine=True).execute()
    if not response.get("items"):
        console.print("[red]No channel found[/red]")
        raise typer.Exit(1)
    return response["items"][0]["id"]


@app.command()
def overview(
    days: int = typer.Option(28, "--days", "-d", help="Number of days to analyze"),
    output: str = typer.Option("table", "--output", "-o", help="Output format: table, json"),
):
    """Get channel overview analytics."""
    data_service, analytics_service = get_services()

    if not analytics_service:
        console.print("[yellow]Analytics API not available. Showing basic stats.[/yellow]\n")

        # Fallback to basic channel stats
        response = (
            data_service.channels()
            .list(
                part="snippet,statistics",
                mine=True,
            )
            .execute()
        )

        if not response.get("items"):
            console.print("[red]No channel found[/red]")
            raise typer.Exit(1)

        channel = response["items"][0]
        snippet = channel["snippet"]
        stats = channel["statistics"]

        if output == "json":
            print(json.dumps(channel, indent=2))
            return

        console.print(
            Panel(
                f"[bold]{snippet['title']}[/bold]\n\n"
                f"Subscribers: {format_number(int(stats.get('subscriberCount', 0)))}\n"
                f"Total views: {format_number(int(stats.get('viewCount', 0)))}\n"
                f"Videos: {stats.get('videoCount', 0)}",
                title="Channel Overview",
            )
        )
        return

    channel_id = get_channel_id(data_service)
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    response = (
        analytics_service.reports()
        .query(
            ids=f"channel=={channel_id}",
            startDate=start_date,
            endDate=end_date,
            metrics="views,estimatedMinutesWatched,averageViewDuration,subscribersGained,subscribersLost,likes,comments",
        )
        .execute()
    )

    if output == "json":
        print(json.dumps(response, indent=2))
        return

    if response.get("rows"):
        row = response["rows"][0]
        metrics = {h["name"]: row[i] for i, h in enumerate(response["columnHeaders"])}

        table = Table(title=f"Channel Analytics (last {days} days)")
        table.add_column("Metric")
        table.add_column("Value", justify="right")

        table.add_row("Views", format_number(int(metrics.get("views", 0))))
        table.add_row("Watch time", f"{int(metrics.get('estimatedMinutesWatched', 0) / 60)} hours")
        table.add_row(
            "Avg view duration",
            f"{int(metrics.get('averageViewDuration', 0) / 60)}:{int(metrics.get('averageViewDuration', 0) % 60):02d}",
        )
        table.add_row("Subscribers gained", f"+{int(metrics.get('subscribersGained', 0))}")
        table.add_row("Subscribers lost", f"-{int(metrics.get('subscribersLost', 0))}")
        table.add_row("Likes", format_number(int(metrics.get("likes", 0))))
        table.add_row("Comments", format_number(int(metrics.get("comments", 0))))

        console.print(table)
    else:
        console.print("[yellow]No analytics data available[/yellow]")


@app.command()
def video(
    video_id: str = typer.Argument(..., help="Video ID"),
    days: int = typer.Option(28, "--days", "-d", help="Number of days to analyze"),
    output: str = typer.Option("table", "--output", "-o", help="Output format: table, json"),
):
    """Get analytics for a specific video."""
    data_service, analytics_service = get_services()

    # Get video info first
    video_response = (
        data_service.videos()
        .list(
            part="snippet,statistics",
            id=video_id,
        )
        .execute()
    )

    if not video_response.get("items"):
        console.print(f"[red]Video not found: {video_id}[/red]")
        raise typer.Exit(1)

    video = video_response["items"][0]
    snippet = video["snippet"]
    stats = video["statistics"]

    if not analytics_service:
        if output == "json":
            print(json.dumps(video, indent=2))
            return

        console.print(f"\n[bold]{snippet['title']}[/bold]")
        console.print(f"[dim]https://youtu.be/{video_id}[/dim]\n")

        table = Table(show_header=False, box=None)
        table.add_column("metric", style="dim")
        table.add_column("value", style="bold")

        table.add_row("views", format_number(int(stats.get("viewCount", 0))))
        table.add_row("likes", format_number(int(stats.get("likeCount", 0))))
        table.add_row("comments", format_number(int(stats.get("commentCount", 0))))

        views = int(stats.get("viewCount", 0))
        likes = int(stats.get("likeCount", 0))
        comments = int(stats.get("commentCount", 0))
        engagement = (likes + comments) / views * 100 if views else 0
        table.add_row("engagement", f"{engagement:.2f}%")

        console.print(table)
        return

    channel_id = get_channel_id(data_service)
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    response = (
        analytics_service.reports()
        .query(
            ids=f"channel=={channel_id}",
            startDate=start_date,
            endDate=end_date,
            metrics="views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,likes,comments",
            filters=f"video=={video_id}",
        )
        .execute()
    )

    if output == "json":
        print(json.dumps({"video": video, "analytics": response}, indent=2))
        return

    console.print(f"\n[bold]{snippet['title']}[/bold]")
    console.print(f"[dim]https://youtu.be/{video_id}[/dim]\n")

    if response.get("rows"):
        row = response["rows"][0]
        metrics = {h["name"]: row[i] for i, h in enumerate(response["columnHeaders"])}

        table = Table(title=f"Video Analytics (last {days} days)")
        table.add_column("Metric")
        table.add_column("Value", justify="right")

        table.add_row("Views", format_number(int(metrics.get("views", 0))))
        table.add_row("Watch time", f"{int(metrics.get('estimatedMinutesWatched', 0))} min")
        table.add_row("Avg view duration", f"{int(metrics.get('averageViewDuration', 0))}s")
        table.add_row("Avg % viewed", f"{metrics.get('averageViewPercentage', 0):.1f}%")
        table.add_row("Likes", format_number(int(metrics.get("likes", 0))))
        table.add_row("Comments", format_number(int(metrics.get("comments", 0))))

        console.print(table)


@app.command()
def traffic(
    video_id: str = typer.Argument(..., help="Video ID"),
    days: int = typer.Option(28, "--days", "-d", help="Number of days to analyze"),
    output: str = typer.Option("table", "--output", "-o", help="Output format: table, json"),
):
    """Get traffic source data for a video."""
    data_service, analytics_service = get_services()

    if not analytics_service:
        console.print("[yellow]Analytics API required for traffic sources[/yellow]")
        raise typer.Exit(1)

    channel_id = get_channel_id(data_service)
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    response = (
        analytics_service.reports()
        .query(
            ids=f"channel=={channel_id}",
            startDate=start_date,
            endDate=end_date,
            metrics="views",
            dimensions="insightTrafficSourceType",
            filters=f"video=={video_id}",
            sort="-views",
        )
        .execute()
    )

    if output == "json":
        print(json.dumps(response, indent=2))
        return

    if response.get("rows"):
        table = Table(title=f"Traffic Sources (last {days} days)")
        table.add_column("Source")
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
    """Show top performing videos."""
    data_service, analytics_service = get_services()

    if not analytics_service:
        # Fallback: get videos and sort by views

        result = fetch_videos(data_service, limit=50)
        videos = sorted(result["videos"], key=lambda x: x["views"], reverse=True)[:limit]

        if output == "json":
            print(json.dumps(videos, indent=2))
            return

        table = Table(title=f"Top {limit} Videos by Views")
        table.add_column("Title", max_width=40)
        table.add_column("Views", justify="right")
        table.add_column("Likes", justify="right")
        table.add_column("Engagement", justify="right")

        for v in videos:
            eng = (v["likes"] + v["comments"]) / v["views"] * 100 if v["views"] else 0
            table.add_row(
                v["title"][:40],
                format_number(v["views"]),
                format_number(v["likes"]),
                f"{eng:.1f}%",
            )

        console.print(table)
        return

    channel_id = get_channel_id(data_service)
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    response = (
        analytics_service.reports()
        .query(
            ids=f"channel=={channel_id}",
            startDate=start_date,
            endDate=end_date,
            metrics="views,estimatedMinutesWatched,likes",
            dimensions="video",
            sort="-views",
            maxResults=limit,
        )
        .execute()
    )

    if output == "json":
        print(json.dumps(response, indent=2))
        return

    if response.get("rows"):
        video_ids = [row[0] for row in response["rows"]]
        videos_response = (
            data_service.videos()
            .list(
                part="snippet",
                id=",".join(video_ids),
            )
            .execute()
        )

        title_map = {v["id"]: v["snippet"]["title"] for v in videos_response.get("items", [])}

        table = Table(title=f"Top {limit} Videos (last {days} days)")
        table.add_column("Title", max_width=40)
        table.add_column("Views", justify="right")
        table.add_column("Watch time", justify="right")

        for row in response["rows"]:
            video_id, views, watch_time, _likes = row[0], row[1], row[2], row[3]
            title = title_map.get(video_id, video_id)

            table.add_row(
                title[:40],
                format_number(int(views)),
                f"{int(watch_time / 60)}h",
            )

        console.print(table)
