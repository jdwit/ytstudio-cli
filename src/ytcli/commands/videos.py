"""Video management commands."""

import json
import re

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Video management commands")
console = Console()


def format_number(n: int) -> str:
    """Format large numbers (1234567 -> 1.2M)."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def get_service():
    """Get authenticated service or exit."""
    from ytcli.auth import get_authenticated_service

    service = get_authenticated_service()
    if not service:
        console.print("[red]Not authenticated. Run 'yt login' first.[/red]")
        raise typer.Exit(1)
    return service


def get_channel_uploads_playlist(service) -> str:
    """Get the uploads playlist ID for the authenticated channel."""
    response = service.channels().list(part="contentDetails", mine=True).execute()
    if not response.get("items"):
        console.print("[red]No channel found[/red]")
        raise typer.Exit(1)
    return response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]


def fetch_videos(service, limit: int = 50, page_token: str | None = None) -> dict:
    """Fetch videos with stats."""
    uploads_playlist_id = get_channel_uploads_playlist(service)

    playlist_response = (
        service.playlistItems()
        .list(
            part="snippet,contentDetails",
            playlistId=uploads_playlist_id,
            maxResults=min(limit, 50),
            pageToken=page_token,
        )
        .execute()
    )

    videos = []
    video_ids = []

    for item in playlist_response.get("items", []):
        video_ids.append(item["contentDetails"]["videoId"])
        videos.append(
            {
                "id": item["contentDetails"]["videoId"],
                "title": item["snippet"]["title"],
                "description": item["snippet"].get("description", ""),
                "published_at": item["snippet"]["publishedAt"],
            }
        )

    if video_ids:
        videos_response = (
            service.videos()
            .list(
                part="statistics,status,snippet,contentDetails",
                id=",".join(video_ids),
            )
            .execute()
        )

        stats_map = {v["id"]: v for v in videos_response.get("items", [])}

        for video in videos:
            data = stats_map.get(video["id"], {})
            stats = data.get("statistics", {})
            snippet = data.get("snippet", {})
            video["views"] = int(stats.get("viewCount", 0))
            video["likes"] = int(stats.get("likeCount", 0))
            video["comments"] = int(stats.get("commentCount", 0))
            video["privacy"] = data.get("status", {}).get("privacyStatus", "unknown")
            video["tags"] = snippet.get("tags", [])
            video["category_id"] = snippet.get("categoryId", "")
            video["duration"] = data.get("contentDetails", {}).get("duration", "")

    return {
        "videos": videos,
        "next_page_token": playlist_response.get("nextPageToken"),
        "total_results": playlist_response.get("pageInfo", {}).get("totalResults"),
    }


@app.command("list")
def list_videos(
    limit: int = typer.Option(20, "--limit", "-n", help="Number of videos to list"),
    page_token: str = typer.Option(None, "--page-token", "-p", help="Page token for pagination"),
    sort: str = typer.Option("date", "--sort", "-s", help="Sort by: date, views, likes"),
    output: str = typer.Option("table", "--output", "-o", help="Output format: table, json, csv"),
):
    """List your YouTube videos."""
    service = get_service()
    result = fetch_videos(service, limit, page_token)
    videos = result["videos"]

    # Sort
    if sort == "views":
        videos.sort(key=lambda x: x["views"], reverse=True)
    elif sort == "likes":
        videos.sort(key=lambda x: x["likes"], reverse=True)

    if output == "json":
        print(json.dumps(result, indent=2))
    elif output == "csv":
        print("id,title,views,likes,comments,privacy,published_at")
        for v in videos:
            title_escaped = v["title"].replace('"', '""')
            print(
                f'{v["id"]},"{title_escaped}",{v["views"]},{v["likes"]},{v["comments"]},{v["privacy"]},{v["published_at"]}'
            )
    else:
        table = Table(title=f"Videos ({result['total_results']} total)")
        table.add_column("Title", max_width=45)
        table.add_column("Views", justify="right")
        table.add_column("Likes", justify="right")
        table.add_column("Comments", justify="right")
        table.add_column("Published")

        for v in videos:
            table.add_row(
                v["title"][:45],
                format_number(v["views"]),
                format_number(v["likes"]),
                format_number(v["comments"]),
                v["published_at"][:10],
            )

        console.print(table)

        if result["next_page_token"]:
            console.print(f"\n[dim]Next page: --page-token {result['next_page_token']}[/dim]")


@app.command()
def get(
    video_id: str = typer.Argument(..., help="Video ID"),
    output: str = typer.Option("table", "--output", "-o", help="Output format: table, json"),
):
    """Get details for a specific video."""
    service = get_service()

    response = (
        service.videos()
        .list(
            part="snippet,statistics,contentDetails,status",
            id=video_id,
        )
        .execute()
    )

    if not response.get("items"):
        console.print(f"[red]Video not found: {video_id}[/red]")
        raise typer.Exit(1)

    video = response["items"][0]
    snippet = video["snippet"]
    stats = video["statistics"]
    content = video["contentDetails"]

    if output == "json":
        print(json.dumps(video, indent=2))
        return

    console.print(f"\n[bold]{snippet['title']}[/bold]")
    console.print(f"[dim]https://youtu.be/{video_id}[/dim]\n")

    table = Table(show_header=False, box=None)
    table.add_column("field", style="dim")
    table.add_column("value")

    table.add_row("views", format_number(int(stats.get("viewCount", 0))))
    table.add_row("likes", format_number(int(stats.get("likeCount", 0))))
    table.add_row("comments", format_number(int(stats.get("commentCount", 0))))
    table.add_row("duration", content.get("duration", "N/A"))
    table.add_row("published", snippet["publishedAt"][:10])
    table.add_row("privacy", video.get("status", {}).get("privacyStatus", "unknown"))

    console.print(table)

    if snippet.get("tags"):
        console.print(f"\n[dim]tags:[/dim] {', '.join(snippet['tags'][:15])}")

    console.print(f"\n[bold]description:[/bold]\n{snippet.get('description', '')[:500]}")


@app.command()
def update(
    video_id: str = typer.Argument(..., help="Video ID"),
    title: str = typer.Option(None, "--title", "-t", help="New title"),
    description: str = typer.Option(None, "--description", "-d", help="New description"),
    tags: str = typer.Option(None, "--tags", help="Comma-separated tags"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Preview without applying"),
):
    """Update a video's metadata."""
    if not any([title, description, tags]):
        console.print(
            "[yellow]Nothing to update. Provide --title, --description, or --tags[/yellow]"
        )
        raise typer.Exit(1)

    service = get_service()

    # Get current video data
    response = service.videos().list(part="snippet", id=video_id).execute()
    if not response.get("items"):
        console.print(f"[red]Video not found: {video_id}[/red]")
        raise typer.Exit(1)

    current = response["items"][0]["snippet"]

    # Build update
    new_title = title if title else current["title"]
    new_desc = description if description else current.get("description", "")
    new_tags = [t.strip() for t in tags.split(",")] if tags else current.get("tags", [])

    if dry_run:
        console.print("[bold]Dry run - changes:[/bold]\n")
        if title:
            console.print(f"title: {current['title'][:40]} → [green]{new_title[:40]}[/green]")
        if description:
            console.print("description: [green](updated)[/green]")
        if tags:
            console.print(f"tags: [green]{', '.join(new_tags[:5])}[/green]")
        console.print("\n[dim]Run without --dry-run to apply[/dim]")
        return

    body = {
        "id": video_id,
        "snippet": {
            "title": new_title,
            "description": new_desc,
            "tags": new_tags,
            "categoryId": current["categoryId"],
        },
    }

    service.videos().update(part="snippet", body=body).execute()
    console.print(f"[green]✓ Updated: {new_title}[/green]")


