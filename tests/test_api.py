from unittest.mock import MagicMock, patch

import pytest
from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError
from typer import Exit
from typer.testing import CliRunner

from ytstudio import api as api_module
from ytstudio.api import api, get_authenticated_service, handle_api_error
from ytstudio.main import app

runner = CliRunner()


def make_http_error(status: int, reason: str = ""):
    resp = MagicMock()
    resp.status = status
    error = HttpError(resp, b"{}")
    error.error_details = [{"reason": reason}] if reason else []
    return error


class TestScopes:
    def test_includes_monetary_analytics_scope(self):
        # Revenue/earnings metrics (estimatedRevenue, cpm, ...) require this
        # scope; without it the Analytics API returns 401 for monetary reports.
        assert "https://www.googleapis.com/auth/yt-analytics-monetary.readonly" in api_module.SCOPES


class TestHandleApiError:
    def test_quota_exceeded_exits(self):
        error = make_http_error(403, "quotaExceeded")

        with pytest.raises(SystemExit):
            handle_api_error(error)

    def test_forbidden_exits(self):
        error = make_http_error(403, "forbidden")

        with pytest.raises(SystemExit):
            handle_api_error(error)

    def test_other_errors_reraise(self):
        error = make_http_error(404)

        with pytest.raises(HttpError):
            handle_api_error(error)


class TestApi:
    def test_returns_result(self):
        request = MagicMock()
        request.execute.return_value = {"items": []}

        assert api(request) == {"items": []}

    def test_refresh_error_exits(self):
        request = MagicMock()
        request.execute.side_effect = RefreshError("revoked")

        with pytest.raises(SystemExit):
            api(request)


class TestGetCredentials:
    def test_returns_none_when_profile_has_no_credentials(self):
        with patch("ytstudio.api.load_credentials", return_value=None):
            assert api_module.get_credentials("missing") is None

    def test_refreshes_expired_credentials_and_saves_new_token(self):
        creds_data = {
            "token": "old-token",
            "refresh_token": "refresh-token",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "client-id",
            "client_secret": "client-secret",
            "scopes": api_module.SCOPES,
        }
        credentials = MagicMock()
        credentials.expired = True
        credentials.refresh_token = "refresh-token"
        credentials.token = "new-token"

        with (
            patch("ytstudio.api.load_credentials", return_value=creds_data),
            patch("ytstudio.api.Credentials", return_value=credentials),
            patch("ytstudio.api.Request", return_value="request"),
            patch("ytstudio.api.save_credentials") as save_credentials,
        ):
            assert api_module.get_credentials("work") is credentials

        credentials.refresh.assert_called_once_with("request")
        save_credentials.assert_called_once_with({**creds_data, "token": "new-token"}, "work")

    def test_refresh_error_exits(self):
        credentials = MagicMock()
        credentials.expired = True
        credentials.refresh_token = "refresh-token"
        credentials.refresh.side_effect = RefreshError("revoked")

        with (
            patch("ytstudio.api.load_credentials", return_value={"token": "old"}),
            patch("ytstudio.api.Credentials", return_value=credentials),
            pytest.raises(SystemExit),
        ):
            api_module.get_credentials("work")


class TestGetAuthenticatedService:
    def test_exits_when_no_credentials(self):
        with patch("ytstudio.api.get_credentials", return_value=None), pytest.raises(Exit):
            get_authenticated_service()

    def test_passes_profile_to_get_credentials(self):
        credentials = MagicMock()
        with (
            patch("ytstudio.api.get_credentials", return_value=credentials) as get_creds,
            patch("ytstudio.api.build") as build,
        ):
            get_authenticated_service("youtube", "v3", profile="work")

        get_creds.assert_called_once_with("work")
        build.assert_called_once_with("youtube", "v3", credentials=credentials)


