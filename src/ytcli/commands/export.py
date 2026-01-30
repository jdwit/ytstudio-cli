"""Export commands."""

import csv
import json
from pathlib import Path

import typer
from rich.console import Console

app = typer.Typer(help="Export data")
console = Console()


def get_service():
    """Get authenticated service or exit."""
    from ytcli.auth import get_authenticated_service

    service = get_authenticated_service()
    if not service:
        console.print("[red]Not authenticated. Run 'yt login' first.[/red]")
        raise typer.Exit(1)
    return service


@app.command()
def videos(
    output: Path = typer.Argument(..., help="Output file path"),
    format: str = typer.Option("csv", "--format", "-f", help="Output format: csv, json"),
    limit: int = typer.Option(100, "--limit", "-n", help="Max videos to export"),
):
    """Export video data to file."""
    from ytcli.commands.videos import fetch_videos

    service = get_service()
    result = fetch_videos(service, limit)
    videos_data = result["videos"]

    if format == "json":
        output.write_text(json.dumps(videos_data, indent=2, ensure_ascii=False))
    else:
        with output.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "title", "views", "likes", "comments", "published"])
            for v in videos_data:
                writer.writerow([
                    v["id"],
                    v["title"],
                    v["views"],
                    v["likes"],
                    v["comments"],
                    v["published_at"][:10],
                ])

    console.print(f"[green]Exported {len(videos_data)} videos to {output}[/green]")


@app.command()
def comments(
    video_id: str = typer.Argument(..., help="Video ID"),
    output: Path = typer.Argument(..., help="Output file path"),
    limit: int = typer.Option(500, "--limit", "-n", help="Max comments to export"),
):
    """Export comments to JSON."""
    service = get_service()

    all_comments = []
    page_token = None

    while len(all_comments) < limit:
        try:
            response = service.commentThreads().list(
                part="snippet",
                videoId=video_id,
                maxResults=min(100, limit - len(all_comments)),
                pageToken=page_token,
                order="relevance",
            ).execute()

            for item in response.get("items", []):
                snippet = item["snippet"]["topLevelComment"]["snippet"]
                all_comments.append({
                    "author": snippet["authorDisplayName"],
                    "text": snippet["textOriginal"],
                    "likes": snippet["likeCount"],
                    "published": snippet["publishedAt"],
                })

            page_token = response.get("nextPageToken")
            if not page_token:
                break
        except Exception as e:
            console.print(f"[yellow]Error fetching comments: {e}[/yellow]")
            break

    output.write_text(json.dumps(all_comments, indent=2, ensure_ascii=False))
    console.print(f"[green]Exported {len(all_comments)} comments to {output}[/green]")


@app.command()
def report(
    output: Path = typer.Argument(..., help="Output file path"),
):
    """Export channel report (JSON)."""
    from ytcli.commands.videos import fetch_videos
    from ytcli.commands.seo import analyze_seo

    service = get_service()

    # Channel info
    channel_response = service.channels().list(
        part="snippet,statistics",
        mine=True,
    ).execute()

    if not channel_response.get("items"):
        console.print("[red]No channel found[/red]")
        raise typer.Exit(1)

    channel = channel_response["items"][0]
    stats = channel["statistics"]

    # Videos
    result = fetch_videos(service, 50)
    videos_data = result["videos"]

    # Calculate metrics
    total_views = sum(v["views"] for v in videos_data)
    total_likes = sum(v["likes"] for v in videos_data)
    n = len(videos_data)

    # Get SEO scores
    video_ids = [v["id"] for v in videos_data]
    videos_response = service.videos().list(part="snippet", id=",".join(video_ids)).execute()
    seo_scores = [analyze_seo(v) for v in videos_response.get("items", [])]
    avg_seo = sum(s["total_score"] for s in seo_scores) / len(seo_scores) if seo_scores else 0

    report_data = {
        "channel": {
            "title": channel["snippet"]["title"],
            "subscribers": int(stats.get("subscriberCount", 0)),
            "total_views": int(stats.get("viewCount", 0)),
            "video_count": int(stats.get("videoCount", 0)),
        },
        "metrics": {
            "avg_views": total_views / n if n else 0,
            "avg_likes": total_likes / n if n else 0,
            "engagement_rate": (total_likes / total_views * 100) if total_views else 0,
            "avg_seo_score": avg_seo,
        },
        "top_videos": sorted(
            [{"id": v["id"], "title": v["title"], "views": v["views"]} for v in videos_data],
            key=lambda x: x["views"],
            reverse=True,
        )[:10],
    }

    output.write_text(json.dumps(report_data, indent=2, ensure_ascii=False))
    console.print(f"[green]Exported channel report to {output}[/green]")
