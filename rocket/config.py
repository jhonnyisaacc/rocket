"""Read-only environment and provider registry. Never deletes or rewrites env vars."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_DIR = PACKAGE_ROOT / "config"

# Names already used in this environment. Rocket consumes them; it does not unset them.
KNOWN_ENV_NAMES = (
    "ROCKET_HOME",
    "ROCKET_PORTFOLIO_STATE",
    "ROCKET_WATCH_STATE",
    "ROCKET_INVENTORY_ADDRESS",
    "FRED_API_KEY",
    "FMP_API_KEY",
    "SUPADATA_API_KEY",
    "SUPADATA_API_TOKEN",
    "HELIUS_API_KEY",
    "MASSIVE_API_KEY",
    "SOLANA_RPC_URL",
    "OPENBB_PYTHON",
    "ROCKET_ASSET_REGISTRY",
    "HL_WALLET",
    "NAVE_PORTFOLIO_STATE_FILE",
    "NAVE_QUANT_WATCH_STATE_FILE",
    "NAVE_RESEARCH_STATE_DIR",
)

ALIASES = {
    "ROCKET_PORTFOLIO_STATE": ("NAVE_PORTFOLIO_STATE_FILE",),
    "ROCKET_WATCH_STATE": ("NAVE_QUANT_WATCH_STATE_FILE",),
    "ROCKET_HOME": ("NAVE_RESEARCH_STATE_DIR",),
    "SUPADATA_API_KEY": ("SUPADATA_API_TOKEN",),
}

FORBIDDEN_PATH_MARKERS = (
    "~/.hermes",
    "~/.openclaw",
    "~/.nanobot",
    "HERMES_HOME",
)


def contains_runtime_path(text: str) -> bool:
    """True when a path or env default is bot-runtime specific."""
    return any(marker in text for marker in FORBIDDEN_PATH_MARKERS)


def env(name: str, default: str | None = None) -> str | None:
    """Read a name or its alias. Never pop or rewrite os.environ."""
    value = os.environ.get(name)
    if value not in (None, ""):
        return value
    for alias in ALIASES.get(name, ()):
        value = os.environ.get(alias)
        if value not in (None, ""):
            return value
    return default


def rocket_home() -> Path:
    configured = env("ROCKET_HOME")
    return Path(configured).expanduser() if configured else Path.home() / ".rocket"


def load_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return tomllib.loads(path.read_text(encoding="utf-8"))


def providers_config(config_dir: Path | None = None) -> Mapping[str, Any]:
    root = config_dir or DEFAULT_CONFIG_DIR
    return load_toml(root / "providers.toml")


def env_config(config_dir: Path | None = None) -> Mapping[str, Any]:
    root = config_dir or DEFAULT_CONFIG_DIR
    return load_toml(root / "env.toml")