class TestStatus:
    def test_get_status_reports_expired_credentials(self):
        credentials = MagicMock()
        credentials.valid = False
        with (
            patch("ytstudio.api.load_credentials", return_value={"token": "old"}),
            patch("ytstudio.api.get_credentials", return_value=credentials),
        ):
            api_module.get_status("work")

    def test_get_status_prints_channel_details(self):
        credentials = MagicMock()
        credentials.valid = True
        service = MagicMock()
        service.channels.return_value.list.return_value.execute.return_value = {
            "items": [
                {
                    "snippet": {"title": "Channel"},
                    "statistics": {"subscriberCount": "10", "videoCount": "2"},
                }
            ]
        }
        with (
            patch("ytstudio.api.load_credentials", return_value={"token": "ok"}),
            patch("ytstudio.api.get_credentials", return_value=credentials),
            patch("ytstudio.api.build", return_value=service),
        ):
            api_module.get_status("work")

        service.channels.return_value.list.assert_called_once_with(
            part="snippet,statistics", mine=True
        )


class TestCommands:
    def test_login_requires_client_secrets(self):
        with patch("ytstudio.api.CLIENT_SECRETS_FILE") as mock_file:
            mock_file.exists.return_value = False
            result = runner.invoke(app, ["login"])
            assert result.exit_code == 1

    def test_login_headless_passes_option(self):
        with patch("ytstudio.main.authenticate") as authenticate:
            result = runner.invoke(app, ["login", "--headless"])

            assert result.exit_code == 0
            authenticate.assert_called_once_with(headless=True)

    def test_status_not_authenticated(self):
        with patch("ytstudio.api.load_credentials", return_value=None):
            result = runner.invoke(app, ["status"])
            assert "Not authenticated" in result.stdout


class TestHelpers:
    def test_create_flow_uses_client_secrets_and_scopes(self):
        with patch("ytstudio.api.InstalledAppFlow.from_client_secrets_file") as factory:
            assert api_module._create_flow() is factory.return_value

        factory.assert_called_once_with(
            str(api_module.CLIENT_SECRETS_FILE), scopes=api_module.SCOPES
        )

    def test_save_credentials_serializes_oauth_fields(self):
        credentials = MagicMock(
            token="token",
            refresh_token="refresh",
            token_uri="token-uri",
            client_id="client-id",
            client_secret="client-secret",
            scopes=["scope"],
        )

        with patch("ytstudio.api.save_credentials") as save_credentials:
            api_module._save_credentials(credentials, "work")

        save_credentials.assert_called_once_with(
            {
                "token": "token",
                "refresh_token": "refresh",
                "token_uri": "token-uri",
                "client_id": "client-id",
                "client_secret": "client-secret",
                "scopes": ["scope"],
            },
            "work",
        )

    def test_fetch_channel_info_returns_channel_metadata(self):
        service = MagicMock()
        service.channels.return_value.list.return_value.execute.return_value = {
            "items": [{"id": "UC123", "snippet": {"title": "Channel", "customUrl": "@c"}}]
        }

        with patch("ytstudio.api.build", return_value=service):
            assert api_module._fetch_channel_info(MagicMock()) == {
                "id": "UC123",
                "title": "Channel",
                "custom_url": "@c",
            }

    def test_fetch_channel_info_returns_none_when_empty_or_error(self):
        service = MagicMock()
        service.channels.return_value.list.return_value.execute.return_value = {"items": []}
        with patch("ytstudio.api.build", return_value=service):
            assert api_module._fetch_channel_info(MagicMock()) is None

        with patch("ytstudio.api.build", side_effect=RuntimeError("offline")):
            assert api_module._fetch_channel_info(MagicMock()) is None

    def test_show_login_success_saves_profile_meta_when_channel_known(self):
        info = {"id": "UC123", "title": "Channel", "custom_url": "@c"}
        with (
            patch("ytstudio.api._fetch_channel_info", return_value=info),
            patch("ytstudio.api.save_profile_meta") as save_profile_meta,
        ):
            api_module._show_login_success(MagicMock(), "work")

        save_profile_meta.assert_called_once_with("work", info)

    def test_logout_clears_credentials(self):
        with patch("ytstudio.api.clear_credentials") as clear_credentials:
            api_module.logout()

        clear_credentials.assert_called_once()


