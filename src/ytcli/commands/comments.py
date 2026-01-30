"""Comment management commands."""

import json

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Comment commands")
console = Console()


def get_service():
    """Get authenticated service or exit."""
    from ytcli.auth import get_authenticated_service

    service = get_authenticated_service()
    if not service:
        console.print("[red]Not authenticated. Run 'yt login' first.[/red]")
        raise typer.Exit(1)
    return service


def time_ago(iso_timestamp: str) -> str:
    """Convert ISO timestamp to relative time."""
    from datetime import datetime, timezone

    dt = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
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


@app.command("list")
def list_comments(
    video_id: str = typer.Argument(..., help="Video ID"),
    limit: int = typer.Option(20, "--limit", "-n", help="Number of comments"),
    output: str = typer.Option("table", "--output", "-o", help="Output format: table, json"),
):
    """List comments for a video."""
    service = get_service()

    try:
        response = service.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=min(limit, 100),
            order="relevance",
        ).execute()
    except Exception as e:
        console.print(f"[yellow]Could not fetch comments (may be disabled): {e}[/yellow]")
        raise typer.Exit(1)

    comments = []
    for item in response.get("items", []):
        snippet = item["snippet"]["topLevelComment"]["snippet"]
        comments.append({
            "author": snippet["authorDisplayName"],
            "text": snippet["textOriginal"],
            "likes": snippet["likeCount"],
            "published": snippet["publishedAt"],
        })

    if output == "json":
        print(json.dumps(comments, indent=2))
        return

    console.print(f"\n[bold]Comments ({len(comments)})[/bold]\n")

    for c in comments:
        text = c["text"][:150]
        if len(c["text"]) > 150:
            text += "..."

        like_str = f" [dim]({c['likes']} likes)[/dim]" if c["likes"] else ""
        console.print(f"[bold]{c['author']}[/bold]{like_str} [dim]{time_ago(c['published'])}[/dim]")
        console.print(f"  {text}\n")


@app.command()
def summary(
    video_id: str = typer.Argument(..., help="Video ID"),
    limit: int = typer.Option(100, "--limit", "-n", help="Number of comments to analyze"),
):
    """Analyze comment sentiment for a video."""
    service = get_service()

    try:
        response = service.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=min(limit, 100),
            order="relevance",
        ).execute()
    except Exception:
        console.print("[yellow]Could not fetch comments[/yellow]")
        raise typer.Exit(1)

    comments = response.get("items", [])
    if not comments:
        console.print("[yellow]No comments found[/yellow]")
        return

    # Simple keyword-based sentiment
    positive_words = {"love", "great", "amazing", "awesome", "best", "perfect", "fantastic", "excellent", "good", "nice", "beautiful", "haha", "lol", "😂", "❤️", "👍", "🔥", "genius", "brilliant"}
    negative_words = {"hate", "bad", "worst", "terrible", "awful", "boring", "stupid", "trash", "garbage", "disappointing", "👎", "cringe", "sucks"}

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

    table = Table(title=f"Comment Sentiment ({total} analyzed)")
    table.add_column("Sentiment")
    table.add_column("Count", justify="right")
    table.add_column("Percentage", justify="right")

    table.add_row("[green]Positive[/green]", str(positive), f"{positive/total*100:.1f}%")
    table.add_row("[red]Negative[/red]", str(negative), f"{negative/total*100:.1f}%")
    table.add_row("[dim]Neutral[/dim]", str(neutral), f"{neutral/total*100:.1f}%")

    console.print(table)

    if negative_comments:
        console.print("\n[bold red]Negative comments:[/bold red]")
        for c in negative_comments[:5]:
            console.print(f"  [dim]{c['author']}:[/dim] {c['text']}")
