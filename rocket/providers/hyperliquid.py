"""Read-only Hyperliquid perpetual metadata. Public /info only; never signs."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from rocket.models import OperationalStatus
from rocket.providers.protocols import ProviderResult

MAINNET_INFO_URL = "https://api.hyperliquid.xyz/info"
SETUP_CANDLE_INTERVAL = "4h"
SETUP_LOOKBACK_DAYS = 14
MAX_SETUP_MARKETS = 100
SUPPORTED_CANDLE_INTERVALS = frozenset(
    {"1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "8h", "12h", "1d", "3d", "1w"}
)


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def spread_bps_from_impact(impact_pxs: Any) -> float | None:
    if not isinstance(impact_pxs, (list, tuple)) or len(impact_pxs) < 2:
        return None
    bid = _finite(impact_pxs[0])
    ask = _finite(impact_pxs[1])
    if bid is None or ask is None or bid <= 0 or ask <= 0 or ask < bid:
        return None
    midpoint = (bid + ask) / 2
    if midpoint <= 0:
        return None
    return (ask - bid) / midpoint * 10_000


def spread_bps_from_book(book: Mapping[str, Any] | None) -> float | None:
    if not isinstance(book, Mapping):
        return None
    levels = book.get("levels")
    if not isinstance(levels, list) or len(levels) < 2:
        return None
    try:
        bid = _finite(levels[0][0]["px"])
        ask = _finite(levels[1][0]["px"])
    except (IndexError, KeyError, TypeError):
        return None
    if bid is None or ask is None or bid <= 0 or ask <= 0 or ask < bid:
        return None
    midpoint = (bid + ask) / 2
    if midpoint <= 0:
        return None
    return (ask - bid) / midpoint * 10_000


def parse_meta_and_asset_ctxs(payload: Any, *, retrieved_at: datetime) -> tuple[dict[str, Any], ...]:
    if not isinstance(payload, list) or len(payload) < 2:
        raise ValueError("metaAndAssetCtxs payload must be [meta, ctxs]")
    meta, ctxs = payload[0], payload[1]
    universe = meta.get("universe") if isinstance(meta, Mapping) else None
    if not isinstance(universe, list) or not isinstance(ctxs, list):
        raise ValueError("metaAndAssetCtxs universe/ctxs missing")
    if len(universe) != len(ctxs):
        raise ValueError("metaAndAssetCtxs universe and ctxs length mismatch")
    records: list[dict[str, Any]] = []
    for asset, ctx in zip(universe, ctxs, strict=True):
        if not isinstance(asset, Mapping) or not isinstance(ctx, Mapping):
            continue
        if asset.get("isDelisted") is True:
            continue
        name = str(asset.get("name") or "").upper()
        if not name:
            continue
        mark = _finite(ctx.get("markPx")) or _finite(ctx.get("midPx"))
        oi_coins = _finite(ctx.get("openInterest"))
        oi_usd = oi_coins * mark if oi_coins is not None and mark is not None else None
        spread = spread_bps_from_impact(ctx.get("impactPxs"))
        if spread is None:
            spread = spread_bps_from_book(ctx.get("l2Book") if isinstance(ctx.get("l2Book"), Mapping) else None)
        records.append(
            {
                "name": name,
                "sz_decimals": asset.get("szDecimals"),
                "max_leverage": asset.get("maxLeverage"),
                "day_notional_volume": _finite(ctx.get("dayNtlVlm")),
                "open_interest_coins": oi_coins,
                "open_interest_usd": oi_usd,
                "mark_px": mark,
                "mid_px": _finite(ctx.get("midPx")),
                "funding": _finite(ctx.get("funding")),
                "spread_bps": spread,
                "slippage_bps": (spread / 2.0) if spread is not None else None,
                "quote_currency": "USDC",
                "exchange_contract_type": "perpetual",
                "retrieved_at": retrieved_at.isoformat(),
            }
        )
    return tuple(records)


def fetch_perp_markets(
    *,
    http: httpx.Client | None = None,
    now: datetime | None = None,
) -> ProviderResult:
    owns = http is None
    client = http or httpx.Client(timeout=20.0, headers={"User-Agent": "rocket-research"})
    retrieved = now or datetime.now(UTC)
    try:
        response = client.post(MAINNET_INFO_URL, json={"type": "metaAndAssetCtxs"})
        response.raise_for_status()
        records = parse_meta_and_asset_ctxs(response.json(), retrieved_at=retrieved)
    except (httpx.HTTPError, TypeError, ValueError, KeyError) as exc:
        if owns:
            client.close()
        return ProviderResult(
            status=OperationalStatus.UNAVAILABLE,
            failure_kind=type(exc).__name__,
            source="hyperliquid",
            retrieved_at=retrieved,
        )
    if owns:
        client.close()
    return ProviderResult(
        status=OperationalStatus.HEALTHY if records else OperationalStatus.UNAVAILABLE,
        records=records,
        retrieved_at=retrieved,
        source="hyperliquid",
        extras={"endpoint": "metaAndAssetCtxs", "signing": False},
    )


class HyperliquidPerps:
    """Capability adapter. Research /info only; no wallet is read."""

    def __init__(self, *, http: httpx.Client | None = None):
        self.http = http

    def fetch(self, *, now: datetime | None = None) -> ProviderResult:
        return fetch_perp_markets(http=self.http, now=now)


def parse_candles(payload: Any) -> tuple[dict[str, Any], ...]:
    if not isinstance(payload, list):
        raise ValueError("candleSnapshot payload must be a list")
    rows: list[dict[str, Any]] = []
    for raw in payload:
        if not isinstance(raw, Mapping):
            continue
        try:
            ts_ms = int(raw["t"])
            item = {
                "timestamp_ms": ts_ms,
                "timestamp": datetime.fromtimestamp(ts_ms / 1000, UTC).isoformat(),
                "open": float(raw["o"]),
                "high": float(raw["h"]),
                "low": float(raw["l"]),
                "close": float(raw["c"]),
                "volume": float(raw["v"]),
                "coin": str(raw.get("s") or ""),
                "interval": str(raw.get("i") or ""),
                "source": "hyperliquid",
            }
        except (KeyError, TypeError, ValueError):
            continue
        if item["high"] <= 0 or item["low"] <= 0 or item["close"] <= 0:
            continue
        rows.append(item)
    rows.sort(key=lambda row: row["timestamp_ms"])
    return tuple(rows)


def fetch_candles(
    coin: str,
    *,
    interval: str = SETUP_CANDLE_INTERVAL,
    start_ms: int,
    end_ms: int,
    http: httpx.Client | None = None,
) -> ProviderResult:
    if interval not in SUPPORTED_CANDLE_INTERVALS:
        return ProviderResult(
            status=OperationalStatus.UNAVAILABLE,
            failure_kind="ValueError",
            source="hyperliquid",
            extras={"coin": coin, "interval": interval},
        )
    owns = http is None
    client = http or httpx.Client(timeout=20.0, headers={"User-Agent": "rocket-research"})
    retrieved = datetime.now(UTC)
    try:
        response = client.post(
            MAINNET_INFO_URL,
            json={
                "type": "candleSnapshot",
                "req": {
                    "coin": coin.upper(),
                    "interval": interval,
                    "startTime": int(start_ms),
                    "endTime": int(end_ms),
                },
            },
        )
        response.raise_for_status()
        records = parse_candles(response.json())
    except (httpx.HTTPError, TypeError, ValueError, KeyError) as exc:
        if owns:
            client.close()
        return ProviderResult(
            status=OperationalStatus.UNAVAILABLE,
            failure_kind=type(exc).__name__,
            source="hyperliquid",
            extras={"coin": coin, "interval": interval},
        )
    if owns:
        client.close()
    return ProviderResult(
        status=OperationalStatus.HEALTHY if records else OperationalStatus.UNAVAILABLE,
        records=records,
        retrieved_at=retrieved,
        source="hyperliquid",
        extras={"coin": coin.upper(), "interval": interval, "signing": False},
    )


def fetch_setup_candles(
    coins: Iterable[str],
    *,
    now: datetime | None = None,
    http: httpx.Client | None = None,
    limit: int = MAX_SETUP_MARKETS,
) -> dict[str, tuple[Mapping[str, Any], ...]]:
    """4h candles for liquid names only. Per-coin failure stays missing, not fatal."""
    observed = now or datetime.now(UTC)
    end_ms = int(observed.timestamp() * 1000)
    start_ms = int((observed - timedelta(days=SETUP_LOOKBACK_DAYS)).timestamp() * 1000)
    owns = http is None
    client = http or httpx.Client(timeout=20.0, headers={"User-Agent": "rocket-research"})
    output: dict[str, tuple[Mapping[str, Any], ...]] = {}
    try:
        for coin in list(coins)[: max(0, limit)]:
            name = str(coin or "").upper()
            if not name:
                continue
            result = fetch_candles(name, start_ms=start_ms, end_ms=end_ms, http=client)
            if result.status is OperationalStatus.UNAVAILABLE:
                result = fetch_candles(name, start_ms=start_ms, end_ms=end_ms, http=client)
            if result.status is OperationalStatus.HEALTHY:
                # Only closed 4h bars were knowable at the scan cutoff.
                output[name] = tuple(row for row in result.records
                                     if row["timestamp_ms"] + 4 * 3600 * 1000 <= end_ms)
    finally:
        if owns:
            client.close()
    return output


def overlay_l2_spread(records: Sequence[Mapping[str, Any]], books: Mapping[str, Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    """Replace impact-px spread with an L2 book when the caller already fetched one."""
    out: list[dict[str, Any]] = []
    for row in records:
        item = dict(row)
        book = books.get(str(item.get("name") or "").upper())
        spread = spread_bps_from_book(book)
        if spread is not None:
            item["spread_bps"] = spread
            item["slippage_bps"] = spread / 2.0
            item["spread_source"] = "l2Book"
        out.append(item)
    return tuple(out)
