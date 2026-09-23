"""Bounded memecoin intake and conservative ranking.

NO_EDGE_VALIDATED. Human-gated. Read-only. Identification ≠ entry.
Browser and X are evidence sources, not execution.
Every result keeps edge=NO_EDGE_VALIDATED and execution_enabled=false.

Discovery reads public JSON that pump.fun and pump.family already call.
Helius is confirm-only, and only through the existing HELIUS_API_KEY.
X is optional and never creates an identity.
"""

from __future__ import annotations

import base64
import json
import math
import time
from collections import deque
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

import httpx

from rocket.capture.spool import replay_segment
from rocket.config import env
from rocket.models import (
    Evidence,
    EvidenceKind,
    OperationalReport,
    OperationalStatus,
    Provenance,
    ProviderHealth,
    ReasonCode,
    ResearchReason,
    ResearchResult,
    ResearchStatus,
)
from rocket.pit import parse_datetime
from rocket.providers.http import get_read
from rocket.providers.inventory import MAINNET_GENESIS, TOKEN_PROGRAMS
from rocket.store import ResearchStore
from rocket.workflows.memecoin import EDGE, canonical_identity

SAFETY_SENTENCE = (
    "NO_EDGE_VALIDATED. Human-gated. Read-only. Identification ≠ entry. "
    "Browser and X are evidence sources, not execution."
)
WATCH_IS_NOT_A_BUY = "A WATCH_ENTER row is not a buy."
DECISIONS = frozenset({"TOO_EARLY", "SKIP", "WATCH_ENTER", "AVOID"})
ABSENCE_WARNING = "Empty, partial, or failed discovery is not evidence that no memecoins exist."

# Minutes, not seconds: slot-0 bonding-curve snipes and the observed 8s/12s
# wallet episode are inside this floor. This is a triage gate, not an edge.
AGE_FLOOR_SECONDS = 30 * 60
LIQUIDITY_FLOOR_USD = 10_000
SELECTED_CAP = 20
RPC_BATCH_CAP = 5
RPC_BATCH_PAUSE_SECONDS = 0.4
INTAKE_FRAME_CAP = 40
SCAN_INTAKE_CAP = 200
FAMILY_CURVE_CAP = 8
CACHE_BYTE_CAP = 256_000

INTAKE_SCHEMA = "rocket.memecoin-intake.v0"
CACHE_SCHEMA = "rocket.memecoin-provider-cache.v0"
SNAPSHOT_SCHEMA = "rocket.memecoin-snapshot.v0"

UNIVERSE_SOURCE = (
    "browser:pump.fun",
    "browser:fomo.family",
    "helius",
    "x",
)

# pump.fun GET /coins uses a shortened mainnet id. Exact match only.
# It is the leading bytes of MAINNET_GENESIS, not a second chain.
PUMP_CHAIN_ALIAS = "solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp"
SOLANA_MAINNET_CHAINS = frozenset({"solana:mainnet", f"solana:{MAINNET_GENESIS}", PUMP_CHAIN_ALIAS})
SOL_QUOTES = frozenset({
    "So11111111111111111111111111111111111111112",
    "11111111111111111111111111111111",
})

PUMP_EXPLORE_URL = "https://pump.fun/explore"
PUMP_COINS_URL = (
    "https://frontend-api-v3.pump.fun/coins"
    "?limit=20&offset=0&sort=created_timestamp&order=DESC&includeNsfw=false&complete=true"
)
FAMILY_EXPLORE_URL = "https://pump.family/explore"
FAMILY_SALES_URL = "https://pump.family/api/sales"
FOMO_HOME_URL = "https://fomo.family/"

HELIUS_ENV = "HELIUS_API_KEY"
WARNINGS = (SAFETY_SENTENCE, WATCH_IS_NOT_A_BUY, ABSENCE_WARNING)


def default_spool_path(state_dir) -> Any:
    return state_dir / "memecoin" / "spool"


def _iso(value: datetime | None) -> str | None:
    return value.astimezone(UTC).isoformat() if value else None


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _epoch(value: Any) -> datetime | None:
    number = _finite(value)
    if number is None:
        return None
    if number > 100_000_000_000:
        number /= 1000
    try:
        return datetime.fromtimestamp(number, UTC)
    except (OverflowError, OSError, ValueError):
        return None


def _health(name: str, status: OperationalStatus, now: datetime, *, failure: str | None = None, coverage: str | None = None) -> ProviderHealth:
    return ProviderHealth(name=name, status=status, retrieved_at=now, failure_kind=failure, coverage=coverage)


def _x_health(now: datetime) -> ProviderHealth:
    return _health("x", OperationalStatus.UNAVAILABLE, now, failure="OPTIONAL_NOT_CONSULTED", coverage="optional")


