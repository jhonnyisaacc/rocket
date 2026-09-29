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
KRAKEN_FUTURES_INSTRUMENTS_URL = "https://futures.kraken.com/derivatives/api/v3/instruments"
KRAKEN_FUTURES_TICKERS_URL = "https://futures.kraken.com/derivatives/api/v3/tickers"
ONDO_PERPS_CONTRACTS_URL = "https://api.ondoperps.xyz/v1/perps/contracts"
RESEARCH_ELIGIBLE = "RESEARCH_ELIGIBLE"
EXECUTION_ELIGIBLE = "EXECUTION_ELIGIBLE"
XSTOCKS_PAGE_SIZE = 100
XSTOCKS_MAX_PAGES = 50


def instrument_record(
    *,
    underlying: str,
    venue: str,
    source: str,
    observed_at: datetime | str,
    available_at: datetime | str | None,
    listing_at: datetime | str | None = None,
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
        listed = parse_datetime(listing_at) if listing_at not in (None, "") else None
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
        "listing_at": listed.isoformat() if listed else None,
        "source": source,
    }
    if extras:
        for key, value in extras.items():
            row.setdefault(key, value)
    return row


def xstock_underlying(token_symbol: str | None) -> str | None:
    """AAPLx → AAPL. Does not treat a spot listing as shortable."""
    token = str(token_symbol or "").strip()
    if len(token) < 2 or not token.endswith("x"):
        return None
    ticker = token[:-1].upper()
    return ticker or None


def xstocks_has_next_page(payload: Mapping[str, Any] | None, *, batch_size: int, page_size: int) -> bool:
    page = payload.get("page") if isinstance(payload, Mapping) else None
    if isinstance(page, Mapping) and "hasNextPage" in page:
        return bool(page.get("hasNextPage"))
    return batch_size >= page_size


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
            underlying=str(node.get("underlyingSymbol") or xstock_underlying(node.get("symbol")) or ""),
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


def fetch_xstocks_assets(client: httpx.Client, *, retrieved_at: datetime, page_size: int = XSTOCKS_PAGE_SIZE) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    page = 1
    while page <= XSTOCKS_MAX_PAGES:
        response = get_read(client, XSTOCKS_ASSETS_URL, params={"page": page, "pageSize": page_size})
        payload = response.json()
        batch = parse_xstocks_assets(payload, retrieved_at=retrieved_at)
        records.extend(batch)
        if not xstocks_has_next_page(payload, batch_size=len(batch), page_size=page_size):
            break
        page += 1
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


def _finite(value: Any) -> float | None:
    try:
        if value in (None, "") or isinstance(value, bool):
            return None
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number


def parse_kraken_xstock_perps(
    instruments: Sequence[Mapping[str, Any]] | None,
    tickers: Sequence[Mapping[str, Any]] | None,
    *,
    retrieved_at: datetime,
) -> list[dict[str, Any]]:
    """Kraken documented equity perps (base like AAPLx). Spot listings are ignored."""
    by_symbol = {
        str(row.get("symbol") or ""): row
        for row in tickers or ()
        if isinstance(row, Mapping) and row.get("symbol")
    }
    records = []
    for row in instruments or ():
        if not isinstance(row, Mapping):
            continue
        token = str(row.get("base") or "")
        underlying = xstock_underlying(token)
        if underlying is None:
            continue
        symbol = str(row.get("symbol") or "")
        ticker = by_symbol.get(symbol) or {}
        tradeable = row.get("tradeable") is True
        suspended = ticker.get("suspended") is True
        short_available = True if tradeable and not suspended else False if tradeable is False or suspended else None
        mark = _finite(ticker.get("markPrice"))
        index = _finite(ticker.get("indexPrice"))
        bid, ask = _finite(ticker.get("bid")), _finite(ticker.get("ask"))
        spread = None if bid is None or ask is None or mark in (None, 0) else (ask - bid) / mark
        listed = row.get("openingDate")
        record = instrument_record(
            underlying=underlying,
            venue="kraken_xstocks_perps",
            source=KRAKEN_FUTURES_INSTRUMENTS_URL,
            observed_at=retrieved_at,
            available_at=retrieved_at,
            listing_at=listed,
            token_symbol=symbol or token,
            instrument_type="tokenized_perp",
            long_available=short_available,
            short_available=short_available,
            extras={
                "spot_perp": "perp",
                "base": token,
                "funding": _finite(ticker.get("fundingRate")),
                "volume": _finite(ticker.get("vol24h")),
                "open_interest": _finite(ticker.get("openInterest")),
                "mark_price": mark,
                "underlying_reference_price": index,
                "spread": spread,
                "basis": None if mark is None or index in (None, 0) else mark / index - 1,
                "opening_date": listed,
                "availability_basis": (
                    "Kraken openingDate is listing_at only; short_available is the "
                    "observed snapshot and does not backfill historical tradeability"
                ),
            },
        )
        if record:
            records.append(record)
    return records


