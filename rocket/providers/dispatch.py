"""Bounded capability acquisition; adapters retain their own evidence clocks."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

from rocket.models import OperationalStatus, ProviderHealth, ReasonCode, ResearchReason
from rocket.providers.protocols import ProviderResult


def failure_kind(exc: Exception) -> str:
    """Never return exception text or request URLs (which can contain credentials)."""
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        return {401: "Authentication", 402: "Entitlement", 403: "Entitlement", 429: "RateLimit"}.get(
            code, "ExternalOutage" if code >= 500 else "UnsupportedEndpoint"
        )
    if isinstance(exc, httpx.TransportError):
        return "ExternalOutage"
    if isinstance(exc, ImportError):
        return "MissingDependency"
    return "InvalidProviderData" if isinstance(exc, (ValueError, TypeError, KeyError)) else type(exc).__name__


@dataclass(frozen=True)
class Acquisition:
    capability: str
    result: ProviderResult | None
    attempts: tuple[ProviderHealth, ...]
    required: bool

    @property
    def reasons(self) -> tuple[ResearchReason, ...]:
        if self.result is not None or not self.required:
            return ()
        return (ResearchReason(ReasonCode.REQUIRED_PROVIDER_UNAVAILABLE,
                               (self.capability,), any(p.failure_kind in {
                                   "ExternalOutage", "RateLimit"} for p in self.attempts)),)


def acquire(capability: str, providers: list[tuple[str, Callable[[], ProviderResult]]], *,
            required: bool = True, sufficient: Callable[[ProviderResult], bool] | None = None,
            retries: int = 1) -> Acquisition:
    """Ordered fallback, at most two attempts per provider and eight providers.

    A partial primary can be sufficient. An empty result requires an explicit
    sufficiency predicate. Optional exhaustion never manufactures research IE.
    """
    if not 0 <= retries <= 1 or not 1 <= len(providers) <= 8:
        raise ValueError("dispatcher bounds exceeded")
    sufficient = sufficient or (lambda r: r.status is OperationalStatus.HEALTHY and bool(r.records))
    attempts = []
    for name, fetch in providers:
        for attempt in range(retries + 1):
            try:
                result = fetch()
                if not isinstance(result, ProviderResult):
                    raise ValueError("adapter must return ProviderResult")
                accepted = result.status not in {OperationalStatus.ERROR, OperationalStatus.UNAVAILABLE} and sufficient(result)
                failure = result.failure_kind or (None if accepted else "InsufficientCoverage")
                attempts.append(ProviderHealth(name, result.status if accepted else OperationalStatus.UNAVAILABLE,
                                               result.retrieved_at or datetime.now(UTC), failure,
                                               f"{len(result.records)} records; attempt {attempt + 1}"))
                if accepted:
                    return Acquisition(capability, result, tuple(attempts), required)
            except Exception as exc:
                failure = failure_kind(exc)
                attempts.append(ProviderHealth(name, OperationalStatus.UNAVAILABLE, datetime.now(UTC), failure,
                                               f"attempt {attempt + 1}"))
            if failure not in {"ExternalOutage", "RateLimit"}:
                break
    return Acquisition(capability, None, tuple(attempts), required)
