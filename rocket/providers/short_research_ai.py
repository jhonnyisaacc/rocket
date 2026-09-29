"""Bounded qualitative short-research contract. Never a numerical selector."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

QUALITATIVE_FIELDS = (
    "bear_thesis",
    "bull_counter_thesis",
    "catalysts",
    "management_claim_contradictions",
    "filing_anomalies",
    "evidence_references",
    "unknowns",
    "invalidation_thesis",
)


def qualitative_contract() -> dict[str, Any]:
    return {
        "layer": "qualitative_short_research",
        "produces": list(QUALITATIVE_FIELDS),
        "must_not": (
            "numerical short signal",
            "factor scores",
            "TRIGGERED/WATCH state",
            "execution instructions",
        ),
        "requires_evidence": True,
        "backtest_dependent": False,
        "reuse": "rocket.providers.news and rocket.providers.claim_verification for evidence acquisition",
    }


class QualitativeShortResearch:
    """Optional future LLM investigator. Numerical selection remains deterministic."""

    def investigate(self, ticker: str, evidence: Sequence[Mapping[str, Any]], *, now=None) -> dict[str, Any]:
        del ticker, evidence, now
        raise RuntimeError("qualitative LLM research is not part of numerical short selection")
