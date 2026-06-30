import json
import stat
from unittest.mock import MagicMock, patch

import pytest

from ytstudio import config


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


class TestCredentials:
    def test_save_and_load(self, temp_config):
        creds = {"token": "test_token"}
        config.save_credentials(creds)
        assert config.load_credentials() == creds

    def test_load_returns_none_when_missing(self, temp_config):
        assert config.load_credentials() is None

    def test_clear(self, temp_config):
        config.save_credentials({"token": "test"})
        config.clear_credentials()
        assert config.load_credentials() is None

    def test_credentials_file_is_private(self, temp_config):
        config.save_credentials({"token": "secret"})
        mode = stat.S_IMODE(config.credentials_path().stat().st_mode)
        assert mode == 0o600

    def test_profile_dir_is_private(self, temp_config):
        config.save_credentials({"token": "secret"}, name="work")
        mode = stat.S_IMODE(config.profile_dir("work").stat().st_mode)
        assert mode == 0o700

    def test_load_returns_none_on_corrupt_json(self, temp_config):
        config.save_credentials({"token": "ok"}, name="work")
        config.credentials_path("work").write_text("{not json")
        assert config.load_credentials("work") is None


class TestSetupCredentials:
    def test_setup_with_file(self, temp_config, tmp_path):
        source = tmp_path / "secrets.json"
        source.write_text('{"installed": {"client_id": "test"}}')

        config.setup_credentials(str(source))

        assert config.get_client_secrets()["installed"]["client_id"] == "test"

    def test_setup_with_missing_file(self, temp_config):
        with pytest.raises(SystemExit):
            config.setup_credentials("/nonexistent/file.json")


class TestActiveProfile:
    def test_default_when_unset(self, temp_config):
        assert config.get_active_profile() == config.DEFAULT_PROFILE

    def test_set_and_get(self, temp_config):
        config.set_active_profile("work")
        assert config.get_active_profile() == "work"

    def test_env_override_wins(self, temp_config, monkeypatch):
        config.set_active_profile("work")
        monkeypatch.setenv(config.PROFILE_ENV_VAR, "personal")
        assert config.get_active_profile() == "personal"

    def test_invalid_env_is_ignored(self, temp_config, monkeypatch):
        config.set_active_profile("work")
        monkeypatch.setenv(config.PROFILE_ENV_VAR, "../../etc")
        assert config.get_active_profile() == "work"


class TestProfiles:
    def test_save_under_named_profile(self, temp_config):
        config.save_credentials({"token": "a"}, name="work")
        config.save_credentials({"token": "b"}, name="home")
        assert config.load_credentials("work") == {"token": "a"}
        assert config.load_credentials("home") == {"token": "b"}

    def test_active_profile_routes_credentials(self, temp_config):
        config.set_active_profile("work")
        config.save_credentials({"token": "w"})
        assert config.load_credentials("work") == {"token": "w"}
        assert config.load_credentials("home") is None

    def test_list_profiles_sorted(self, temp_config):
        assert config.list_profiles() == []
        config.save_credentials({"token": "a"}, name="work")
        config.save_credentials({"token": "b"}, name="home")
        assert config.list_profiles() == ["home", "work"]

    def test_profile_exists(self, temp_config):
        assert not config.profile_exists("work")
        config.save_credentials({"token": "a"}, name="work")
        assert config.profile_exists("work")

    def test_remove_profile(self, temp_config):
        config.save_credentials({"token": "a"}, name="work")
        config.remove_profile("work")
        assert not config.profile_exists("work")

    def test_remove_active_profile_resets_active(self, temp_config):
        config.save_credentials({"token": "a"}, name="work")
        config.set_active_profile("work")
        config.remove_profile("work")
        assert config.get_active_profile() == config.DEFAULT_PROFILE


class TestProfileNames:
    @pytest.mark.parametrize("name", ["work", "work-2", "home_tv", "a", "Channel1"])
    def test_valid(self, name):
        assert config.is_valid_profile_name(name)

    @pytest.mark.parametrize(
        "name", ["", "..", "a/b", "a b", ".hidden", "work.tv", "wo:rk", "work\n", "/abs"]
    )
    def test_invalid(self, name):
        assert not config.is_valid_profile_name(name)

    def test_profile_dir_rejects_traversal(self, temp_config):
        with pytest.raises(ValueError):
            config.profile_dir("../../etc")

    def test_profile_exists_false_for_invalid_name(self, temp_config):
        assert config.profile_exists("../../etc") is False


