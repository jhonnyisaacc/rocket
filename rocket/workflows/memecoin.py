"""Memecoin research primitives. Strategy is not shipped. NO EDGE VALIDATED."""

from __future__ import annotations

import base64
import math
import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from rocket.models import (
    Evidence,
    EvidenceKind,
    OperationalReport,
    OperationalStatus,
    Provenance,
    ResearchResult,
    ResearchStatus,
)
from rocket.pit import parse_datetime
from rocket.store import ResearchStore

WORKFLOW = "memecoin.scan"
EDGE = "NO_EDGE_VALIDATED"


def canonical_identity(row: Mapping[str, Any]) -> str | None:
    chain = str(row.get("chain_id") or "").strip()
    address = str(row.get("contract_address") or row.get("mint") or "").strip()
    if re.fullmatch(r"eip155:[1-9][0-9]*", chain):
        if not re.fullmatch(r"0x[0-9a-fA-F]{40}", address) or int(address, 16) == 0:
            return None
        address = address.lower()
    elif chain == "solana:mainnet":
        alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
        if not 32 <= len(address) <= 44 or any(char not in alphabet for char in address):
            return None
        number = 0
        for char in address:
            number = number * 58 + alphabet.index(char)
        leading = len(address) - len(address.lstrip("1"))
        if leading + (number.bit_length() + 7) // 8 != 32:
            return None
    else:
        return None
    return f"{chain}:{address}"


def _eligible(row: Mapping[str, Any]) -> tuple[bool, list[str]]:
    decision = parse_datetime(row.get("decision_time"))
    if decision is None:
        return False, ["invalid_decision_time"]
    if not row.get("available_at"):
        return False, ["unknown_feature_availability"]
    available = parse_datetime(row.get("available_at"))
    if available is None:
        return False, ["invalid_feature_availability"]
    if available > decision:
        return False, ["hindsight_feature_not_available_at_decision"]
    if canonical_identity(row) is None:
        return False, ["unknown_identity"]
    blockers: list[str] = []
    features = row.get("features") if isinstance(row.get("features"), Mapping) else row
    try:
        volume = float(features.get("volume_acceleration"))
        if not math.isfinite(volume):
            blockers.append("volume_acceleration_missing")
    except (TypeError, ValueError):
        blockers.append("volume_acceleration_missing")
    try:
        liquidity = float(features.get("liquidity_usd"))
        if not math.isfinite(liquidity):
            blockers.append("liquidity_missing")
    except (TypeError, ValueError):
        blockers.append("liquidity_missing")
    return not blockers, blockers


def frames_from_payload(payload: Any) -> list[tuple[bytes, datetime]]:
    rows = payload.get("frames", payload) if isinstance(payload, Mapping) else payload
    frames: list[tuple[bytes, datetime]] = []
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        return frames
    for row in rows:
        if isinstance(row, Mapping):
            raw = row.get("raw") or row.get("raw_base64")
            stamp = parse_datetime(row.get("received_at") or row.get("available_at"))
            if isinstance(raw, str):
                try:
                    raw_bytes = base64.b64decode(raw)
                except (ValueError, TypeError):
                    raw_bytes = raw.encode()
            elif isinstance(raw, bytes):
                raw_bytes = raw
            else:
                continue
            if stamp is None:
                continue
            frames.append((raw_bytes, stamp))
        elif isinstance(row, bytes):
            frames.append((row, datetime.now(UTC)))
    return frames


