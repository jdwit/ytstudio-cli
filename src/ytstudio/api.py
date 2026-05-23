from urllib.parse import parse_qs, urlparse

import typer
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from rich.prompt import Prompt

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

HEADLESS_REDIRECT_URI = "http://127.0.0.1:9876/"


def _create_flow() -> InstalledAppFlow:
    return InstalledAppFlow.from_client_secrets_file(
        str(CLIENT_SECRETS_FILE),
        scopes=SCOPES,
    )


def _save_credentials(credentials: Credentials) -> None:
    creds_data = {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": credentials.scopes,
    }
    save_credentials(creds_data)


def _show_login_success(credentials: Credentials) -> None:
    service = build("youtube", "v3", credentials=credentials)
    response = service.channels().list(part="snippet", mine=True).execute()

    console.print()
    if response.get("items"):
        channel = response["items"][0]["snippet"]
        success_message(f"Logged in as: {channel['title']}")
    else:
        success_message("Authentication successful")


def _parse_authorization_response(authorization_response: str, expected_state: str) -> str:
    parsed_url = urlparse(authorization_response)
    query = parse_qs(parsed_url.query)

    if error := query.get("error"):
        error_description = query.get("error_description", [""])[0]
        message = error_description or error[0]
        console.print(f"[red]Authorization failed: {message}[/red]")
        raise SystemExit(1) from None

    if not query.get("code"):
        console.print("[red]Redirect URL is missing an authorization code.[/red]")
        raise SystemExit(1) from None

    state = query.get("state", [""])[0]
    if state != expected_state:
        console.print("[red]Redirect URL state does not match this login attempt.[/red]")
        raise SystemExit(1) from None

    return query["code"][0]


def _authenticate_headless() -> Credentials:
    flow = _create_flow()
    flow.redirect_uri = HEADLESS_REDIRECT_URI
    authorization_url, state = flow.authorization_url(prompt="consent")

    console.print("Open this URL in a browser on any machine:\n")
    console.print(f"[bold]{authorization_url}[/bold]\n")
    console.print(
        "After approving access, the browser will fail to load a 127.0.0.1 page. "
        "Copy the full failed redirect URL from the address bar and paste it below."
    )

    authorization_response = Prompt.ask("Redirect URL").strip()
    code = _parse_authorization_response(authorization_response, state)

    try:
        flow.fetch_token(code=code)
    except Exception as error:
        console.print(f"[red]Could not complete OAuth token exchange: {error}[/red]")
        raise SystemExit(1) from None

    return flow.credentials


def authenticate(headless: bool = False) -> None:
    if not CLIENT_SECRETS_FILE.exists():
        console.print("[red]No client secrets found. Run 'ytstudio init' first.[/red]")
        raise SystemExit(1) from None

    console.print("[bold]Authenticating with YouTube...[/bold]\n")

    if headless:
        credentials = _authenticate_headless()
    else:
        flow = _create_flow()
        credentials = flow.run_local_server(
            port=9876,
            prompt="consent",
            open_browser=True,
        )

    _save_credentials(credentials)
    _show_login_success(credentials)


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
