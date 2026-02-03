"""Analytics commands."""

import json
from datetime import datetime, timedelta

import typer
from rich.panel import Panel

from ytcli.auth import api, get_authenticated_service
from ytcli.commands.videos import fetch_videos
from ytcli.demo import DEMO_ANALYTICS, DEMO_CHANNEL, is_demo_mode
from ytcli.ui import console, create_kv_table, create_table, dim, format_number

app = typer.Typer(help="Analytics commands")


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
    response = api(service.channels().list(part="id", mine=True))
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
    if is_demo_mode():
        if output == "json":
            print(
                json.dumps(
                    {"channel": DEMO_CHANNEL, "analytics": DEMO_ANALYTICS, "days": days}, indent=2
                )
            )
            return

        table = create_kv_table()

        table.add_row(dim("views"), format_number(DEMO_ANALYTICS["views"]))
        table.add_row(dim("watch time"), f"{DEMO_ANALYTICS['watch_time_hours']} hours")
        table.add_row(dim("avg duration"), DEMO_ANALYTICS["avg_view_duration"])
        table.add_row(dim("subs gained"), f"[green]+{DEMO_ANALYTICS['subscribers_gained']}[/green]")
        table.add_row(dim("subs lost"), f"[red]-{DEMO_ANALYTICS['subscribers_lost']}[/red]")
        table.add_row(dim("likes"), format_number(DEMO_ANALYTICS["likes"]))
        table.add_row(dim("comments"), format_number(DEMO_ANALYTICS["comments"]))
        table.add_row(dim("impressions"), format_number(DEMO_ANALYTICS["impressions"]))
        table.add_row(dim("CTR"), f"{DEMO_ANALYTICS['ctr']}%")

        console.print(f"\n[bold]Channel Analytics[/bold] {dim(f'(last {days} days)')}\n")
        console.print(table)
        return

    data_service, analytics_service = get_services()

    if not analytics_service:
        console.print("[yellow]Analytics API not available. Showing basic stats.[/yellow]\n")

        response = api(data_service.channels().list(part="snippet,statistics", mine=True))

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

    response = api(
        analytics_service.reports().query(
            ids=f"channel=={channel_id}",
            startDate=start_date,
            endDate=end_date,
            metrics="views,estimatedMinutesWatched,averageViewDuration,subscribersGained,subscribersLost,likes,comments",
        )
    )

    if output == "json":
        print(json.dumps(response, indent=2))
        return

    if response.get("rows"):
        row = response["rows"][0]
        metrics = {h["name"]: row[i] for i, h in enumerate(response["columnHeaders"])}

        console.print(f"\n[bold]Channel Analytics[/bold] {dim(f'(last {days} days)')}\n")
        table = create_kv_table()

        table.add_row(dim("views"), format_number(int(metrics.get("views", 0))))
        table.add_row(
            dim("watch time"), f"{int(metrics.get('estimatedMinutesWatched', 0) / 60)} hours"
        )
        table.add_row(
            dim("avg duration"),
            f"{int(metrics.get('averageViewDuration', 0) / 60)}:{int(metrics.get('averageViewDuration', 0) % 60):02d}",
        )
        table.add_row(
            dim("subs gained"), f"[green]+{int(metrics.get('subscribersGained', 0))}[/green]"
        )
        table.add_row(dim("subs lost"), f"[red]-{int(metrics.get('subscribersLost', 0))}[/red]")
        table.add_row(dim("likes"), format_number(int(metrics.get("likes", 0))))
        table.add_row(dim("comments"), format_number(int(metrics.get("comments", 0))))

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

    video_response = api(data_service.videos().list(part="snippet,statistics", id=video_id))

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

        table = create_kv_table()
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

    response = api(
        analytics_service.reports().query(
            ids=f"channel=={channel_id}",
            startDate=start_date,
            endDate=end_date,
            metrics="views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,likes,comments",
            filters=f"video=={video_id}",
        )
    )

    if output == "json":
        print(json.dumps({"video": video, "analytics": response}, indent=2))
        return

    console.print(f"\n[bold]{snippet['title']}[/bold]")
    console.print(f"[dim]https://youtu.be/{video_id}[/dim]\n")

    if response.get("rows"):
        row = response["rows"][0]
        metrics = {h["name"]: row[i] for i, h in enumerate(response["columnHeaders"])}

        console.print(f"[bold]Analytics[/bold] {dim(f'(last {days} days)')}\n")
        table = create_kv_table()

        table.add_row(dim("views"), format_number(int(metrics.get("views", 0))))
        table.add_row(dim("watch time"), f"{int(metrics.get('estimatedMinutesWatched', 0))} min")
        table.add_row(dim("avg duration"), f"{int(metrics.get('averageViewDuration', 0))}s")
        table.add_row(dim("avg % viewed"), f"{metrics.get('averageViewPercentage', 0):.1f}%")
        table.add_row(dim("likes"), format_number(int(metrics.get("likes", 0))))
        table.add_row(dim("comments"), format_number(int(metrics.get("comments", 0))))

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
    """Show top performing videos."""
    data_service, analytics_service = get_services()

    if not analytics_service:
        result = fetch_videos(data_service, limit=50)
        videos = sorted(result["videos"], key=lambda x: x["views"], reverse=True)[:limit]

        if output == "json":
            print(json.dumps(videos, indent=2))
            return

        console.print(f"\n[bold]Top {limit} Videos by Views[/bold]\n")
        table = create_table()
        table.add_column("Title", max_width=40)
        table.add_column("Views", justify="right")
        table.add_column("Likes", justify="right")
        table.add_column("Engagement", justify="right", style="dim")

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

    response = api(
        analytics_service.reports().query(
            ids=f"channel=={channel_id}",
            startDate=start_date,
            endDate=end_date,
            metrics="views,estimatedMinutesWatched,likes",
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
