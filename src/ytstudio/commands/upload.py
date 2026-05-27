from pathlib import Path

import typer

from ytstudio.ui import console, create_table, dim
from ytstudio.upload_pipeline import (
    DiscoveryError,
    ValidationError,
    discover,
    validate_jobs,
)


def upload(
    path: Path = typer.Argument(..., help="Video file or directory of videos with yaml sidecars"),
    execute: bool = typer.Option(False, "--execute", help="Actually upload (default is dry-run)"),
    max_uploads: int = typer.Option(
        0, "--max", "-m", help="Maximum number of uploads in this run (0 = no limit)"
    ),
) -> None:
    """Upload one or more videos described by yaml sidecars."""
    try:
        jobs = discover(path)
    except DiscoveryError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from e

    try:
        validate_jobs(jobs)
    except ValidationError as e:
        console.print(f"[red]Validation failed:[/red]\n{e}")
        raise typer.Exit(1) from e

    pending = [j for j in jobs if not j.already_uploaded]
    skipped = [j for j in jobs if j.already_uploaded]

    if not pending:
        console.print(dim("Nothing to upload (all sidecars already have video_id)."))
        return

    table = create_table()
    table.add_column("File", style="yellow")
    table.add_column("Title", style="cyan")
    table.add_column("Privacy")
    table.add_column("Publish at")
    table.add_column("Thumb")

    for job in pending:
        spec = job.spec
        publish_at = spec.publish_at.isoformat() if spec.publish_at else "-"
        thumb = "yes" if job.thumbnail_path else "-"
        table.add_row(job.video_path.name, spec.title, spec.privacy.value, publish_at, thumb)

    console.print(table)

    for job in skipped:
        console.print(dim(f"skipped (already uploaded): {job.video_path.name}"))

    if not execute:
        console.print("\n[dim]Dry-run. Re-run with --execute to upload.[/dim]")
        return

    # Task 9 will implement the --execute branch.
    console.print("[yellow]--execute not yet implemented in this commit[/yellow]")
    raise typer.Exit(0)
