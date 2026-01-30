"""Video management commands."""

import json
import sys

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Video management commands")
console = Console()


@app.command("list")
def list_videos(
    limit: int = typer.Option(20, "--limit", "-n", help="Number of videos to list (max 50)"),
    page_token: str = typer.Option(None, "--page-token", "-p", help="Page token for pagination"),
    output: str = typer.Option("table", "--output", "-o", help="Output format: table, json, csv"),
):
    """List your YouTube videos."""
    from ytcli.auth import get_authenticated_service

    service = get_authenticated_service()
    if not service:
        console.print("[red]Not authenticated. Run 'yt login' first.[/red]")
        raise typer.Exit(1)

    # Cap limit at 50 (YouTube API max)
    limit = min(limit, 50)

    # Get channel's uploads playlist
    channels_response = service.channels().list(
        part="contentDetails",
        mine=True,
    ).execute()

    if not channels_response.get("items"):
        console.print("[red]No channel found[/red]")
        raise typer.Exit(1)

    uploads_playlist_id = channels_response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

    # Get videos from uploads playlist
    playlist_response = service.playlistItems().list(
        part="snippet,contentDetails",
        playlistId=uploads_playlist_id,
        maxResults=limit,
        pageToken=page_token,
    ).execute()

    videos = []
    video_ids = []

    for item in playlist_response.get("items", []):
        video_ids.append(item["contentDetails"]["videoId"])
        videos.append({
            "id": item["contentDetails"]["videoId"],
            "title": item["snippet"]["title"],
            "published_at": item["snippet"]["publishedAt"],
        })

    # Get additional video stats
    if video_ids:
        videos_response = service.videos().list(
            part="statistics,status",
            id=",".join(video_ids),
        ).execute()

        stats_map = {v["id"]: v for v in videos_response.get("items", [])}

        for video in videos:
            stats = stats_map.get(video["id"], {})
            video["views"] = int(stats.get("statistics", {}).get("viewCount", 0))
            video["likes"] = int(stats.get("statistics", {}).get("likeCount", 0))
            video["comments"] = int(stats.get("statistics", {}).get("commentCount", 0))
            video["privacy"] = stats.get("status", {}).get("privacyStatus", "unknown")

    result = {
        "videos": videos,
        "next_page_token": playlist_response.get("nextPageToken"),
        "total_results": playlist_response.get("pageInfo", {}).get("totalResults"),
    }

    # Output
    if output == "json":
        print(json.dumps(result, indent=2))
    elif output == "csv":
        print("id,title,views,likes,comments,privacy,published_at")
        for v in videos:
            title_escaped = v["title"].replace('"', '""')
            print(f'{v["id"]},"{title_escaped}",{v["views"]},{v["likes"]},{v["comments"]},{v["privacy"]},{v["published_at"]}')
    else:
        # Table output
        table = Table(title="Videos")
        table.add_column("ID", style="dim")
        table.add_column("Title", max_width=50)
        table.add_column("Views", justify="right")
        table.add_column("Likes", justify="right")
        table.add_column("Published")

        for v in videos:
            table.add_row(
                v["id"],
                v["title"][:50],
                f"{v['views']:,}",
                f"{v['likes']:,}",
                v["published_at"][:10],
            )

        console.print(table)

        if result["next_page_token"]:
            console.print(f"\n[dim]Next page: --page-token {result['next_page_token']}[/dim]")
        console.print(f"[dim]Total videos: {result['total_results']}[/dim]")


@app.command()
def get(
    video_id: str = typer.Argument(..., help="Video ID"),
    output: str = typer.Option("table", "--output", "-o", help="Output format: table, json"),
):
    """Get details for a specific video."""
    # TODO: implement
    console.print(f"[yellow]Getting video {video_id} not yet implemented[/yellow]")


@app.command()
def update(
    video_id: str = typer.Argument(..., help="Video ID"),
    title: str = typer.Option(None, "--title", "-t", help="New title"),
    description: str = typer.Option(None, "--description", "-d", help="New description"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show changes without applying"),
):
    """Update a video's metadata."""
    # TODO: implement
    console.print(f"[yellow]Updating video {video_id} not yet implemented[/yellow]")


@app.command("bulk-update")
def bulk_update(
    search: str = typer.Option(..., "--search", "-s", help="Text to search for"),
    replace: str = typer.Option(..., "--replace", "-r", help="Text to replace with"),
    field: str = typer.Option("title", "--field", "-f", help="Field to update: title, description"),
    dry_run: bool = typer.Option(True, "--dry-run/--execute", help="Preview changes without applying"),
):
    """Bulk update videos using search and replace."""
    # TODO: implement
    console.print("[yellow]Bulk update not yet implemented[/yellow]")