def parse_ondo_perps(payload: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None, *, retrieved_at: datetime) -> list[dict[str, Any]]:
    rows = payload.get("result") if isinstance(payload, Mapping) else payload
    records = []
    for row in rows or ():
        if not isinstance(row, Mapping):
            continue
        if str(row.get("productType") or "").lower() != "perpetual":
            continue
        underlying = str(row.get("baseCurrency") or "").strip().upper()
        if not underlying:
            continue
        disabled = row.get("disabled") is True
        short_available = not disabled
        mark = _finite(row.get("lastPrice"))
        index = _finite(row.get("indexPrice"))
        bid, ask = _finite(row.get("bid")), _finite(row.get("ask"))
        spread = None if bid is None or ask is None or mark in (None, 0) else (ask - bid) / mark
        record = instrument_record(
            underlying=underlying,
            venue="ondo_perps",
            source=ONDO_PERPS_CONTRACTS_URL,
            observed_at=retrieved_at,
            available_at=retrieved_at,
            token_symbol=str(row.get("market") or "") or None,
            instrument_type="tokenized_perp",
            long_available=short_available,
            short_available=short_available,
            extras={
                "spot_perp": "perp",
                "funding": _finite(row.get("fundingRate")),
                "volume": _finite(row.get("usdVolume") or row.get("quoteVolume")),
                "open_interest": _finite(row.get("openInterestUsd") or row.get("openInterest")),
                "mark_price": mark,
                "underlying_reference_price": index,
                "spread": spread,
                "basis": None if mark is None or index in (None, 0) else mark / index - 1,
                "availability_basis": "current Ondo Perps contract list; listing vintage unknown",
            },
        )
        if record:
            records.append(record)
    return records


def acquire_tokenized_snapshot(*, http: httpx.Client | None = None, now: datetime | None = None) -> ProviderResult:
    retrieved = now or datetime.now(UTC)
    owns = http is None
    client = http or httpx.Client(timeout=20.0, headers={"User-Agent": "rocket-research"}, follow_redirects=True)
    records: list[dict[str, Any]] = []
    attempts = []
    try:
        try:
            xstocks = fetch_xstocks_assets(client, retrieved_at=retrieved)
            records.extend(xstocks)
            attempts.append({"name": "xstocks.public.assets", "status": "HEALTHY", "coverage": str(len(xstocks))})
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            attempts.append({"name": "xstocks.public.assets", "status": "UNAVAILABLE", "failure_kind": type(exc).__name__})
        try:
            instruments = get_read(client, KRAKEN_FUTURES_INSTRUMENTS_URL).json().get("instruments") or []
            tickers = get_read(client, KRAKEN_FUTURES_TICKERS_URL).json().get("tickers") or []
            kraken = parse_kraken_xstock_perps(instruments, tickers, retrieved_at=retrieved)
            records.extend(kraken)
            attempts.append({"name": "kraken.futures.xstocks_perps", "status": "HEALTHY", "coverage": str(len(kraken))})
        except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
            attempts.append({"name": "kraken.futures.xstocks_perps", "status": "UNAVAILABLE", "failure_kind": type(exc).__name__})
        try:
            ondo_payload = get_read(client, ONDO_PERPS_CONTRACTS_URL).json()
            ondo = parse_ondo_perps(ondo_payload, retrieved_at=retrieved)
            records.extend(ondo)
            attempts.append({"name": "ondo.perps.contracts", "status": "HEALTHY", "coverage": str(len(ondo))})
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            attempts.append({"name": "ondo.perps.contracts", "status": "UNAVAILABLE", "failure_kind": type(exc).__name__})
        records.extend(ondo_current_registry(retrieved_at=retrieved))
        attempts.append({"name": "ondo.current_registry", "status": "PARTIAL", "coverage": "current reviewed mints; not historical"})
        healthy = any(row["status"] == "HEALTHY" for row in attempts)
        return ProviderResult(
            status=OperationalStatus.HEALTHY if healthy else OperationalStatus.PARTIAL,
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
    `observed_at` is known and <= decision time, and `short_available` is True.
    `listing_at` / `openingDate` only proves the contract existed by that date.
    It does not prove later tradeability, short availability, or liquidity.
    Tokenized spot never implies a short. Present listings never backfill
    historical shortability.
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
            observed = parse_datetime(row.get("observed_at"))
        except ValueError:
            observed = None
        if observed is None or observed > now:
            continue
        if row.get("instrument_type") == "tokenized_spot" and row.get("short_available") is not True:
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
