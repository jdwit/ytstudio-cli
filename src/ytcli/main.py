"""Main CLI entry point."""

import typer
from rich.console import Console

from ytcli import __version__
from ytcli.auth import authenticate, get_status
from ytcli.commands import analytics, auth, comments, export, seo, videos
from ytcli.config import setup_credentials

app = typer.Typer(
    name="yts",
    help="CLI tool to manage and analyze your YouTube channel",
    no_args_is_help=True,
    rich_markup_mode="markdown",
)

console = Console()

app.add_typer(auth.app, name="auth")
app.add_typer(videos.app, name="videos")
app.add_typer(analytics.app, name="analytics")
app.add_typer(comments.app, name="comments")
app.add_typer(seo.app, name="seo")
app.add_typer(export.app, name="export")


INIT_EPILOG = """
**Setup Instructions**


1. Go to `console.cloud.google.com`

2. Create a new project (or select existing)

3. Enable **YouTube Data API v3**: APIs & Services → Enable APIs

4. Create **OAuth credentials**: APIs & Services → Credentials → Create Credentials → OAuth client ID → Select "Desktop app" → Download JSON

5. Run: `yts init -c ~/Downloads/client_secret_xxx.json`

6. Authenticate: `yts login`

---

⚠️  **Note**: Add yourself as test user in OAuth consent screen until verified
"""


@app.command(epilog=INIT_EPILOG)
def init(
    client_secrets_file: str = typer.Option(
        None,
        "--client-secrets",
        "-c",
        help="Path to Google OAuth client secrets JSON file",
    ),
):
    """Initialize ytstudio-cli with Google OAuth credentials."""
    setup_credentials(client_secrets_file)


@app.command()
def login():
    """Authenticate with YouTube via OAuth."""
    authenticate()


@app.command()
def status():
    """Show current authentication status."""
    get_status()


@app.callback(invoke_without_command=True)
def main(
    version: bool = typer.Option(False, "--version", "-v", help="Show version"),
):
    """ytstudio-cli - Manage and analyze your YouTube channel from the terminal."""
    if version:
        console.print(f"ytstudio-cli v{__version__}")
        raise typer.Exit()


if __name__ == "__main__":
    app()