class TestAuthenticate:
    def test_normal_login_uses_local_server(self):
        credentials = MagicMock()
        flow = MagicMock()
        flow.run_local_server.return_value = credentials

        with (
            patch("ytstudio.api.CLIENT_SECRETS_FILE") as mock_file,
            patch("ytstudio.api._create_flow", return_value=flow),
            patch("ytstudio.api.get_active_profile", return_value="default"),
            patch("ytstudio.api._save_credentials") as save_credentials,
            patch("ytstudio.api._show_login_success") as show_login_success,
        ):
            mock_file.exists.return_value = True

            api_module.authenticate()

        flow.run_local_server.assert_called_once_with(
            port=9876,
            prompt="consent",
            open_browser=True,
        )
        save_credentials.assert_called_once_with(credentials, "default")
        show_login_success.assert_called_once_with(credentials, "default")

    def test_login_resolves_active_profile_once(self):
        """A profile switch mid-OAuth must not redirect freshly minted credentials."""
        credentials = MagicMock()
        flow = MagicMock()
        flow.run_local_server.return_value = credentials

        with (
            patch("ytstudio.api.CLIENT_SECRETS_FILE") as mock_file,
            patch("ytstudio.api._create_flow", return_value=flow),
            patch("ytstudio.api.get_active_profile") as get_active,
            patch("ytstudio.api._save_credentials") as save_credentials,
            patch("ytstudio.api._show_login_success") as show_login_success,
        ):
            mock_file.exists.return_value = True
            get_active.side_effect = ["work", "personal", "personal"]

            api_module.authenticate()

        save_credentials.assert_called_once_with(credentials, "work")
        show_login_success.assert_called_once_with(credentials, "work")

    def test_headless_login_exchanges_pasted_redirect_url(self):
        credentials = MagicMock()
        authorization_url = "https://accounts.google.com/o/oauth2/auth?state=test-state"
        redirect_url = "http://127.0.0.1:9876/?state=test-state&code=test-code"
        flow = MagicMock()
        flow.authorization_url.return_value = (authorization_url, "test-state")
        flow.credentials = credentials

        with (
            patch("ytstudio.api.CLIENT_SECRETS_FILE") as mock_file,
            patch("ytstudio.api._create_flow", return_value=flow),
            patch("ytstudio.api.get_active_profile", return_value="default"),
            patch("ytstudio.api.Prompt.ask", return_value=redirect_url),
            patch("ytstudio.api._save_credentials") as save_credentials,
            patch("ytstudio.api._show_login_success") as show_login_success,
        ):
            mock_file.exists.return_value = True

            api_module.authenticate(headless=True)

        assert flow.redirect_uri == api_module.HEADLESS_REDIRECT_URI
        flow.authorization_url.assert_called_once_with(prompt="consent")
        flow.fetch_token.assert_called_once_with(code="test-code")
        save_credentials.assert_called_once_with(credentials, "default")
        show_login_success.assert_called_once_with(credentials, "default")

    def test_headless_login_rejects_missing_code(self):
        with pytest.raises(SystemExit):
            api_module._parse_authorization_response(
                "http://127.0.0.1:9876/?state=test-state",
                "test-state",
            )

    def test_headless_login_rejects_authorization_error(self):
        with pytest.raises(SystemExit):
            api_module._parse_authorization_response(
                "http://127.0.0.1:9876/?error=access_denied",
                "test-state",
            )

    def test_headless_login_rejects_state_mismatch(self):
        with pytest.raises(SystemExit):
            api_module._parse_authorization_response(
                "http://127.0.0.1:9876/?state=wrong&code=test-code",
                "test-state",
            )

    def test_headless_login_exits_when_token_exchange_fails(self):
        flow = MagicMock()
        flow.authorization_url.return_value = ("https://accounts.google.com/o/oauth2/auth", "state")
        flow.fetch_token.side_effect = ValueError("token exchange failed")

        with (
            patch("ytstudio.api._create_flow", return_value=flow),
            patch(
                "ytstudio.api.Prompt.ask",
                return_value="http://127.0.0.1:9876/?state=state&code=test-code",
            ),
            pytest.raises(SystemExit),
        ):
            api_module._authenticate_headless()
