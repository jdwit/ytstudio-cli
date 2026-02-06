import json
from dataclasses import asdict, dataclass
from enum import StrEnum

import typer
from googleapiclient.errors import HttpError

from ytstudio.auth import api, get_authenticated_service, handle_api_error
from ytstudio.demo import DEMO_COMMENTS, is_demo_mode
from ytstudio.ui import console, time_ago

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


def get_service():
    return get_authenticated_service()


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
    if is_demo_mode():
        return [
            Comment(
                id=c.get("id", f"comment_{i}"),
                author=c["author"],
                text=c["text"],
                likes=c["likes"],
                published_at=c["published"].isoformat()
                if hasattr(c["published"], "isoformat")
                else c["published"],
                video_id=c.get("video_id", "demo_video"),
            )
            for i, c in enumerate(DEMO_COMMENTS[:limit])
        ]

    try:
        # Build query parameters based on filters
        params = {
            "part": "snippet",
            "maxResults": min(limit, 100),
            "order": order.value,
        }

        if video_id:
            # Video-specific query (moderationStatus not supported)
            params["videoId"] = video_id
        else:
            # Channel-wide query (supports moderation filtering)
            channel_id = get_channel_id(data_service)
            params["allThreadsRelatedToChannelId"] = channel_id
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
    sort: SortOrder = typer.Option(SortOrder.relevance, "--sort", "-s", help="Sort order"),
    output: str = typer.Option("table", "--output", "-o", help="Output format: table, json"),
):
    """List comments across channel or for a specific video"""
    service = get_service()
    comments = fetch_comments(service, video_id, limit, sort, status)

    if output == "json":
        print(json.dumps([asdict(c) for c in comments], indent=2))
        return

    status_label = {"published": "Published", "held": "Held for Review", "spam": "Likely Spam"}
    label = status_label.get(status.value, status.value)
    scope = f"video {video_id}" if video_id else "channel"
    console.print(f"\n[bold]{label} Comments ({len(comments)})[/bold] — {scope}\n")

    for c in comments:
        text = c.text[:150]
        if len(c.text) > 150:
            text += "..."

        like_str = f" [dim]({c.likes} likes)[/dim]" if c.likes else ""
        video_str = f" [dim cyan]on {c.video_id}[/dim cyan]" if c.video_id and not video_id else ""
        console.print(
            f"[bold]{c.author}[/bold]{like_str}{video_str} [dim]{time_ago(c.published_at)}[/dim]"
        )
        console.print(f"  {text}\n")
