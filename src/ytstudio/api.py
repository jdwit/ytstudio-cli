import typer
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from ytstudio.config import (
    CLIENT_SECRETS_FILE,
    clear_credentials,
    load_credentials,
    save_credentials,
)
from ytstudio.ui import console, success_message


def handle_api_error(error: HttpError) -> None:
    if error.resp.status == 403:
        error_details = error.error_details[0] if error.error_details else {}
        reason = error_details.get("reason", "")

        if reason == "quotaExceeded":
            console.print(
                "[red]Daily YouTube API quota exceeded.[/red] "
                "Quota resets at midnight Pacific Time (PT).\n"
                "See: https://developers.google.com/youtube/v3/guides/quota_and_compliance_audits"
            )
            raise SystemExit(1) from None

        if reason == "forbidden":
            console.print("[red]Access denied. You may not have permission for this action.[/red]")
            raise SystemExit(1) from None

    # Re-raise for other errors
    raise error


def api(request):
    """Execute an API request with automatic error handling.

    Usage:
        response = api(service.videos().list(part="snippet", id=video_id))
    """
    try:
        return request.execute()
    except HttpError as e:
        handle_api_error(e)
    except RefreshError:
        console.print(
            "[red]Session expired or revoked.[/red] Run [bold]ytstudio login[/bold] to re-authenticate."
        )
        raise SystemExit(1) from None


# YouTube API scopes
SCOPES = [
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]


def authenticate() -> None:
    if not CLIENT_SECRETS_FILE.exists():
        console.print("[red]No client secrets found. Run 'ytstudio init' first.[/red]")
        raise SystemExit(1) from None

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

    console.print()
    if response.get("items"):
        channel = response["items"][0]["snippet"]
        success_message(f"Logged in as: {channel['title']}")
    else:
        success_message("Authentication successful")


def get_credentials() -> Credentials | None:
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
        try:
            credentials.refresh(Request())
        except RefreshError:
            console.print(
                "[red]Session expired or revoked.[/red] Run [bold]ytstudio login[/bold] to re-authenticate."
            )
            raise SystemExit(1) from None
        # Save refreshed credentials
        creds_data["token"] = credentials.token
        save_credentials(creds_data)

    return credentials


def get_authenticated_service(api_name: str = "youtube", version: str = "v3"):
    credentials = get_credentials()
    if not credentials:
        console.print("[red]Not authenticated. Run 'ytstudio login' first.[/red]")
        raise typer.Exit(1)
    return build(api_name, version, credentials=credentials)


def get_status() -> None:
    creds_data = load_credentials()

    if not creds_data:
        console.print("[yellow]Not authenticated. Run 'ytstudio login' to authenticate.[/yellow]")
        return

    credentials = get_credentials()
    if not credentials or not credentials.valid:
        console.print(
            "[yellow]Credentials expired. Run 'ytstudio login' to re-authenticate.[/yellow]"
        )
        return

    # Get channel info
    service = build("youtube", "v3", credentials=credentials)
    response = api(service.channels().list(part="snippet,statistics", mine=True))

    if response.get("items"):
        channel = response["items"][0]
        snippet = channel["snippet"]
        stats = channel["statistics"]

        success_message("Authenticated")
        console.print(f"  Channel: [bold]{snippet['title']}[/bold]")
        console.print(f"  Subscribers: {stats.get('subscriberCount', 'N/A')}")
        console.print(f"  Videos: {stats.get('videoCount', 'N/A')}")


def logout() -> None:
    clear_credentials()
    success_message("Logged out successfully")
