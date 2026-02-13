import json
from dataclasses import asdict, dataclass
from enum import StrEnum

import typer
from googleapiclient.errors import HttpError

from ytstudio.api import api, handle_api_error
from ytstudio.services import get_data_service
from ytstudio.ui import console, create_table, time_ago, truncate

app = typer.Typer(help="Comment commands")


class SortOrder(StrEnum):
    relevance = "relevance"
    time = "time"


class ModerationStatus(StrEnum):
    published = "published"
    held = "held"
    spam = "spam"

    def to_api_value(self) -> str:
        """Convert to YouTube API moderationStatus value"""
        return {"published": "published", "held": "heldForReview", "spam": "likelySpam"}[self.value]


@dataclass
class Comment:
    id: str
    author: str
    text: str
    likes: int
    published_at: str
    video_id: str = ""


def get_channel_id(service) -> str:
    response = api(service.channels().list(part="id", mine=True))
    if not response.get("items"):
        console.print("[red]No channel found[/red]")
        raise typer.Exit(1)
    return response["items"][0]["id"]


def fetch_comments(
    data_service,
    video_id: str | None = None,
    limit: int = 100,
    order: SortOrder = SortOrder.relevance,
    moderation_status: ModerationStatus = ModerationStatus.published,
) -> list[Comment]:
    try:
        # Build query parameters based on filters
        params = {
            "part": "snippet",
            "maxResults": min(limit, 100),
            "order": order.value,
        }

        if video_id:
            params["videoId"] = video_id
        else:
            channel_id = get_channel_id(data_service)
            params["allThreadsRelatedToChannelId"] = channel_id
            if moderation_status != ModerationStatus.published:
                params["moderationStatus"] = moderation_status.to_api_value()

        response = api(data_service.commentThreads().list(**params))
    except HttpError as e:
        handle_api_error(e)
    except Exception as e:
        console.print(f"[yellow]Could not fetch comments (may be disabled): {e}[/yellow]")
        raise typer.Exit(1) from None

    comments = []
    for item in response.get("items", []):
        snippet = item["snippet"]["topLevelComment"]["snippet"]
        comments.append(
            Comment(
                id=item["id"],
                author=snippet["authorDisplayName"],
                text=snippet["textOriginal"],
                likes=snippet["likeCount"],
                published_at=snippet["publishedAt"],
                video_id=snippet.get("videoId", ""),
            )
        )
    return comments


@app.command("list")
def list_comments(
    video_id: str = typer.Option(None, "--video", "-v", help="Filter by video ID"),
    status: ModerationStatus = typer.Option(
        ModerationStatus.published, "--status", help="Moderation status: published, held, spam"
    ),
    limit: int = typer.Option(20, "--limit", "-n", help="Number of comments"),
    sort: SortOrder = typer.Option(SortOrder.time, "--sort", "-s", help="Sort order"),
    output: str = typer.Option("table", "--output", "-o", help="Output format: table, json"),
):
    """List comments across channel or for a specific video"""
    if sort == SortOrder.relevance and not video_id:
        console.print("[red]--sort relevance requires --video (YouTube API limitation)[/red]")
        raise typer.Exit(1)

    service = get_data_service()
    comments = fetch_comments(service, video_id, limit, sort, status)

    if output == "json":
        print(json.dumps([asdict(c) for c in comments], indent=2))
        return

    status_label = {"published": "Published", "held": "Held for Review", "spam": "Likely Spam"}
    label = status_label.get(status.value, status.value)
    scope = f"video {video_id}" if video_id else "channel"
    console.print(f"\n[bold]{label} Comments ({len(comments)})[/bold] — {scope}\n")

    table = create_table()
    table.add_column("ID", style="yellow")
    if not video_id:
        table.add_column("Video", style="cyan")
    table.add_column("Author")
    table.add_column("Posted")
    table.add_column("Comment")

    for c in comments:
        date = f"{c.published_at[:16].replace('T', ' ')} ({time_ago(c.published_at)})"
        row = [c.id]
        if not video_id:
            row.append(c.video_id)
        row += [c.author, date, truncate(c.text, 80)]
        table.add_row(*row)

    console.print(table)


def _set_moderation_status(comment_ids: list[str], status: str, ban_author: bool = False) -> int:
    service = get_data_service()
    success = 0
    batch_size = 50
    for i in range(0, len(comment_ids), batch_size):
        batch = comment_ids[i : i + batch_size]
        try:
            params = {
                "id": ",".join(batch),
                "moderationStatus": status,
            }
            if ban_author and status == "rejected":
                params["banAuthor"] = True
            api(service.comments().setModerationStatus(**params))
            success += len(batch)
        except HttpError as e:
            handle_api_error(e)
    return success


@app.command()
def publish(
    comment_ids: list[str] = typer.Argument(help="Comment IDs to publish"),
):
    """Publish held comments (approve for public display)"""
    count = _set_moderation_status(comment_ids, "published")
    console.print(f"{count} comment(s) published")


@app.command()
def reject(
    comment_ids: list[str] = typer.Argument(help="Comment IDs to reject"),
    ban: bool = typer.Option(False, "--ban", help="Also ban the comment author"),
):
    """Reject comments (hide from public display)"""
    count = _set_moderation_status(comment_ids, "rejected", ban_author=ban)
    console.print(f"{count} comment(s) rejected")
