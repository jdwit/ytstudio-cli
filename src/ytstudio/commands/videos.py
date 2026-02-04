"""Video management commands."""

import json
import re

import typer
from googleapiclient.errors import HttpError

from ytstudio.auth import api, get_authenticated_service, handle_api_error
from ytstudio.demo import DEMO_VIDEOS, get_demo_video, is_demo_mode
from ytstudio.ui import console, create_kv_table, create_table, bold, cyan, dim, error, format_number, muted

app = typer.Typer(help="Video management commands")


def format_duration(iso_duration: str) -> str:
    """Format ISO 8601 duration (PT1M19S -> 1:19)."""
    if not iso_duration:
        return ""
    
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', iso_duration)
    if not match:
        return ""
    
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def get_service():
    """Get authenticated service or exit. Returns None in demo mode."""
    if is_demo_mode():
        return None
    service = get_authenticated_service()
    if not service:
        console.print("[red]Not authenticated. Run 'yt login' first.[/red]")
        raise typer.Exit(1)
    return service


def get_channel_uploads_playlist(service) -> str:
    """Get the uploads playlist ID for the authenticated channel."""
    response = api(service.channels().list(part="contentDetails", mine=True))
    if not response.get("items"):
        console.print("[red]No channel found[/red]")
        raise typer.Exit(1)
    return response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]


def fetch_videos(service, limit: int = 50, page_token: str | None = None) -> dict:
    """Fetch videos with stats. Automatically paginates to reach limit."""
    uploads_playlist_id = get_channel_uploads_playlist(service)

    all_videos = []
    current_page_token = page_token
    total_results = None
    next_page_token = None

    while len(all_videos) < limit:
        batch_size = min(limit - len(all_videos), 50)
        
        playlist_response = api(
            service.playlistItems().list(
                part="snippet,contentDetails",
                playlistId=uploads_playlist_id,
                maxResults=batch_size,
                pageToken=current_page_token,
            )
        )

        if total_results is None:
            total_results = playlist_response.get("pageInfo", {}).get("totalResults", 0)

        items = playlist_response.get("items", [])
        if not items:
            break

        video_ids = [item["contentDetails"]["videoId"] for item in items]
        
        videos_response = api(
            service.videos().list(
                part="statistics,status,snippet,contentDetails",
                id=",".join(video_ids),
            )
        )

        stats_map = {v["id"]: v for v in videos_response.get("items", [])}

        for item in items:
            video_id = item["contentDetails"]["videoId"]
            data = stats_map.get(video_id, {})
            stats = data.get("statistics", {})
            snippet = data.get("snippet", {})
            content_details = data.get("contentDetails", {})
            
            all_videos.append({
                "id": video_id,
                "title": item["snippet"]["title"],
                "description": item["snippet"].get("description", ""),
                "published_at": item["snippet"]["publishedAt"],
                "views": int(stats.get("viewCount", 0)),
                "likes": int(stats.get("likeCount", 0)),
                "comments": int(stats.get("commentCount", 0)),
                "privacy": data.get("status", {}).get("privacyStatus", "unknown"),
                "tags": snippet.get("tags", []),
                "category_id": snippet.get("categoryId", ""),
                "duration": content_details.get("duration", ""),
                "licensed": content_details.get("licensedContent", False),
            })

        next_page_token = playlist_response.get("nextPageToken")
        if not next_page_token:
            break
        current_page_token = next_page_token

    return {
        "videos": all_videos,
        "next_page_token": next_page_token,
        "total_results": total_results,
    }


