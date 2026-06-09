import json
from dataclasses import asdict, dataclass, field

import typer
from googleapiclient.errors import HttpError
from rich.prompt import Confirm

from ytstudio.api import api, handle_api_error
from ytstudio.services import get_data_service
from ytstudio.ui import (
    console,
    create_kv_table,
    create_table,
    dim,
    format_number,
    success_message,
    truncate,
)

app = typer.Typer(help="Playlist management commands")


@dataclass
class Playlist:
    id: str
    title: str
    description: str
    published_at: str
    item_count: int
    privacy: str
    default_language: str | None = None
    localizations: dict = field(default_factory=dict)


@dataclass
class PlaylistItem:
    id: str
    video_id: str
    title: str
    position: int
    added_at: str
    note: str = ""


# Uploads playlists are channel-owned and cannot be mutated through the
# playlists or playlistItems APIs.
def _is_uploads_playlist(playlist_id: str) -> bool:
    return playlist_id.startswith("UU")


def _refuse_uploads_playlist(playlist_id: str) -> None:
    if _is_uploads_playlist(playlist_id):
        console.print(
            "[red]Cannot modify the channel uploads playlist. "
            "Manage video privacy or delete videos instead.[/red]"
        )
        raise typer.Exit(1)


def _http_reason(error: HttpError) -> str:
    detail = error.error_details[0] if getattr(error, "error_details", None) else {}
    if isinstance(detail, dict):
        return detail.get("reason", "") or ""
    return ""


def _parse_playlist(item: dict) -> Playlist:
    snippet = item.get("snippet") or {}
    content = item.get("contentDetails") or {}
    status = item.get("status") or {}
    return Playlist(
        id=str(item["id"]),
        title=snippet.get("title", ""),
        description=snippet.get("description", ""),
        published_at=snippet.get("publishedAt", ""),
        item_count=int(content.get("itemCount", 0) or 0),
        privacy=status.get("privacyStatus", "unknown"),
        default_language=snippet.get("defaultLanguage"),
        localizations=item.get("localizations", {}) or {},
    )


def _parse_playlist_item(item: dict) -> PlaylistItem:
    snippet = item.get("snippet") or {}
    content = item.get("contentDetails") or {}
    resource = snippet.get("resourceId") or {}
    return PlaylistItem(
        id=str(item.get("id", "")),
        video_id=resource.get("videoId") or content.get("videoId", ""),
        title=snippet.get("title", ""),
        position=int(snippet.get("position", 0) or 0),
        added_at=snippet.get("publishedAt", ""),
        note=content.get("note", "") or "",
    )


def _fetch_playlist(service, playlist_id: str) -> Playlist | None:
    response = api(
        service.playlists().list(
            part="snippet,contentDetails,status,localizations",
            id=playlist_id,
        )
    )
    items = (response or {}).get("items", [])
    if not items:
        return None
    return _parse_playlist(items[0])


def _fetch_all_items(service, playlist_id: str, limit: int | None = None) -> list[PlaylistItem]:
    """Paginate through playlistItems, capping at `limit` if provided."""
    items: list[PlaylistItem] = []
    page_token: str | None = None

    while True:
        remaining = None if limit is None else max(0, limit - len(items))
        if remaining == 0:
            break
        batch_size = 50 if remaining is None else min(50, remaining)

        response = (
            api(
                service.playlistItems().list(
                    part="snippet,contentDetails",
                    playlistId=playlist_id,
                    maxResults=batch_size,
                    pageToken=page_token,
                )
            )
            or {}
        )

        for raw in response.get("items", []):
            items.append(_parse_playlist_item(raw))

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return items


def _list_items_page(service, playlist_id: str, max_results: int, page_token: str | None) -> dict:
    response = (
        api(
            service.playlistItems().list(
                part="snippet,contentDetails",
                playlistId=playlist_id,
                maxResults=max_results,
                pageToken=page_token,
            )
        )
        or {}
    )
    parsed = [_parse_playlist_item(raw) for raw in response.get("items", [])]
    return {
        "items": parsed,
        "next_page_token": response.get("nextPageToken"),
        "total_results": (response.get("pageInfo") or {}).get("totalResults", 0),
    }


def _print_playlists_table(playlists: list[Playlist]) -> None:
    table = create_table()
    table.add_column("ID", style="yellow")
    table.add_column("Title", style="cyan")
    table.add_column("Items", justify="right")
    table.add_column("Privacy")
    table.add_column("Updated")

    for p in playlists:
        table.add_row(
            p.id,
            truncate(p.title),
            format_number(p.item_count),
            p.privacy,
            p.published_at[:10],
        )
    console.print(table)


