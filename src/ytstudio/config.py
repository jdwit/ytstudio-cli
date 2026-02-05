"""Configuration management."""

import json
from pathlib import Path

from rich.console import Console
from rich.prompt import Prompt

CONFIG_DIR = Path.home() / ".config" / "ytstudio-cli"
CLIENT_SECRETS_FILE = CONFIG_DIR / "client_secrets.json"
CREDENTIALS_FILE = CONFIG_DIR / "credentials.json"

console = Console()


def ensure_config_dir():
    """Ensure the config directory exists."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def setup_credentials(client_secrets_file: str | None = None):
    """Set up Google OAuth client credentials."""
    ensure_config_dir()

    if client_secrets_file:
        # Copy provided file
        source = Path(client_secrets_file)
        if not source.exists():
            console.print(f"[red]File not found: {client_secrets_file}[/red]")
            raise SystemExit(1)

        CLIENT_SECRETS_FILE.write_text(source.read_text())
        console.print(f"[green]✓ Client secrets saved to {CLIENT_SECRETS_FILE}[/green]")
    else:
        # Interactive setup
        console.print("\n[bold]ytstudio-cli Setup[/bold]\n")
        console.print("You need to create a Google Cloud project and OAuth credentials.")
        console.print("See: https://github.com/jdwit/ytstudio-cli#setup\n")

        client_id = Prompt.ask("Enter your OAuth Client ID")
        client_secret = Prompt.ask("Enter your OAuth Client Secret")

        secrets = {
            "installed": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost"],
            }
        }

        CLIENT_SECRETS_FILE.write_text(json.dumps(secrets, indent=2))
        console.print(f"\n[green]✓ Client secrets saved to {CLIENT_SECRETS_FILE}[/green]")

    console.print("\nRun [bold]ytstudio login[/bold] to authenticate with YouTube.")


def get_client_secrets() -> dict | None:
    """Load client secrets from config."""
    if not CLIENT_SECRETS_FILE.exists():
        return None
    return json.loads(CLIENT_SECRETS_FILE.read_text())


def save_credentials(credentials: dict):
    """Save OAuth credentials."""
    ensure_config_dir()
    CREDENTIALS_FILE.write_text(json.dumps(credentials, indent=2))


def load_credentials() -> dict | None:
    """Load stored OAuth credentials."""
    if not CREDENTIALS_FILE.exists():
        return None
    return json.loads(CREDENTIALS_FILE.read_text())


def clear_credentials():
    """Remove stored credentials."""
    if CREDENTIALS_FILE.exists():
        CREDENTIALS_FILE.unlink()
