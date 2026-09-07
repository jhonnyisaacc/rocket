"""Small capability contracts. Workflows depend on these, not vendor modules."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from rocket.models import OperationalStatus


@dataclass(frozen=True)
class ProviderResult:
    status: OperationalStatus
    records: tuple[Mapping[str, Any], ...] = ()
    retrieved_at: datetime | None = None
    failure_kind: str | None = None
    source: str = ""
    extras: Mapping[str, Any] = field(default_factory=dict)


class MacroSeries(Protocol):
    def fetch(self, symbol: str, *, now: datetime | None = None) -> ProviderResult: ...


class Quotes(Protocol):
    def fetch(self, symbols: tuple[str, ...], *, now: datetime | None = None) -> ProviderResult: ...


class Inventory(Protocol):
    def fetch(self, *, address: str, now: datetime | None = None) -> ProviderResult: ...
