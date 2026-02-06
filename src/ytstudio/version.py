import json
import urllib.request
from datetime import datetime, timedelta
from importlib.metadata import version

from packaging.version import Version

from ytstudio.config import CONFIG_DIR

VERSION_CACHE_FILE = CONFIG_DIR / "version_check.json"
PYPI_URL = "https://pypi.org/pypi/ytstudio-cli/json"
CACHE_DURATION = timedelta(days=1)


def get_current_version() -> str:
    return version("ytstudio-cli")


def check_pypi_version() -> str | None:
    """Fetch the latest version from PyPI, returns None on failure"""
    try:
        with urllib.request.urlopen(PYPI_URL, timeout=5) as response:
            data = json.loads(response.read().decode())
            return data["info"]["version"]
    except Exception:
        return None


def _load_cache() -> dict | None:
    if not VERSION_CACHE_FILE.exists():
        return None
    try:
        return json.loads(VERSION_CACHE_FILE.read_text())
    except Exception:
        return None


def _save_cache(latest_version: str) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    cache = {
        "latest_version": latest_version,
        "checked_at": datetime.now().isoformat(),
    }
    VERSION_CACHE_FILE.write_text(json.dumps(cache))


def _is_cache_valid(cache: dict) -> bool:
    try:
        checked_at = datetime.fromisoformat(cache["checked_at"])
        return datetime.now() - checked_at < CACHE_DURATION
    except Exception:
        return False


def get_latest_version(use_cache: bool = True) -> str | None:
    """Get latest version, using cache if available and valid"""
    if use_cache:
        cache = _load_cache()
        if cache and _is_cache_valid(cache):
            return cache.get("latest_version")

    latest = check_pypi_version()
    if latest:
        _save_cache(latest)
    return latest


def is_update_available() -> tuple[bool, str | None]:
    """Check if an update is available. Returns (is_available, latest_version)"""
    latest = get_latest_version()
    if not latest:
        return False, None

    current = get_current_version()
    try:
        return Version(latest) > Version(current), latest
    except Exception:
        return False, None
