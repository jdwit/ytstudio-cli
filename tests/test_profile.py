from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from ytstudio import config
from ytstudio.main import app

runner = CliRunner()


@pytest.fixture
def temp_config(tmp_path, monkeypatch):
    config_dir = tmp_path / ".config" / "ytstudio-cli"
    config_dir.mkdir(parents=True)

    monkeypatch.delenv(config.PROFILE_ENV_VAR, raising=False)

    with (
        patch.object(config, "CONFIG_DIR", config_dir),
        patch.object(config, "CLIENT_SECRETS_FILE", config_dir / "client_secrets.json"),
        patch.object(config, "PROFILES_DIR", config_dir / "profiles"),
        patch.object(config, "STATE_FILE", config_dir / "state.json"),
        patch.object(config, "LEGACY_CREDENTIALS_FILE", config_dir / "credentials.json"),
    ):
        yield config_dir


def _make_profile(name, title=None):
    config.save_credentials({"token": "x"}, name=name)
    config.save_profile_meta(name, {"title": title or f"{name} channel"})


class TestProfileAdd:
    def test_add_authenticates_and_activates(self, temp_config):
        def fake_auth(headless=False, profile=None):
            _make_profile(profile)

        with patch("ytstudio.commands.profile.authenticate", side_effect=fake_auth) as auth:
            result = runner.invoke(app, ["profile", "add", "work"])

        assert result.exit_code == 0
        auth.assert_called_once_with(headless=False, profile="work")
        assert config.profile_exists("work")
        assert config.get_active_profile() == "work"

    def test_add_rejects_invalid_name(self, temp_config):
        result = runner.invoke(app, ["profile", "add", "bad/name"])
        assert result.exit_code == 1
        assert not config.profile_exists("bad/name")

    def test_add_rejects_duplicate(self, temp_config):
        _make_profile("work")
        result = runner.invoke(app, ["profile", "add", "work"])
        assert result.exit_code == 1


class TestProfileList:
    def test_list_empty(self, temp_config):
        result = runner.invoke(app, ["profile", "list"])
        assert result.exit_code == 0
        assert "No profiles yet" in result.stdout

    def test_list_shows_profiles_and_active(self, temp_config):
        _make_profile("work", "Work Channel")
        _make_profile("home", "Home Channel")
        config.set_active_profile("home")

        result = runner.invoke(app, ["profile", "list"])

        assert result.exit_code == 0
        assert "Work Channel" in result.stdout
        assert "Home Channel" in result.stdout
        assert "home" in result.stdout


class TestProfileUse:
    def test_use_switches_active(self, temp_config):
        _make_profile("work")
        result = runner.invoke(app, ["profile", "use", "work"])
        assert result.exit_code == 0
        assert config.get_active_profile() == "work"

    def test_use_missing_exits(self, temp_config):
        result = runner.invoke(app, ["profile", "use", "ghost"])
        assert result.exit_code == 1


class TestProfileRemove:
    def test_remove_force(self, temp_config):
        _make_profile("work")
        result = runner.invoke(app, ["profile", "remove", "work", "--force"])
        assert result.exit_code == 0
        assert not config.profile_exists("work")

    def test_remove_missing_exits(self, temp_config):
        result = runner.invoke(app, ["profile", "remove", "ghost"])
        assert result.exit_code == 1

    def test_remove_aborts_without_confirmation(self, temp_config):
        _make_profile("work")
        runner.invoke(app, ["profile", "remove", "work"], input="n\n")
        assert config.profile_exists("work")


class TestProfileStatus:
    def test_status_delegates_to_target(self, temp_config):
        _make_profile("work")
        with patch("ytstudio.commands.profile.get_status") as get_status:
            result = runner.invoke(app, ["profile", "status", "work"])

        assert result.exit_code == 0
        get_status.assert_called_once_with("work")

    def test_status_defaults_to_active(self, temp_config):
        _make_profile("work")
        config.set_active_profile("work")
        with patch("ytstudio.commands.profile.get_status") as get_status:
            result = runner.invoke(app, ["profile", "status"])

        assert result.exit_code == 0
        get_status.assert_called_once_with("work")

    def test_status_missing_profile_exits(self, temp_config):
        result = runner.invoke(app, ["profile", "status", "ghost"])
        assert result.exit_code == 1
