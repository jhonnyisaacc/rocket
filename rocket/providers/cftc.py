"""Official CFTC Commitment of Traders. OpenBB is optional and not required."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import UTC, datetime
from html import unescape
from typing import Any

import httpx

from rocket.models import OperationalStatus
from rocket.providers.protocols import ProviderResult

CFTC_FUTURES_URL = "https://www.cftc.gov/dea/futures/deacmelf.htm"
MARKET_NAMES = {
    "BTC": "BITCOIN - CHICAGO MERCANTILE EXCHANGE",
    "ETH": "ETHER CASH SETTLED - CHICAGO MERCANTILE EXCHANGE",
}
STALE_AFTER_DAYS = 14


def _ints(line: str) -> list[int]:
    values: list[int] = []
    for token in re.findall(r"[-+]?\d[\d,]*", line):
        try:
            values.append(int(token.replace(",", "")))
        except ValueError:
            continue
    return values


def _as_of(block: list[str]) -> datetime | None:
    for line in block[:8]:
        match = re.search(r"([A-Za-z]+\s+\d{1,2},\s+\d{4})", line)
        if not match:
            continue
        for fmt in ("%B %d, %Y", "%b %d, %Y"):
            try:
                return datetime.strptime(match.group(1), fmt).replace(tzinfo=UTC)
            except ValueError:
                continue
    return None


def parse_cftc_report(html: str) -> dict[str, dict[str, Any]]:
    match = re.search(r"<pre[^>]*>(.*?)</pre>", html, re.IGNORECASE | re.DOTALL)
    text = unescape(match.group(1) if match else html)
    lines = [line.rstrip() for line in text.splitlines()]
    header_indexes = [index for index, line in enumerate(lines) if "CODE-" in line.upper()]
    markets: dict[str, dict[str, Any]] = {}
    for asset, market_name in MARKET_NAMES.items():
        target = market_name.upper()
        header_idx = next(
            (index for index in header_indexes if target in lines[index].upper()),
            None,
        )
        if header_idx is None:
            continue
        next_header = next((index for index in header_indexes if index > header_idx), len(lines))
        block = lines[header_idx:next_header]
        all_line = next(
            (line for line in block if line.strip().upper().startswith("ALL") and ":" in line),
            "",
        )
        values = _ints(all_line)
        if len(values) < 6:
            continue
        open_interest, noncomm_long, noncomm_short = values[0], values[1], values[2]
        comm_long, comm_short = values[4], values[5]
        if open_interest <= 0:
            continue
        net_noncomm = noncomm_long - noncomm_short
        pct_oi = net_noncomm / open_interest * 100.0
        as_of = _as_of(block)
        markets[asset] = {
            "asset": asset,
            "market": market_name,
            "open_interest": open_interest,
            "noncomm_long": noncomm_long,
            "noncomm_short": noncomm_short,
            "comm_long": comm_long,
            "comm_short": comm_short,
            "net_non_commercial": net_noncomm,
            "pct_oi_non_com": pct_oi,
            "bias": bias_from_speculator_pct(pct_oi),
            "as_of_date": as_of.date().isoformat() if as_of else None,
            "release_date": as_of.date().isoformat() if as_of else None,
            "source": "cftc_direct",
        }
    return markets


def bias_from_speculator_pct(pct_oi: float) -> str:
    """Contrarian to non-commercial specs. Same thresholds as the documented CFTC rule."""
    if pct_oi > 0:
        return "bearish"
    if pct_oi < -8:
        return "bullish"
    return "neutral"


def regime_from_markets(markets: Mapping[str, Mapping[str, Any]]) -> str:
    directions = {str(row.get("bias")) for row in markets.values()}
    if directions == {"bullish"} and len(markets) >= 2:
        return "bullish"
    if directions == {"bearish"} and len(markets) >= 2:
        return "bearish"
    if markets:
        return "neutral"
    return "unknown"


def fetch_cftc_direct(*, http: httpx.Client | None = None) -> ProviderResult:
    owns = http is None
    client = http or httpx.Client(timeout=30.0, headers={"User-Agent": "rocket-research"}, follow_redirects=True)
    retrieved = datetime.now(UTC)
    try:
        response = client.get(CFTC_FUTURES_URL)
        response.raise_for_status()
        markets = parse_cftc_report(response.text)
    except (httpx.HTTPError, TypeError, ValueError) as exc:
        if owns:
            client.close()
        return ProviderResult(
            status=OperationalStatus.UNAVAILABLE,
            failure_kind=type(exc).__name__,
            source="cftc",
            retrieved_at=retrieved,
        )
    if owns:
        client.close()
    records = tuple(markets[name] for name in ("BTC", "ETH") if name in markets)
    status = OperationalStatus.HEALTHY if len(records) == 2 else (
        OperationalStatus.PARTIAL if records else OperationalStatus.UNAVAILABLE
    )
    return ProviderResult(
        status=status,
        records=records,
        retrieved_at=retrieved,
        source="cftc_direct",
        extras={"url": CFTC_FUTURES_URL, "markets": markets},
    )


def cot_context_from_result(result: ProviderResult, *, now: datetime | None = None) -> dict[str, Any]:
    observed = now or datetime.now(UTC)
    markets = {str(row["asset"]): dict(row) for row in result.records if row.get("asset")}
    as_of_dates = []
    for row in markets.values():
        raw = row.get("as_of_date")
        if raw:
            try:
                as_of_dates.append(datetime.fromisoformat(str(raw)).date())
            except ValueError:
                continue
    freshest = min(as_of_dates) if as_of_dates else None
    freshness_days = (observed.date() - freshest).days if freshest else None
    stale = freshness_days is None or freshness_days > STALE_AFTER_DAYS
    incomplete = result.status is not OperationalStatus.HEALTHY or len(markets) < 2
    regime = regime_from_markets(markets)
    status = "UNAVAILABLE"
    if result.status is OperationalStatus.UNAVAILABLE:
        regime = "unknown"
    elif stale:
        status = "STALE"
        regime = "unknown"
    elif incomplete:
        status = "PARTIAL"
        regime = "unknown"
    else:
        status = "OK"
    warnings = []
    if status == "UNAVAILABLE":
        warnings.append("COT unavailable from official CFTC futures report")
    if incomplete and status != "UNAVAILABLE":
        warnings.append("COT market coverage is incomplete")
    if stale:
        warnings.append("COT report is stale; no directional COT gate was applied")
    return {
        "status": status,
        "regime": regime,
        "scope": "market/regime context; no per-altcoin COT signal",
        "source": "CFTC futures-only report",
        "as_of_date": freshest.isoformat() if freshest else None,
        "freshness_days": freshness_days,
        "markets": markets,
        "warnings": warnings,
        "failure_kind": result.failure_kind,
    }


def fetch_cot_context(*, now: datetime | None = None, http: httpx.Client | None = None) -> dict[str, Any]:
    return cot_context_from_result(fetch_cftc_direct(http=http), now=now)
