from unittest.mock import MagicMock, patch

import pytest
from click.exceptions import Exit
from googleapiclient.errors import HttpError
from typer.testing import CliRunner

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

    def test_status_not_authenticated(self):
        with patch("ytstudio.api.load_credentials", return_value=None):
            result = runner.invoke(app, ["status"])
            assert "Not authenticated" in result.stdout