@app.command("list")
def list_playlists(
    limit: int = typer.Option(50, "--limit", "-n", help="Number of playlists to list"),
    page_token: str = typer.Option(None, "--page-token", "-p", help="Page token for pagination"),
    sort: str = typer.Option("date", "--sort", "-s", help="Sort by: date, title, count"),
    output: str = typer.Option("table", "--output", "-o", help="Output format: table, json, csv"),
):
    """List your playlists."""
    service = get_data_service()

    all_playlists: list[Playlist] = []
    current_token = page_token
    next_page_token: str | None = None
    total_results = 0

    while len(all_playlists) < limit:
        batch = min(limit - len(all_playlists), 50)
        response = (
            api(
                service.playlists().list(
                    part="snippet,contentDetails,status",
                    mine=True,
                    maxResults=batch,
                    pageToken=current_token,
                )
            )
            or {}
        )

        if not total_results:
            total_results = (response.get("pageInfo") or {}).get("totalResults", 0)

        for raw in response.get("items", []):
            all_playlists.append(_parse_playlist(raw))

        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break
        current_token = next_page_token

    if sort == "title":
        all_playlists.sort(key=lambda p: p.title.lower())
    elif sort == "count":
        all_playlists.sort(key=lambda p: p.item_count, reverse=True)

    if output == "json":
        print(
            json.dumps(
                {
                    "playlists": [asdict(p) for p in all_playlists],
                    "next_page_token": next_page_token,
                    "total_results": total_results,
                },
                indent=2,
            )
        )
        return

    if output == "csv":
        print("id,title,items,privacy,published_at")
        for p in all_playlists:
            title_escaped = p.title.replace('"', '""')
            print(f'{p.id},"{title_escaped}",{p.item_count},{p.privacy},{p.published_at}')
        return

    _print_playlists_table(all_playlists)

    if next_page_token:
        console.print(f"\nNext page: --page-token {next_page_token}")


@app.command()
def show(
    playlist_id: str = typer.Argument(..., help="Playlist ID"),
    output: str = typer.Option("table", "--output", "-o", help="Output format: table, json"),
    items: bool = typer.Option(
        False, "--items", "-i", help="Also fetch and render the first 50 items"
    ),
):
    """Show details for a specific playlist."""
    service = get_data_service()
    playlist = _fetch_playlist(service, playlist_id)

    if not playlist:
        console.print(f"[red]Playlist not found: {playlist_id}[/red]")
        raise typer.Exit(1)

    rendered_items: list[PlaylistItem] = []
    if items:
        rendered_items = _fetch_all_items(service, playlist_id, limit=50)

    if output == "json":
        payload: dict = {"playlist": asdict(playlist)}
        if items:
            payload["items"] = [asdict(it) for it in rendered_items]
        print(json.dumps(payload, indent=2))
        return

    console.print(f"\n[bold]{playlist.title}[/bold]\n")

    table = create_kv_table()
    table.add_column("field", style="dim")
    table.add_column("value")
    table.add_row("title", playlist.title)
    table.add_row("description", playlist.description or "-")
    table.add_row("items", format_number(playlist.item_count))
    table.add_row("privacy", playlist.privacy)
    table.add_row("published", playlist.published_at[:10] if playlist.published_at else "-")
    table.add_row("language", playlist.default_language or "-")
    console.print(table)

    if not items:
        return

    if not rendered_items:
        console.print(dim("\nPlaylist is empty."))
        return

    console.print()
    items_table = create_table()
    items_table.add_column("Position", justify="right")
    items_table.add_column("Video ID", style="yellow")
    items_table.add_column("Title", style="cyan")
    items_table.add_column("Added")
    for it in rendered_items:
        items_table.add_row(
            str(it.position),
            it.video_id,
            truncate(it.title),
            it.added_at[:10] if it.added_at else "-",
        )
    console.print(items_table)