class TestProfileMeta:
    def test_save_and_load(self, temp_config):
        config.save_profile_meta("work", {"title": "My Channel"})
        assert config.load_profile_meta("work")["title"] == "My Channel"

    def test_missing_returns_empty(self, temp_config):
        assert config.load_profile_meta("work") == {}


class TestMigration:
    def test_migrates_legacy_credentials(self, temp_config):
        config.ensure_config_dir()
        config.LEGACY_CREDENTIALS_FILE.write_text('{"token": "legacy"}')

        migrated = config.migrate_legacy_credentials()

        assert migrated is True
        assert config.load_credentials("default") == {"token": "legacy"}
        assert config.get_active_profile() == "default"
        assert not config.LEGACY_CREDENTIALS_FILE.exists()

    def test_noop_without_legacy_file(self, temp_config):
        assert config.migrate_legacy_credentials() is False

    def test_noop_when_profiles_already_exist(self, temp_config):
        config.save_credentials({"token": "new"}, name="work")
        config.ensure_config_dir()
        config.LEGACY_CREDENTIALS_FILE.write_text('{"token": "legacy"}')

        assert config.migrate_legacy_credentials() is False
        assert config.LEGACY_CREDENTIALS_FILE.exists()


class TestCrossPlatformLock:
    def test_config_lock_roundtrip(self, temp_config):
        """The lock acquires and releases without error on the host platform."""
        with config._config_lock():
            pass
        assert (temp_config / ".lock").exists()

    def test_lock_uses_msvcrt_when_fcntl_absent(self, temp_config):
        """On Windows (no fcntl) the lock falls through to msvcrt.locking."""
        fake_msvcrt = MagicMock()
        fake_msvcrt.LK_LOCK = 1
        fake_msvcrt.LK_UNLCK = 0
        with (
            patch.object(config, "fcntl", None),
            patch.object(config, "msvcrt", fake_msvcrt),
            config._config_lock(),
        ):
            pass
        # msvcrt.locking(fd, mode, nbytes); fd is runtime-dependent so assert on mode/nbytes.
        modes = [(call.args[1], call.args[2]) for call in fake_msvcrt.locking.call_args_list]
        assert (fake_msvcrt.LK_LOCK, 1) in modes
        assert (fake_msvcrt.LK_UNLCK, 1) in modes

    def test_lock_degrades_without_any_primitive(self, temp_config):
        """With neither fcntl nor msvcrt the lock is a no-op, not a crash."""
        with (
            patch.object(config, "fcntl", None),
            patch.object(config, "msvcrt", None),
            config._config_lock(),
        ):
            pass

    def test_set_active_profile_under_simulated_windows(self, temp_config):
        """A real state mutation works on the msvcrt code path."""
        fake_msvcrt = MagicMock()
        fake_msvcrt.LK_LOCK = 1
        fake_msvcrt.LK_UNLCK = 0
        with patch.object(config, "fcntl", None), patch.object(config, "msvcrt", fake_msvcrt):
            config.set_active_profile("work")
        assert config.get_active_profile() == "work"


class TestAtomicState:
    def test_state_file_write_is_atomic(self, temp_config):
        """A truncated/partial state.json must not slip past _save_state."""
        config.set_active_profile("work")
        # No leftover temp file from the atomic rename.
        assert not (temp_config / "state.json.tmp").exists()
        assert json.loads(config.STATE_FILE.read_text())["active_profile"] == "work"


class TestListProfilesFiltering:
    def test_list_profiles_skips_invalid_directory_names(self, temp_config):
        config.save_credentials({"token": "a"}, name="work")
        # Simulate a stray directory with an invalid profile name (e.g. left over
        # from a manual edit). list_profiles must not surface it.
        config.PROFILES_DIR.mkdir(parents=True, exist_ok=True)
        (config.PROFILES_DIR / "not.a.profile").mkdir()
        (config.PROFILES_DIR / ".hidden").mkdir()

        assert config.list_profiles() == ["work"]

    def test_migration_skips_when_only_invalid_dirs_exist(self, temp_config):
        """Stray invalid directories must not block legacy migration."""
        config.ensure_config_dir()
        config.PROFILES_DIR.mkdir(parents=True)
        (config.PROFILES_DIR / "not.a.profile").mkdir()
        config.LEGACY_CREDENTIALS_FILE.write_text('{"token": "legacy"}')

        migrated = config.migrate_legacy_credentials()

        assert migrated is True
        assert config.load_credentials("default") == {"token": "legacy"}
