"""SEO analysis commands."""

import json

import typer
from rich.panel import Panel

from ytstudio.auth import api, get_authenticated_service
from ytstudio.ui import console, create_table

app = typer.Typer(help="SEO analysis commands")

# SEO thresholds
TITLE_MIN = 30
TITLE_MAX = 70
DESC_MIN = 200
TAGS_MIN = 5


def get_service():
    """Get authenticated service or exit."""
    service = get_authenticated_service()
    if not service:
        console.print("[red]Not authenticated. Run 'yt login' first.[/red]")
        raise typer.Exit(1)
    return service


def score_color(score: int) -> str:
    """Get color for score display."""
    if score >= 80:
        return "green"
    if score >= 50:
        return "yellow"
    return "red"


def analyze_seo(video: dict) -> dict:
    """Analyze SEO for a single video."""
    snippet = video["snippet"]
    title = snippet["title"]
    desc = snippet.get("description", "")
    tags = snippet.get("tags", [])

    # Title score
    title_score = 100
    title_issues = []
    if len(title) < TITLE_MIN:
        title_score -= 30
        title_issues.append(f"too short ({len(title)} chars)")
    elif len(title) > TITLE_MAX:
        title_score -= 20
        title_issues.append(f"too long ({len(title)} chars)")

    # Description score
    desc_score = 100
    desc_issues = []
    if len(desc) < DESC_MIN:
        desc_score -= 40
        desc_issues.append(f"too short ({len(desc)} chars)")
    if not desc.strip():
        desc_score = 0
        desc_issues = ["empty"]

    # Tags score
    tags_score = 100
    tags_issues = []
    if len(tags) < TAGS_MIN:
        tags_score -= 30
        tags_issues.append(f"too few ({len(tags)} tags)")
    if not tags:
        tags_score = 0
        tags_issues = ["no tags"]

    total = (title_score + desc_score + tags_score) // 3

    return {
        "video_id": video["id"],
        "title": title,
        "total_score": total,
        "title_score": title_score,
        "title_issues": title_issues,
        "desc_score": desc_score,
        "desc_issues": desc_issues,
        "tags_score": tags_score,
        "tags_issues": tags_issues,
    }


@app.command()
def check(
    video_id: str = typer.Argument(..., help="Video ID"),
    output: str = typer.Option("table", "--output", "-o", help="Output format: table, json"),
):
    """Check SEO score for a video."""
    service = get_service()

    response = api(service.videos().list(part="snippet", id=video_id))

    if not response.get("items"):
        console.print(f"[red]Video not found: {video_id}[/red]")
        raise typer.Exit(1)

    seo = analyze_seo(response["items"][0])

    if output == "json":
        print(json.dumps(seo, indent=2))
        return

    console.print(f"\n[bold]{seo['title']}[/bold]")
    console.print(f"[cyan]https://youtu.be/{video_id}[/cyan]\n")

    color = score_color(seo["total_score"])
    console.print(
        Panel(
            f"[bold {color}]{seo['total_score']}/100[/bold {color}]",
            title="SEO Score",
            border_style=color,
        )
    )

    table = create_table()
    table.add_column("Aspect", style="dim")
    table.add_column("Score", justify="center")
    table.add_column("Issues")

    table.add_row(
        "Title",
        f"[{score_color(seo['title_score'])}]{seo['title_score']}[/]",
        ", ".join(seo["title_issues"]) or "[green]ok[/green]",
    )
    table.add_row(
        "Description",
        f"[{score_color(seo['desc_score'])}]{seo['desc_score']}[/]",
        ", ".join(seo["desc_issues"]) or "[green]ok[/green]",
    )
    table.add_row(
        "Tags",
        f"[{score_color(seo['tags_score'])}]{seo['tags_score']}[/]",
        ", ".join(seo["tags_issues"]) or "[green]ok[/green]",
    )

    console.print(table)


@app.command()
def audit(
    limit: int = typer.Option(50, "--limit", "-n", help="Number of videos to analyze"),
    output: str = typer.Option("table", "--output", "-o", help="Output format: table, json"),
):
    """Audit SEO for all channel videos."""
    service = get_service()

    channels_response = api(service.channels().list(part="contentDetails", mine=True))

    if not channels_response.get("items"):
        console.print("[red]No channel found[/red]")
        raise typer.Exit(1)

    uploads_id = channels_response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

    playlist_response = api(
        service.playlistItems().list(
            part="contentDetails",
            playlistId=uploads_id,
            maxResults=min(limit, 50),
        )
    )

    video_ids = [item["contentDetails"]["videoId"] for item in playlist_response.get("items", [])]

    if not video_ids:
        console.print("[yellow]No videos found[/yellow]")
        return

    videos_response = api(service.videos().list(part="snippet", id=",".join(video_ids)))

    scores = [analyze_seo(v) for v in videos_response.get("items", [])]
    avg_score = sum(s["total_score"] for s in scores) / len(scores) if scores else 0

    if output == "json":
        print(json.dumps({"average_score": avg_score, "videos": scores}, indent=2))
        return

    console.print(
        Panel(
            f"[bold]Average SEO Score: [{score_color(int(avg_score))}]{avg_score:.0f}/100[/][/bold]\n"
            f"Analyzed {len(scores)} videos",
            title="Channel SEO Audit",
        )
    )

    worst = sorted(scores, key=lambda s: s["total_score"])
    needs_work = [s for s in worst if s["total_score"] < 80]

    if needs_work:
        console.print("\n[bold]Videos Needing Attention[/bold]\n")
        table = create_table()
        table.add_column("Score", justify="center")
        table.add_column("Title", max_width=40)
        table.add_column("Main Issue", style="dim")

        for seo in needs_work[:15]:
            issue = (
                seo["title_issues"][0]
                if seo["title_issues"]
                else seo["desc_issues"][0]
                if seo["desc_issues"]
                else seo["tags_issues"][0]
                if seo["tags_issues"]
                else ""
            )
            table.add_row(
                f"[{score_color(seo['total_score'])}]{seo['total_score']}[/]",
                seo["title"][:40],
                issue,
            )

        console.print(table)
    else:
        console.print("[green]All videos have good SEO scores![/green]")
