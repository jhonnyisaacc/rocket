"""Daily market check as a ResearchResult. Read-only."""

from __future__ import annotations

import csv
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from rocket.market_check.actions import _book_weights, changed_against, decide, snapshot_book
from rocket.market_check.backtest import run_backtest
from rocket.market_check.config import Config, load_config
from rocket.market_check.panel import SeriesPanel
from rocket.market_check.scorecard import load_scorecard, pending_due
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
from rocket.pit import iso
from rocket.store import ResearchStore

WORKFLOW = "market_check"


def close_timestamp(day: date) -> datetime:
    """US cash-close stand-in. Daily bars are judged after the regular session."""
    return datetime(day.year, day.month, day.day, 21, 0, tzinfo=UTC)


def previous_session(panel: SeriesPanel, day: date) -> date | None:
    for name in ("spy", "btc", "yield_10y"):
        prior = [stamp for stamp in panel.dates(name) if stamp < day]
        if prior:
            return prior[-1]
    return None


def _evidence(decision: dict[str, Any], decided: datetime) -> tuple[Evidence, ...]:
    rows = []
    for name, pillar in decision["pillars"].items():
        if pillar["color"] == "missing":
            continue
        rows.append(Evidence(
            source="market_check",
            reference=name,
            claim=f"{name} is {pillar['color']}",
            kind=EvidenceKind.INFERENCE,
            event_time=decided,
            observed_at=decided,
            available_at=decided,
            retrieved_at=decided,
            decision_time=decided,
            provenance=Provenance.PROVIDER_RESULT,
            metadata={"color": pillar["color"]},
        ))
    return tuple(rows)


