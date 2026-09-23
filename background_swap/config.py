"""Settings loaded from environment variables, a project .env file, or the per-user config file.

Precedence: real environment variables > ``.env`` in the working directory > user config.
The user config is what the app's "API keys" panel writes, so a distributed copy of the
project never needs to contain anyone's key.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values, set_key

APP_NAME = "background-swap"
KEY_VARS = ("PEXELS_API_KEY", "UNSPLASH_ACCESS_KEY")


def user_config_path() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / APP_NAME / "config.env"


def _load() -> None:
    # Earlier files win; empty values (e.g. "PEXELS_API_KEY=" in a template .env) never
    # shadow a real value from a later file.
    files = [Path.cwd() / ".env", Path(__file__).resolve().parent.parent / ".env", user_config_path()]
    for path in dict.fromkeys(files):
        if path.is_file():
            for name, value in dotenv_values(path).items():
                if value and not os.environ.get(name):
                    os.environ[name] = value


_load()


def save_user_keys(**keys: str) -> Path:
    """Persist API keys (e.g. PEXELS_API_KEY="...") to the user config and apply them now."""
    path = user_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(mode=0o600, exist_ok=True)
    for name, value in keys.items():
        value = (value or "").strip()
        set_key(str(path), name, value, quote_mode="never")
        if value:
            os.environ[name] = value
        else:
            os.environ.pop(name, None)
    return path


def user_keys() -> dict[str, str]:
    stored = dotenv_values(user_config_path()) if user_config_path().exists() else {}
    return {k: stored.get(k) or "" for k in KEY_VARS}


@dataclass(frozen=True)
class Settings:
    pexels_api_key: str | None
    unsplash_access_key: str | None
    background_provider: str
    rembg_model: str

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            pexels_api_key=os.getenv("PEXELS_API_KEY") or None,
            unsplash_access_key=os.getenv("UNSPLASH_ACCESS_KEY") or None,
            background_provider=os.getenv("BACKGROUND_PROVIDER", "pexels").strip().lower(),
            rembg_model=os.getenv("REMBG_MODEL", "isnet-general-use").strip(),
        )

    @property
    def has_key(self) -> bool:
        return bool(self.pexels_api_key or self.unsplash_access_key)
