import json
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from ytstudio import demo_service
from ytstudio.main import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _clear_demo_env(monkeypatch):
    """Each test starts with a clean YTSTUDIO_DEMO state and a fresh banner flag."""
    monkeypatch.delenv("YTSTUDIO_DEMO", raising=False)
    demo_service._reset_banner_for_tests()
    yield


def test_demo_videos_uses_fixture_data():
    result = runner.invoke(app, ["demo", "videos"])
    assert result.exit_code == 0, result.stdout
    assert "Building a Cabin" in result.stdout


def test_demo_videos_json_output():
    result = runner.invoke(app, ["demo", "videos", "-o", "json"])
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert isinstance(payload["videos"], list)
    assert len(payload["videos"]) >= 5


def test_demo_analytics_renders_overview():
    result = runner.invoke(app, ["demo", "analytics"])
    assert result.exit_code == 0, result.stdout
    # Either the human format `123.5K` or any digit run shows something rendered.
    assert any(ch.isdigit() for ch in result.stdout)
    assert "views" in result.stdout.lower()


def test_demo_comments_lists_fake_comments():
    result = runner.invoke(app, ["demo", "comments"])
    assert result.exit_code == 0, result.stdout
    assert "Maya Ortiz" in result.stdout or "Ben Liu" in result.stdout


def test_demo_tour_runs_all_three_sections():
    result = runner.invoke(app, ["demo", "tour", "--no-pauses"])
    assert result.exit_code == 0, result.stdout
    assert "Building a Cabin" in result.stdout
    assert "views" in result.stdout.lower()
    assert "Maya Ortiz" in result.stdout or "Priya Shah" in result.stdout


def test_demo_info_lists_sources_and_env_var():
    result = runner.invoke(app, ["demo", "info"])
    assert result.exit_code == 0, result.stdout
    assert "YTSTUDIO_DEMO" in result.stdout
    assert "fixtures" in result.stdout


def test_env_var_routes_existing_videos_list_to_fake(monkeypatch):
    monkeypatch.setenv("YTSTUDIO_DEMO", "1")
    with patch("ytstudio.api.build") as build_mock:
        result = runner.invoke(app, ["videos", "list"])
    assert result.exit_code == 0, result.stdout
    assert "Building a Cabin" in result.stdout
    build_mock.assert_not_called()


def test_env_var_routes_analytics_overview_to_fake(monkeypatch):
    monkeypatch.setenv("YTSTUDIO_DEMO", "1")
    with patch("ytstudio.api.build") as build_mock:
        result = runner.invoke(app, ["analytics", "overview"])
    assert result.exit_code == 0, result.stdout
    assert "views" in result.stdout.lower()
    build_mock.assert_not_called()


def test_env_var_status_short_circuits_without_credentials(monkeypatch):
    monkeypatch.setenv("YTSTUDIO_DEMO", "1")
    with patch("ytstudio.api.load_credentials") as load_mock:
        result = runner.invoke(app, ["status"])
    assert result.exit_code == 0, result.stdout
    assert "demo" in result.stdout.lower()
    load_mock.assert_not_called()


def test_demo_banner_printed_once(monkeypatch, capsys):
    monkeypatch.setenv("YTSTUDIO_DEMO", "1")
    demo_service._reset_banner_for_tests()
    monkeypatch.setattr("sys.argv", ["ytstudio", "demo", "info"])
    demo_service.print_demo_banner_once()
    demo_service.print_demo_banner_once()
    captured = capsys.readouterr()
    assert captured.err.count("demo mode") == 1


def test_real_path_unaffected_when_env_unset(monkeypatch, mock_auth):
    monkeypatch.delenv("YTSTUDIO_DEMO", raising=False)
    result = runner.invoke(app, ["videos", "list"])
    assert result.exit_code == 0, result.stdout
    mock_auth.channels.return_value.list.assert_called()