class MarketCheckWorkflow:
    name = WORKFLOW

    def __init__(self, config: Config | None = None, *, store: ResearchStore | None = None):
        self.store = store
        self.config = config or load_config()

    def run(
        self,
        panel: SeriesPanel,
        *,
        asof: date,
        scorecard: Path | None = None,
        book: dict[str, float] | None = None,
        regular_hours: bool | None = None,
    ) -> ResearchResult:
        decided = close_timestamp(asof)
        weights, basis = _book_weights(book, self.config, asof)
        decision = decide(panel, asof, self.config, book=weights, regular_hours=regular_hours)
        decision["porto"]["book_basis"] = basis
        prior_day = previous_session(panel, asof)
        yesterday = None
        if prior_day is not None:
            yesterday = decide(panel, prior_day, self.config, book=weights, regular_hours=regular_hours)
            yesterday["porto"]["book_basis"] = basis
        changed = changed_against(decision, yesterday)
        warnings: list[str] = []
        missing = [name for name, pillar in decision["pillars"].items() if pillar["color"] == "missing"]
        if missing:
            warnings.append("Missing pillars: " + ", ".join(missing))
        cava: list[dict[str, str]] = []
        if scorecard is not None:
            try:
                cava = pending_due(
                    load_scorecard(scorecard), asof, within_days=self.config.scorecard.within_days,
                )
            except (OSError, csv.Error, UnicodeError):
                warnings.append("Cava scorecard could not be read")
        known = len(decision["pillars"]) - len(missing)
        if decision["regime"] == "unknown":
            operational = OperationalStatus.PARTIAL if known else OperationalStatus.UNAVAILABLE
            status = ResearchStatus.INSUFFICIENT_EVIDENCE
        else:
            operational = OperationalStatus.PARTIAL if missing else OperationalStatus.HEALTHY
            status = ResearchStatus.NO_SETUP
        payload: dict[str, Any] = {
            "contract": "market_check_v1",
            "execution_enabled": False,
            "as_of": asof.isoformat(),
            "regime": decision["regime"],
            "score": decision["score"],
            "regime_rule": decision["regime_rule"],
            "pillars": decision["pillars"],
            "oil_shock": decision["oil_shock"],
            "events_today": decision["events_today"],
            "events_upcoming": decision["events_upcoming"],
            "event_schedule": {
                "fomc": "static decision dates in config/market_check.toml",
                "cpi": "second Wednesday of each month, a release proxy",
                "nfp": "first Friday of each month",
            },
            "perps": decision["perps"],
            "porto": decision["porto"],
            "phillip": decision["phillip"],
            "changed": changed,
            "previous_session": prior_day.isoformat() if prior_day else None,
            "current_book": snapshot_book(self.config.current_book),
            "cava_pending": cava,
            "sources": panel.meta.get("sources") or {},
            "move_proxy": "TLT 20-session realized volatility; ICE MOVE is not on a free historical feed",
            "fed_pressure_proxy": "2-year yield minus effective fed funds; futures-implied odds are not used",
        }
        reasons = ()
        if status is ResearchStatus.INSUFFICIENT_EVIDENCE:
            reasons = (ResearchReason(
                ReasonCode.REQUIRED_EVIDENCE_MISSING,
                tuple(f"pillar:{name}" for name in missing) or ("regime",),
                True,
            ),)
        speak = bool(changed["changed"]) and status is ResearchStatus.NO_SETUP
        result = ResearchResult(
            workflow=WORKFLOW,
            status=status,
            operational=OperationalReport(
                status=operational,
                providers=(ProviderHealth("market_check.panel", operational, decided, coverage="asof"),),
            ),
            decision_time=decided,
            started_at=decided,
            completed_at=decided,
            mode=Mode.REPLAY,
            payload=payload,
            evidence=_evidence(decision, decided),
            warnings=tuple(warnings),
            reasons=reasons,
            presentation={"market_result": speak, "silent": not speak, "diagnostic_only": False},
        )
        if self.store is not None:
            self.store.save_result(result)
            self.store.save_state("market_check_fingerprint", {
                "as_of": asof.isoformat(),
                "fingerprint": changed["today"],
                "decision_time": iso(decided),
            })
        return result

    def backtest(
        self,
        panel: SeriesPanel,
        *,
        trade_log: list[dict[str, Any]] | None = None,
        report_path: Path | None = None,
    ) -> ResearchResult:
        started = close_timestamp(self.config.window.end)
        result_payload = run_backtest(panel, self.config, trade_log=trade_log)
        markdown = result_payload.pop("markdown")
        if report_path is not None:
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(markdown, encoding="utf-8")
        portfolio = dict(result_payload["portfolio"])
        portfolio.pop("nav", None)
        result_payload["portfolio"] = portfolio
        result_payload["report_path"] = str(report_path) if report_path else None
        full = result_payload["portfolio"]["full"]["strategy"]
        claim = (
            f"Backtest {self.config.window.start.isoformat()} to {self.config.window.end.isoformat()} "
            f"CAGR {full.get('cagr')}"
        )
        result = ResearchResult(
            workflow="market_check.backtest",
            status=ResearchStatus.NO_SETUP,
            operational=OperationalReport(
                OperationalStatus.HEALTHY,
                (ProviderHealth("market_check.panel", OperationalStatus.HEALTHY, started, coverage="historical"),),
            ),
            decision_time=started,
            started_at=started,
            completed_at=started,
            mode=Mode.REPLAY,
            payload=result_payload,
            evidence=(Evidence(
                source="market_check.backtest",
                reference=f"{self.config.window.start.isoformat()}:{self.config.window.end.isoformat()}",
                claim=claim,
                kind=EvidenceKind.INFERENCE,
                event_time=started,
                available_at=started,
                retrieved_at=started,
                decision_time=started,
                provenance=Provenance.PROVIDER_RESULT,
            ),),
            warnings=("Research record only. execution_enabled is false. See assumptions in the payload.",),
            presentation={"market_result": True, "silent": False, "diagnostic_only": False},
        )
        if self.store is not None:
            self.store.save_result(result)
        return result
