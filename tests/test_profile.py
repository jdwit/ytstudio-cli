import os
import stat
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


class TestProfileBrand:
    def test_brand_path_helper(self, temp_config):
        path = config.brand_path("work")
        assert path.name == "brand.md"
        assert path.parent == config.profile_dir("work")

    def test_set_and_show(self, temp_config, tmp_path):
        _make_profile("work")
        config.set_active_profile("work")
        src = tmp_path / "brand.md"
        src.write_text("# Voice\nPlayful and concise.")

        set_result = runner.invoke(app, ["profile", "brand", "set", "--file", str(src)])
        assert set_result.exit_code == 0

        show_result = runner.invoke(app, ["profile", "brand", "show"])
        assert show_result.exit_code == 0
        assert "Playful and concise." in show_result.stdout

    def test_set_targets_named_profile(self, temp_config, tmp_path):
        _make_profile("work")
        _make_profile("home")
        config.set_active_profile("home")
        src = tmp_path / "b.md"
        src.write_text("work voice")

        result = runner.invoke(app, ["profile", "brand", "set", "--file", str(src), "-p", "work"])
        assert result.exit_code == 0
        assert config.load_brand("work") == "work voice"
        assert config.load_brand("home") is None

    def test_show_missing(self, temp_config):
        _make_profile("work")
        config.set_active_profile("work")
        result = runner.invoke(app, ["profile", "brand", "show"])
        assert result.exit_code == 1
        assert "No brand voice" in result.stdout

    def test_set_bad_profile(self, temp_config, tmp_path):
        src = tmp_path / "b.md"
        src.write_text("x")
        result = runner.invoke(app, ["profile", "brand", "set", "--file", str(src), "-p", "ghost"])
        assert result.exit_code == 1
        assert "No profile named" in result.stdout

    def test_set_missing_file(self, temp_config):
        _make_profile("work")
        config.set_active_profile("work")
        result = runner.invoke(app, ["profile", "brand", "set", "--file", "/nope/x.md"])
        assert result.exit_code == 1
        assert "File not found" in result.stdout

    def test_edit_seeds_template_and_perms(self, temp_config):
        _make_profile("work")
        config.set_active_profile("work")
        with patch("ytstudio.commands.profile.subprocess.run") as run:
            result = runner.invoke(app, ["profile", "brand", "edit"])
        assert result.exit_code == 0
        run.assert_called_once()
        path = config.brand_path("work")
        assert path.exists()
        assert "Brand voice" in path.read_text()
        if os.name == "posix":
            assert stat.S_IMODE(path.stat().st_mode) == 0o600

    def test_edit_keeps_existing_content(self, temp_config, tmp_path):
        _make_profile("work")
        config.set_active_profile("work")
        config.save_brand("work", "existing voice")
        with patch("ytstudio.commands.profile.subprocess.run"):
            result = runner.invoke(app, ["profile", "brand", "edit"])
        assert result.exit_code == 0
        assert config.load_brand("work") == "existing voice"

    def test_edit_reasserts_owner_only_perms(self, temp_config):
        if os.name != "posix":
            pytest.skip("POSIX permissions only")
        _make_profile("work")
        config.set_active_profile("work")
        path = config.brand_path("work")

        def loosen(*args, **kwargs):
            # Simulate an editor that rewrites the file with world-readable perms.
            path.write_text("edited by editor")
            path.chmod(0o644)

        with patch("ytstudio.commands.profile.subprocess.run", side_effect=loosen):
            result = runner.invoke(app, ["profile", "brand", "edit"])
        assert result.exit_code == 0
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        assert path.read_text() == "edited by editor"
