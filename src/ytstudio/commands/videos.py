import json
import re
from dataclasses import asdict, dataclass, field

import typer
from googleapiclient.errors import HttpError

from ytstudio.auth import api, get_authenticated_service, handle_api_error
from ytstudio.demo import DEMO_VIDEOS, get_demo_video, is_demo_mode
from ytstudio.ui import (
    console,
    create_kv_table,
    create_table,
    dim,
    format_number,
    success_message,
    truncate,
)

app = typer.Typer(help="Video management commands")


@dataclass
class Video:
    id: str
    title: str
    description: str
    published_at: str
    views: int
    likes: int
    comments: int
    duration: str
    privacy: str
    tags: list[str] = field(default_factory=list)
    category_id: str = ""
    licensed: bool = False
    default_language: str | None = None
    default_audio_language: str | None = None
    localizations: dict = field(default_factory=dict)


def format_duration(iso_duration: str) -> str:
    """Format ISO 8601 duration (PT1M19S -> 1:19)"""
    if not iso_duration:
        return ""

    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso_duration)
    if not match:
        return ""

    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)

    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def get_service():
    if is_demo_mode():
        return None
    return get_authenticated_service()


def get_channel_uploads_playlist(service) -> str:
    response = api(service.channels().list(part="contentDetails", mine=True))
    if not response.get("items"):
        console.print("[red]No channel found[/red]")
        raise typer.Exit(1)
    return response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]


def fetch_video(data_service, video_id: str) -> Video | None:
    if is_demo_mode():
        demo = get_demo_video(video_id)
        if not demo:
            return None
        return Video(
            id=demo["id"],
            title=demo["title"],
            description=demo.get("description", ""),
            published_at=demo["published"].strftime("%Y-%m-%dT%H:%M:%SZ"),
            views=demo["views"],
            likes=demo["likes"],
            comments=demo["comments"],
            duration=demo["duration"],
            privacy=demo["privacy"],
            tags=demo.get("tags", []),
            default_language=demo.get("defaultLanguage"),
            default_audio_language=demo.get("defaultAudioLanguage"),
            localizations=demo.get("localizations", {}),
        )

    response = api(
        data_service.videos().list(
            part="snippet,statistics,contentDetails,status,localizations",
            id=video_id,
        )
    )

    if not response.get("items"):
        return None

    item = response["items"][0]
    snippet = item["snippet"]
    stats = item.get("statistics", {})
    content = item.get("contentDetails", {})

    return Video(
        id=item["id"],
        title=snippet["title"],
        description=snippet.get("description", ""),
        published_at=snippet["publishedAt"],
        views=int(stats.get("viewCount", 0)),
        likes=int(stats.get("likeCount", 0)),
        comments=int(stats.get("commentCount", 0)),
        duration=content.get("duration", ""),
        privacy=item.get("status", {}).get("privacyStatus", "unknown"),
        tags=snippet.get("tags", []),
        default_language=snippet.get("defaultLanguage"),
        default_audio_language=snippet.get("defaultAudioLanguage"),
        localizations=item.get("localizations", {}),
    )


