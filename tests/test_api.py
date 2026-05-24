from unittest.mock import MagicMock, patch

import pytest
from click.exceptions import Exit
from googleapiclient.errors import HttpError
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


class TestHandleApiError:
    def test_quota_exceeded_exits(self):
        error = make_http_error(403, "quotaExceeded")

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


class TestGetAuthenticatedService:
    def test_exits_when_no_credentials(self):
        with patch("ytstudio.api.get_credentials", return_value=None), pytest.raises(Exit):
            get_authenticated_service()


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


class TestAuthenticate:
    def test_normal_login_uses_local_server(self):
        credentials = MagicMock()
        flow = MagicMock()
        flow.run_local_server.return_value = credentials

        with (
            patch("ytstudio.api.CLIENT_SECRETS_FILE") as mock_file,
            patch("ytstudio.api._create_flow", return_value=flow),
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
        save_credentials.assert_called_once_with(credentials, None)
        show_login_success.assert_called_once_with(credentials, None)

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
            patch("ytstudio.api.Prompt.ask", return_value=redirect_url),
            patch("ytstudio.api._save_credentials") as save_credentials,
            patch("ytstudio.api._show_login_success") as show_login_success,
        ):
            mock_file.exists.return_value = True

            api_module.authenticate(headless=True)

        assert flow.redirect_uri == api_module.HEADLESS_REDIRECT_URI
        flow.authorization_url.assert_called_once_with(prompt="consent")
        flow.fetch_token.assert_called_once_with(code="test-code")
        save_credentials.assert_called_once_with(credentials, None)
        show_login_success.assert_called_once_with(credentials, None)

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