@app.command()
def create(
    title: str = typer.Option(..., "--title", "-t", help="Playlist title"),
    description: str = typer.Option("", "--description", "-d", help="Playlist description"),
    privacy: str = typer.Option("private", "--privacy", help="Privacy: private, public, unlisted"),
    language: str = typer.Option(None, "--language", help="Default language tag (e.g. en, nl)"),
    execute: bool = typer.Option(False, "--execute", help="Create the playlist (default dry-run)"),
):
    """Create a new playlist."""
    if privacy not in {"private", "public", "unlisted"}:
        console.print("[red]Invalid --privacy. Use: private, public, unlisted[/red]")
        raise typer.Exit(2)

    snippet: dict = {"title": title, "description": description}
    if language:
        snippet["defaultLanguage"] = language
    body = {"snippet": snippet, "status": {"privacyStatus": privacy}}

    if not execute:
        console.print("[bold]Preview new playlist:[/bold]\n")
        preview = create_kv_table()
        preview.add_column("field", style="dim")
        preview.add_column("value")
        preview.add_row("title", title)
        preview.add_row("description", description or "-")
        preview.add_row("privacy", privacy)
        preview.add_row("language", language or "-")
        console.print(preview)
        console.print("\nRun with --execute to create.")
        return

    service = get_data_service()
    response = api(service.playlists().insert(part="snippet,status", body=body)) or {}
    playlist_id = response.get("id", "unknown")
    success_message(f"Created: {title} ({playlist_id})")


@app.command()
def update(
    playlist_id: str = typer.Argument(..., help="Playlist ID"),
    title: str = typer.Option(None, "--title", "-t", help="New title"),
    description: str = typer.Option(None, "--description", "-d", help="New description"),
    privacy: str = typer.Option(None, "--privacy", help="New privacy: private, public, unlisted"),
    language: str = typer.Option(None, "--language", help="New default language"),
    execute: bool = typer.Option(False, "--execute", help="Apply changes (default is dry-run)"),
):
    """Update a playlist's metadata."""
    _refuse_uploads_playlist(playlist_id)

    if all(v is None for v in (title, description, privacy, language)):
        console.print(
            "[yellow]Nothing to update. Provide --title, --description, --privacy, "
            "or --language[/yellow]"
        )
        raise typer.Exit(1)

    if privacy is not None and privacy not in {"private", "public", "unlisted"}:
        console.print("[red]Invalid --privacy. Use: private, public, unlisted[/red]")
        raise typer.Exit(2)

    service = get_data_service()
    current = _fetch_playlist(service, playlist_id)
    if not current:
        console.print(f"[red]Playlist not found: {playlist_id}[/red]")
        raise typer.Exit(1)

    new_title = title if title is not None else current.title
    new_description = description if description is not None else current.description
    new_privacy = privacy if privacy is not None else current.privacy
    new_language = language if language is not None else current.default_language

    if not execute:
        console.print("[bold]Preview changes:[/bold]\n")
        preview = create_kv_table()
        preview.add_column("field", style="dim")
        preview.add_column("current")
        preview.add_column("new", style="green")
        if title is not None:
            preview.add_row("title", current.title, new_title)
        if description is not None:
            preview.add_row("description", current.description or "-", new_description or "-")
        if privacy is not None:
            preview.add_row("privacy", current.privacy, new_privacy)
        if language is not None:
            preview.add_row("language", current.default_language or "-", new_language or "-")
        console.print(preview)
        console.print("\nRun with --execute to apply.")
        return

    # snippet PUTs replace the whole part, so we always re-specify the current
    # title and description even when only changing one field.
    snippet: dict = {"title": new_title, "description": new_description}
    if new_language:
        snippet["defaultLanguage"] = new_language
    body = {
        "id": playlist_id,
        "snippet": snippet,
        "status": {"privacyStatus": new_privacy},
    }

    api(service.playlists().update(part="snippet,status", body=body))
    success_message(f"Updated: {new_title}")