def _base_payload(**extra: Any) -> dict[str, Any]:
    payload = {
        "edge": EDGE,
        "execution_enabled": False,
        "safety": SAFETY_SENTENCE,
        "notice": WATCH_IS_NOT_A_BUY,
        "universe_source": list(UNIVERSE_SOURCE),
        "age_floor_seconds": AGE_FLOOR_SECONDS,
        "liquidity_floor_usd": LIQUIDITY_FLOOR_USD,
        "selected_cap": SELECTED_CAP,
        "x_required": False,
        "overfit_guard": "no asset-specific rule added",
        "case_study": None,
    }
    payload.update(extra)
    return payload


def _clock(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    return parse_datetime(value)


def normalize_chain(chain: Any) -> str | None:
    text = str(chain or "").strip()
    if text in SOLANA_MAINNET_CHAINS:
        return "solana:mainnet"
    return None


def _liquidity_from_reserves(reserves: Any, quote: Any, sol_usd: float | None) -> float | None:
    """Quote-reserve lamports times the same-snapshot SOL print. Market cap is not liquidity."""
    amount = _finite(reserves)
    price = _finite(sol_usd)
    if amount is None or price is None or amount <= 0 or str(quote or "") not in SOL_QUOTES:
        return None
    return round((amount / 1_000_000_000) * price, 2)


def _social(value: Any) -> str:
    text = str(value or "unknown").strip().lower()
    return text if text in {"none", "low", "high", "unknown"} else "unknown"


def _observation(
    *,
    mint: Any,
    asset: Any,
    chain: str,
    source: str,
    source_urls: list[str],
    retrieved_at: datetime,
    event_time: datetime | None,
    graduation_status: str,
    window_state: str,
    liquidity_usd: float | None,
    advertised_market_cap_usd: float | None,
    pool: Any,
    chain_id_source: str,
) -> dict[str, Any]:
    discovered = event_time or retrieved_at
    return {
        "schema": INTAKE_SCHEMA,
        "chain_id": chain,
        "chain_id_source": chain_id_source,
        "mint": str(mint or "").strip(),
        "asset": str(asset or "").strip() or None,
        "source": source,
        "sources": [source],
        "source_urls": source_urls,
        "retrieved_at": _iso(retrieved_at),
        "discovered_at": _iso(discovered),
        "event_time": _iso(event_time),
        "available_at": _iso(retrieved_at),
        "graduation_status": graduation_status,
        "window_state": window_state,
        "liquidity_usd": liquidity_usd,
        "advertised_market_cap_usd": advertised_market_cap_usd,
        "pool": str(pool).strip() if pool else None,
        "volume_acceleration": None,
        "social_heat": "unknown",
        "bundle_or_dev_hold": "UNKNOWN",
    }


def normalize_pump_coin(raw: Mapping[str, Any], *, now: datetime, sol_usd: float | None) -> dict[str, Any] | None:
    if raw.get("complete") is not True:
        return None
    mint = str(raw.get("mint") or "").strip()
    chain = normalize_chain(raw.get("chain_id")) or "solana:mainnet"
    event = _epoch(raw.get("created_timestamp"))
    liquidity = _liquidity_from_reserves(raw.get("real_quote_reserves"), raw.get("quote_mint"), sol_usd)
    return _observation(
        mint=mint,
        asset=raw.get("symbol") or raw.get("name"),
        chain=chain if normalize_chain(raw.get("chain_id")) else str(raw.get("chain_id") or ""),
        source="browser:pump.fun",
        source_urls=[PUMP_EXPLORE_URL, PUMP_COINS_URL, f"https://pump.fun/coin/{mint}"],
        retrieved_at=now,
        event_time=event,
        graduation_status="graduated",
        window_state="closed",
        liquidity_usd=liquidity,
        advertised_market_cap_usd=_finite(raw.get("usd_market_cap")),
        pool=raw.get("pump_swap_pool"),
        chain_id_source="pump.fun coins chain_id",
    )


def normalize_family_sale(raw: Mapping[str, Any], *, now: datetime) -> dict[str, Any] | None:
    phase = str(raw.get("phase") or "")
    if phase == "migrated":
        graduation, window = "graduated", "closed"
    elif phase == "launched":
        graduation, window = "still_on_curve", "closed"
    else:
        return None
    mint = str(raw.get("mint") or "").strip()
    event = _epoch(raw.get("windowEnd")) or _epoch(raw.get("firstSeen"))
    return _observation(
        mint=mint,
        asset=raw.get("symbol") or raw.get("name"),
        chain="solana:mainnet",
        source="browser:fomo.family",
        source_urls=[FOMO_HOME_URL, FAMILY_EXPLORE_URL, FAMILY_SALES_URL],
        retrieved_at=now,
        event_time=event,
        graduation_status=graduation,
        window_state=window,
        liquidity_usd=None,
        advertised_market_cap_usd=_finite(raw.get("marketCap")),
        pool=raw.get("pool"),
        chain_id_source="pump.family page rpc map solana:mainnet",
    )


def _bound_family(sales: Sequence[Mapping[str, Any]], *, now: datetime) -> tuple[list[dict[str, Any]], dict[str, int]]:
    migrated, launched = [], []
    excluded = {"open_or_other": 0}
    for raw in sales:
        if not isinstance(raw, Mapping):
            excluded["open_or_other"] += 1
            continue
        row = normalize_family_sale(raw, now=now)
        if row is None:
            excluded["open_or_other"] += 1
            continue
        if row["graduation_status"] == "graduated":
            migrated.append(row)
        else:
            launched.append(row)
    launched.sort(key=lambda item: item.get("event_time") or "", reverse=True)
    return migrated + launched[:FAMILY_CURVE_CAP], excluded


def _cache_frame(url: str, body: bytes, now: datetime) -> bytes:
    record: dict[str, Any] = {
        "schema": CACHE_SCHEMA,
        "source_url": url.split("?", 1)[0],
        "retrieved_at": _iso(now),
        "bytes": len(body),
    }
    if len(body) <= CACHE_BYTE_CAP:
        try:
            record["body"] = json.loads(body)
        except (UnicodeError, json.JSONDecodeError):
            record["body_decoded"] = False
    else:
        record["truncated"] = True
    return json.dumps(record, separators=(",", ":"), default=str).encode()


def _read_json(client: httpx.Client, url: str) -> tuple[Any | None, bytes, str | None]:
    try:
        response = get_read(client, url)
    except httpx.HTTPStatusError as exc:
        return None, b"", f"HTTP_{exc.response.status_code}"
    except httpx.HTTPError:
        return None, b"", "TRANSPORT_ERROR"
    body = response.content
    try:
        return response.json(), body, None
    except (UnicodeError, json.JSONDecodeError):
        return None, body, "INVALID_JSON"


def discover(client: httpx.Client, *, now: datetime) -> dict[str, Any]:
    """Bounded public snapshot. No Helius call. No key material."""
    providers: list[ProviderHealth] = []
    caches: list[bytes] = []
    family_rows: list[dict[str, Any]] = []
    sol_usd = None
    payload, body, failure = _read_json(client, FAMILY_SALES_URL)
    if failure or not isinstance(payload, dict) or not isinstance(payload.get("sales"), list):
        providers.append(_health(
            "browser:fomo.family", OperationalStatus.UNAVAILABLE, now,
            failure=failure or "LOGIN_WALLED_OR_UNEXPECTED_BODY",
            coverage="fomo.family login-walled; pump.family/api/sales failed",
        ))
    else:
        sol_usd = _finite(payload.get("solUsd"))
        family_rows, excluded = _bound_family(payload["sales"], now=now)
        caches.append(_cache_frame(FAMILY_SALES_URL, body, now))
        providers.append(_health(
            "browser:fomo.family", OperationalStatus.HEALTHY, now,
            coverage=f"fomo.family login-walled; pump.family/api/sales migrated+closed excluded={excluded['open_or_other']}",
        ))
    pump_rows: list[dict[str, Any]] = []
    payload, body, failure = _read_json(client, PUMP_COINS_URL)
    if failure or not isinstance(payload, list):
        providers.append(_health(
            "browser:pump.fun", OperationalStatus.UNAVAILABLE, now,
            failure=failure or "UNEXPECTED_BODY",
            coverage=PUMP_COINS_URL.split("?", 1)[0],
        ))
    else:
        caches.append(_cache_frame(PUMP_COINS_URL, body, now))
        for raw in payload[:20]:
            if isinstance(raw, Mapping):
                row = normalize_pump_coin(raw, now=now, sol_usd=sol_usd)
                if row is not None:
                    pump_rows.append(row)
        providers.append(_health(
            "browser:pump.fun", OperationalStatus.HEALTHY, now,
            coverage="frontend-api-v3.pump.fun GET /coins complete=true",
        ))
    observations = (pump_rows + family_rows)[:INTAKE_FRAME_CAP]
    return {"observations": observations, "providers": providers, "caches": caches, "sol_usd": sol_usd}


def helius_endpoint() -> str | None:
    key = env(HELIUS_ENV)
    if not key:
        return None
    return f"https://mainnet.helius-rpc.com/?api-key={key}"


def _decode_mint(data: bytes) -> tuple[int, int] | None:
    if len(data) < 82 or data[45] != 1:
        return None
    supply = int.from_bytes(data[36:44], "little")
    return supply, data[44]


def _rpc_post(client: httpx.Client, url: str, calls: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
    """One JSON-RPC batch. A 429 is retried. The URL is never returned."""
    delay = 0.0
    for attempt in range(3):
        if delay:
            time.sleep(delay)
        try:
            response = client.post(url, json=calls)
            if response.status_code == 429 and attempt < 2:
                delay = 1.5 * (attempt + 1)
                continue
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, UnicodeError, json.JSONDecodeError, ValueError):
            return None
        if isinstance(payload, dict):
            payload = [payload]
        return payload if isinstance(payload, list) else None
    return None


def _rpc_batch(client: httpx.Client, url: str, calls: list[dict[str, Any]]) -> tuple[list[dict[str, Any]] | None, bool]:
    """Small batches with a pause. A later 429 keeps earlier confirms."""
    merged: list[dict[str, Any]] = []
    incomplete = False
    for index, start in enumerate(range(0, len(calls), RPC_BATCH_CAP)):
        if index:
            time.sleep(RPC_BATCH_PAUSE_SECONDS)
        part = _rpc_post(client, url, calls[start:start + RPC_BATCH_CAP])
        if part is None:
            incomplete = True
            continue
        merged.extend(part)
    return (merged or None), incomplete


def confirm_helius(rows: Sequence[Mapping[str, Any]], client: httpx.Client, *, now: datetime) -> tuple[list[dict[str, Any]], ProviderHealth]:
    """Confirm mint accounts. The endpoint URL, which carries the key, is never returned."""
    url = helius_endpoint()
    copied = [dict(row) for row in rows]
    if url is None:
        return copied, _health("helius", OperationalStatus.UNAVAILABLE, now, failure="HELIUS_API_KEY_ABSENT", coverage="not_called")
    calls = []
    seen: set[str] = set()
    for row in copied[:SELECTED_CAP]:
        mint = str(row.get("mint") or "")
        pool = str(row.get("pool") or "")
        if mint and f"m:{mint}" not in seen:
            seen.add(f"m:{mint}")
            calls.append({"jsonrpc": "2.0", "id": f"m:{mint}", "method": "getAccountInfo", "params": [mint, {"encoding": "base64"}]})
            calls.append({"jsonrpc": "2.0", "id": f"l:{mint}", "method": "getTokenLargestAccounts", "params": [mint]})
        if pool and f"p:{pool}" not in seen:
            seen.add(f"p:{pool}")
            calls.append({"jsonrpc": "2.0", "id": f"p:{pool}", "method": "getAccountInfo", "params": [pool, {"encoding": "base64"}]})
    if not calls:
        return copied, _health("helius", OperationalStatus.HEALTHY, now, coverage="no_mints")
    payload, incomplete = _rpc_batch(client, url, calls)
    if payload is None:
        return copied, _health("helius", OperationalStatus.UNAVAILABLE, now, failure="HELIUS_HTTP_ERROR", coverage="getAccountInfo")
    by_id = {str(item.get("id")): item for item in payload if isinstance(item, Mapping)}
    confirmed = 0
    for row in copied[:SELECTED_CAP]:
        mint = str(row.get("mint") or "")
        pool = str(row.get("pool") or "")
        mint_item = by_id.get(f"m:{mint}")
        if not isinstance(mint_item, Mapping) or mint_item.get("error"):
            row["helius"] = {"mint_exists": None, "retrieved_at": _iso(now)}
            continue
        value = (mint_item.get("result") or {}).get("value") if isinstance(mint_item.get("result"), Mapping) else None
        decoded = None
        if isinstance(value, Mapping) and value.get("owner") in TOKEN_PROGRAMS:
            data = value.get("data")
            try:
                raw = base64.b64decode(data[0]) if isinstance(data, list) and data else b""
            except (ValueError, TypeError, IndexError):
                raw = b""
            decoded = _decode_mint(raw)
        exists = decoded is not None
        top_bps = None
        if exists and decoded and decoded[0] > 0:
            largest = by_id.get(f"l:{mint}") or {}
            holders = (largest.get("result") or {}).get("value") if isinstance(largest.get("result"), Mapping) else None
            if isinstance(holders, list) and holders:
                amount = _finite((holders[0] or {}).get("amount"))
                if amount is not None and amount >= 0:
                    top_bps = int(amount) * 10_000 // decoded[0]
        pool_exists = None
        if pool:
            pool_item = by_id.get(f"p:{pool}")
            if isinstance(pool_item, Mapping) and not pool_item.get("error"):
                pool_value = (pool_item.get("result") or {}).get("value") if isinstance(pool_item.get("result"), Mapping) else None
                pool_exists = pool_value is not None
        row["helius"] = {
            "mint_exists": exists,
            "pool_exists": pool_exists,
            "top1_holder_bps": top_bps,
            "dev_hold": "UNKNOWN",
            "retrieved_at": _iso(now),
        }
        if top_bps is None:
            row["bundle_or_dev_hold"] = "UNKNOWN"
        else:
            row["bundle_or_dev_hold"] = {"top1_holder_bps": top_bps, "dev_hold": "UNKNOWN"}
        if exists:
            confirmed += 1
            sources = list(row.get("sources") or [])
            if "helius" not in sources:
                sources.append("helius")
            row["sources"] = sources
    status = OperationalStatus.PARTIAL if incomplete else OperationalStatus.HEALTHY
    failure = "HELIUS_HTTP_ERROR" if incomplete else None
    return copied, _health(
        "helius", status, now, failure=failure,
        coverage=f"getAccountInfo+getTokenLargestAccounts confirmed={confirmed}",
    )


def _reject(reason: str, row: Mapping[str, Any] | None = None) -> dict[str, Any]:
    item: dict[str, Any] = {"reason": reason}
    if row:
        identity = row.get("identity")
        mint = str(row.get("mint") or "").strip()
        if identity:
            item["identity"] = identity
        elif mint:
            item["mint"] = mint
    return item


def classify_row(row: Mapping[str, Any], *, now: datetime) -> dict[str, Any]:
    if row.get("decode_error"):
        return {"bucket": "rejected", "item": _reject("failed_decode", row)}
    chain = normalize_chain(row.get("chain_id"))
    minted = dict(row)
    if chain:
        minted["chain_id"] = chain
    identity = canonical_identity(minted)
    if identity is None or chain is None:
        return {"bucket": "rejected", "item": _reject("unknown_identity", minted)}
    minted["identity"] = identity
    try:
        event = _clock(row.get("event_time"))
        available = _clock(row.get("available_at"))
    except ValueError:
        return {"bucket": "rejected", "item": _reject("invalid_clock", minted)}
    if available is not None and available > now:
        return {"bucket": "rejected", "item": _reject("future_available_at", minted)}
    if event is not None and event > now:
        return {"bucket": "rejected", "item": _reject("future_event_time", minted)}
    helius = row.get("helius") if isinstance(row.get("helius"), Mapping) else {}
    if helius.get("mint_exists") is False:
        return {"bucket": "rejected", "item": _reject("mint_not_found", minted)}
    unknowns: list[str] = []
    known_fails: list[str] = []
    if helius.get("mint_exists") is not True:
        unknowns.append("helius_confirm_missing")
    if event is None or available is None:
        unknowns.append("clocks_incomplete")
    age = int((now - event).total_seconds()) if event is not None else None
    if age is None:
        unknowns.append("age_unknown")
    elif age < AGE_FLOOR_SECONDS:
        known_fails.append("below_age_floor")
    liquidity = _finite(row.get("liquidity_usd"))
    if liquidity is None:
        unknowns.append("liquidity_unknown")
    elif liquidity < LIQUIDITY_FLOOR_USD:
        known_fails.append("liquidity_below_floor")
    graduation = str(row.get("graduation_status") or "unknown")
    window = str(row.get("window_state") or "unknown")
    if graduation == "still_on_curve" or window == "open":
        known_fails.append("still_on_curve" if graduation == "still_on_curve" else "window_open")
    elif graduation not in {"graduated"} or window != "closed":
        unknowns.append("graduation_unknown")
    confirmed = helius.get("mint_exists") is True
    state, reasons = _decision(confirmed=confirmed, age=age, unknowns=unknowns, known_fails=known_fails)
    volume = _finite(row.get("volume_acceleration"))
    selected = {
        "identity": identity,
        "asset": row.get("asset"),
        "mint": minted.get("mint"),
        "state": state,
        "liquidity_usd": liquidity,
        "age_seconds": age,
        "volume_acceleration": volume,
        "sources": list(row.get("sources") or ([row.get("source")] if row.get("source") else [])),
        "social_heat": _social(row.get("social_heat")),
        "reasons": reasons,
        "discovered_at": _iso(event) or row.get("discovered_at"),
        "available_at": _iso(available),
        "source_urls": list(row.get("source_urls") or []),
        "bundle_or_dev_hold": row.get("bundle_or_dev_hold") if helius.get("mint_exists") is True else "UNKNOWN",
        "event_time": _iso(event),
        "graduation_status": graduation,
        "window_state": window,
    }
    return {"bucket": "selected", "item": selected, "event": event, "available": available}


def _decision(*, confirmed: bool, age: int | None, unknowns: list[str], known_fails: list[str]) -> tuple[str, list[str]]:
    """Bot label for a selected row. SKIP is not safe. WATCH_ENTER is not a buy.

    Priority is documented in artifacts/memecoin_radar/DECISION_CONTRACT_v0.md.
    Age below the floor on a Helius-confirmed mint is TOO_EARLY ahead of other
    hard fails. A hard fail other than age is AVOID only after that confirm.
    Anything that cannot be computed, including a missing confirm, is SKIP.
    """
    if confirmed and age is not None and age < AGE_FLOOR_SECONDS:
        reasons = ["below_age_floor"]
        for item in [*unknowns, *known_fails]:
            if item not in reasons and item != "age_unknown":
                reasons.append(item)
        return "TOO_EARLY", reasons
    hard = [item for item in known_fails if item != "below_age_floor"]
    if confirmed and hard:
        reasons = list(hard)
        for item in unknowns:
            if item not in reasons:
                reasons.append(item)
        return "AVOID", reasons
    if unknowns or not confirmed:
        reasons = list(unknowns)
        for item in known_fails:
            if item not in reasons:
                reasons.append(item)
        if not confirmed and "helius_confirm_missing" not in reasons:
            reasons.insert(0, "helius_confirm_missing")
        return "SKIP", reasons or ["helius_confirm_missing"]
    return "WATCH_ENTER", ["floors_met_not_an_entry"]


def rank_rows(rows: Sequence[Mapping[str, Any]], *, now: datetime) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected, rejected = [], []
    for row in rows:
        if not isinstance(row, Mapping):
            rejected.append({"reason": "failed_decode"})
            continue
        outcome = classify_row(row, now=now)
        if outcome["bucket"] == "rejected":
            rejected.append(outcome["item"])
        elif outcome["item"].get("state") not in DECISIONS:
            rejected.append(_reject("failed_decode", outcome["item"]))
        else:
            selected.append(outcome)
    selected.sort(
        key=lambda item: (
            str(item["item"].get("discovered_at") or ""),
            item["item"]["liquidity_usd"] if isinstance(item["item"].get("liquidity_usd"), (int, float)) else -1.0,
        ),
        reverse=True,
    )
    kept, seen = [], set()
    for outcome in selected:
        identity = outcome["item"]["identity"]
        if identity in seen:
            rejected.append({"identity": identity, "reason": "duplicate_snapshot_identity"})
            continue
        seen.add(identity)
        kept.append(outcome)
    overflow = kept[SELECTED_CAP:]
    kept = kept[:SELECTED_CAP]
    for outcome in overflow:
        rejected.append({"identity": outcome["item"]["identity"], "reason": "selected_cap"})
    return [item["item"] for item in kept], rejected[:40]


def _evidence_for(rows: Sequence[Mapping[str, Any]], *, now: datetime) -> tuple[Evidence, ...]:
    evidence = []
    for row in rows:
        identity = str(row.get("identity") or "")
        if not identity:
            continue
        try:
            event = _clock(row.get("event_time"))
            available = _clock(row.get("available_at"))
        except ValueError:
            continue
        evidence.append(Evidence(
            source="memecoin.radar",
            reference=identity,
            claim="Intake row ranked for human review. Identification is not an entry.",
            kind=EvidenceKind.FACT if row.get("state") == "WATCH_ENTER" else EvidenceKind.UNKNOWN,
            event_time=event,
            available_at=available,
            retrieved_at=now,
            decision_time=now,
            provenance=Provenance.PROVIDER_RESULT,
        ))
    return tuple(evidence)


def _overall(providers: Sequence[ProviderHealth], *, discovery_failed: bool, has_rows: bool) -> OperationalStatus:
    if discovery_failed and not has_rows:
        return OperationalStatus.UNAVAILABLE
    if not has_rows:
        return OperationalStatus.HEALTHY
    required = [item for item in providers if item.name != "x"]
    if any(item.status is not OperationalStatus.HEALTHY for item in required):
        return OperationalStatus.PARTIAL
    return OperationalStatus.HEALTHY


def _coverage(status: OperationalStatus, *, discovery_failed: bool, has_rows: bool) -> str:
    if discovery_failed and not has_rows:
        return "DATA_UNAVAILABLE"
    if not has_rows:
        return "EMPTY_INTAKE"
    if status is OperationalStatus.PARTIAL:
        return "PARTIAL"
    if status is OperationalStatus.UNAVAILABLE:
        return "DATA_UNAVAILABLE"
    return "OBSERVED"


def scan_feed(
    rows: Sequence[Mapping[str, Any]],
    *,
    now: datetime | None = None,
    store: ResearchStore | None = None,
    providers: Sequence[ProviderHealth] = (),
    discovery_failed: bool = False,
) -> ResearchResult:
    decided = now or datetime.now(UTC)
    selected, rejected = rank_rows(rows, now=decided)
    provider_rows = tuple(providers) if providers else (_x_health(decided),)
    if not any(item.name == "x" for item in provider_rows):
        provider_rows = (*provider_rows, _x_health(decided))
    operational = _overall(provider_rows, discovery_failed=discovery_failed, has_rows=bool(selected) or bool(rows))
    coverage = _coverage(operational, discovery_failed=discovery_failed, has_rows=bool(rows))
    if coverage == "DATA_UNAVAILABLE":
        reason = ResearchReason(ReasonCode.REQUIRED_PROVIDER_UNAVAILABLE, ("memecoin discovery feed",), retryable=True)
    elif not selected:
        reason = ResearchReason(ReasonCode.REQUIRED_EVIDENCE_MISSING, ("bounded intake rows passing triage",))
    else:
        reason = ResearchReason(ReasonCode.STRATEGY_UNVALIDATED, ("costed out-of-sample strategy validation and human review",))
    result = ResearchResult(
        workflow="memecoin.scan",
        status=ResearchStatus.INSUFFICIENT_EVIDENCE,
        reasons=(reason,),
        operational=OperationalReport(status=operational, providers=provider_rows),
        decision_time=decided,
        started_at=decided,
        completed_at=decided,
        payload=_base_payload(
            selected=selected,
            rejected=rejected,
            provider_health=[item.to_dict() for item in provider_rows],
            coverage_status=coverage,
            intake_rows=len(list(rows)) if not isinstance(rows, int) else 0,
        ),
        evidence=_evidence_for(selected, now=decided),
        warnings=WARNINGS,
    )
    if store:
        store.save_result(result)
    return result


def _snapshot_frame(providers: Sequence[ProviderHealth], now: datetime, *, sol_usd: float | None) -> bytes:
    record = {
        "schema": SNAPSHOT_SCHEMA,
        "retrieved_at": _iso(now),
        "provider_health": [item.to_dict() for item in providers],
        "sol_usd": sol_usd,
        "safety": SAFETY_SENTENCE,
    }
    return json.dumps(record, separators=(",", ":")).encode()


def append_intake(spool: Any, rows: Sequence[Mapping[str, Any]], caches: Sequence[bytes], providers: Sequence[ProviderHealth], *, now: datetime, sol_usd: float | None = None) -> int:
    frames: list[tuple[bytes, datetime]] = []
    for raw in list(caches)[:4]:
        frames.append((raw, now))
    for row in list(rows)[:INTAKE_FRAME_CAP]:
        frames.append((json.dumps(dict(row), separators=(",", ":"), default=str).encode(), now))
    frames.append((_snapshot_frame(providers, now, sol_usd=sol_usd), now))
    receipts = spool.append_batch(frames)
    return len(receipts)


def collect_snapshot(
    spool: Any,
    *,
    now: datetime | None = None,
    store: ResearchStore | None = None,
    observations: Sequence[Mapping[str, Any]] | None = None,
    client: httpx.Client | None = None,
    helius_client: httpx.Client | None = None,
) -> ResearchResult:
    decided = now or datetime.now(UTC)
    caches: list[bytes] = []
    sol_usd = None
    discovery_failed = False
    if observations is None:
        if client is None:
            discovery_failed = True
            providers = [
                _health("browser:pump.fun", OperationalStatus.UNAVAILABLE, decided, failure="NO_HTTP_CLIENT", coverage=PUMP_EXPLORE_URL),
                _health("browser:fomo.family", OperationalStatus.UNAVAILABLE, decided, failure="NO_HTTP_CLIENT", coverage=FOMO_HOME_URL),
            ]
            rows: list[dict[str, Any]] = []
        else:
            found = discover(client, now=decided)
            rows = found["observations"]
            providers = list(found["providers"])
            caches = found["caches"]
            sol_usd = found["sol_usd"]
            discovery_failed = not rows and all(item.status is not OperationalStatus.HEALTHY for item in providers)
    else:
        rows = [dict(row) for row in observations][:INTAKE_FRAME_CAP]
        providers = []
    if helius_client is not None and rows:
        rows, helius_health = confirm_helius(rows, helius_client, now=decided)
        providers.append(helius_health)
    elif not any(item.name == "helius" for item in providers):
        failure = None if helius_endpoint() else "HELIUS_API_KEY_ABSENT"
        status = OperationalStatus.HEALTHY if failure is None else OperationalStatus.UNAVAILABLE
        providers.append(_health("helius", status, decided, failure=failure, coverage="confirm_skipped" if failure is None else "not_called"))
    providers.append(_x_health(decided))
    has_rows = bool(rows)
    operational = _overall(providers, discovery_failed=discovery_failed, has_rows=has_rows)
    coverage = _coverage(operational, discovery_failed=discovery_failed, has_rows=has_rows)
    appended = 0
    if coverage != "DATA_UNAVAILABLE":
        appended = append_intake(spool, rows, caches, providers, now=decided, sol_usd=sol_usd)
    if coverage == "DATA_UNAVAILABLE":
        research = ResearchStatus.INSUFFICIENT_EVIDENCE
        reasons = (ResearchReason(ReasonCode.REQUIRED_PROVIDER_UNAVAILABLE, ("memecoin discovery feed",), retryable=True),)
    else:
        research = ResearchStatus.NO_SETUP
        reasons = ()
    result = ResearchResult(
        workflow="memecoin.collect",
        status=research,
        reasons=reasons,
        operational=OperationalReport(status=operational, providers=tuple(providers)),
        decision_time=decided,
        started_at=decided,
        completed_at=decided,
        payload=_base_payload(
            frames_appended=appended,
            intake_rows=len(rows),
            collector="spool_first",
            provider_health=[item.to_dict() for item in providers],
            coverage_status=coverage,
            snapshot_bound=INTAKE_FRAME_CAP,
            helius_env=HELIUS_ENV,
            helius_key_present=bool(env(HELIUS_ENV)),
        ),
        warnings=WARNINGS,
    )
    if store:
        store.save_result(result)
    return result


def load_spool(root: Any, *, limit: int = SCAN_INTAKE_CAP) -> dict[str, Any]:
    intakes: deque[dict[str, Any]] = deque(maxlen=limit)
    rejected = []
    manifest = None
    paths = sorted(root.glob("segment-*.jsonl")) if root.exists() else []
    for path in paths:
        for raw, _stamp, _meta in replay_segment(path):
            try:
                record = json.loads(raw)
            except (UnicodeError, json.JSONDecodeError):
                rejected.append({"reason": "failed_decode"})
                continue
            if not isinstance(record, dict):
                rejected.append({"reason": "failed_decode"})
                continue
            schema = record.get("schema")
            if schema == CACHE_SCHEMA:
                continue
            if schema == SNAPSHOT_SCHEMA:
                manifest = record
                continue
            if schema not in {None, INTAKE_SCHEMA} and "mint" not in record:
                rejected.append({"reason": "failed_decode"})
                continue
            intakes.append(record)
    return {"rows": list(intakes), "rejected_prefix": rejected, "manifest": manifest}


def providers_from_manifest(manifest: Mapping[str, Any] | None, *, now: datetime) -> list[ProviderHealth]:
    if not manifest:
        return []
    found = []
    for item in manifest.get("provider_health") or []:
        if isinstance(item, Mapping):
            found.append(ProviderHealth.from_dict(item))
    return found


def scan_spool(
    root: Any,
    *,
    now: datetime | None = None,
    store: ResearchStore | None = None,
    helius_client: httpx.Client | None = None,
) -> ResearchResult:
    decided = now or datetime.now(UTC)
    missing = not root.exists() or not any(root.glob("segment-*.jsonl"))
    if missing:
        return scan_feed(
            [],
            now=decided,
            store=store,
            providers=(
                _health("browser:pump.fun", OperationalStatus.UNAVAILABLE, decided, failure="SPOOL_MISSING", coverage=str(root)),
                _health("browser:fomo.family", OperationalStatus.UNAVAILABLE, decided, failure="SPOOL_MISSING", coverage=str(root)),
                _health("helius", OperationalStatus.UNAVAILABLE, decided, failure="HELIUS_API_KEY_ABSENT" if not helius_endpoint() else "SPOOL_MISSING", coverage="not_called"),
            ),
            discovery_failed=True,
        )
    loaded = load_spool(root)
    rows = loaded["rows"]
    providers = providers_from_manifest(loaded["manifest"], now=decided)
    if helius_client is not None and rows:
        rows, helius_health = confirm_helius(rows, helius_client, now=decided)
        providers = [item for item in providers if item.name != "helius"]
        providers.append(helius_health)
    elif not any(item.name == "helius" for item in providers):
        failure = None if helius_endpoint() else "HELIUS_API_KEY_ABSENT"
        providers.append(_health(
            "helius",
            OperationalStatus.HEALTHY if failure is None else OperationalStatus.UNAVAILABLE,
            decided,
            failure=failure,
            coverage="not_called",
        ))
    result = scan_feed(rows, now=decided, store=store, providers=providers, discovery_failed=False)
    if loaded["rejected_prefix"]:
        payload = dict(result.payload)
        payload["rejected"] = (loaded["rejected_prefix"] + list(payload.get("rejected") or []))[:40]
        result = ResearchResult(
            workflow=result.workflow,
            status=result.status,
            reasons=result.reasons,
            operational=result.operational,
            decision_time=result.decision_time,
            started_at=result.started_at,
            completed_at=result.completed_at,
            run_id=result.run_id,
            payload=payload,
            evidence=result.evidence,
            warnings=result.warnings,
            mode=result.mode,
        )
        if store:
            store.save_result(result)
    return result


def is_legacy_snapshot(payload: Any) -> bool:
    rows = payload.get("rows", payload.get("frames", payload)) if isinstance(payload, Mapping) else payload
    if not isinstance(rows, list) or not rows or not isinstance(rows[0], Mapping):
        return False
    row = rows[0]
    if row.get("schema") in {INTAKE_SCHEMA, CACHE_SCHEMA, SNAPSHOT_SCHEMA}:
        return False
    if "raw" in row or "raw_base64" in row:
        return False
    return "features" in row or ("contract_address" in row and "mint" not in row)


def radar_rows_from_payload(payload: Any) -> list[Any]:
    if isinstance(payload, Mapping) and isinstance(payload.get("observations"), list):
        return list(payload["observations"])
    if isinstance(payload, Mapping) and isinstance(payload.get("rows"), list):
        return list(payload["rows"])
    if isinstance(payload, list):
        return list(payload)
    return []