@app.command("bulk-update")
def bulk_update(
    search: str = typer.Option(..., "--search", "-s", help="Text to search for"),
    replace: str = typer.Option(..., "--replace", "-r", help="Text to replace with"),
    field: str = typer.Option("title", "--field", "-f", help="Field to update: title, description"),
    regex: bool = typer.Option(False, "--regex", help="Treat search as regex"),
    limit: int = typer.Option(100, "--limit", "-n", help="Max videos to process"),
    execute: bool = typer.Option(False, "--execute", help="Apply changes (default is dry-run)"),
):
    """Bulk update videos using search and replace."""
    service = get_service()
    result = fetch_videos(service, limit)
    videos = result["videos"]

    changes = []

    for video in videos:
        old_value = video.get(field, "")
        if regex:
            new_value = re.sub(search, replace, old_value)
        else:
            new_value = old_value.replace(search, replace)

        if new_value != old_value:
            changes.append(
                {
                    "id": video["id"],
                    "field": field,
                    "old": old_value,
                    "new": new_value,
                }
            )

    if not changes:
        console.print("[yellow]No matches found[/yellow]")
        return

    # Show preview
    table = Table(title=f"{'Pending' if not execute else 'Applying'} changes ({len(changes)})")
    table.add_column("Video ID", style="dim")
    table.add_column("Current")
    table.add_column("→", justify="center")
    table.add_column("New")

    for c in changes[:20]:
        table.add_row(
            c["id"][:11],
            c["old"][:30],
            "→",
            f"[green]{c['new'][:30]}[/green]",
        )

    if len(changes) > 20:
        table.add_row("...", f"and {len(changes) - 20} more", "", "")

    console.print(table)

    if not execute:
        console.print("\n[dim]Run with --execute to apply changes[/dim]")
        return

    # Apply changes
    console.print("\n[bold]Applying changes...[/bold]\n")
    success = 0
    failed = 0

    for c in changes:
        try:
            response = service.videos().list(part="snippet", id=c["id"]).execute()
            if not response.get("items"):
                continue

            snippet = response["items"][0]["snippet"]
            snippet[field] = c["new"]

            service.videos().update(
                part="snippet",
                body={"id": c["id"], "snippet": snippet},
            ).execute()

            console.print(f"[green]✓[/green] {c['id']}: {c['new'][:40]}")
            success += 1
        except Exception as e:
            console.print(f"[red]✗[/red] {c['id']}: {e}")
            failed += 1

    console.print(f"\n[bold]Done:[/bold] {success} updated, {failed} failed")
