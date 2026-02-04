"""Comment management commands."""

import json
from datetime import UTC, datetime

import typer
from googleapiclient.errors import HttpError

from ytstudio.auth import api, get_authenticated_service, handle_api_error
from ytstudio.ui import console, create_table, dim

app = typer.Typer(help="Comment commands")


def get_service():
    """Get authenticated service or exit."""
    service = get_authenticated_service()
    if not service:
        console.print("[red]Not authenticated. Run 'yt login' first.[/red]")
        raise typer.Exit(1) from None
    return service


def time_ago(iso_timestamp: str) -> str:
    """Convert ISO timestamp to relative time."""
    dt = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
    now = datetime.now(UTC)
    delta = now - dt

    if delta.days > 365:
        return f"{delta.days // 365}y ago"
    if delta.days > 30:
        return f"{delta.days // 30}mo ago"
    if delta.days > 0:
        return f"{delta.days}d ago"
    if delta.seconds > 3600:
        return f"{delta.seconds // 3600}h ago"
    return "recently"


def fetch_comments(service, video_id: str, limit: int = 100):
    """Fetch comments with error handling for disabled comments."""
    try:
        return api(
            service.commentThreads().list(
                part="snippet",
                videoId=video_id,
                maxResults=min(limit, 100),
                order="relevance",
            )
        )
    except HttpError as e:
        # Handle quota errors
        handle_api_error(e)
    except Exception as e:
        console.print(f"[yellow]Could not fetch comments (may be disabled): {e}[/yellow]")
        raise typer.Exit(1) from None


@app.command("list")
def list_comments(
    video_id: str = typer.Argument(..., help="Video ID"),
    limit: int = typer.Option(20, "--limit", "-n", help="Number of comments"),
    output: str = typer.Option("table", "--output", "-o", help="Output format: table, json"),
):
    """List comments for a video."""
    service = get_service()
    response = fetch_comments(service, video_id, limit)

    comments = []
    for item in response.get("items", []):
        snippet = item["snippet"]["topLevelComment"]["snippet"]
        comments.append(
            {
                "author": snippet["authorDisplayName"],
                "text": snippet["textOriginal"],
                "likes": snippet["likeCount"],
                "published": snippet["publishedAt"],
            }
        )

    if output == "json":
        print(json.dumps(comments, indent=2))
        return

    console.print(f"\n[bold]Comments ({len(comments)})[/bold]\n")

    for c in comments:
        text = c["text"][:150]
        if len(c["text"]) > 150:
            text += "..."

        like_str = f" [bright_black]({c['likes']} likes)[/bright_black]" if c["likes"] else ""
        console.print(
            f"[bold]{c['author']}[/bold]{like_str} [bright_black]{time_ago(c['published'])}[/bright_black]"
        )
        console.print(f"  {text}\n")


@app.command()
def summary(
    video_id: str = typer.Argument(..., help="Video ID"),
    limit: int = typer.Option(100, "--limit", "-n", help="Number of comments to analyze"),
):
    """Analyze comment sentiment for a video."""
    service = get_service()
    response = fetch_comments(service, video_id, limit)

    comments = response.get("items", [])
    if not comments:
        console.print("[yellow]No comments found[/yellow]")
        return

    # Simple keyword-based sentiment
    positive_words = {
        "love",
        "great",
        "amazing",
        "awesome",
        "best",
        "perfect",
        "fantastic",
        "excellent",
        "good",
        "nice",
        "beautiful",
        "haha",
        "lol",
        "😂",
        "❤️",
        "👍",
        "🔥",
        "genius",
        "brilliant",
    }
    negative_words = {
        "hate",
        "bad",
        "worst",
        "terrible",
        "awful",
        "boring",
        "stupid",
        "trash",
        "garbage",
        "disappointing",
        "👎",
        "cringe",
        "sucks",
    }

    positive = 0
    negative = 0
    negative_comments = []

    for item in comments:
        text = item["snippet"]["topLevelComment"]["snippet"]["textOriginal"].lower()
        author = item["snippet"]["topLevelComment"]["snippet"]["authorDisplayName"]

        has_pos = any(w in text for w in positive_words)
        has_neg = any(w in text for w in negative_words)

        if has_neg and not has_pos:
            negative += 1
            negative_comments.append({"author": author, "text": text[:100]})
        elif has_pos and not has_neg:
            positive += 1

    neutral = len(comments) - positive - negative
    total = len(comments)

    console.print(f"\n[bold]Comment Sentiment[/bold] {dim(f'({total} analyzed)')}\n")
    table = create_table()
    table.add_column("Sentiment", style="bright_black")
    table.add_column("Count", justify="right")
    table.add_column("Percentage", justify="right")

    table.add_row("[green]Positive[/green]", str(positive), f"{positive / total * 100:.1f}%")
    table.add_row("[red]Negative[/red]", str(negative), f"{negative / total * 100:.1f}%")
    table.add_row(
        "[bright_black]Neutral[/bright_black]", str(neutral), f"{neutral / total * 100:.1f}%"
    )

    console.print(table)

    if negative_comments:
        console.print("\n[bold red]Negative comments:[/bold red]")
        for c in negative_comments[:5]:
            console.print(f"  [bright_black]{c['author']}:[/bright_black] {c['text']}")
