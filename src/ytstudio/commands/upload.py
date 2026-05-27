from datetime import UTC, datetime
from pathlib import Path

import typer
from googleapiclient.errors import HttpError
from rich.progress import BarColumn, Progress, TextColumn, TimeRemainingColumn

from ytstudio.api import handle_api_error
from ytstudio.services import get_data_service
from ytstudio.ui import console, create_table, dim
from ytstudio.upload_pipeline import (
    DiscoveryError,
    UploadJob,
    ValidationError,
    discover,
    set_thumbnail,
    upload_video,
    validate_jobs,
    write_back,
)


class _QuotaExceeded(Exception):
    def __init__(self, cause: HttpError) -> None:
        self.cause = cause


def _is_quota_exceeded(e: HttpError) -> bool:
    return any(detail.get("reason") == "quotaExceeded" for detail in e.error_details or [])


def _upload_one(service, job: UploadJob) -> str:
    file_size = job.video_path.stat().st_size
    with Progress(
        TextColumn("[bold blue]{task.fields[name]}"),
        BarColumn(),
        TextColumn("{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
        console=console,
        transient=True,
    ) as progress:
        task_id = progress.add_task("upload", total=file_size, name=job.video_path.name)

        def _on_progress(done: int, total: int) -> None:
            progress.update(task_id, completed=done)

        try:
            video_id = upload_video(service, job, on_progress=_on_progress)
        except HttpError as e:
            if _is_quota_exceeded(e):
                raise _QuotaExceeded(e) from e
            raise

    if job.thumbnail_path is not None:
        try:
            set_thumbnail(service, video_id=video_id, thumbnail_path=job.thumbnail_path)
        except HttpError as e:
            console.print(f"[yellow]thumbnail for {job.video_path.name} failed: {e}[/yellow]")

    write_back(
        job.sidecar_path,
        video_id=video_id,
        uploaded_at_iso=datetime.now(UTC).isoformat(),
    )
    console.print(f"[green]ok[/green] {job.video_path.name} -> https://youtu.be/{video_id}")
    return video_id


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

    if max_uploads > 0:
        pending = pending[:max_uploads]

    service = get_data_service()

    estimated = len(pending) * 1600
    console.print(dim(f"\nGoing to upload {len(pending)} videos (~{estimated} quota units)."))

    succeeded = 0
    for job in pending:
        try:
            _upload_one(service, job)
        except _QuotaExceeded as e:
            console.print(
                f"\n[red]Quota exceeded after {succeeded} upload(s).[/red] Try again tomorrow."
            )
            handle_api_error(e.cause)
            break
        except HttpError as e:
            console.print(f"[red]X {job.video_path.name}: {e}[/red]")
            continue

        succeeded += 1

    console.print(f"\n[bold]Done:[/bold] {succeeded}/{len(pending)} uploaded.")
