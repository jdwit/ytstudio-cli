from unittest.mock import patch

import pytest

from ytstudio import config


@pytest.fixture
def temp_config(tmp_path):
    config_dir = tmp_path / ".config" / "ytstudio-cli"
    config_dir.mkdir(parents=True)

    with (
        patch.object(config, "CONFIG_DIR", config_dir),
        patch.object(config, "CLIENT_SECRETS_FILE", config_dir / "client_secrets.json"),
        patch.object(config, "CREDENTIALS_FILE", config_dir / "credentials.json"),
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


class TestSetupCredentials:
    def test_setup_with_file(self, temp_config, tmp_path):
        source = tmp_path / "secrets.json"
        source.write_text('{"installed": {"client_id": "test"}}')

        config.setup_credentials(str(source))

        assert config.get_client_secrets()["installed"]["client_id"] == "test"

    def test_setup_with_missing_file(self, temp_config):
        with pytest.raises(SystemExit):
            config.setup_credentials("/nonexistent/file.json")
