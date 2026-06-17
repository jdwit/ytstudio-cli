from unittest.mock import patch

from typer.testing import CliRunner

from ytstudio.main import _show_update_notification, app

runner = CliRunner()


class TestMain:
    def test_version_option_prints_current_version(self):
        with patch("ytstudio.main.get_current_version", return_value="1.2.3"):
            result = runner.invoke(app, ["--version"])

        assert result.exit_code == 0
        assert "ytstudio v1.2.3" in result.stdout

    def test_registers_update_notification_once(self):
        with (
            patch("ytstudio.main.migrate_legacy_credentials") as migrate,
            patch("ytstudio.main.get_status"),
            patch("ytstudio.main.atexit.register") as register,
            patch.dict("ytstudio.main._update_state", {"registered": False}),
        ):
            result = runner.invoke(app, ["status"])

        assert result.exit_code == 0
        migrate.assert_called_once()
        register.assert_called_once()

    def test_show_update_notification_prints_when_available(self):
        with (
            patch("ytstudio.main.is_update_available", return_value=(True, "2.0.0")),
            patch("ytstudio.main.get_current_version", return_value="1.0.0"),
            patch("ytstudio.main.console.print") as print_,
        ):
            _show_update_notification()

        message = print_.call_args.args[0]
        assert "Update available: 1.0.0 → 2.0.0" in message
        assert "uv tool upgrade ytstudio-cli" in message

    def test_show_update_notification_swallows_errors(self):
        with patch("ytstudio.main.is_update_available", side_effect=RuntimeError("network")):
            _show_update_notification()
