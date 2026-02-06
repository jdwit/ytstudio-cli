import atexit

import typer
from rich.console import Console

from ytstudio.auth import authenticate, get_status
from ytstudio.commands import analytics, auth, comments, videos
from ytstudio.config import setup_credentials
from ytstudio.version import get_current_version, is_update_available

app = typer.Typer(
    name="ytstudio",
    help="Manage your YouTube channel from the terminal",
    no_args_is_help=True,
    rich_markup_mode="markdown",
)

console = Console()

app.add_typer(auth.app, name="auth")
app.add_typer(videos.app, name="videos")
app.add_typer(analytics.app, name="analytics")
app.add_typer(comments.app, name="comments")


@app.command()
def init(
    client_secrets_file: str = typer.Option(
        None,
        "--client-secrets",
        "-c",
        help="Path to Google OAuth client secrets JSON file",
    ),
):
    """Initialize with Google OAuth credentials"""
    setup_credentials(client_secrets_file)


@app.command()
def login():
    """Authenticate with YouTube via OAuth"""
    authenticate()


@app.command()
def status():
    """Show current authentication status"""
    get_status()


_update_state = {"registered": False}


def _show_update_notification():
    try:
        available, latest = is_update_available()
        if available:
            console.print(
                f"\n[cyan]Update available: {get_current_version()} → {latest}[/cyan]\n"
                f"Run: [bold]uv tool upgrade ytstudio-cli[/bold]"
            )
    except Exception:
        pass  # Silent on errors


@app.callback(invoke_without_command=True)
def main(
    show_version: bool = typer.Option(False, "--version", "-v", help="Show version"),
):
    """ytstudio - Manage your YouTube channel from the terminal"""
    if show_version:
        console.print(f"ytstudio v{get_current_version()}")
        raise typer.Exit()

    if not _update_state["registered"]:
        atexit.register(_show_update_notification)
        _update_state["registered"] = True


if __name__ == "__main__":
    app()
