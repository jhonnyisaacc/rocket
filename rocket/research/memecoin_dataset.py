"""Point-in-time memecoin snapshot builder for offline research.

Inputs are already decoded observations. This module does not infer protocol state
from a market-data proxy or turn a snapshot into a trading decision.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from rocket.pit import Availability, PointInTime, iso, parse_datetime
from rocket.workflows.memecoin import canonical_identity

SCHEMA = "rocket.memecoin.pit-snapshot.v1"


class SnapshotError(ValueError):
    """An observation cannot support a point-in-time research row."""


def _required_time(value: Any, name: str) -> datetime:
    try:
        stamp = parse_datetime(value)
    except ValueError as exc:
        raise SnapshotError(f"{name}: {exc}") from exc
    if stamp is None:
        raise SnapshotError(f"{name} is required")
    return stamp


def build_snapshot(
    identity: Mapping[str, Any],
    observations: Sequence[Mapping[str, Any]],
    *,
    decision_time: str | datetime,
    lifecycle_stage: str,
    discovery_source: str,
    protocol_version: str,
    fee_model_version: str,
) -> dict[str, Any]:
    """Freeze eligible observations; reject ambiguity instead of backfilling it.

    Each observation must contain a name, value, event_time, available_at,
    source_ref and source_hash. An observation known only from a historical RPC
    read uses its actual retrieval time as available_at, never its block time.
    Outcomes belong in a separately joined label table after the row is frozen.
    """
    key = canonical_identity(identity)
    if key is None:
        raise SnapshotError("canonical chain and mint are required")
    decision = _required_time(decision_time, "decision_time")
    if not lifecycle_stage or not discovery_source or not protocol_version or not fee_model_version:
        raise SnapshotError("stage, discovery source and protocol/fee versions are required")
    if not observations:
        raise SnapshotError("at least one observation is required")

    features: dict[str, Any] = {}
    provenance: dict[str, dict[str, str]] = {}
    for item in observations:
        if not isinstance(item, Mapping):
            raise SnapshotError("observation must be an object")
        name = item.get("name")
        if not isinstance(name, str) or not name or name in features:
            raise SnapshotError("feature name is missing or duplicated")
        if name in {"outcome", "forward_return", "graduated", "future_price"}:
            raise SnapshotError("outcome labels cannot enter the feature table")
        event = _required_time(item.get("event_time"), f"{name}.event_time")
        available = _required_time(item.get("available_at"), f"{name}.available_at")
        if available < event:
            raise SnapshotError(f"{name} availability precedes its event")
        if PointInTime(event, available, decision).availability is not Availability.ELIGIBLE:
            raise SnapshotError(f"{name} was unavailable at decision time")
        source_ref, source_hash = item.get("source_ref"), item.get("source_hash")
        if not isinstance(source_ref, str) or not source_ref:
            raise SnapshotError(f"{name} needs a source reference")
        if not isinstance(source_hash, str) or len(source_hash) != 64:
            raise SnapshotError(f"{name} needs a SHA-256 source hash")
        try:
            int(source_hash, 16)
        except ValueError as exc:
            raise SnapshotError(f"{name} needs a SHA-256 source hash") from exc
        value = item.get("value")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise SnapshotError(f"{name} needs a finite numeric value")
        features[name] = value
        provenance[name] = {
            "event_time": iso(event),
            "available_at": iso(available),
            "source_ref": source_ref,
            "source_hash": source_hash.lower(),
        }

    row = {
        "schema": SCHEMA,
        "identity": key,
        "decision_time": iso(decision),
        "lifecycle_stage": lifecycle_stage,
        "discovery_source": discovery_source,
        "protocol_version": protocol_version,
        "fee_model_version": fee_model_version,
        "features": dict(sorted(features.items())),
        "provenance": dict(sorted(provenance.items())),
    }
    canonical = json.dumps(row, sort_keys=True, separators=(",", ":"), allow_nan=False)
    row["fingerprint"] = hashlib.sha256(canonical.encode()).hexdigest()
    return row
