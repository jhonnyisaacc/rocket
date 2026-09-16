"""Tokenized-equity availability. Current listings are not historical shortability."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

import httpx

from rocket.models import OperationalStatus
from rocket.pit import parse_datetime
from rocket.providers.http import get_read
from rocket.providers.inventory import KNOWN_ONDO
from rocket.providers.protocols import ProviderResult

XSTOCKS_ASSETS_URL = "https://api.xstocks.fi/api/v2/public/assets"
RESEARCH_ELIGIBLE = "RESEARCH_ELIGIBLE"
EXECUTION_ELIGIBLE = "EXECUTION_ELIGIBLE"


def instrument_record(
    *,
    underlying: str,
    venue: str,
    source: str,
    observed_at: datetime | str,
    available_at: datetime | str | None,
    token_symbol: str | None = None,
    instrument_type: str | None = None,
    long_available: bool | None = None,
    short_available: bool | None = None,
    extras: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    ticker = str(underlying or "").strip().upper()
    if not ticker or not venue or not source:
        return None
    try:
        observed = parse_datetime(observed_at)
        available = parse_datetime(available_at)
    except ValueError:
        return None
    if observed is None:
        return None
    row = {
        "underlying": ticker,
        "venue": venue,
        "token_symbol": token_symbol,
        "instrument_type": instrument_type,
        "long_available": long_available,
        "short_available": short_available,
        "spot_perp": extras.get("spot_perp") if extras else None,
        "funding": extras.get("funding") if extras else None,
        "spread": extras.get("spread") if extras else None,
        "volume": extras.get("volume") if extras else None,
        "open_interest": extras.get("open_interest") if extras else None,
        "mark_price": extras.get("mark_price") if extras else None,
        "underlying_reference_price": extras.get("underlying_reference_price") if extras else None,
        "basis": extras.get("basis") if extras else None,
        "observed_at": observed.isoformat(),
        "available_at": available.isoformat() if available else None,
        "source": source,
    }
    if extras:
        for key, value in extras.items():
            row.setdefault(key, value)
    return row


def parse_xstocks_assets(payload: Mapping[str, Any] | None, *, retrieved_at: datetime) -> list[dict[str, Any]]:
    nodes = payload.get("nodes") if isinstance(payload, Mapping) else None
    records = []
    for node in nodes or ():
        if not isinstance(node, Mapping):
            continue
        halted = node.get("isTradingHalted")
        long_available = False if halted is True else True if halted is False else None
        extras = {
            "spot_perp": "spot",
            "isin": node.get("isin"),
            "deployments": node.get("deployments"),
        }
        record = instrument_record(
            underlying=str(node.get("underlyingSymbol") or ""),
            venue="xstocks",
            source=XSTOCKS_ASSETS_URL,
            observed_at=retrieved_at,
            available_at=retrieved_at,
            token_symbol=str(node.get("symbol") or "") or None,
            instrument_type="tokenized_spot",
            long_available=long_available,
            short_available=None,
            extras=extras,
        )
        if record:
            records.append(record)
    return records


def ondo_current_registry(*, retrieved_at: datetime) -> list[dict[str, Any]]:
    """Reviewed current ONDO mint map. Listing dates are not reconstructed."""
    rows = []
    for mint, (token, underlying) in KNOWN_ONDO.items():
        record = instrument_record(
            underlying=underlying,
            venue="ondo",
            source="Rocket reviewed ONDO mint registry",
            observed_at=retrieved_at,
            available_at=None,
            token_symbol=token,
            instrument_type="tokenized_spot",
            long_available=True,
            short_available=None,
            extras={"mint": mint, "availability_basis": "current registry only; historical listing date unknown"},
        )
        if record:
            rows.append(record)
    return rows


def acquire_tokenized_snapshot(*, http: httpx.Client | None = None, now: datetime | None = None) -> ProviderResult:
    retrieved = now or datetime.now(UTC)
    owns = http is None
    client = http or httpx.Client(timeout=20.0, headers={"User-Agent": "rocket-research"}, follow_redirects=True)
    records: list[dict[str, Any]] = []
    attempts = []
    try:
        try:
            response = get_read(client, XSTOCKS_ASSETS_URL, params={"page": 1, "pageSize": 100})
            payload = response.json()
            records.extend(parse_xstocks_assets(payload, retrieved_at=retrieved))
            attempts.append({"name": "xstocks.public.assets", "status": "HEALTHY", "coverage": str(len(records))})
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            attempts.append({"name": "xstocks.public.assets", "status": "UNAVAILABLE", "failure_kind": type(exc).__name__})
        records.extend(ondo_current_registry(retrieved_at=retrieved))
        attempts.append({"name": "ondo.current_registry", "status": "PARTIAL", "coverage": "current reviewed mints; not historical"})
        status = OperationalStatus.HEALTHY if any(row.get("source") == XSTOCKS_ASSETS_URL for row in records) else OperationalStatus.PARTIAL
        return ProviderResult(
            status=status,
            records=tuple(records),
            retrieved_at=retrieved,
            source="tokenized_equities",
            extras={"provider_attempts": attempts, "historical_reconstructed": False},
        )
    finally:
        if owns:
            client.close()


def eligibility(
    underlying: str,
    instruments: Sequence[Mapping[str, Any]] | None,
    *,
    now: datetime,
    allow_current_as_historical: bool = False,
) -> dict[str, Any]:
    """Research eligibility is independent of venue shortability.

    Historical execution eligibility requires an instrument snapshot whose
    `available_at` is known and <= decision time. Present listings never
    backfill January 2026 availability.
    """
    del allow_current_as_historical
    ticker = underlying.strip().upper()
    research = {
        "status": RESEARCH_ELIGIBLE,
        "underlying": ticker,
        "reason": "listed-equity research does not require a tokenized venue",
    }
    matches = [row for row in instruments or () if str(row.get("underlying") or "").upper() == ticker]
    executable = []
    for row in matches:
        try:
            available = parse_datetime(row.get("available_at"))
        except ValueError:
            available = None
        if available is None or available > now:
            continue
        if row.get("short_available") is True:
            executable.append(row)
    return {
        "research": research,
        "execution": {
            "status": EXECUTION_ELIGIBLE if executable else "UNKNOWN",
            "instruments": executable,
            "observed_instruments": matches,
            "reason": None if executable else "short availability was not proven at decision time",
        },
        "short_availability": True if executable else None,
        "short_liquidity": None,
        "short_carry_cost": None,
        "squeeze_risk": None,
    }
