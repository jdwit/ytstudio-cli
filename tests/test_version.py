import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from ytstudio import version as version_module


def _use_temp_cache(monkeypatch, tmp_path):
    cache = tmp_path / "version_check.json"
    monkeypatch.setattr(version_module, "VERSION_CACHE_FILE", cache)
    return cache


class TestVersionCheck:
    def test_check_pypi_version_returns_latest(self):
        response = MagicMock()
        response.read.return_value = json.dumps({"info": {"version": "1.2.3"}}).encode()
        response.__enter__.return_value = response

        with patch("ytstudio.version.urllib.request.urlopen", return_value=response) as urlopen:
            assert version_module.check_pypi_version() == "1.2.3"

        urlopen.assert_called_once_with(version_module.PYPI_URL, timeout=5)

    def test_check_pypi_version_returns_none_on_error(self):
        with patch("ytstudio.version.urllib.request.urlopen", side_effect=OSError("offline")):
            assert version_module.check_pypi_version() is None

    def test_get_latest_version_uses_valid_cache(self, monkeypatch, tmp_path):
        cache = _use_temp_cache(monkeypatch, tmp_path)
        cache.write_text(
            json.dumps(
                {
                    "latest_version": "2.0.0",
                    "checked_at": datetime.now().isoformat(),
                }
            )
        )

        with patch("ytstudio.version.check_pypi_version") as check_pypi:
            assert version_module.get_latest_version() == "2.0.0"

        check_pypi.assert_not_called()

    def test_get_latest_version_refreshes_stale_cache(self, monkeypatch, tmp_path):
        cache = _use_temp_cache(monkeypatch, tmp_path)
        cache.write_text(
            json.dumps(
                {
                    "latest_version": "1.0.0",
                    "checked_at": (datetime.now() - timedelta(days=2)).isoformat(),
                }
            )
        )

        with patch("ytstudio.version.check_pypi_version", return_value="2.0.0"):
            assert version_module.get_latest_version() == "2.0.0"

        assert json.loads(cache.read_text())["latest_version"] == "2.0.0"

    def test_get_latest_version_ignores_invalid_cache(self, monkeypatch, tmp_path):
        cache = _use_temp_cache(monkeypatch, tmp_path)
        cache.write_text("not json")

        with patch("ytstudio.version.check_pypi_version", return_value="2.0.0"):
            assert version_module.get_latest_version() == "2.0.0"

    @pytest.mark.parametrize(
        ("latest", "current", "expected"),
        [
            ("2.0.0", "1.0.0", (True, "2.0.0")),
            ("1.0.0", "1.0.0", (False, "1.0.0")),
            (None, "1.0.0", (False, None)),
            ("not-a-version", "1.0.0", (False, None)),
        ],
    )
    def test_is_update_available(self, latest, current, expected):
        with (
            patch("ytstudio.version.get_latest_version", return_value=latest),
            patch("ytstudio.version.get_current_version", return_value=current),
        ):
            assert version_module.is_update_available() == expected