def fetch_videos(
    data_service, limit: int = 50, page_token: str | None = None
) -> dict[str, list[Video] | str | int | None]:
    if is_demo_mode():
        videos = [
            Video(
                id=v["id"],
                title=v["title"],
                description=v.get("description", ""),
                published_at=v["published"].strftime("%Y-%m-%dT%H:%M:%SZ"),
                views=v["views"],
                likes=v["likes"],
                comments=v["comments"],
                privacy=v["privacy"],
                tags=v.get("tags", []),
                duration=v["duration"],
                localizations=v.get("localizations", {}),
                default_language=v.get("defaultLanguage"),
                default_audio_language=v.get("defaultAudioLanguage"),
            )
            for v in DEMO_VIDEOS[:limit]
        ]
        return {"videos": videos, "next_page_token": None, "total_results": len(DEMO_VIDEOS)}

    uploads_playlist_id = get_channel_uploads_playlist(data_service)

    all_videos = []
    current_page_token = page_token
    total_results = None
    next_page_token = None

    parts = "statistics,status,snippet,contentDetails,localizations"

    while len(all_videos) < limit:
        batch_size = min(limit - len(all_videos), 50)

        playlist_response = api(
            data_service.playlistItems().list(
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
            data_service.videos().list(
                part=parts,
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

            video = Video(
                id=video_id,
                title=item["snippet"]["title"],
                description=item["snippet"].get("description", ""),
                published_at=item["snippet"]["publishedAt"],
                views=int(stats.get("viewCount", 0)),
                likes=int(stats.get("likeCount", 0)),
                comments=int(stats.get("commentCount", 0)),
                privacy=data.get("status", {}).get("privacyStatus", "unknown"),
                tags=snippet.get("tags", []),
                category_id=snippet.get("categoryId", ""),
                duration=content_details.get("duration", ""),
                licensed=content_details.get("licensedContent", False),
                localizations=data.get("localizations", {}),
                default_language=snippet.get("defaultLanguage"),
                default_audio_language=snippet.get("defaultAudioLanguage"),
            )

            all_videos.append(video)

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
    audio_lang: str = typer.Option(
        None, "--audio-lang", help="Filter by audio language (e.g., en, nl)"
    ),
    meta_lang: str = typer.Option(
        None, "--meta-lang", help="Filter by metadata language (e.g., en, nl)"
    ),
    has_localization: str = typer.Option(
        None, "--has-localization", help="Filter by available translation (e.g., en, nl)"
    ),
):
    """List your YouTube videos"""
    service = get_service()
    result = fetch_videos(service, limit, page_token)
    videos: list[Video] = result["videos"]

    if audio_lang:
        videos = [v for v in videos if v.default_audio_language == audio_lang]
    if meta_lang:
        videos = [v for v in videos if v.default_language == meta_lang]
    if has_localization:
        videos = [v for v in videos if has_localization in v.localizations]

    if sort == "views":
        videos.sort(key=lambda x: x.views, reverse=True)
    elif sort == "likes":
        videos.sort(key=lambda x: x.likes, reverse=True)

    if output == "json":
        print(
            json.dumps(
                {
                    "videos": [asdict(v) for v in videos],
                    "next_page_token": result["next_page_token"],
                    "total_results": result["total_results"],
                },
                indent=2,
            )
        )
    elif output == "csv":
        print("id,title,views,likes,comments,privacy,published_at")
        for v in videos:
            title_escaped = v.title.replace('"', '""')
            print(
                f'{v.id},"{title_escaped}",{v.views},{v.likes},{v.comments},{v.privacy},{v.published_at}'
            )
    else:
        table = create_table()
        table.add_column("ID", style="yellow")
        table.add_column("Title", style="cyan")
        table.add_column("URL")
        table.add_column("Views", justify="right")
        table.add_column("Likes", justify="right")
        table.add_column("Comments", justify="right")
        table.add_column("Published")

        for v in videos:
            video_url = f"https://youtu.be/{v.id}"
            title = truncate(v.title)
            table.add_row(
                v.id,
                title,
                video_url,
                format_number(v.views),
                format_number(v.likes),
                format_number(v.comments),
                v.published_at[:10],
            )

        console.print(table)

        if result["next_page_token"]:
            console.print(f"\nNext page: --page-token {result['next_page_token']}")


@app.command()
def show(
    video_id: str = typer.Argument(..., help="Video ID"),
    output: str = typer.Option("table", "--output", "-o", help="Output format: table, json"),
):
    """Show details for a specific video"""
    service = get_service()
    video = fetch_video(service, video_id)

    if not video:
        console.print(f"[red]Video not found: {video_id}[/red]")
        raise typer.Exit(1)

    if output == "json":
        print(json.dumps(asdict(video), indent=2))
        return

    console.print(f"\n[bold]{video.title}[/bold]")
    console.print(f"[cyan]https://youtu.be/{video_id}[/cyan]\n")

    table = create_kv_table()
    table.add_column("field", style="dim")
    table.add_column("value")

    table.add_row("views", format_number(video.views))
    table.add_row("likes", format_number(video.likes))
    table.add_row("comments", format_number(video.comments))
    table.add_row("duration", video.duration or "N/A")
    table.add_row("published", video.published_at[:10])
    table.add_row("privacy", video.privacy)
    table.add_row("language", video.default_language or "-")
    table.add_row("audio language", video.default_audio_language or "-")

    if video.localizations:
        table.add_row("localizations", ", ".join(sorted(video.localizations.keys())))

    console.print(table)

    if video.tags:
        console.print(f"\n[dim]tags:[/dim] {', '.join(video.tags[:15])}")

    console.print(f"\n[bold]description:[/bold]\n{video.description}")


@app.command()
def update(
    video_id: str = typer.Argument(..., help="Video ID"),
    title: str = typer.Option(None, "--title", "-t", help="New title"),
    description: str = typer.Option(None, "--description", "-d", help="New description"),
    tags: str = typer.Option(None, "--tags", help="Comma-separated tags"),
    execute: bool = typer.Option(False, "--execute", help="Apply changes (default is dry-run)"),
):
    """Update a video's metadata"""
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

    if not execute:
        console.print("[bold]Preview changes:[/bold]\n")
        if title:
            console.print(f"title: {current['title']} → [green]{new_title}[/green]")
        if description:
            console.print("description: [green](updated)[/green]")
        if tags:
            console.print(f"tags: [green]{', '.join(new_tags[:5])}[/green]")
        console.print("\nRun with --execute to apply")
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
    success_message(f"Updated: {new_title}")


@app.command("search-replace")
def search_replace(
    search: str = typer.Option(..., "--search", "-s", help="Text to search for"),
    replace: str = typer.Option(..., "--replace", "-r", help="Text to replace with"),
    field: str = typer.Option(..., "--field", "-f", help="Field to update: title, description"),
    regex: bool = typer.Option(False, "--regex", help="Treat search as regex"),
    limit: int = typer.Option(10, "--limit", "-n", help="Max matches to find"),
    execute: bool = typer.Option(False, "--execute", help="Apply changes (default is dry-run)"),
):
    """Bulk update videos using search and replace"""
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
                changes.append(
                    {
                        "id": video["id"],
                        "field": field,
                        "old": old_value,
                        "new": new_value,
                    }
                )

        page_token = playlist_response.get("nextPageToken")
        if not page_token:
            break

    if not changes:
        console.print("[yellow]No matches found[/yellow]")
        return

    table = create_table()
    table.add_column("Video ID", style="yellow")
    table.add_column("Current")
    table.add_column("→", justify="center", style="dim")
    table.add_column("New")

    for c in changes:
        table.add_row(c["id"], c["old"], "→", f"[green]{c['new']}[/green]")

    console.print(dim(f"{'Pending' if not execute else 'Applying'} {len(changes)} changes\n"))

    console.print(table)

    if not execute:
        console.print("\n[dim]Run with --execute to apply changes[/dim]")
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
                console.print(
                    f"\n[bold]Partial progress:[/bold] {success} updated, {failed} failed"
                )
                handle_api_error(e)
            console.print(f"[red]✗[/red] {c['id']}: {e}")
            failed += 1
        except Exception as e:
            console.print(f"[red]✗[/red] {c['id']}: {e}")
            failed += 1

    console.print(f"\n[bold]Done:[/bold] {success} updated, {failed} failed")
