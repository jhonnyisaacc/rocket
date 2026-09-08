"""Explicit registry: capability → primary + fallbacks from providers.toml."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from rocket.config import providers_config

ProviderFactory = Callable[..., Any]


class Registry:
    def __init__(self, config: Mapping[str, Any] | None = None):
        self.config = dict(config or providers_config())
        self._factories: dict[str, dict[str, ProviderFactory]] = {}

    def register(self, capability: str, name: str, factory: ProviderFactory) -> None:
        self._factories.setdefault(capability, {})[name] = factory

    def capability(self, name: str) -> Mapping[str, Any]:
        row = self.config.get(name)
        if not isinstance(row, Mapping):
            raise KeyError(f"unknown capability: {name}")
        return row

    def factories(self, capability: str) -> dict[str, ProviderFactory]:
        return dict(self._factories.get(capability) or {})

    def acquire(self, capability: str, *, required=True, sufficient=None, **kwargs):
        from rocket.models import OperationalStatus
        from rocket.providers.dispatch import acquire
        from rocket.providers.protocols import ProviderResult

        config = self.capability(capability)
        factories = self.factories(capability)
        def fetch(name):
            if name not in factories:
                return ProviderResult(OperationalStatus.UNAVAILABLE, source=name,
                                      failure_kind="MissingImplementation")
            return factories[name](**kwargs)
        names = list(dict.fromkeys([config["primary"], *config.get("fallbacks", [])]))
        return acquire(capability, [(name, lambda name=name: fetch(name)) for name in names],
                       required=required, sufficient=sufficient)


_REGISTRY: Registry | None = None


def load_registry(config_dir: Path | None = None) -> Registry:
    global _REGISTRY
    if _REGISTRY is None or config_dir is not None:
        from rocket.config import DEFAULT_CONFIG_DIR

        _REGISTRY = Registry(providers_config(config_dir or DEFAULT_CONFIG_DIR))
    return _REGISTRY


def capability(name: str) -> Mapping[str, Any]:
    return load_registry().capability(name)