class MemecoinWorkflow:
    name = WORKFLOW

    def __init__(self, *, store: ResearchStore | None = None):
        self.store = store

    def status(self, *, now: datetime | None = None) -> ResearchResult:
        decided = now or datetime.now(UTC)
        result = ResearchResult(
            workflow="memecoin.status",
            status=ResearchStatus.INSUFFICIENT_EVIDENCE,
            operational=OperationalReport(status=OperationalStatus.HEALTHY),
            decision_time=decided,
            started_at=decided,
            completed_at=decided,
            payload={
                "edge": EDGE,
                "strategy_state": "EXPERIMENTAL",
                "collector": "spool_first",
                "execution_enabled": False,
            },
            warnings=("NO EDGE VALIDATED. Primitives only; no production strategy job.",),
        )
        if self.store:
            self.store.save_result(result)
        return result

    def scan(self, rows: Sequence[Mapping[str, Any]], *, now: datetime | None = None) -> ResearchResult:
        decided = now or datetime.now(UTC)
        selected, rejected = [], []
        evidence = []
        seen: set[str] = set()
        for row in rows:
            identity = canonical_identity(row)
            ok, blockers = _eligible(row)
            if identity is None:
                rejected.append({"reason": "unknown_identity", "overfit_guard": "no asset-specific rule added"})
                continue
            if identity in seen:
                rejected.append({"identity": identity, "reason": "duplicate_snapshot_identity"})
                continue
            seen.add(identity)
            if not ok:
                rejected.append({"identity": identity, "rejection_filters": blockers})
                continue
            selected.append({"identity": identity, "asset": row.get("asset")})
            evidence.append(
                Evidence(
                    source="memecoin.snapshot",
                    reference=identity,
                    claim="Point-in-time memecoin snapshot was eligible for research",
                    kind=EvidenceKind.FACT,
                    event_time=parse_datetime(row.get("decision_time")),
                    available_at=parse_datetime(row.get("available_at")),
                    retrieved_at=decided,
                    decision_time=parse_datetime(row.get("decision_time")) or decided,
                    provenance=Provenance.TEST_FIXTURE,
                )
            )
        research = ResearchStatus.INSUFFICIENT_EVIDENCE
        result = ResearchResult(
            workflow=WORKFLOW,
            status=research,
            operational=OperationalReport(status=OperationalStatus.HEALTHY),
            decision_time=decided,
            started_at=decided,
            completed_at=decided,
            payload={
                "edge": EDGE,
                "selected": selected,
                "rejected": rejected,
                "case_study": None,
                "overfit_guard": "no asset-specific rule added",
                "execution_enabled": False,
            },
            evidence=tuple(evidence),
            warnings=("NO EDGE VALIDATED. Discovery is research-only.",),
        )
        if self.store:
            self.store.save_result(result)
        return result

    def collect(self, spool: Any, frames: Sequence[tuple[bytes, datetime]], *, now: datetime | None = None) -> ResearchResult:
        decided = now or datetime.now(UTC)
        receipts = spool.append_batch(frames)
        result = ResearchResult(
            workflow="memecoin.collect",
            status=ResearchStatus.INSUFFICIENT_EVIDENCE,
            operational=OperationalReport(status=OperationalStatus.HEALTHY),
            decision_time=decided,
            started_at=decided,
            completed_at=decided,
            payload={
                "edge": EDGE,
                "frames_appended": len(receipts),
                "receipts": receipts,
                "collector": "spool_first",
                "execution_enabled": False,
            },
            warnings=("NO EDGE VALIDATED. Capture is spool-first; this is not a live websocket job.",),
        )
        if self.store:
            self.store.save_result(result)
        return result

    def evaluate(
        self,
        scan_result: ResearchResult,
        outcomes: Sequence[Mapping[str, Any]],
        *,
        now: datetime | None = None,
    ) -> ResearchResult:
        decided = now or datetime.now(UTC)
        selected = {
            str(item.get("identity"))
            for item in (scan_result.payload.get("selected") or [])
            if isinstance(item, Mapping) and item.get("identity")
        }
        evaluated = []
        for outcome in outcomes:
            if not isinstance(outcome, Mapping):
                continue
            identity = canonical_identity(outcome) or str(outcome.get("identity") or "")
            if not identity or identity not in selected:
                continue
            try:
                forward = float(outcome["forward_return"])
            except (KeyError, TypeError, ValueError):
                continue
            if not math.isfinite(forward):
                continue
            evaluated.append({"identity": identity, "forward_return": forward, "hit": forward >= 0})
        result = ResearchResult(
            workflow="memecoin.evaluate",
            status=ResearchStatus.INSUFFICIENT_EVIDENCE,
            operational=OperationalReport(status=OperationalStatus.HEALTHY),
            decision_time=decided,
            started_at=decided,
            completed_at=decided,
            payload={
                "edge": EDGE,
                "strategy_state": "EXPERIMENTAL",
                "metrics": {
                    "evaluated_count": len(evaluated),
                    "hit_rate": (sum(item["hit"] for item in evaluated) / len(evaluated)) if evaluated else None,
                },
                "outcomes": evaluated,
                "source_scan_run_id": scan_result.run_id,
                "execution_enabled": False,
            },
            warnings=("NO EDGE VALIDATED. Evaluation is research evidence only.",),
        )
        if self.store:
            self.store.save_result(result)
        return result
