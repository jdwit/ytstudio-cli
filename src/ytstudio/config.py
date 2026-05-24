import json
import os
import re
import shutil
from pathlib import Path

from rich.prompt import Prompt

from ytstudio.ui import console, success_message

CONFIG_DIR = Path.home() / ".config" / "ytstudio-cli"
CLIENT_SECRETS_FILE = CONFIG_DIR / "client_secrets.json"
PROFILES_DIR = CONFIG_DIR / "profiles"
STATE_FILE = CONFIG_DIR / "state.json"

# Pre-profiles single credentials file, kept only for one-shot migration.
LEGACY_CREDENTIALS_FILE = CONFIG_DIR / "credentials.json"

DEFAULT_PROFILE = "default"
PROFILE_ENV_VAR = "YTSTUDIO_PROFILE"

_VALID_PROFILE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


def ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def _write_private(path: Path, text: str) -> None:
    """Write a file that holds secrets with owner-only permissions."""
    path.write_text(text)
    path.chmod(0o600)


# --- client secrets (shared OAuth app, identical for every profile) ---


def setup_credentials(client_secrets_file: str | None = None) -> None:
    ensure_config_dir()

    if client_secrets_file:
        # Copy provided file
        source = Path(client_secrets_file)
        if not source.exists():
            console.print(f"[red]File not found: {client_secrets_file}[/red]")
            raise SystemExit(1)

        _write_private(CLIENT_SECRETS_FILE, source.read_text())
        success_message(f"Client secrets saved to {CLIENT_SECRETS_FILE}")
    else:
        # Interactive setup
        console.print("\n[bold]ytstudio-cli Setup[/bold]\n")
        console.print("You need to create a Google Cloud project and OAuth credentials.")
        console.print("See: https://github.com/jdwit/ytstudio-cli#setup\n")

        client_id = Prompt.ask("Enter your OAuth Client ID")
        client_secret = Prompt.ask("Enter your OAuth Client Secret")

        secrets = {
            "installed": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost"],
            }
        }

        _write_private(CLIENT_SECRETS_FILE, json.dumps(secrets, indent=2))
        console.print()
        success_message(f"Client secrets saved to {CLIENT_SECRETS_FILE}")

    console.print("\nRun [bold]ytstudio login[/bold] to authenticate with YouTube.")


def get_client_secrets() -> dict | None:
    if not CLIENT_SECRETS_FILE.exists():
        return None
    return json.loads(CLIENT_SECRETS_FILE.read_text())


# --- profiles (one named credential set per YouTube channel) ---


def is_valid_profile_name(name: str) -> bool:
    return bool(_VALID_PROFILE_NAME.match(name))


def _load_state() -> dict:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text())
    except json.JSONDecodeError:
        return {}


def _save_state(state: dict) -> None:
    ensure_config_dir()
    STATE_FILE.write_text(json.dumps(state, indent=2))


def get_active_profile() -> str:
    env = os.environ.get(PROFILE_ENV_VAR)
    if env:
        return env
    return _load_state().get("active_profile", DEFAULT_PROFILE)


def set_active_profile(name: str) -> None:
    state = _load_state()
    state["active_profile"] = name
    _save_state(state)


def profile_dir(name: str) -> Path:
    return PROFILES_DIR / name


def credentials_path(name: str | None = None) -> Path:
    return profile_dir(name or get_active_profile()) / "credentials.json"


def _meta_path(name: str) -> Path:
    return profile_dir(name) / "meta.json"


def list_profiles() -> list[str]:
    if not PROFILES_DIR.exists():
        return []
    return sorted(p.name for p in PROFILES_DIR.iterdir() if p.is_dir())


def profile_exists(name: str) -> bool:
    return profile_dir(name).is_dir()


def remove_profile(name: str) -> None:
    target = profile_dir(name)
    if target.exists():
        shutil.rmtree(target)

    state = _load_state()
    if state.get("active_profile") == name:
        state.pop("active_profile", None)
        _save_state(state)


def save_credentials(credentials: dict, name: str | None = None) -> None:
    target = profile_dir(name or get_active_profile())
    target.mkdir(parents=True, exist_ok=True)
    _write_private(target / "credentials.json", json.dumps(credentials, indent=2))


def load_credentials(name: str | None = None) -> dict | None:
    path = credentials_path(name)
    if not path.exists():
        return None
    return json.loads(path.read_text())


def clear_credentials(name: str | None = None) -> None:
    path = credentials_path(name)
    if path.exists():
        path.unlink()


def save_profile_meta(name: str, meta: dict) -> None:
    target = profile_dir(name)
    target.mkdir(parents=True, exist_ok=True)
    _meta_path(name).write_text(json.dumps(meta, indent=2))


def load_profile_meta(name: str) -> dict:
    path = _meta_path(name)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}


def migrate_legacy_credentials() -> bool:
    """Move a pre-profiles credentials.json into the default profile. One-shot."""
    if not LEGACY_CREDENTIALS_FILE.exists() or list_profiles():
        return False

    dest = profile_dir(DEFAULT_PROFILE)
    dest.mkdir(parents=True, exist_ok=True)
    _write_private(dest / "credentials.json", LEGACY_CREDENTIALS_FILE.read_text())
    LEGACY_CREDENTIALS_FILE.unlink()
    set_active_profile(DEFAULT_PROFILE)
    return True
