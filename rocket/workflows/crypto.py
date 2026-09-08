"""One crypto futures engine: top-100 universe → funnel → optional Cava overlay."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rocket.models import (
    Evidence,
    EvidenceKind,
    Mode,
    OperationalReport,
    OperationalStatus,
    Provenance,
    ProviderHealth,
    ReasonCode,
    ResearchReason,
    ResearchResult,
    ResearchStatus,
)
from rocket.pit import Availability, PointInTime, parse_datetime
from rocket.store import ResearchStore
from rocket.workflows.macro import macro_is_usable

WORKFLOW_SCAN = "crypto.scan"
WORKFLOW_EVAL = "crypto.evaluate"
WORKFLOW_MISSED = "crypto.missed"
UNIVERSE_SIZE = 100
MIN_QUOTE_VOLUME_24H = 5_000_000.0
MIN_OPEN_INTEREST_USD = 1_000_000.0
MAX_SPREAD_BPS = 20.0
MAX_SLIPPAGE_BPS = 25.0
STRUCTURE_BARS = 6
MIN_SETUP_BARS = 24
NO_CHASE_PCT = 0.02


def _asset_key(candidate: Mapping[str, Any]) -> str:
    canonical = candidate.get("canonical_asset_id")
    if canonical:
        return "canonical:" + str(canonical).lower()
    chain, address = candidate.get("chain_id"), candidate.get("contract_address")
    if chain and address:
        return f"{chain}:{address}"
    key = candidate.get("asset_key")
    if key and ":" in str(key):
        return str(key)
    venue, contract = candidate.get("venue"), candidate.get("contract_symbol")
    if venue and contract:
        return f"perp:{venue}:{str(contract).upper()}"
    return "unknown"


def _direction(candidate: Mapping[str, Any]) -> str | None:
    setup = candidate.get("setup_validation")
    if isinstance(setup, Mapping) and setup.get("direction") in {"long", "short"}:
        return str(setup["direction"])
    return None


def cot_regime_passes(regime: str, direction: str | None) -> bool:
    normalized = regime.strip().lower()
    if normalized not in {"bullish", "bearish", "neutral"} or direction not in {"long", "short"}:
        return False
    if normalized == "bullish":
        return direction == "long"
    if normalized == "bearish":
        return direction == "short"
    return True


def build_funnel(
    payload: Mapping[str, Any],
    *,
    macro_context: Mapping[str, Any] | None = None,
    cot_regime: str = "unknown",
    cot_context: Mapping[str, Any] | None = None,
    context_decision_time: datetime | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[Evidence]]:
    counts = {
        "universe": 0,
        "eligible": 0,
        "liquid": 0,
        "momentum_pass": 0,
        "derivatives_pass": 0,
        "macro_pass": 0,
        "cot_pass": 0,
        "final_candidates": 0,
        "invalid_observations": 0,
        "unavailable_instruments": 0,
        "incomplete_evaluations": 0,
    }
    final_candidates: list[dict[str, Any]] = []
    evidence: list[Evidence] = []
    unique_members: set[str] = set()
    macro_checks: list[bool] = []
    effective_cot = str((cot_context or {}).get("regime") if cot_context is not None else cot_regime).lower()
    if effective_cot not in {"bullish", "bearish", "neutral"}:
        effective_cot = "unknown"
    if cot_context is not None and cot_context.get("status") not in {"OK", "OVERRIDE"}:
        effective_cot = "unknown"
    for observation in payload.get("observations") or []:
        if not isinstance(observation, Mapping):
            continue
        observation_time = parse_datetime(observation.get("observation_timestamp"))
        if observation_time is None:
            counts["invalid_observations"] += 1
            continue
        source_time = parse_datetime(observation.get("source_timestamp"))
        if (not observation.get("source") or PointInTime(observation_time, source_time, observation_time).availability is not Availability.ELIGIBLE):
            counts["invalid_observations"] += 1
            continue
        macro_checks.append(macro_is_usable(macro_context, context_decision_time or observation_time))
        members = observation.get("universe_members_deduplicated") or observation.get("universe_members") or []
        for member in members:
            if isinstance(member, Mapping):
                member_key = _asset_key(member)
            else:
                member_key = str(member).strip().lower()
            if member_key and member_key != "unknown":
                unique_members.add(member_key)
        counts["universe"] = len(unique_members)
        evidence.append(
            Evidence(
                source=str(observation.get("source") or "crypto.universe"),
                reference=f"crypto-universe-{observation_time.isoformat()}",
                claim=f"The point-in-time universe contained {len(members)} deduplicated members",
                kind=EvidenceKind.FACT,
                event_time=observation_time,
                available_at=parse_datetime(observation.get("source_timestamp")),
                retrieved_at=observation_time,
                decision_time=observation_time,
                provenance=Provenance.PROVIDER_RESULT,
            )
        )
        for raw_candidate in observation.get("candidates") or []:
            if not isinstance(raw_candidate, Mapping):
                continue
            state = raw_candidate.get("ranking_state")
            liquidity = raw_candidate.get("liquidity") if isinstance(raw_candidate.get("liquidity"), Mapping) else {}
            eligible = state == "ELIGIBLE"
            liquid = liquidity.get("state") == "PASS"
            setup = raw_candidate.get("setup_validation")
            setup_valid = bool(isinstance(setup, Mapping) and setup.get("valid") is True)
            direction = _direction(raw_candidate)
            macro_pass = macro_checks[-1]
            if macro_pass and (macro_context or {}).get("contract") == "current_macro_v1":
                macro_pass = cot_regime_passes(str(macro_context.get("regime")), direction)
            features = raw_candidate.get("features") if isinstance(raw_candidate.get("features"), Mapping) else {}
            if eligible and (liquidity.get("state") == "UNKNOWN" or
                             liquid and isinstance(setup, Mapping) and setup.get("reason") in {
                                 "insufficient_4h_history", "candle_provider_unavailable", "not_evaluated"}):
                counts["incomplete_evaluations"] += 1
            if state == "UNKNOWN" and not features:
                counts["unavailable_instruments"] += 1
                continue
            available = parse_datetime(features.get("data_timestamp"))
            if _asset_key(raw_candidate) == "unknown" or not features.get("data_source") or available is None or available > observation_time:
                counts["invalid_observations"] += 1
                continue
            cot_pass = True if effective_cot == "unknown" else cot_regime_passes(effective_cot, direction)
            if eligible:
                counts["eligible"] += 1
            if eligible and liquid:
                counts["liquid"] += 1
            if eligible and liquid and setup_valid:
                counts["momentum_pass"] += 1
                counts["derivatives_pass"] += 1
            if eligible and liquid and setup_valid and macro_pass:
                counts["macro_pass"] += 1
            if eligible and liquid and setup_valid and macro_pass and cot_pass:
                counts["cot_pass"] += 1
            if not (eligible and liquid and setup_valid and macro_pass and cot_pass):
                continue
            candidate = {
                "asset": raw_candidate.get("symbol"),
                "asset_key": _asset_key(raw_candidate),
                "direction": direction,
                "entry_research_zone": setup.get("entry_zone") if isinstance(setup, Mapping) else None,
                "invalidation": setup.get("invalidation") if isinstance(setup, Mapping) else None,
                "rank_score": raw_candidate.get("rank_score"),
                "observation_timestamp": observation_time.isoformat(),
            }
            final_candidates.append(candidate)
            evidence.append(
                Evidence(
                    source=str(features.get("data_source") or "crypto.futures"),
                    reference=f"crypto-{_asset_key(raw_candidate)}-{observation_time.isoformat()}",
                    claim="Momentum, market structure, and derivatives filters were evaluated",
                    kind=EvidenceKind.INFERENCE,
                    event_time=observation_time,
                    available_at=available,
                    retrieved_at=observation_time,
                    decision_time=observation_time,
                    provenance=Provenance.PROVIDER_RESULT,
                    metadata={"asset": _asset_key(raw_candidate)},
                )
            )
    counts["final_candidates"] = len(final_candidates)
    funnel = {
        **counts,
        "cot_regime": effective_cot,
        "cot_scope": "market/regime context; no per-altcoin COT signal",
        "macro_context_validated": bool(macro_checks) and all(macro_checks),
        "universe_policy": "top_100_market_cap_plus_liquid_perps",
        "universe_size_target": UNIVERSE_SIZE,
    }
    return funnel, final_candidates, evidence


def analyze_missed_moves(
    scan_payload: Mapping[str, Any],
    outcomes: list[Mapping[str, Any]],
    *,
    move_threshold: float = 0.20,
) -> list[dict[str, Any]]:
    selected = {
        _asset_key(candidate)
        for candidate in (scan_payload.get("final_candidates") or [])
        if isinstance(candidate, Mapping)
    }
    candidate_by_key: dict[str, Mapping[str, Any]] = {}
    for observation in scan_payload.get("observations") or []:
        if not isinstance(observation, Mapping):
            continue
        for candidate in observation.get("candidates") or []:
            if isinstance(candidate, Mapping):
                candidate_by_key[_asset_key(candidate)] = candidate
    missed: list[dict[str, Any]] = []
    for outcome in outcomes:
        if not isinstance(outcome, Mapping):
            continue
        try:
            move = float(outcome.get("forward_return"))
        except (TypeError, ValueError):
            continue
        key = _asset_key(outcome)
        if not math.isfinite(move) or move < move_threshold or key in selected:
            continue
        candidate = candidate_by_key.get(key) if key != "unknown" else None
        decision_time = parse_datetime((candidate or {}).get("observation_timestamp") or outcome.get("decision_time"))
        available_at = parse_datetime(outcome.get("information_available_at"))
        if available_at is None or decision_time is None or key == "unknown":
            information_state = "UNKNOWN"
        else:
            information_state = "BEFORE_MOVE" if available_at <= decision_time else "AFTER_DECISION"
        missed.append(
            {
                "asset": outcome.get("asset") or outcome.get("symbol"),
                "asset_key": key,
                "later_move": move,
                "information_existed_before_move": information_state,
                "hindsight_data_used_as_signal": False,
            }
        )
    return missed


def _ids_by_symbol(rows: Sequence[Mapping[str, Any]]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for row in rows:
        symbol = str(row.get("symbol") or "").upper()
        canonical = row.get("canonical_asset_id")
        if symbol and canonical:
            grouped.setdefault(symbol, []).append(str(canonical))
    return grouped


def _contract_for_row(
    row: Mapping[str, Any],
    contracts: Sequence[Mapping[str, Any]],
    ids_by_symbol: Mapping[str, list[str]],
) -> Mapping[str, Any] | None:
    if not contracts:
        return None
    row_id = str(row.get("canonical_asset_id") or "").lower()
    explicit = [
        contract
        for contract in contracts
        if contract.get("canonical_asset_id")
        and str(contract["canonical_asset_id"]).lower() == row_id
    ]
    if len(explicit) == 1:
        return explicit[0]
    symbol = str(row.get("symbol") or "").upper()
    if len(contracts) == 1 and len(ids_by_symbol.get(symbol, [])) == 1:
        return contracts[0]
    return None


def assess_live_liquidity(perp: Mapping[str, Any] | None) -> dict[str, Any]:
    if perp is None:
        return {
            "state": "REJECT",
            "quote_volume_24h": None,
            "open_interest": None,
            "spread_bps": None,
            "slippage_bps": None,
            "reasons": ["no_perpetual_contract_metadata"],
        }
    volume = perp.get("day_notional_volume")
    open_interest = perp.get("open_interest_usd")
    spread = perp.get("spread_bps")
    slippage = perp.get("slippage_bps")
    missing = [
        name
        for name, value in (
            ("quote_volume_24h", volume),
            ("open_interest", open_interest),
            ("spread_bps", spread),
            ("slippage_bps", slippage),
        )
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value)
    ]
    if missing:
        return {
            "state": "UNKNOWN",
            "quote_volume_24h": volume if "quote_volume_24h" not in missing else None,
            "open_interest": open_interest if "open_interest" not in missing else None,
            "spread_bps": spread if "spread_bps" not in missing else None,
            "slippage_bps": slippage if "slippage_bps" not in missing else None,
            "reasons": missing,
        }
    rejected: list[str] = []
    if float(volume) < MIN_QUOTE_VOLUME_24H:
        rejected.append("quote_volume_below_minimum")
    if float(open_interest) < MIN_OPEN_INTEREST_USD:
        rejected.append("open_interest_below_minimum")
    if float(spread) > MAX_SPREAD_BPS:
        rejected.append("spread_above_maximum")
    if float(slippage) > MAX_SLIPPAGE_BPS:
        rejected.append("slippage_above_maximum")
    return {
        "state": "REJECT" if rejected else "PASS",
        "quote_volume_24h": float(volume),
        "open_interest": float(open_interest),
        "spread_bps": float(spread),
        "slippage_bps": float(slippage),
        "reasons": rejected,
    }


def _ohlc(bars: Sequence[Mapping[str, Any]]) -> list[dict[str, float]]:
    parsed: list[dict[str, float]] = []
    for bar in bars:
        try:
            high = float(bar["high"])
            low = float(bar["low"])
            close = float(bar["close"])
        except (KeyError, TypeError, ValueError):
            continue
        if not all(math.isfinite(v) for v in (high, low, close)) or high <= 0 or low <= 0 or close <= 0 or high < low:
            continue
        parsed.append({"high": high, "low": low, "close": close})
    return parsed


def structure_state(bars: Sequence[Mapping[str, float]]) -> str:
    window = list(bars)[-STRUCTURE_BARS:]
    if len(window) < STRUCTURE_BARS:
        return "INSUFFICIENT_DATA"
    highs = [row["high"] for row in window]
    lows = [row["low"] for row in window]
    higher = all(highs[index] > highs[index - 1] for index in range(1, len(highs))) and all(
        lows[index] > lows[index - 1] for index in range(1, len(lows))
    )
    lower = all(highs[index] < highs[index - 1] for index in range(1, len(highs))) and all(
        lows[index] < lows[index - 1] for index in range(1, len(lows))
    )
    if higher:
        return "HIGHER_HIGH_HIGHER_LOW"
    if lower:
        return "LOWER_HIGH_LOWER_LOW"
    return "MIXED"


def setup_from_candles(bars: Sequence[Mapping[str, Any]] | None) -> dict[str, Any]:
    """Conservative 4h structure setup. Missing bars stay invalid; nothing is imputed."""
    parsed = _ohlc(bars or ())
    if len(parsed) < MIN_SETUP_BARS:
        return {
            "valid": False,
            "reason": "insufficient_4h_history",
            "bars": len(parsed),
        }
    structure = structure_state(parsed)
    prior = parsed[-(STRUCTURE_BARS + 1) : -1]
    if len(prior) < STRUCTURE_BARS:
        return {
            "valid": False,
            "reason": "insufficient_4h_history",
            "bars": len(parsed),
        }
    close = parsed[-1]["close"]
    swing_high = max(row["high"] for row in prior)
    swing_low = min(row["low"] for row in prior)
    if structure == "HIGHER_HIGH_HIGHER_LOW":
        if close > swing_high * (1 + NO_CHASE_PCT):
            return {
                "valid": False,
                "reason": "extended_beyond_retest_band",
                "direction": "long",
                "structure": structure,
            }
        return {
            "valid": True,
            "direction": "long",
            "structure": structure,
            "entry_zone": [swing_low, (swing_low + swing_high) / 2],
            "invalidation": swing_low,
            "reason": None,
        }
    if structure == "LOWER_HIGH_LOWER_LOW":
        if close < swing_low * (1 - NO_CHASE_PCT):
            return {
                "valid": False,
                "reason": "extended_beyond_retest_band",
                "direction": "short",
                "structure": structure,
            }
        return {
            "valid": True,
            "direction": "short",
            "structure": structure,
            "entry_zone": [(swing_low + swing_high) / 2, swing_high],
            "invalidation": swing_high,
            "reason": None,
        }
    return {"valid": False, "reason": "mixed_or_insufficient_structure", "structure": structure}


def apply_setup_candles(
    observation: dict[str, Any],
    candles_by_coin: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    from rocket.providers.hyperliquid import MAX_SETUP_MARKETS

    ranked: list[dict[str, Any]] = []
    for candidate in observation.get("candidates") or []:
        if not isinstance(candidate, dict):
            continue
        liquid = (
            isinstance(candidate.get("liquidity"), Mapping)
            and candidate["liquidity"].get("state") == "PASS"
        )
        if candidate.get("ranking_state") == "ELIGIBLE" and liquid and candidate.get("contract_symbol"):
            ranked.append(candidate)
    ranked.sort(key=lambda row: (row.get("universe_rank") is None, row.get("universe_rank") or 10**9))
    allowed = {str(row.get("contract_symbol")).upper() for row in ranked[:MAX_SETUP_MARKETS]}
    for candidate in observation.get("candidates") or []:
        if not isinstance(candidate, dict):
            continue
        coin = str(candidate.get("contract_symbol") or "").upper()
        if coin not in allowed:
            continue
        setup = setup_from_candles(candles_by_coin.get(coin))
        if coin not in candles_by_coin:
            setup["reason"] = "candle_provider_unavailable"
        candidate["setup_validation"] = setup
        features = dict(candidate.get("features") or {})
        last = None
        series = candles_by_coin.get(coin) or ()
        if series:
            last = series[-1].get("timestamp") if isinstance(series[-1], Mapping) else None
        if last:
            features["data_timestamp"] = last
            features["data_source"] = "hyperliquid"
        features["structure_4h"] = setup.get("structure")
        candidate["features"] = features
    return observation


def _candidate_row(
    *,
    symbol: str,
    canonical_asset_id: Any,
    venue: str | None,
    contract: Mapping[str, Any] | None,
    ranking_state: str,
    universe_source: str,
    rank: Any,
    stamp: str,
) -> dict[str, Any]:
    features: dict[str, Any] = {
        "data_timestamp": stamp,
        "data_source": "hyperliquid" if contract else "coingecko",
    }
    if contract is not None:
        features.update(
            {
                "mark_px": contract.get("mark_px"),
                "funding": contract.get("funding"),
                "quote_volume_24h": contract.get("day_notional_volume"),
                "open_interest_usd": contract.get("open_interest_usd"),
            }
        )
    return {
        "symbol": symbol,
        "canonical_asset_id": canonical_asset_id,
        "venue": venue,
        "contract_symbol": contract.get("name") if contract is not None else None,
        "ranking_state": ranking_state,
        "rank_score": None,
        "universe_rank": rank,
        "universe_source": universe_source,
        "features": features,
        "liquidity": assess_live_liquidity(contract),
        "setup_validation": {
            "valid": False,
            "reason": "not_evaluated",
        },
        "observation_timestamp": stamp,
    }


def build_live_observation(
    market_cap: Sequence[Mapping[str, Any]],
    perps: Sequence[Mapping[str, Any]],
    *,
    now: datetime,
) -> dict[str, Any]:
    """Join current top-100 market-cap rows to Hyperliquid perps without ticker-only identity."""
    contracts_by_symbol: dict[str, list[Mapping[str, Any]]] = {}
    for perp in perps:
        if isinstance(perp, Mapping) and perp.get("name"):
            contracts_by_symbol.setdefault(str(perp["name"]).upper(), []).append(perp)
    ids_by_symbol = _ids_by_symbol(market_cap)
    members: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    known_ids: set[str] = set()
    stamp = now.isoformat()
    joined = 0
    for row in market_cap:
        if not isinstance(row, Mapping):
            continue
        symbol = str(row.get("symbol") or "").upper()
        canonical = row.get("canonical_asset_id")
        contract = _contract_for_row(row, contracts_by_symbol.get(symbol, ()), ids_by_symbol)
        if contract is not None:
            joined += 1
        rank = row.get("rank")
        member = {
            "symbol": symbol,
            "canonical_asset_id": canonical,
            "venue": "hyperliquid" if contract is not None else None,
            "contract_symbol": str(contract["name"]) if contract is not None else None,
            "quote_currency": str(contract.get("quote_currency") or "USDC") if contract is not None else "USD",
            "universe_source": row.get("universe_source") or "current_top_market_cap",
            "rank": rank,
            "exchange_contract_type": "perpetual",
        }
        members.append(member)
        if canonical:
            known_ids.add(str(canonical).lower())
        ranking = "ELIGIBLE" if canonical and contract is not None else "UNKNOWN"
        candidates.append(
            _candidate_row(
                symbol=symbol,
                canonical_asset_id=canonical,
                venue=member["venue"],
                contract=contract,
                ranking_state=ranking,
                universe_source=str(member["universe_source"]),
                rank=rank,
                stamp=stamp,
            )
        )
    unresolved = 0
    for symbol, contracts in sorted(contracts_by_symbol.items()):
        for contract in contracts:
            mapped = ids_by_symbol.get(symbol, [])
            canonical = mapped[0] if len(mapped) == 1 else None
            if canonical and canonical.lower() in known_ids:
                continue
            unresolved += 1
            members.append(
                {
                    "symbol": symbol,
                    "canonical_asset_id": canonical,
                    "venue": "hyperliquid",
                    "contract_symbol": str(contract["name"]),
                    "quote_currency": str(contract.get("quote_currency") or "USDC"),
                    "universe_source": "liquid_perpetual",
                    "rank": None,
                    "data_completeness": "complete" if canonical else "incomplete",
                    "missingness_reason": None if canonical else "canonical_asset_id_unresolved",
                    "exchange_contract_type": "perpetual",
                }
            )
            if not canonical:
                continue
            candidates.append(
                _candidate_row(
                    symbol=symbol,
                    canonical_asset_id=canonical,
                    venue="hyperliquid",
                    contract=contract,
                    ranking_state="BELOW_RANK_THRESHOLD",
                    universe_source="liquid_perpetual",
                    rank=None,
                    stamp=stamp,
                )
            )
    return {
        "observation_timestamp": stamp,
        "source": "live:CoinGecko+Hyperliquid",
        "source_timestamp": stamp,
        "universe_members_deduplicated": members,
        "candidates": candidates,
        "join": {
            "market_cap_source": "coingecko",
            "perpetual_source": "hyperliquid",
            "joined_count": joined,
            "unresolved_perp_count": unresolved,
            "spread_source": "hyperliquid impactPxs; half-spread slippage, depth not imputed",
        },
    }


class CryptoWorkflow:
    name = WORKFLOW_SCAN

    def __init__(self, *, store: ResearchStore | None = None):
        self.store = store

    def scan_payload(
        self,
        replay_payload: Mapping[str, Any],
        *,
        macro_context: Mapping[str, Any] | None = None,
        cot_regime: str = "unknown",
        cot_context: Mapping[str, Any] | None = None,
        cava_context: Mapping[str, Any] | None = None,
        mode: Mode = Mode.REPLAY,
        now: datetime | None = None,
    ) -> ResearchResult:
        observations = replay_payload.get("observations") or []
        times = [parse_datetime(row.get("observation_timestamp")) for row in observations if isinstance(row, Mapping)]
        known = [stamp for stamp in times if stamp is not None]
        if mode is Mode.REPLAY:
            if not known:
                raise ValueError("REPLAY requires a historical observation timestamp")
            now = max(known)
        elif now is None:
            now = max(known) if known else datetime.now(UTC)
        funnel, candidates, evidence = build_funnel(
            replay_payload,
            macro_context=macro_context,
            cot_regime=cot_regime,
            cot_context=cot_context,
            context_decision_time=now if mode is Mode.LIVE else None,
        )
        evidence = [replace(item, decision_time=now) for item in evidence]
        cava_status = "unavailable"
        if cava_context:
            cava_status = "available" if cava_context.get("validated") is True else "insufficient"
        funnel["cava_context_status"] = cava_status
        warnings = []
        if not funnel["macro_context_validated"]:
            warnings.append("core macro evidence unavailable")
        if funnel["cot_regime"] not in {"bullish", "bearish", "neutral"}:
            warnings.append("COT regime unavailable; COT is not applied as an asset-level signal")
        extra_warnings = replay_payload.get("warnings") or ()
        warnings.extend(str(item) for item in extra_warnings if item)
        if candidates:
            research = ResearchStatus.SETUP_FOUND
        elif (funnel.get("invalid_observations") or funnel.get("incomplete_evaluations")
              or funnel.get("unavailable_instruments")
              or funnel["momentum_pass"] and not funnel["macro_context_validated"]):
            research = ResearchStatus.INSUFFICIENT_EVIDENCE
        else:
            research = ResearchStatus.NO_SETUP
        operational = OperationalStatus.HEALTHY
        raw_providers = replay_payload.get("providers")
        if raw_providers:
            provider_health = tuple(
                item if isinstance(item, ProviderHealth) else ProviderHealth.from_dict(item)
                for item in raw_providers
            )
        else:
            provider_health = (ProviderHealth(name="crypto.universe", status=operational, retrieved_at=now),)
        statuses = {item.status for item in provider_health}
        if replay_payload.get("provider_status") == "UNAVAILABLE" or (
            statuses and statuses <= {OperationalStatus.UNAVAILABLE, OperationalStatus.ERROR}
        ):
            operational = OperationalStatus.UNAVAILABLE
            research = ResearchStatus.INSUFFICIENT_EVIDENCE
        elif statuses - {OperationalStatus.HEALTHY}:
            operational = OperationalStatus.PARTIAL
        required_failures = [p.name for p in provider_health
                             if p.status in {OperationalStatus.UNAVAILABLE, OperationalStatus.ERROR}
                             and (p.name in {"coingecko", "hyperliquid"} or p.name.startswith("hyperliquid.candles:"))]
        if required_failures and not candidates:
            research = ResearchStatus.INSUFFICIENT_EVIDENCE
        gaps = list(required_failures)
        if funnel["momentum_pass"] and not funnel["macro_context_validated"]:
            gaps.append("current macro context for otherwise eligible setup")
        for field in ("invalid_observations", "incomplete_evaluations", "unavailable_instruments"):
            if funnel.get(field):
                gaps.append(f"{field}:{funnel[field]}")
        if operational is OperationalStatus.UNAVAILABLE and not gaps:
            gaps.append("current universe provider")
        if funnel.get("incomplete_evaluations") and mode is Mode.LIVE and operational is OperationalStatus.HEALTHY:
            operational = OperationalStatus.PARTIAL
        result = ResearchResult(
            workflow=WORKFLOW_SCAN,
            status=research,
            reasons=(ResearchReason(ReasonCode.REQUIRED_PROVIDER_UNAVAILABLE
                                    if required_failures or operational is OperationalStatus.UNAVAILABLE
                                    else ReasonCode.REQUIRED_EVIDENCE_MISSING,
                                    tuple(gaps), mode is Mode.LIVE),)
            if research is ResearchStatus.INSUFFICIENT_EVIDENCE else (),
            operational=OperationalReport(
                status=operational,
                providers=provider_health,
            ),
            decision_time=now,
            started_at=now,
            completed_at=now,
            mode=mode,
            payload={
                "mode": mode.value,
                "funnel": funnel,
                "macro_context": dict(macro_context or {}),
                "cot_context": dict(cot_context or {}),
                "cava_context_status": cava_status,
                "final_candidates": candidates,
                "observations": list(observations),
                "execution_enabled": False,
                "loaded_live_context": False,
            },
            evidence=tuple(evidence),
            warnings=tuple(warnings),
        )
        if self.store:
            self.store.save_result(result)
        return result

    def scan_from_fixture(self, path: Path, *, cot_regime: str = "unknown") -> ResearchResult:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return self.scan_payload(payload, cot_regime=cot_regime, mode=Mode.REPLAY)

    def scan_live(
        self,
        *,
        now: datetime | None = None,
        macro_context: Mapping[str, Any] | None = None,
        universe=None,
        perps=None,
        candles: Mapping[str, Sequence[Mapping[str, Any]]] | None = None,
        cot_regime: str = "unknown",
        cot_context: Mapping[str, Any] | None = None,
    ) -> ResearchResult:
        from rocket.providers.cftc import fetch_cot_context
        from rocket.providers.coingecko import fetch_top_universe
        from rocket.providers.hyperliquid import fetch_perp_markets, fetch_setup_candles
        from rocket.workflows.macro import MacroWorkflow

        observed = now or datetime.now(UTC)
        discovery = universe or fetch_top_universe()
        if discovery.status is not OperationalStatus.HEALTHY:
            result = ResearchResult(
                workflow=WORKFLOW_SCAN,
                status=ResearchStatus.INSUFFICIENT_EVIDENCE,
                reasons=(ResearchReason(ReasonCode.REQUIRED_PROVIDER_UNAVAILABLE, ("current top-100 universe",), True),),
                operational=OperationalReport(
                    status=OperationalStatus.UNAVAILABLE,
                    providers=(
                        ProviderHealth(
                            name="coingecko",
                            status=OperationalStatus.UNAVAILABLE,
                            failure_kind=discovery.failure_kind,
                            retrieved_at=observed,
                        ),
                    ),
                ),
                decision_time=observed,
                started_at=observed,
                completed_at=observed,
                mode=Mode.LIVE,
                payload={
                    "mode": "LIVE",
                    "funnel": {"universe": 0, "final_candidates": 0, "universe_size_target": UNIVERSE_SIZE},
                    "final_candidates": [],
                    "execution_enabled": False,
                },
                warnings=("live current-universe discovery is unavailable",),
            )
            if self.store:
                self.store.save_result(result)
            return result
        perps_result = perps or fetch_perp_markets(now=observed)
        macro_result = None
        if macro_context is None:
            macro_result = MacroWorkflow(store=self.store).run(now=now)
            macro_context = macro_result.payload
        if cot_context is None and cot_regime in {"bullish", "bearish", "neutral"}:
            cot_context = {
                "status": "OVERRIDE",
                "regime": cot_regime,
                "scope": "market/regime context; no per-altcoin COT signal",
                "override": True,
            }
        elif cot_context is None:
            cot_context = fetch_cot_context(now=observed)
        cava = self.store.load_context("cava") if self.store else None
        perp_records = perps_result.records if perps_result.status is OperationalStatus.HEALTHY else ()
        observation = build_live_observation(discovery.records, perp_records, now=observed)
        if candles is None:
            coins = [
                str(row.get("contract_symbol"))
                for row in observation.get("candidates") or []
                if isinstance(row, Mapping)
                and row.get("ranking_state") == "ELIGIBLE"
                and isinstance(row.get("liquidity"), Mapping)
                and row["liquidity"].get("state") == "PASS"
                and row.get("contract_symbol")
            ]
            candles = fetch_setup_candles(coins, now=observed)
        observed = now or datetime.now(UTC)
        observation["observation_timestamp"] = observed.isoformat()
        apply_setup_candles(observation, candles)
        live_warnings: list[str] = []
        if perps_result.status is not OperationalStatus.HEALTHY:
            live_warnings.append("hyperliquid perpetual metadata unavailable")
        live_warnings.extend(str(item) for item in (cot_context or {}).get("warnings") or () if item)
        providers = [
            {
                "name": "coingecko",
                "status": discovery.status.value,
                "retrieved_at": observed.isoformat(),
                "failure_kind": discovery.failure_kind,
            },
            {
                "name": "hyperliquid",
                "status": perps_result.status.value,
                "retrieved_at": (perps_result.retrieved_at or observed).isoformat(),
                "failure_kind": perps_result.failure_kind,
            },
        ]
        if cot_context and cot_context.get("status") != "OVERRIDE":
            cot_status = {
                "OK": OperationalStatus.HEALTHY.value,
                "PARTIAL": OperationalStatus.PARTIAL.value,
                "STALE": OperationalStatus.PARTIAL.value,
            }.get(str(cot_context.get("status")), OperationalStatus.UNAVAILABLE.value)
            providers.extend(cot_context.get("provider_attempts") or [
                {
                    "name": "cftc",
                    "status": cot_status,
                    "retrieved_at": observed.isoformat(),
                    "failure_kind": cot_context.get("failure_kind"),
                }
            ])
        requested = [row for row in observation["candidates"] if row["ranking_state"] == "ELIGIBLE"
                     and row["liquidity"]["state"] == "PASS"]
        for row in requested:
            coin = str(row["contract_symbol"])
            providers.append({"name": f"hyperliquid.candles:{coin}",
                              "status": "HEALTHY" if coin in candles else "UNAVAILABLE",
                              "failure_kind": None if coin in candles else "CandleAcquisitionFailed",
                              "coverage": str(len(candles.get(coin, ())))})
        if macro_result is not None:
            providers.extend(item.to_dict() for item in macro_result.operational.providers)
        else:
            if macro_is_usable(macro_context, observed):
                macro_status = OperationalStatus.HEALTHY
            elif (macro_context or {}).get("status") == "UNAVAILABLE":
                macro_status = OperationalStatus.UNAVAILABLE
            else:
                macro_status = OperationalStatus.PARTIAL
            providers.append(
                {
                    "name": "macro",
                    "status": macro_status.value,
                    "retrieved_at": observed.isoformat(),
                }
            )
        return self.scan_payload(
            {
                "observations": [observation],
                "window": {"mode": "LIVE"},
                "warnings": live_warnings,
                "providers": providers,
            },
            macro_context=macro_context,
            cot_regime=cot_regime,
            cot_context=cot_context,
            cava_context=cava,
            mode=Mode.LIVE,
            now=observed,
        )

    def evaluate(self, scan_result: ResearchResult, outcomes: list[Mapping[str, Any]]) -> ResearchResult:
        selected = scan_result.payload.get("final_candidates") or []
        evaluated = []
        for outcome in outcomes:
            if not isinstance(outcome, Mapping):
                continue
            key = _asset_key(outcome)
            if key == "unknown" or key not in {_asset_key(item) for item in selected if isinstance(item, Mapping)}:
                continue
            try:
                forward = float(outcome["forward_return"])
            except (KeyError, TypeError, ValueError):
                continue
            if not math.isfinite(forward):
                continue
            evaluated.append({**dict(outcome), "asset_key": key, "hit": forward >= 0})
        now = datetime.now(UTC)
        result = ResearchResult(
            workflow=WORKFLOW_EVAL,
            status=ResearchStatus.INSUFFICIENT_EVIDENCE,
            reasons=(ResearchReason(ReasonCode.STRATEGY_UNVALIDATED, ("costed out-of-sample strategy validation and human review",)),),
            operational=OperationalReport(status=OperationalStatus.HEALTHY),
            decision_time=now,
            started_at=now,
            completed_at=now,
            payload={
                "strategy_state": "EXPERIMENTAL",
                "metrics": {
                    "evaluated_count": len(evaluated),
                    "hit_rate": (sum(item["hit"] for item in evaluated) / len(evaluated)) if evaluated else None,
                },
                "outcomes": evaluated,
                "source_scan_run_id": scan_result.run_id,
                "execution_enabled": False,
            },
            warnings=("evaluation is research evidence; Rocket never writes VALIDATED",),
        )
        if self.store:
            self.store.save_result(result)
        return result

    def missed(self, scan_result: ResearchResult, outcomes: list[Mapping[str, Any]]) -> ResearchResult:
        missed = analyze_missed_moves(scan_result.payload, outcomes)
        now = datetime.now(UTC)
        result = ResearchResult(
            workflow=WORKFLOW_MISSED,
            status=ResearchStatus.NO_SETUP if not missed else ResearchStatus.ACTION_REQUIRED,
            operational=OperationalReport(status=OperationalStatus.HEALTHY),
            decision_time=now,
            started_at=now,
            completed_at=now,
            payload={"missed_moves": missed, "hindsight_data_used_as_signal": False, "execution_enabled": False},
            warnings=("Missed moves require human review for systematic blind spots.",),
        )
        if self.store:
            self.store.save_result(result)
        return result
