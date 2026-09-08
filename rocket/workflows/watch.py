"""Deterministic price conditions only. No model. No A1/A2/A4 mix-in."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
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
from rocket.providers.quotes import acquire_quotes
from rocket.store import ResearchStore

WORKFLOW = "watch.check"
CONDITIONS = {"ABOVE", "BELOW", "CROSS_ABOVE", "CROSS_BELOW", "ZONE"}


def positive_number(value: Any) -> bool:
    try:
        return not isinstance(value, bool) and math.isfinite(float(value)) and float(value) > 0
    except (TypeError, ValueError, OverflowError):
        return False


def load_watches(path: Path) -> list[dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    rows = raw.get("watches", raw) if isinstance(raw, dict) else raw
    if not isinstance(rows, list):
        raise ValueError("watch file must contain a list or watches array")
    return [dict(item) if isinstance(item, dict) else {} for item in rows]


def check_watch(
    watches: Sequence[Mapping[str, Any]],
    prices: Mapping[str, float],
    *,
    previous_prices: Mapping[str, float] | None = None,
    quote_evidence: Mapping[str, Mapping[str, Any]] | None = None,
    now: datetime | None = None,
) -> ResearchResult:
    events: list[dict[str, Any]] = []
    evaluations: list[dict[str, Any]] = []
    unavailable: list[str] = []
    invalid: list[str] = []
    missing_previous: list[str] = []
    evaluated_count = 0
    valid_watch_count = 0
    previous_prices = dict(previous_prices or {})
    decision_time = now or datetime.now(UTC)
    checked: dict[str, float | None] = {}
    for watch in watches:
        ticker = str(watch.get("ticker") or "").strip().upper()
        if not ticker:
            invalid.append("UNKNOWN")
            continue
        condition_raw = watch.get("condition")
        if not condition_raw:
            invalid.append(ticker)
            continue
        condition = str(condition_raw).upper()
        if condition not in CONDITIONS:
            invalid.append(ticker)
            continue
        try:
            threshold = watch.get("threshold")
            lower = upper = None
            zone = watch.get("zone")
            if isinstance(zone, (list, tuple)) and len(zone) == 2:
                lower, upper = float(zone[0]), float(zone[1])
            if condition in {"ABOVE", "BELOW", "CROSS_ABOVE", "CROSS_BELOW"} and threshold is None:
                invalid.append(ticker)
                continue
            if condition == "ZONE" and not (lower is not None and upper is not None):
                invalid.append(ticker)
                continue
            bounds = [value for value in (threshold, lower, upper) if value is not None]
            if any(not positive_number(value) for value in bounds) or (
                lower is not None and upper is not None and lower > upper
            ):
                invalid.append(ticker)
                continue
            valid_watch_count += 1
            price = prices.get(ticker)
            price_ok = positive_number(price)
            if quote_evidence is not None:
                from rocket.clock import equity_observation_fresh
                from rocket.pit import Availability, PointInTime, parse_datetime

                quote = quote_evidence.get(ticker, {})
                try:
                    pit = PointInTime(parse_datetime(quote.get("observation_at")),
                                      parse_datetime(quote.get("available_at")), decision_time)
                    price_ok = price_ok and quote.get("status") == "OK" and bool(quote.get("source")) and (
                        pit.availability is Availability.ELIGIBLE
                        and equity_observation_fresh(quote.get("observation_at"), decision_time, daily=False)
                    )
                except (ValueError, TypeError):
                    price_ok = False
            if not price_ok:
                checked[ticker] = None
                unavailable.append(ticker)
                evaluations.append(
                    {
                        "ticker": ticker,
                        "condition": condition,
                        "status": "UNAVAILABLE",
                        "triggered": None,
                    }
                )
                continue
            current = float(price)
            checked[ticker] = current
            if condition in {"CROSS_ABOVE", "CROSS_BELOW"} and not positive_number(previous_prices.get(ticker)):
                missing_previous.append(ticker)
                evaluations.append({"ticker": ticker, "condition": condition, "price": current,
                                    "status": "WARMUP", "triggered": False})
                continue
            if condition == "ABOVE":
                reached = current >= float(threshold)
            elif condition == "BELOW":
                reached = current <= float(threshold)
            elif condition == "CROSS_ABOVE":
                previous = previous_prices.get(ticker)
                reached = previous is not None and float(previous) < float(threshold) <= current
            elif condition == "CROSS_BELOW":
                previous = previous_prices.get(ticker)
                reached = previous is not None and current <= float(threshold) < float(previous)
            else:
                reached = lower is not None and upper is not None and lower <= current <= upper
            evaluated_count += 1
            evaluations.append(
                {
                    "ticker": ticker,
                    "condition": condition,
                    "price": current,
                    "status": "EVALUATED",
                    "condition_met": bool(reached),
                }
            )
            previous = previous_prices.get(ticker)
            if reached and positive_number(previous) and condition in {"ZONE", "ABOVE", "BELOW"}:
                prior = float(previous)
                previously_reached = (
                    prior <= float(threshold)
                    if condition == "BELOW"
                    else prior >= float(threshold)
                    if condition == "ABOVE"
                    else lower <= prior <= upper
                )
                reached = not previously_reached
        except (TypeError, ValueError):
            invalid.append(ticker)
            continue
        if reached:
            events.append(
                {
                    "ticker": ticker,
                    "price": current,
                    "condition": condition,
                    "threshold": float(threshold) if threshold is not None else None,
                    "event": "ZONE_REACHED" if condition == "ZONE" else condition,
                    "thesis": watch.get("thesis"),
                    "source_reference": watch.get("source_reference"),
                }
            )
    reasons = []
    if invalid:
        reasons.append(ResearchReason(ReasonCode.INVALID_INPUT, tuple(sorted(set(invalid)))))
    if unavailable:
        reasons.append(ResearchReason(ReasonCode.REQUIRED_PROVIDER_UNAVAILABLE,
                                      tuple(f"quote:{ticker}" for ticker in unavailable), True))
    if missing_previous:
        reasons.append(ResearchReason(ReasonCode.WARMUP_STATE, tuple(missing_previous), True))
    if events or evaluated_count or missing_previous:
        research = ResearchStatus.ACTION_REQUIRED if events else ResearchStatus.NO_SETUP
        operational = OperationalStatus.PARTIAL if unavailable or invalid else OperationalStatus.HEALTHY
    elif valid_watch_count:
        research = ResearchStatus.INSUFFICIENT_EVIDENCE
        operational = OperationalStatus.UNAVAILABLE
    elif invalid:
        research = ResearchStatus.ERROR
        operational = OperationalStatus.ERROR
    else:
        research = ResearchStatus.NO_SETUP
        operational = OperationalStatus.HEALTHY
    warnings = []
    if watches and not valid_watch_count:
        warnings.append("no valid deterministic watch conditions were supplied")
    if invalid:
        warnings.append("watch conditions are incomplete or invalid for: " + ", ".join(sorted(set(invalid))))
    if missing_previous:
        warnings.append("previous observation unavailable for: " + ", ".join(missing_previous))
    if unavailable:
        warnings.append("current price unavailable for: " + ", ".join(unavailable))
    if events:
        warnings.append("watch events notify a human; they never execute")
    evidence = []
    for ticker, price in checked.items():
        if price is None:
            continue
        quote = (quote_evidence or {}).get(ticker, {})
        available = quote.get("available_at")
        from rocket.pit import parse_datetime

        stamp = parse_datetime(available) if available else decision_time
        evidence.append(
            Evidence(
                source=str(quote.get("source") or "quotes"),
                reference=f"watch-{ticker}",
                claim=f"{ticker} quoted {price}",
                kind=EvidenceKind.FACT,
                event_time=parse_datetime(quote.get("observation_at")) if quote else stamp,
                observed_at=parse_datetime(quote.get("observation_at")) if quote else stamp,
                available_at=stamp,
                retrieved_at=decision_time,
                decision_time=decision_time,
                provenance=Provenance.PROVIDER_RESULT if quote else Provenance.CALLER_STATE,
            )
        )
    return ResearchResult(
        workflow=WORKFLOW,
        status=research,
        operational=OperationalReport(
            status=operational,
            providers=(
                ProviderHealth(
                    name="quotes",
                    status=OperationalStatus.PARTIAL if unavailable and any(checked.values()) else OperationalStatus.UNAVAILABLE if unavailable else OperationalStatus.HEALTHY,
                    retrieved_at=decision_time,
                    coverage=f"{evaluated_count}/{valid_watch_count}" if valid_watch_count else "0",
                ),
            ) if valid_watch_count else (),
        ),
        decision_time=decision_time,
        started_at=decision_time,
        completed_at=decision_time,
        mode=Mode.LIVE,
        payload={
            "events": events,
            "evaluations": evaluations,
            "evaluated_count": evaluated_count,
            "coverage_status": "NOT_APPLICABLE" if not watches else "INVALID_INPUT" if not valid_watch_count
            else "DATA_UNAVAILABLE" if unavailable and not any(checked.values())
            else "PARTIAL" if unavailable or invalid else "WARMUP" if missing_previous else "OK",
            "silent": not bool(events),
            "checked": len(watches),
            "valid_watch_count": valid_watch_count,
            "invalid_watches": sorted(set(invalid)),
            "missing_previous": sorted(set(missing_previous)),
            "prices": checked,
            "unavailable_prices": unavailable,
            "model_escalation": False,
            "execution_enabled": False,
        },
        evidence=tuple(evidence),
        warnings=tuple(warnings),
        reasons=tuple(reasons),
    )


class WatchWorkflow:
    name = WORKFLOW

    def __init__(self, *, store: ResearchStore | None = None, quote_fetcher=None):
        self.store = store
        self.quote_fetcher = quote_fetcher or acquire_quotes

    def run(
        self,
        watches: Sequence[Mapping[str, Any]],
        *,
        now: datetime | None = None,
        prices: Mapping[str, float] | None = None,
        quote_evidence: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> ResearchResult:
        decision_time = now or datetime.now(UTC)
        previous = {}
        if self.store:
            previous = dict((self.store.load_state("watch_last_quotes") or {}).get("prices") or {})
        if prices is None:
            # Validate definitions before spending provider requests on caller errors.
            preflight = check_watch(watches, {}, now=decision_time)
            valid_tickers = {row["ticker"] for row in preflight.payload["evaluations"]}
            configured = [row for row in watches if str(row.get("ticker") or "").strip().upper() in valid_tickers]
            quote_evidence = self.quote_fetcher(configured, now=now) if configured else {}
            prices = {
                ticker: row["price"]
                for ticker, row in quote_evidence.items()
                if isinstance(row, Mapping) and row.get("status") == "OK"
            }
        decision_time = now or datetime.now(UTC)
        result = check_watch(
            watches,
            prices,
            previous_prices=previous,
            quote_evidence=quote_evidence,
            now=decision_time,
        )
        accepted = {ticker: price for ticker, price in result.payload["prices"].items() if price is not None}
        if self.store:
            self.store.save_result(result)
            merged = {**previous, **accepted}
            self.store.save_state("watch_last_quotes", {"prices": merged, "updated_at": decision_time.isoformat()})
        return result
