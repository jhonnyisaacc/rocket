"""Capability protocols and a toml-driven registry. Not a plugin bus."""

from rocket.providers.protocols import ProviderResult
from rocket.providers.registry import capability, load_registry

__all__ = ["ProviderResult", "capability", "load_registry"]
