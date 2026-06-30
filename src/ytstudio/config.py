import json
import os
import re
import shutil
from contextlib import contextmanager
from pathlib import Path

try:
    import fcntl  # POSIX advisory locking
except ImportError:  # Windows
    fcntl = None
try:
    import msvcrt  # Windows advisory locking
except ImportError:  # POSIX
    msvcrt = None

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

_VALID_PROFILE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")


def is_valid_profile_name(name: str) -> bool:
    return bool(_VALID_PROFILE_NAME.fullmatch(name))


def _ensure_private_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    if os.name == "posix":
        # On Windows chmod only toggles the read-only bit; owner-only is a POSIX guarantee.
        path.chmod(0o700)


def ensure_config_dir() -> None:
    _ensure_private_dir(CONFIG_DIR)


def _ensure_profile_dir(name: str) -> Path:
    ensure_config_dir()
    _ensure_private_dir(PROFILES_DIR)
    target = profile_dir(name)
    _ensure_private_dir(target)
    return target


def _write_private(path: Path, text: str) -> None:
    """Atomically write a secret with owner-only permissions, with no readable window."""
    tmp = path.with_name(path.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, text.encode())
        os.fsync(fd)
    finally:
        os.close(fd)
    tmp.replace(path)


def _atomic_write_text(path: Path, text: str, mode: int = 0o644) -> None:
    tmp = path.with_name(path.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    try:
        os.write(fd, text.encode())
        os.fsync(fd)
    finally:
        os.close(fd)
    tmp.replace(path)


def _lock_file(fh) -> None:
    if fcntl is not None:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
    elif msvcrt is not None:
        fh.seek(0)
        msvcrt.locking(fh.fileno(), msvcrt.LK_LOCK, 1)
    # else: no advisory locking primitive available; a single-user CLI degrades safely.


def _unlock_file(fh) -> None:
    if fcntl is not None:
        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    elif msvcrt is not None:
        fh.seek(0)
        msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)


@contextmanager
def _config_lock():
    """Serialize state mutations and the legacy migration across CLI invocations."""
    ensure_config_dir()
    lock_path = CONFIG_DIR / ".lock"
    with lock_path.open("w") as fh:
        _lock_file(fh)
        try:
            yield
        finally:
            _unlock_file(fh)


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


def _load_state() -> dict:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text())
    except json.JSONDecodeError:
        return {}


def _save_state(state: dict) -> None:
    ensure_config_dir()
    _atomic_write_text(STATE_FILE, json.dumps(state, indent=2))


def get_active_profile() -> str:
    env = os.environ.get(PROFILE_ENV_VAR)
    if env:
        if is_valid_profile_name(env):
            return env
        console.print(
            f"[yellow]Ignoring invalid {PROFILE_ENV_VAR}='{env}'; "
            f"using the configured active channel.[/yellow]"
        )

    name = _load_state().get("active_profile", DEFAULT_PROFILE)
    return name if is_valid_profile_name(name) else DEFAULT_PROFILE


def set_active_profile(name: str) -> None:
    with _config_lock():
        state = _load_state()
        state["active_profile"] = name
        _save_state(state)


def profile_dir(name: str) -> Path:
    if not is_valid_profile_name(name):
        raise ValueError(f"Invalid profile name: {name!r}")
    return PROFILES_DIR / name


def credentials_path(name: str | None = None) -> Path:
    return profile_dir(name or get_active_profile()) / "credentials.json"


def _meta_path(name: str) -> Path:
    return profile_dir(name) / "meta.json"


def list_profiles() -> list[str]:
    if not PROFILES_DIR.exists():
        return []
    return sorted(
        p.name for p in PROFILES_DIR.iterdir() if p.is_dir() and is_valid_profile_name(p.name)
    )


def profile_exists(name: str) -> bool:
    return is_valid_profile_name(name) and profile_dir(name).is_dir()


def remove_profile(name: str) -> None:
    target = profile_dir(name)
    if target.exists():
        shutil.rmtree(target)

    with _config_lock():
        state = _load_state()
        if state.get("active_profile") == name:
            state.pop("active_profile", None)
            _save_state(state)


def save_credentials(credentials: dict, name: str | None = None) -> None:
    target = _ensure_profile_dir(name or get_active_profile())
    _write_private(target / "credentials.json", json.dumps(credentials, indent=2))


def load_credentials(name: str | None = None) -> dict | None:
    path = credentials_path(name)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return None


def clear_credentials(name: str | None = None) -> None:
    path = credentials_path(name)
    if path.exists():
        path.unlink()


def save_profile_meta(name: str, meta: dict) -> None:
    _ensure_profile_dir(name)
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
    """Move a pre-profiles credentials.json into the default profile. One-shot.

    Held under the config lock so concurrent first-run invocations cannot both
    pass the existence check and race on read/unlink.
    """
    if not LEGACY_CREDENTIALS_FILE.exists() or list_profiles():
        return False

    with _config_lock():
        if not LEGACY_CREDENTIALS_FILE.exists() or list_profiles():
            return False

        dest = _ensure_profile_dir(DEFAULT_PROFILE)
        _write_private(dest / "credentials.json", LEGACY_CREDENTIALS_FILE.read_text())
        LEGACY_CREDENTIALS_FILE.unlink()
        state = _load_state()
        state["active_profile"] = DEFAULT_PROFILE
        _save_state(state)
    return True
