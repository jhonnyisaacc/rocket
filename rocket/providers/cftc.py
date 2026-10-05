"""Official CFTC Commitment of Traders. OpenBB is optional and not required."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from html import unescape
from typing import Any

import httpx

from rocket.models import OperationalStatus
from rocket.pit import Availability, PointInTime, iso, parse_datetime
from rocket.providers.protocols import ProviderResult

CFTC_FUTURES_URL = "https://www.cftc.gov/dea/futures/deacmelf.htm"
MARKET_NAMES = {
    "BTC": "BITCOIN - CHICAGO MERCANTILE EXCHANGE",
    "ETH": "ETHER CASH SETTLED - CHICAGO MERCANTILE EXCHANGE",
}
STALE_AFTER_DAYS = 14
HISTORY_METADATA = {
    "history_kind": "CURRENT_REPORTED_LATEST_REPORT",
    "historical_pit": False,
    "historical_available_at": None,
    "vintage_id": None,
}


def _positions_line(block: list[str]) -> str:
    """Commitments row, not the later percent-of-open-interest row that also starts with All."""
    percent_at = next(
        (index for index, line in enumerate(block) if "PERCENT OF OPEN INTEREST" in line.upper()),
        len(block),
    )
    for line in block[:percent_at]:
        if line.strip().upper().startswith("ALL") and ":" in line:
            return line
    return ""


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
        all_line = _positions_line(block)
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
            "release_date": None,
            "event_time": iso(as_of),
            "event_time_precision": "date",
            "available_at": None,
            "ingested_at": None,
            "availability_basis": "publication timestamp absent from current report",
            **HISTORY_METADATA,
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
    try:
        response = client.get(CFTC_FUTURES_URL)
        response.raise_for_status()
        retrieved = datetime.now(UTC)
        markets = parse_cftc_report(response.text)
        source_sha256 = hashlib.sha256(response.content).hexdigest()
        for row in markets.values():
            row.update({
                "available_at": iso(retrieved),
                "ingested_at": iso(retrieved),
                "availability_basis": "observed response receipt; historical publication unknown",
                "source_sha256": source_sha256,
            })
    except (httpx.HTTPError, TypeError, ValueError) as exc:
        if owns:
            client.close()
        return ProviderResult(
            status=OperationalStatus.UNAVAILABLE,
            failure_kind=type(exc).__name__,
            source="cftc",
            retrieved_at=datetime.now(UTC),
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
        extras={"url": CFTC_FUTURES_URL, "markets": markets,
                "source_sha256": source_sha256, **HISTORY_METADATA},
    )


def cot_context_from_result(result: ProviderResult, *, now: datetime | None = None) -> dict[str, Any]:
    observed = now or datetime.now(UTC)
    markets = {str(row["asset"]): dict(row) for row in result.records if row.get("asset")}
    as_of_dates = []
    for row in markets.values():
        for key, value in HISTORY_METADATA.items():
            row.setdefault(key, value)
        raw = row.get("as_of_date")
        if raw:
            try:
                as_of_dates.append(datetime.fromisoformat(str(raw)).date())
            except ValueError:
                continue
        # The positions date is a date-granularity event marker. It cannot
        # stand in for knowledge time, even on a normal Tuesday-Friday week.
        try:
            event = parse_datetime(row.get("event_time"))
            if event is None and raw:
                event = datetime.fromisoformat(str(raw)).replace(tzinfo=UTC)
            receipt = parse_datetime(row.get("available_at")) or result.retrieved_at
            row["point_in_time"] = PointInTime(event, receipt, observed).to_dict()
        except ValueError:
            row["point_in_time"] = PointInTime(decision_time=observed).to_dict()
    freshest = min(as_of_dates) if as_of_dates else None
    freshness_days = (observed.date() - freshest).days if freshest else None
    stale = freshness_days is None or not 0 <= freshness_days <= STALE_AFTER_DAYS
    incomplete = result.status is not OperationalStatus.HEALTHY or len(markets) < 2
    pit_states = {row.get("point_in_time", {}).get("availability", "UNKNOWN")
                  for row in markets.values()}
    knowledge_time_status = (
        "LATE" if "LATE" in pit_states else
        "ELIGIBLE" if pit_states == {"ELIGIBLE"} and not incomplete else "UNKNOWN"
    )
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
    elif knowledge_time_status == Availability.LATE.value:
        status = "LATE"
        regime = "unknown"
    elif knowledge_time_status != Availability.ELIGIBLE.value:
        status = "UNKNOWN"
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
    if status == "LATE":
        warnings.append("COT source was observed after the decision; no directional COT gate was applied")
    if status == "UNKNOWN":
        warnings.append("COT publication/receipt availability is unknown; no directional COT gate was applied")
    return {
        "status": status,
        "regime": regime,
        "scope": "market/regime context; no per-altcoin COT signal",
        "source": "OpenBB/CFTC futures-only report" if result.source == "OpenBB/CFTC" else "CFTC futures-only report",
        "as_of_date": freshest.isoformat() if freshest else None,
        "freshness_days": freshness_days,
        "knowledge_time_status": knowledge_time_status,
        "retrieved_at": iso(result.retrieved_at),
        **HISTORY_METADATA,
        "markets": markets,
        "warnings": warnings,
        "failure_kind": result.failure_kind,
    }


def fetch_cot_context(*, now: datetime | None = None, http: httpx.Client | None = None) -> dict[str, Any]:
    from rocket.providers.openbb_cftc import OpenBBCFTC
    from rocket.providers.registry import Registry

    observed = now or datetime.now(UTC)
    direct: dict[str, ProviderResult] = {}

    def fetch_direct() -> ProviderResult:
        result = fetch_cftc_direct(http=http)
        direct["result"] = result
        return result

    registry = Registry()
    registry.register("cot", "cftc", fetch_direct)
    registry.register("cot", "openbb_cftc", lambda: OpenBBCFTC().fetch(now=observed))
    acquisition = registry.acquire(
        "cot",
        required=False,
        sufficient=lambda r: cot_context_from_result(r, now=now or datetime.now(UTC))["status"] == "OK",
    )
    # A stale or partial official report is a diagnosis. Do not replace it with
    # SourcesExhausted when the OpenBB fallback also fails.
    result = acquisition.result
    if result is None and "result" in direct:
        result = direct["result"]
    if result is None:
        result = ProviderResult(
            OperationalStatus.UNAVAILABLE,
            source="cot",
            failure_kind="SourcesExhausted",
            retrieved_at=observed,
        )
    context = cot_context_from_result(result, now=now or datetime.now(UTC))
    context["provider_attempts"] = [attempt.to_dict() for attempt in acquisition.attempts]
    context["required"] = False
    context["endpoint"] = CFTC_FUTURES_URL
    context["stale_after_days"] = STALE_AFTER_DAYS
    context["staleness_rule"] = (
        f"cot_regime is unknown unless BTC and ETH both parse and the older as-of date "
        f"is 0 to {STALE_AFTER_DAYS} days before the decision date; an observed receipt "
        "after the decision cannot be used"
    )
    return context