@app.command("list")
def list_videos(
    limit: int = typer.Option(20, "--limit", "-n", help="Number of videos to list"),
    page_token: str = typer.Option(None, "--page-token", "-p", help="Page token for pagination"),
    sort: str = typer.Option("date", "--sort", "-s", help="Sort by: date, views, likes"),
    output: str = typer.Option("table", "--output", "-o", help="Output format: table, json, csv"),
):
    """List your YouTube videos."""
    if is_demo_mode():
        videos = [
            {
                "id": v["id"],
                "title": v["title"],
                "description": v["description"],
                "published_at": v["published"].isoformat(),
                "views": v["views"],
                "likes": v["likes"],
                "comments": v["comments"],
                "privacy": v["privacy"],
                "tags": v["tags"],
                "duration": v["duration"],
            }
            for v in DEMO_VIDEOS[:limit]
        ]
        result = {"videos": videos, "next_page_token": None, "total_results": len(DEMO_VIDEOS)}
    else:
        service = get_service()
        result = fetch_videos(service, limit, page_token)
        videos = result["videos"]

    if sort == "views":
        videos.sort(key=lambda x: x["views"], reverse=True)
    elif sort == "likes":
        videos.sort(key=lambda x: x["likes"], reverse=True)

    if output == "json":
        print(json.dumps({"videos": videos, **{k: v for k, v in result.items() if k != "videos"}}, indent=2))
    elif output == "csv":
        print("id,title,views,likes,comments,privacy,published_at")
        for v in videos:
            title_escaped = v["title"].replace('"', '""')
            print(
                f'{v["id"]},"{title_escaped}",{v["views"]},{v["likes"]},{v["comments"]},{v["privacy"]},{v["published_at"]}'
            )
    else:
        table = create_table()
        table.add_column("ID", style="bright_black")
        table.add_column("Title")
        table.add_column("Views", justify="right")
        table.add_column("Likes", justify="right")
        table.add_column("Comments", justify="right")
        table.add_column("Published", style="bright_black")

        for v in videos:
            video_url = f"https://youtu.be/{v['id']}"
            title_link = f"[cyan][link={video_url}]{v['title']}[/link][/cyan]"
            table.add_row(
                v["id"],
                title_link,
                format_number(v["views"]),
                format_number(v["likes"]),
                format_number(v["comments"]),
                v["published_at"][:10],
            )

        console.print(table)
        console.print(dim(f"\n{result['total_results']} videos"))

        if result["next_page_token"]:
            console.print(f"\n[bright_black]Next page: --page-token {result['next_page_token']}[/bright_black]")


