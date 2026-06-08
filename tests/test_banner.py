from typer.testing import CliRunner

from ytstudio.main import app
from ytstudio.version import get_current_version

runner = CliRunner()


def test_version_shows_banner_tagline_and_version():
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert "WWW" in result.stdout
    assert "Manage and analyze your YouTube channel from the terminal." in result.stdout
    assert "Designed for humans and AI agents." in result.stdout
    assert f"v{get_current_version()}" in result.stdout
