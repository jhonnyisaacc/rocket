"""Small causal primitives; future labels are deliberately separate from snapshots."""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from collections.abc import Iterable
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from itertools import pairwise
from typing import Any

from rocket.pit import Availability, PointInTime

HOUR = 3_600_000
FOUR_HOURS = 4 * HOUR
LAG = 5 * 60_000
DAY = 24 * HOUR
CONTRACT = "btc-breakout-triple-barrier-v1"
FEATURE_SCHEMA = "price-market-v1"


def fingerprint(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def dt(stamp: int) -> datetime:
    return datetime.fromtimestamp(stamp / 1000, UTC)


@dataclass(frozen=True)
class Observation:
    name: str
    value: float | None
    event_time: int
    available_at: int | None
    ingested_at: int
    source: str
    vintage: str

    def eligible(self, decision: int, *, prospective: bool = False) -> bool:
        pit = PointInTime(
            dt(self.event_time),
            dt(self.available_at) if self.available_at is not None else None,
            dt(decision),
        )
        return pit.availability == Availability.ELIGIBLE and (
            not prospective or self.ingested_at <= decision
        )


def pit_join(observations: Iterable[Observation], decision: int, *, prospective=False):
    """Latest eligible event and latest known vintage; unknown receipt never guesses."""
    result = {}
    identities = {}
    for row in observations:
        key = (row.name, row.event_time, row.available_at, row.vintage)
        if key in identities and identities[key] != row:
            raise ValueError("conflicting observation identity")
        identities[key] = row
        if not row.eligible(decision, prospective=prospective):
            continue
        previous = result.get(row.name)
        if previous is None or (row.event_time, row.available_at, row.vintage) > (
            previous.event_time,
            previous.available_at,
            previous.vintage,
        ):
            result[row.name] = row
    return result


@dataclass(frozen=True)
class Bar:
    open_time: int
    end_time: int
    available_at: int
    ingested_at: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    source: str = "binance-spot-BTCUSDT"

    def __post_init__(self):
        prices = (self.open, self.high, self.low, self.close)
        if (
            self.end_time <= self.open_time
            or self.available_at < self.end_time
            or not all(math.isfinite(x) and x > 0 for x in prices)
            or not self.low <= self.open <= self.high
            or not self.low <= self.close <= self.high
            or not math.isfinite(self.volume)
            or self.volume < 0
        ):
            raise ValueError("invalid bar or clock")


def validate_bars(bars: Iterable[Bar], interval: int) -> list[Bar]:
    rows = sorted(bars, key=lambda b: b.open_time)
    if any(b.open_time % interval or b.end_time - b.open_time != interval for b in rows):
        raise ValueError("bar interval/alignment mismatch")
    if len({b.open_time for b in rows}) != len(rows):
        raise ValueError("duplicate bar")
    return rows


def aggregate_four_hours(hourly: Iterable[Bar]) -> list[Bar]:
    rows = validate_bars(hourly, HOUR)
    groups = {}
    for b in rows:
        groups.setdefault(b.open_time // FOUR_HOURS * FOUR_HOURS, []).append(b)
    result = []
    for start, group in sorted(groups.items()):
        if [b.open_time for b in group] != [start + i * HOUR for i in range(4)]:
            continue  # Missing groups remain a gap; never synthesize a bar.
        result.append(
            Bar(
                start,
                start + FOUR_HOURS,
                max(b.available_at for b in group),
                max(b.ingested_at for b in group),
                group[0].open,
                max(b.high for b in group),
                min(b.low for b in group),
                group[-1].close,
                sum(b.volume for b in group),
            )
        )
    return result


@dataclass(frozen=True)
class FeatureSnapshot:
    decision_time: int
    data_cutoff: int
    state: str
    direction: int | None
    reference_price: float | None
    sigma: float | None
    values: dict[str, float | None]
    unknown: tuple[str, ...]
    schema: str = FEATURE_SCHEMA

    @property
    def identity(self):
        return fingerprint(asdict(self))


def snapshot(bars: Iterable[Bar], decision: int, cutoff: int, *, prospective=False):
    """No future row can change the snapshot; only complete, contiguous bars enter."""
    if cutoff % FOUR_HOURS or cutoff + LAG > decision:
        raise ValueError("decision must follow cutoff plus receipt allowance")
    visible = [
        b
        for b in bars
        if b.end_time <= cutoff
        and b.available_at <= decision
        and (not prospective or b.ingested_at <= decision)
    ]
    # Validation is applied AFTER eligibility: future invalid/duplicate rows cannot affect t.
    visible = validate_bars(visible, FOUR_HOURS)[-181:]
    names = (
        "signed_return_24h",
        "rv_ratio",
        "relative_volume",
        "funding_24h",
        "oi_change_24h",
        "spot_perp_volume_ratio",
    )
    empty = dict.fromkeys(names)
    if (
        len(visible) != 181
        or visible[-1].end_time != cutoff
        or any(b.open_time != visible[0].open_time + i * FOUR_HOURS for i, b in enumerate(visible))
    ):
        return FeatureSnapshot(decision, cutoff, "UNKNOWN", None, None, None, empty, tuple(names))
    returns = [math.log(b.close / a.close) for a, b in pairwise(visible)]
    sigma = statistics.stdev(returns)
    if sigma <= 0:
        return FeatureSnapshot(decision, cutoff, "UNKNOWN", None, None, None, empty, tuple(names))
    latest, prior = visible[-1], visible[-43:-1]
    up = math.log(latest.close / max(b.high for b in prior)) >= 0.5 * sigma
    down = math.log(min(b.low for b in prior) / latest.close) >= 0.5 * sigma
    direction = 1 if up else -1 if down else None
    values = dict(empty)
    values["signed_return_24h"] = (
        direction * math.log(latest.close / visible[-7].close) / (sigma * math.sqrt(6))
        if direction
        else None
    )
    values["rv_ratio"] = statistics.stdev(returns[-6:]) / sigma
    denominator = statistics.mean(b.volume for b in visible[-181:-7])
    values["relative_volume"] = (
        statistics.mean(b.volume for b in visible[-6:]) / denominator if denominator > 0 else None
    )
    return FeatureSnapshot(
        decision,
        cutoff,
        "ACTIVE" if direction else "NO_CANDIDATE",
        direction,
        latest.close,
        sigma,
        values,
        tuple(k for k, v in values.items() if v is None),
    )


@dataclass(frozen=True)
class CandidateEvent:
    event_id: str
    decision_time: int
    data_cutoff: int
    direction: int
    reference_price: float
    scale: float
    snapshot_id: str
    generator: str = CONTRACT


def candidates(bars: Iterable[Bar]) -> tuple[list[CandidateEvent], int]:
    rows = validate_bars(bars, FOUR_HOURS)
    active, events, eligible = None, [], 0
    for i, b in enumerate(rows):
        view = snapshot(rows[max(0, i - 180) : i + 1], b.end_time + LAG, b.end_time)
        if view.state == "UNKNOWN":
            active = None
            continue
        eligible += 1
        if view.direction and view.direction != active:
            key = {"cutoff": b.end_time, "direction": view.direction, "generator": CONTRACT}
            events.append(
                CandidateEvent(
                    fingerprint(key),
                    view.decision_time,
                    view.data_cutoff,
                    view.direction,
                    view.reference_price,
                    view.sigma * math.sqrt(42),
                    view.identity,
                )
            )
        active = view.direction
    return events, eligible


def spaced_events(events: Iterable[CandidateEvent], cooldown: int = 14 * DAY):
    accepted, next_time = [], -1
    for e in sorted(events, key=lambda e: e.decision_time):
        if e.decision_time >= next_time:
            accepted.append(e)
            next_time = e.decision_time + cooldown
    return accepted


def interval_groups(events: Iterable[CandidateEvent], horizon: int = 14 * DAY):
    groups, end = [], -1
    for e in sorted(events, key=lambda e: e.decision_time):
        if not groups or e.decision_time > end:
            groups.append([])
        groups[-1].append(e.event_id)
        end = max(end, e.data_cutoff + horizon)
    return groups


@dataclass(frozen=True)
class ForwardLabel:
    event_id: str
    outcome: str
    horizon_days: int
    upper: float
    lower: float
    label_end: int
    available_at: int
    barrier_time: int | None
    signed_return: float | None
    mfe: float | None
    mae: float | None
    mfe_normalized: float | None
    mae_normalized: float | None
    delay_4h_return: float | None
    reason: str | None = None
    contract: str = CONTRACT


def label(event: CandidateEvent, hourly: Iterable[Bar], days=7, upper=2.0, lower=1.0):
    if days not in (3, 7, 14) or upper <= 0 or lower <= 0:
        raise ValueError("invalid barrier contract")
    end = event.data_cutoff + days * DAY
    rows = validate_bars(
        [b for b in hourly if b.open_time >= event.decision_time and b.end_time <= end], HOUR
    )
    base = ForwardLabel(
        event.event_id,
        "UNKNOWN",
        days,
        upper,
        lower,
        end,
        end + LAG,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
    )
    expected = (end - event.data_cutoff) // HOUR - 1
    if (
        len(rows) != expected
        or not rows
        or rows[0].open_time != event.data_cutoff + HOUR
        or any(b.open_time != rows[0].open_time + i * HOUR for i, b in enumerate(rows))
    ):
        return replace(base, reason="INCOMPLETE_HORIZON")
    favorable, adverse = [], []
    outcome, hit, reason = "TIMEOUT", None, None
    for b in rows:
        fprice = b.high if event.direction == 1 else b.low
        aprice = b.low if event.direction == 1 else b.high
        f = event.direction * math.log(fprice / event.reference_price)
        a = event.direction * math.log(aprice / event.reference_price)
        favorable.append(f)
        adverse.append(a)
        if hit is None:
            good, bad = f >= upper * event.scale, a <= -lower * event.scale
            if good or bad:
                hit = b.end_time
                if good and bad:
                    outcome, reason = "UNKNOWN", "AMBIGUOUS_INTRABAR_ORDER"
                elif bad:
                    outcome = "FAILS"
                else:
                    outcome = "CONTINUES_UP" if event.direction == 1 else "CONTINUES_DOWN"
    directional = event.direction * math.log(rows[-1].close / event.reference_price)
    mfe, mae = max(0.0, max(favorable)), max(0.0, -min(adverse))
    delayed = next(b.close for b in rows if b.end_time == event.data_cutoff + FOUR_HOURS)
    return replace(
        base,
        outcome=outcome,
        barrier_time=hit,
        signed_return=directional,
        mfe=mfe,
        mae=mae,
        mfe_normalized=mfe / event.scale,
        mae_normalized=mae / event.scale,
        delay_4h_return=event.direction * math.log(rows[-1].close / delayed),
        reason=reason,
    )


@dataclass(frozen=True)
class ResearchFold:
    test_start: int
    test_end: int
    embargo: int = 14 * DAY

    def training(self, events: Iterable[CandidateEvent], labels: dict[str, ForwardLabel]):
        # Closed intervals touching test start are purged. Only earlier training allowed.
        return [
            e
            for e in events
            if e.decision_time < self.test_start - self.embargo
            and e.event_id in labels
            and labels[e.event_id].available_at < self.test_start
            and labels[e.event_id].label_end < self.test_start
        ]

    def testing(self, events: Iterable[CandidateEvent]):
        return [e for e in events if self.test_start <= e.decision_time < self.test_end]
