"""First-run demo mode: try the CLI against a built-in fake channel.

Each subcommand sets `YTSTUDIO_DEMO=1` for the duration of the call and then
delegates to the real command function, so users see identical output to the
production code path without needing an account or OAuth credentials.
"""

import os
import time
from contextlib import contextmanager

import typer

from ytstudio.commands import analytics as analytics_cmd
from ytstudio.commands import comments as comments_cmd
from ytstudio.commands import videos as videos_cmd
from ytstudio.ui import console, create_kv_table, dim

app = typer.Typer(help="Try the CLI against a built-in fake channel - no OAuth required")


@contextmanager
def _demo_env():
    previous = os.environ.get("YTSTUDIO_DEMO")
    os.environ["YTSTUDIO_DEMO"] = "1"
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("YTSTUDIO_DEMO", None)
        else:
            os.environ["YTSTUDIO_DEMO"] = previous


@app.command()
def videos(
    limit: int = typer.Option(5, "--limit", "-n", help="Number of videos to list"),
    output: str = typer.Option("table", "--output", "-o", help="Output format: table, json"),
):
    """List fake videos from the demo channel."""
    with _demo_env():
        videos_cmd.list_videos(
            limit=limit,
            page_token=None,
            sort="date",
            output=output,
            audio_lang=None,
            meta_lang=None,
            has_localization=None,
            scheduled=False,
        )


@app.command()
def analytics(
    days: int = typer.Option(28, "--days", "-d", help="Number of days to analyze"),
    output: str = typer.Option("table", "--output", "-o", help="Output format: table, json"),
):
    """Show fake channel analytics overview."""
    with _demo_env():
        analytics_cmd.overview(days=days, output=output)


@app.command()
def comments(
    limit: int = typer.Option(10, "--limit", "-n", help="Number of comments"),
    output: str = typer.Option("table", "--output", "-o", help="Output format: table, json"),
):
    """List fake comments across the demo channel."""
    with _demo_env():
        comments_cmd.list_comments(
            video_id=None,
            status=comments_cmd.ModerationStatus.published,
            limit=limit,
            sort=comments_cmd.SortOrder.time,
            output=output,
        )


@app.command()
def tour(
    no_pauses: bool = typer.Option(False, "--no-pauses", help="Skip the pacing sleeps"),
):
    """Run videos, analytics, and comments back-to-back."""
    console.print(dim("\nytstudio demo tour: videos -> analytics -> comments\n"))

    with _demo_env():
        console.print(dim("[1/3] videos\n"))
        videos_cmd.list_videos(
            limit=5,
            page_token=None,
            sort="date",
            output="table",
            audio_lang=None,
            meta_lang=None,
            has_localization=None,
            scheduled=False,
        )
        if not no_pauses:
            time.sleep(1.5)

        console.print(dim("\n[2/3] analytics\n"))
        analytics_cmd.overview(days=28, output="table")
        if not no_pauses:
            time.sleep(1.5)

        console.print(dim("\n[3/3] comments\n"))
        comments_cmd.list_comments(
            video_id=None,
            status=comments_cmd.ModerationStatus.published,
            limit=10,
            sort=comments_cmd.SortOrder.time,
            output="table",
        )

    console.print(dim("\nDone. Connect your real channel with: ytstudio init && ytstudio login\n"))


@app.command()
def info():
    """Show what powers demo mode."""
    fixtures_path = "ytstudio/fixtures/ (bundled in the wheel)"
    table = create_kv_table()
    table.add_column("field", style="dim")
    table.add_column("value")
    table.add_row("fixtures", fixtures_path)
    table.add_row("env var", "YTSTUDIO_DEMO")
    table.add_row("channel", "Demo Creator Channel (@democreator)")
    table.add_row("network", "none; quota/error paths are bypassed")
    console.print(table)
    console.print("\n[dim]To use your real channel: ytstudio init && ytstudio login[/dim]")
