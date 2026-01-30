"""YouTube OAuth authentication."""

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from rich.console import Console

from ytcli.config import (
    CLIENT_SECRETS_FILE,
    clear_credentials,
    load_credentials,
    save_credentials,
)

console = Console()

# YouTube API scopes
SCOPES = [
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]


def authenticate():
    """Run OAuth authentication flow."""
    if not CLIENT_SECRETS_FILE.exists():
        console.print("[red]No client secrets found. Run 'yt init' first.[/red]")
        raise SystemExit(1)

    console.print("[bold]Authenticating with YouTube...[/bold]\n")

    flow = InstalledAppFlow.from_client_secrets_file(
        str(CLIENT_SECRETS_FILE),
        scopes=SCOPES,
    )

    # Run local server for OAuth callback
    credentials = flow.run_local_server(
        port=9876,
        prompt="consent",
        open_browser=True,
    )

    # Save credentials
    creds_data = {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": credentials.scopes,
    }
    save_credentials(creds_data)

    # Get channel info
    service = build("youtube", "v3", credentials=credentials)
    response = service.channels().list(part="snippet", mine=True).execute()

    if response.get("items"):
        channel = response["items"][0]["snippet"]
        console.print(f"\n[green]✓ Logged in as: {channel['title']}[/green]")
    else:
        console.print("\n[green]✓ Authentication successful[/green]")


def get_credentials() -> Credentials | None:
    """Get valid credentials, refreshing if needed."""
    creds_data = load_credentials()
    if not creds_data:
        return None

    credentials = Credentials(
        token=creds_data.get("token"),
        refresh_token=creds_data.get("refresh_token"),
        token_uri=creds_data.get("token_uri"),
        client_id=creds_data.get("client_id"),
        client_secret=creds_data.get("client_secret"),
        scopes=creds_data.get("scopes"),
    )

    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        # Save refreshed credentials
        creds_data["token"] = credentials.token
        save_credentials(creds_data)

    return credentials


def get_authenticated_service(api: str = "youtube", version: str = "v3"):
    """Get an authenticated YouTube API service."""
    credentials = get_credentials()
    if not credentials:
        return None
    return build(api, version, credentials=credentials)


def get_status():
    """Show authentication status."""
    creds_data = load_credentials()

    if not creds_data:
        console.print("[yellow]Not authenticated. Run 'yt login' to authenticate.[/yellow]")
        return

    credentials = get_credentials()
    if not credentials or not credentials.valid:
        console.print("[yellow]Credentials expired. Run 'yt login' to re-authenticate.[/yellow]")
        return

    # Get channel info
    try:
        service = build("youtube", "v3", credentials=credentials)
        response = service.channels().list(part="snippet,statistics", mine=True).execute()

        if response.get("items"):
            channel = response["items"][0]
            snippet = channel["snippet"]
            stats = channel["statistics"]

            console.print("[green]✓ Authenticated[/green]")
            console.print(f"  Channel: [bold]{snippet['title']}[/bold]")
            console.print(f"  Subscribers: {stats.get('subscriberCount', 'N/A')}")
            console.print(f"  Videos: {stats.get('videoCount', 'N/A')}")
    except Exception as e:
        console.print(f"[red]Error checking status: {e}[/red]")


def logout():
    """Remove stored credentials."""
    clear_credentials()
    console.print("[green]✓ Logged out successfully[/green]")