@app.command()
def get(
    video_id: str = typer.Argument(..., help="Video ID"),
    output: str = typer.Option("table", "--output", "-o", help="Output format: table, json"),
):
    """Get details for a specific video."""
    if is_demo_mode():
        demo_video = get_demo_video(video_id)
        if not demo_video:
            console.print(f"[red]Video not found: {video_id}[/red]")
            raise typer.Exit(1)

        if output == "json":
            print(json.dumps({"id": demo_video["id"], "snippet": {"title": demo_video["title"], "description": demo_video["description"], "tags": demo_video["tags"], "publishedAt": demo_video["published"].isoformat()}, "statistics": {"viewCount": demo_video["views"], "likeCount": demo_video["likes"], "commentCount": demo_video["comments"]}, "contentDetails": {"duration": demo_video["duration"]}, "status": {"privacyStatus": demo_video["privacy"]}}, indent=2))
            return

        console.print(f"\n[bold]{demo_video['title']}[/bold]")
        console.print(f"[cyan]https://youtu.be/{video_id}[/cyan]\n")

        table = create_kv_table()
        table.add_column("field", style="bright_black")
        table.add_column("value")

        table.add_row("views", format_number(demo_video["views"]))
        table.add_row("likes", format_number(demo_video["likes"]))
        table.add_row("comments", format_number(demo_video["comments"]))
        table.add_row("duration", demo_video["duration"])
        table.add_row("published", demo_video["published"].strftime("%Y-%m-%d"))
        table.add_row("privacy", demo_video["privacy"])

        console.print(table)

        if demo_video.get("tags"):
            console.print(f"\n[bright_black]tags:[/bright_black] {', '.join(demo_video['tags'][:15])}")

        console.print(f"\n[bold]description:[/bold]\n{demo_video.get('description', '')}")
        return

    service = get_service()

    response = api(
        service.videos().list(
            part="snippet,statistics,contentDetails,status",
            id=video_id,
        )
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
    console.print(f"[cyan]https://youtu.be/{video_id}[/cyan]\n")

    table = create_kv_table()
    table.add_column("field", style="bright_black")
    table.add_column("value")

    table.add_row("views", format_number(int(stats.get("viewCount", 0))))
    table.add_row("likes", format_number(int(stats.get("likeCount", 0))))
    table.add_row("comments", format_number(int(stats.get("commentCount", 0))))
    table.add_row("duration", content.get("duration", "N/A"))
    table.add_row("published", snippet["publishedAt"][:10])
    table.add_row("privacy", video.get("status", {}).get("privacyStatus", "unknown"))

    console.print(table)

    if snippet.get("tags"):
        console.print(f"\n[bright_black]tags:[/bright_black] {', '.join(snippet['tags'][:15])}")

    console.print(f"\n[bold]description:[/bold]\n{snippet.get('description', '')}")


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

    response = api(service.videos().list(part="snippet", id=video_id))
    if not response.get("items"):
        console.print(f"[red]Video not found: {video_id}[/red]")
        raise typer.Exit(1)

    current = response["items"][0]["snippet"]

    new_title = title if title else current["title"]
    new_desc = description if description else current.get("description", "")
    new_tags = [t.strip() for t in tags.split(",")] if tags else current.get("tags", [])

    if dry_run:
        console.print("[bold]Dry run - changes:[/bold]\n")
        if title:
            console.print(f"title: {current['title']} → [green]{new_title}[/green]")
        if description:
            console.print("description: [green](updated)[/green]")
        if tags:
            console.print(f"tags: [green]{', '.join(new_tags[:5])}[/green]")
        console.print("\n[bright_black]Run without --dry-run to apply[/bright_black]")
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

    api(service.videos().update(part="snippet", body=body))
    console.print(f"[green]✓ Updated: {new_title}[/green]")


@app.command("search-replace")
def search_replace(
    search: str = typer.Option(..., "--search", "-s", help="Text to search for"),
    replace: str = typer.Option(..., "--replace", "-r", help="Text to replace with"),
    field: str = typer.Option(..., "--field", "-f", help="Field to update: title, description"),
    regex: bool = typer.Option(False, "--regex", help="Treat search as regex"),
    limit: int = typer.Option(10, "--limit", "-n", help="Max matches to find"),
    execute: bool = typer.Option(False, "--execute", help="Apply changes (default is dry-run)"),
):
    """Bulk update videos using search and replace."""
    service = get_service()
    uploads_playlist_id = get_channel_uploads_playlist(service)

    changes = []
    page_token = None

    while len(changes) < limit:
        # Fetch batch of videos
        playlist_response = api(
            service.playlistItems().list(
                part="snippet,contentDetails",
                playlistId=uploads_playlist_id,
                maxResults=50,
                pageToken=page_token,
            )
        )

        items = playlist_response.get("items", [])
        if not items:
            break

        video_ids = [item["contentDetails"]["videoId"] for item in items]

        videos_response = api(
            service.videos().list(
                part="snippet",
                id=",".join(video_ids),
            )
        )

        for video in videos_response.get("items", []):
            if len(changes) >= limit:
                break

            old_value = video["snippet"].get(field, "")
            if regex:
                new_value = re.sub(search, replace, old_value)
            else:
                new_value = old_value.replace(search, replace)

            if new_value != old_value:
                changes.append({
                    "id": video["id"],
                    "field": field,
                    "old": old_value,
                    "new": new_value,
                })

        page_token = playlist_response.get("nextPageToken")
        if not page_token:
            break

    if not changes:
        console.print("[yellow]No matches found[/yellow]")
        return

    table = create_table()
    table.add_column("Video ID", style="bright_black")
    table.add_column("Current")
    table.add_column("→", justify="center", style="bright_black")
    table.add_column("New")

    for c in changes:
        table.add_row(c["id"], c["old"], "→", f"[green]{c['new']}[/green]")
    
    console.print(dim(f"{'Pending' if not execute else 'Applying'} {len(changes)} changes\n"))

    console.print(table)

    if not execute:
        console.print("\n[bright_black]Run with --execute to apply changes[/bright_black]")
        return

    console.print("\n[bold]Applying changes...[/bold]\n")
    success = 0
    failed = 0

    for c in changes:
        try:
            response = api(service.videos().list(part="snippet", id=c["id"]))
            if not response.get("items"):
                continue

            snippet = response["items"][0]["snippet"]
            snippet[field] = c["new"]

            api(service.videos().update(part="snippet", body={"id": c["id"], "snippet": snippet}))

            console.print(f"[green]✓[/green] {c['id']}: {c['new']}")
            success += 1
        except HttpError as e:
            # Quota exceeded - stop immediately
            error_details = e.error_details[0] if e.error_details else {}
            if error_details.get("reason") == "quotaExceeded":
                console.print(f"\n[bold]Partial progress:[/bold] {success} updated, {failed} failed")
                handle_api_error(e)
            console.print(f"[red]✗[/red] {c['id']}: {e}")
            failed += 1
        except Exception as e:
            console.print(f"[red]✗[/red] {c['id']}: {e}")
            failed += 1

    console.print(f"\n[bold]Done:[/bold] {success} updated, {failed} failed")
