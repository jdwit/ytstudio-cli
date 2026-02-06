import json
from pathlib import Path

from rich.prompt import Prompt

from ytstudio.ui import console, success_message

CONFIG_DIR = Path.home() / ".config" / "ytstudio-cli"
CLIENT_SECRETS_FILE = CONFIG_DIR / "client_secrets.json"
CREDENTIALS_FILE = CONFIG_DIR / "credentials.json"


def ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def setup_credentials(client_secrets_file: str | None = None) -> None:
    ensure_config_dir()

    if client_secrets_file:
        # Copy provided file
        source = Path(client_secrets_file)
        if not source.exists():
            console.print(f"[red]File not found: {client_secrets_file}[/red]")
            raise SystemExit(1)

        CLIENT_SECRETS_FILE.write_text(source.read_text())
        success_message(f"Client secrets saved to {CLIENT_SECRETS_FILE}")
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
        console.print()
        success_message(f"Client secrets saved to {CLIENT_SECRETS_FILE}")

    console.print("\nRun [bold]ytstudio login[/bold] to authenticate with YouTube.")


def get_client_secrets() -> dict | None:
    if not CLIENT_SECRETS_FILE.exists():
        return None
    return json.loads(CLIENT_SECRETS_FILE.read_text())


def save_credentials(credentials: dict) -> None:
    ensure_config_dir()
    CREDENTIALS_FILE.write_text(json.dumps(credentials, indent=2))


def load_credentials() -> dict | None:
    if not CREDENTIALS_FILE.exists():
        return None
    return json.loads(CREDENTIALS_FILE.read_text())


def clear_credentials() -> None:
    if CREDENTIALS_FILE.exists():
        CREDENTIALS_FILE.unlink()
