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
    return [dict(item) for item in rows if isinstance(item, dict)]


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
        ticker = str(watch.get("ticker") or "").upper()
        if not ticker:
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
                price_ok = price_ok and quote_evidence.get(ticker, {}).get("status") == "OK"
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
    if events:
        research = ResearchStatus.ACTION_REQUIRED
        operational = OperationalStatus.PARTIAL if unavailable else OperationalStatus.HEALTHY
    elif evaluated_count:
        research = ResearchStatus.NO_SETUP
        operational = OperationalStatus.PARTIAL if unavailable else OperationalStatus.HEALTHY
    elif missing_previous:
        research = ResearchStatus.INSUFFICIENT_EVIDENCE
        operational = OperationalStatus.PARTIAL
    elif valid_watch_count:
        research = ResearchStatus.INSUFFICIENT_EVIDENCE
        operational = OperationalStatus.UNAVAILABLE if unavailable else OperationalStatus.HEALTHY
    else:
        research = ResearchStatus.INSUFFICIENT_EVIDENCE
        operational = OperationalStatus.HEALTHY
        if not watches:
            operational = OperationalStatus.HEALTHY
    warnings = []
    if not valid_watch_count:
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
        available = quote.get("available_at") or quote.get("observation_at")
        from rocket.pit import parse_datetime

        stamp = parse_datetime(available) if available else decision_time
        evidence.append(
            Evidence(
                source=str(quote.get("source") or "quotes"),
                reference=f"watch-{ticker}",
                claim=f"{ticker} quoted {price}",
                kind=EvidenceKind.FACT,
                event_time=stamp,
                observed_at=stamp,
                available_at=stamp,
                retrieved_at=decision_time,
                decision_time=decision_time,
                provenance=Provenance.PROVIDER_RESULT,
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
                    status=operational,
                    retrieved_at=decision_time,
                    coverage=f"{evaluated_count}/{valid_watch_count}" if valid_watch_count else "0",
                ),
            ),
        ),
        decision_time=decision_time,
        started_at=decision_time,
        completed_at=decision_time,
        mode=Mode.LIVE,
        payload={
            "events": events,
            "evaluations": evaluations,
            "evaluated_count": evaluated_count,
            "coverage_status": "OK"
            if evaluated_count and evaluated_count == len(watches)
            else "PARTIAL"
            if evaluated_count
            else "DATA_UNAVAILABLE",
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
            quote_evidence = self.quote_fetcher(watches, now=decision_time)
            prices = {
                ticker: row["price"]
                for ticker, row in quote_evidence.items()
                if isinstance(row, Mapping) and row.get("status") == "OK"
            }
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