@app.command()
def delete(
    playlist_id: str = typer.Argument(..., help="Playlist ID"),
    execute: bool = typer.Option(False, "--execute", help="Apply deletion (default is dry-run)"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
):
    """Delete a playlist."""
    _refuse_uploads_playlist(playlist_id)

    service = get_data_service()
    current = _fetch_playlist(service, playlist_id)
    if not current:
        console.print(f"[red]Playlist not found: {playlist_id}[/red]")
        raise typer.Exit(1)

    if not execute:
        console.print(
            f"[yellow]Would delete:[/yellow] {current.title} ({current.item_count} items)"
        )
        console.print("\nRun with --execute to apply.")
        return

    if not yes and not Confirm.ask(f"Delete playlist '{current.title}'?", default=False):
        console.print(dim("Aborted."))
        return

    api(service.playlists().delete(id=playlist_id))
    success_message(f"Deleted: {current.title}")


@app.command()
def items(
    playlist_id: str = typer.Argument(..., help="Playlist ID"),
    limit: int = typer.Option(50, "--limit", "-n", help="Number of items to list"),
    page_token: str = typer.Option(None, "--page-token", "-p", help="Page token for pagination"),
    output: str = typer.Option("table", "--output", "-o", help="Output format: table, json, csv"),
):
    """List the items in a playlist."""
    service = get_data_service()

    all_items: list[PlaylistItem] = []
    current_token = page_token
    next_page_token: str | None = None
    total_results = 0

    while len(all_items) < limit:
        batch = min(limit - len(all_items), 50)
        result = _list_items_page(service, playlist_id, batch, current_token)
        if not total_results:
            total_results = result["total_results"]
        all_items.extend(result["items"])
        next_page_token = result["next_page_token"]
        if not next_page_token:
            break
        current_token = next_page_token

    if output == "json":
        print(
            json.dumps(
                {
                    "items": [asdict(it) for it in all_items],
                    "next_page_token": next_page_token,
                    "total_results": total_results,
                },
                indent=2,
            )
        )
        return

    if output == "csv":
        print("item_id,video_id,position,title,added_at")
        for it in all_items:
            title_escaped = it.title.replace('"', '""')
            print(f'{it.id},{it.video_id},{it.position},"{title_escaped}",{it.added_at}')
        return

    if not all_items:
        console.print(dim("Playlist is empty."))
        return

    table = create_table()
    table.add_column("Position", justify="right")
    table.add_column("Item ID", style="yellow")
    table.add_column("Video ID")
    table.add_column("Title", style="cyan")
    table.add_column("Added")
    for it in all_items:
        table.add_row(
            str(it.position),
            it.id,
            it.video_id,
            truncate(it.title),
            it.added_at[:10] if it.added_at else "-",
        )
    console.print(table)

    if next_page_token:
        console.print(f"\nNext page: --page-token {next_page_token}")


def _resolve_search_video_ids(service, query: str, limit: int) -> list[tuple[str, str]]:
    """Return [(video_id, title)] from search().list, capped at `limit`."""
    results: list[tuple[str, str]] = []
    page_token: str | None = None

    while len(results) < limit:
        batch = min(50, limit - len(results))
        response = (
            api(
                service.search().list(
                    part="snippet",
                    forMine=True,
                    type="video",
                    q=query,
                    maxResults=batch,
                    pageToken=page_token,
                )
            )
            or {}
        )

        for item in response.get("items", []):
            vid_field = item.get("id") or {}
            video_id = vid_field.get("videoId") if isinstance(vid_field, dict) else None
            if not video_id:
                continue
            title = (item.get("snippet") or {}).get("title", "")
            results.append((video_id, title))
            if len(results) >= limit:
                break

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return results[:limit]


@app.command()
def add(
    playlist_id: str = typer.Argument(..., help="Playlist ID"),
    video: list[str] = typer.Option(None, "--video", "-v", help="Video ID to add (repeatable)"),
    from_search: str = typer.Option(
        None, "--from-search", help="Add the top results from a search of your videos"
    ),
    limit: int = typer.Option(
        50, "--limit", "-n", help="Max videos to add per invocation (search mode)"
    ),
    position: int = typer.Option(None, "--position", help="Insert at this position"),
    note: str = typer.Option(None, "--note", help="Set contentDetails.note on each item"),
    execute: bool = typer.Option(False, "--execute", help="Apply changes (default is dry-run)"),
):
    """Add videos to a playlist by ID or search query.

    If --video is passed more than once, every ID is added. --from-search runs
    search().list(forMine=True, type=video, q=...) and adds up to --limit hits.
    Quota is 50 units per inserted video; a running counter is printed.
    """
    _refuse_uploads_playlist(playlist_id)

    if not video and not from_search:
        console.print("[red]Pass at least one --video or --from-search[/red]")
        raise typer.Exit(2)

    service = get_data_service()

    candidates: list[tuple[str, str]] = []
    if video:
        candidates.extend((vid, "") for vid in video)
    if from_search:
        found = _resolve_search_video_ids(service, from_search, limit)
        if not found:
            console.print("[yellow]No videos matched search[/yellow]")
            raise typer.Exit(0)
        candidates.extend(found)

    candidates = candidates[:limit] if from_search and not video else candidates

    table = create_table()
    table.add_column("Video ID", style="yellow")
    table.add_column("Title", style="cyan")
    table.add_column("Position", justify="right")
    for vid, title in candidates:
        table.add_row(vid, truncate(title) if title else "-", str(position) if position else "-")

    if not execute:
        console.print(dim(f"Pending {len(candidates)} adds\n"))
        console.print(table)
        console.print("\n[dim]Run with --execute to apply changes[/dim]")
        return

    console.print(dim(f"Adding {len(candidates)} videos\n"))
    console.print(table)
    console.print()

    added = 0
    failed = 0
    for idx, (vid, _title) in enumerate(candidates, start=1):
        snippet: dict = {
            "playlistId": playlist_id,
            "resourceId": {"kind": "youtube#video", "videoId": vid},
        }
        if position is not None:
            snippet["position"] = position
        body: dict = {"snippet": snippet}
        if note is not None:
            body["contentDetails"] = {"note": note}

        try:
            service.playlistItems().insert(part="snippet,contentDetails", body=body).execute()
            console.print(f"[green]Added[/green] {idx}/{len(candidates)} {vid}")
            added += 1
        except HttpError as e:
            reason = _http_reason(e)
            if reason == "quotaExceeded":
                console.print(f"\n[bold]Partial progress:[/bold] {added} added, {failed} failed")
                handle_api_error(e)
            if reason == "playlistContainsMaximumNumberOfVideos":
                console.print(
                    f"[red]Playlist reached the 5000-item limit.[/red] Stopped at {added} added."
                )
                raise typer.Exit(1) from None
            if reason == "videoNotFound":
                console.print(f"[red]Not found[/red] {vid}")
                failed += 1
                continue
            console.print(f"[red]Failed[/red] {vid}: {e}")
            failed += 1

    console.print(f"\n[bold]Done:[/bold] {added} added, {failed} failed")


def _resolve_video_to_item_ids(service, playlist_id: str, video_id: str) -> list[str]:
    """Return every playlistItem id for `video_id` in this playlist."""
    found: list[str] = []
    page_token: str | None = None
    while True:
        response = (
            api(
                service.playlistItems().list(
                    part="snippet",
                    playlistId=playlist_id,
                    videoId=video_id,
                    maxResults=50,
                    pageToken=page_token,
                )
            )
            or {}
        )
        for raw in response.get("items", []):
            if raw.get("id"):
                found.append(raw["id"])
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    return found


@app.command()
def remove(
    playlist_id: str = typer.Argument(..., help="Playlist ID"),
    item: list[str] = typer.Option(
        None, "--item", "-i", help="Playlist item ID (PLPLI...) to remove (repeatable)"
    ),
    video: list[str] = typer.Option(
        None,
        "--video",
        "-v",
        help=(
            "Video ID to remove (repeatable). Resolves to all playlist items for that video; "
            "duplicates are all removed."
        ),
    ),
    execute: bool = typer.Option(False, "--execute", help="Apply changes (default is dry-run)"),
):
    """Remove items from a playlist by item id or video id."""
    _refuse_uploads_playlist(playlist_id)

    if not item and not video:
        console.print("[red]Pass at least one --item or --video[/red]")
        raise typer.Exit(2)

    service = get_data_service()

    targets: list[str] = list(item) if item else []
    if video:
        for vid in video:
            resolved = _resolve_video_to_item_ids(service, playlist_id, vid)
            if not resolved:
                console.print(f"[yellow]Not in playlist: {vid}[/yellow]")
                continue
            targets.extend(resolved)

    if not targets:
        console.print("[yellow]Nothing to remove[/yellow]")
        raise typer.Exit(0)

    table = create_table()
    table.add_column("Item ID", style="yellow")
    for item_id in targets:
        table.add_row(item_id)

    if not execute:
        console.print(dim(f"Pending {len(targets)} removals\n"))
        console.print(table)
        console.print("\n[dim]Run with --execute to apply changes[/dim]")
        return

    console.print(dim(f"Removing {len(targets)} items\n"))
    console.print(table)
    console.print()

    removed = 0
    failed = 0
    for idx, item_id in enumerate(targets, start=1):
        try:
            service.playlistItems().delete(id=item_id).execute()
            console.print(f"[green]Removed[/green] {idx}/{len(targets)} {item_id}")
            removed += 1
        except HttpError as e:
            reason = _http_reason(e)
            if reason == "quotaExceeded":
                console.print(
                    f"\n[bold]Partial progress:[/bold] {removed} removed, {failed} failed"
                )
                handle_api_error(e)
            console.print(f"[red]Failed[/red] {item_id}: {e}")
            failed += 1

    console.print(f"\n[bold]Done:[/bold] {removed} removed, {failed} failed")


def _hydrate_sort_keys(service, video_ids: list[str]) -> dict[str, dict]:
    """Batch-fetch statistics+snippet for `video_ids` in chunks of 50."""
    out: dict[str, dict] = {}
    for start in range(0, len(video_ids), 50):
        chunk = video_ids[start : start + 50]
        response = (
            api(
                service.videos().list(
                    part="statistics,snippet",
                    id=",".join(chunk),
                )
            )
            or {}
        )
        for vid_item in response.get("items", []):
            out[vid_item["id"]] = vid_item
    return out


def _sort_key(item: PlaylistItem, hydrated: dict, by: str):
    """Compose (primary, video_id) sort tuple; video_id keeps ties stable."""
    data = hydrated.get(item.video_id, {})
    snippet = data.get("snippet", {})
    stats = data.get("statistics", {})
    if by == "views":
        primary = int(stats.get("viewCount", 0) or 0)
    elif by == "likes":
        primary = int(stats.get("likeCount", 0) or 0)
    elif by == "published":
        primary = snippet.get("publishedAt", "")
    elif by == "title":
        primary = snippet.get("title", "").lower()
    else:
        primary = 0
    return (primary, item.video_id)


@app.command()
def reorder(
    playlist_id: str = typer.Argument(..., help="Playlist ID"),
    by: str = typer.Option("views", "--by", help="Sort by: views, likes, published, title"),
    order: str = typer.Option("desc", "--order", help="Order: asc, desc"),
    execute: bool = typer.Option(False, "--execute", help="Apply changes (default is dry-run)"),
):
    """Reorder a playlist by one of views, likes, published, title."""
    _refuse_uploads_playlist(playlist_id)

    if by not in {"views", "likes", "published", "title"}:
        console.print("[red]Invalid --by. Use: views, likes, published, title[/red]")
        raise typer.Exit(2)
    if order not in {"asc", "desc"}:
        console.print("[red]Invalid --order. Use: asc, desc[/red]")
        raise typer.Exit(2)

    service = get_data_service()

    items = _fetch_all_items(service, playlist_id)
    if not items:
        console.print(dim("Playlist is empty."))
        return

    hydrated = _hydrate_sort_keys(service, [it.video_id for it in items])

    reverse = order == "desc"
    sorted_items = sorted(items, key=lambda it: _sort_key(it, hydrated, by), reverse=reverse)

    moves: list[tuple[PlaylistItem, int, int]] = []
    for new_pos, it in enumerate(sorted_items):
        if it.position != new_pos:
            moves.append((it, it.position, new_pos))

    if not moves:
        console.print("[yellow]No changes; playlist already sorted.[/yellow]")
        return

    moves.sort(key=lambda m: m[2])

    table = create_table()
    table.add_column("Item ID", style="yellow")
    table.add_column("Title", style="cyan")
    table.add_column("Current", justify="right")
    table.add_column("Target", justify="right")
    for it, cur, tgt in moves:
        table.add_row(it.id, truncate(it.title), str(cur), str(tgt))

    if not execute:
        console.print(dim(f"Pending {len(moves)} moves\n"))
        console.print(table)
        console.print("\n[dim]Run with --execute to apply changes[/dim]")
        return

    console.print(dim(f"Applying {len(moves)} moves\n"))
    console.print(table)
    console.print()

    updated = 0
    failed = 0
    for idx, (it, _cur, tgt) in enumerate(moves, start=1):
        body = {
            "id": it.id,
            "snippet": {
                "playlistId": playlist_id,
                "resourceId": {"kind": "youtube#video", "videoId": it.video_id},
                "position": tgt,
            },
        }
        try:
            service.playlistItems().update(part="snippet", body=body).execute()
            console.print(f"[green]Moved[/green] {idx}/{len(moves)} {it.id} -> {tgt}")
            updated += 1
        except HttpError as e:
            reason = _http_reason(e)
            if reason == "manualSortRequired":
                console.print(
                    "[red]Playlist is not set to Manual sort. "
                    "Open it in YouTube Studio -> Sort by -> Manual, then retry.[/red]"
                )
                raise typer.Exit(1) from None
            if reason == "quotaExceeded":
                console.print(f"\n[bold]Partial progress:[/bold] {updated} moved, {failed} failed")
                handle_api_error(e)
            console.print(f"[red]Failed[/red] {it.id}: {e}")
            failed += 1

    console.print(f"\n[bold]Done:[/bold] {updated} moved, {failed} failed")
