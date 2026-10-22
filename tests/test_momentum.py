"""Momentum primitives: bars, candidates, labels, episodes, folds.

Covers bar timestamp semantics, triple-barrier outcomes, event
deduplication/spacing, episode grouping, purge/embargo, UNKNOWN
handling, deterministic replay and version identity.
"""

from __future__ import annotations

import math

from rocket.momentum import contracts
from rocket.momentum.bars import aggregate_4h, contiguous_4h_before, parse_kline_csv
from rocket.momentum.candidates import (
    crossing_state,
    sample_sd,
    scan_crossings,
    sigma_at,
    space_candidates,
)
from rocket.momentum.episodes import kish_effective_n, overlap_components, segment_legs
from rocket.momentum.folds import build_folds
from rocket.momentum.labels import full_window_excursions, label_candidate

HOUR = 3600 * 1000


def _kline_text(rows):
    lines = []
    for open_ms, o, h, low, c in rows:
        lines.append(
            f"{open_ms},{o},{h},{low},{c},1.5,{open_ms + HOUR - 1},100.0,10,0.7,50.0,0"
        )
    return "\n".join(lines) + "\n"


def _bars_1h(n, start_ms=10 * HOUR, price=100.0, drift=0.0):
    rows = []
    for i in range(n):
        p = price * (1 + drift * i)
        rows.append((start_ms + i * HOUR, p, p * 1.001, p * 0.999, p))
    return parse_kline_csv(_kline_text(rows), vintage="test", ingested_at="test")


def _bars_4h(n, start_ms=12 * HOUR, price=100.0, drift=0.0):
    out = []
    for i in range(n):
        p = price * (1 + drift * i)
        out.append(
            {"open_ms": start_ms + i * 4 * HOUR, "open": p, "high": p * 1.002,
             "low": p * 0.998, "close": p, "volume": 1.0, "quote_volume": 100.0,
             "trades": 5}
        )
    return out


def test_kline_ms_and_us_units():
    ms_rows = _bars_1h(3)
    assert all(r["timestamp_unit"] == "ms" for r in ms_rows)
    base_us = 1577836800000000  # 2020-01-01T00:00:00Z, hour-aligned.
    us_lines = []
    for i in range(3):
        open_us = base_us + i * HOUR * 1000
        us_lines.append(
            f"{open_us},100,101,99,100.5,1.5,{open_us + HOUR * 1000 - 1},100.0,10,0.7,50.0,0"
        )
    us_rows = parse_kline_csv("\n".join(us_lines) + "\n", vintage="t", ingested_at="t")
    assert all(r["timestamp_unit"] == "us" for r in us_rows)
    assert us_rows[0]["open_ms"] == 1577836800000
    assert us_rows[0]["open"] == 100.0


def test_kline_quarantines_bad_close_time_and_misalignment():
    # Malformed vendor rows are quarantined and skipped (gap -> UNKNOWN
    # downstream), never abort the ingest and never imputed.
    good = "3600000,100,101,99,100,1.5,7199999,100.0,10,0.7,50.0,0\n"
    bad = "0,100,101,99,100,1,3599998,100,10,0.7,50,0\n"
    misaligned = "1,100,101,99,100,1,3600000,100,10,0.7,50,0\n"
    quarantine: list = []
    rows = parse_kline_csv(good + bad + misaligned + good, vintage="t",
                           ingested_at="t", quarantine=quarantine)
    assert len(rows) == 2  # only the two valid rows survive.
    assert len(quarantine) == 2
    assert any("close_time" in q["reason"] for q in quarantine)
    assert any("hour-aligned" in q["reason"] for q in quarantine)
    assert all(q["vintage"] == "t" for q in quarantine)


def test_aggregate_4h_requires_all_four_hours():
    rows = _bars_1h(8, start_ms=12 * HOUR)
    bars = aggregate_4h(rows)
    assert len(bars) == 2
    assert bars[0]["close"] == rows[3]["close"]
    assert bars[0]["high"] == max(r["high"] for r in rows[:4])
    del rows[5]
    bars = aggregate_4h(rows)
    assert len(bars) == 1  # gap group dropped, never imputed.


def test_contiguous_history_empty_on_gap():
    bars = _bars_4h(200)
    cutoff = bars[-1]["open_ms"] + 4 * HOUR
    assert len(contiguous_4h_before(bars, cutoff)) == 180
    bars_gapped = [b for b in bars if b["open_ms"] != bars[100]["open_ms"]]
    assert contiguous_4h_before(bars_gapped, cutoff) == []


def test_sigma_none_without_181_closes():
    assert sigma_at(_bars_4h(180)) is None
    assert sigma_at(_bars_4h(181)) is not None


def test_flat_sigma_is_unknown():
    hist = _bars_4h(43)
    assert crossing_state(hist, sigma=0.0) == {"UP": "UNKNOWN", "DOWN": "UNKNOWN"}


def test_crossing_fires_up_only():
    hist = _bars_4h(43, drift=0.0)
    sig = 0.001
    state = crossing_state(hist, sigma=sig)
    assert state == {"UP": "INACTIVE", "DOWN": "INACTIVE"}
    hist2 = [dict(b) for b in hist]
    prior_high = max(b["high"] for b in hist2[-43:-1])
    hist2[-1]["close"] = prior_high * math.exp(0.6 * sig)
    hist2[-1]["high"] = hist2[-1]["close"]
    assert crossing_state(hist2, sigma=sig)["UP"] == "ACTIVE"


def test_scan_and_spacing_cover_and_cooldown():
    bars = _bars_4h(600, drift=0.005)
    for i, b in enumerate(bars):  # realistic wiggle around the drift.
        b["close"] *= 1 + 0.001 * ((i * 37) % 5 - 2)
        b["high"] = max(b["high"], b["close"])
        b["low"] = min(b["low"], b["close"])
    events = scan_crossings(bars)
    assert events, "drifting series should cross"
    spaced = space_candidates(events)
    import itertools

    accepted = [e["cutoff_ms"] for e in spaced if e["independent"]]
    for a, b in itertools.pairwise(accepted):
        assert b - a >= contracts.COOLDOWN_SECONDS * 1000
    assert spaced[0]["generator"] == contracts.CANDIDATE_GENERATOR_VERSION


def _label_event(direction="UP", ref_log=math.log(100.0), scale=0.02, cutoff=4 * HOUR):
    return {"direction": direction, "reference_log": ref_log, "scale_S": scale,
            "cutoff_ms": cutoff, "sigma": 0.01}


def test_label_continues_up_and_mae_mfe():
    bars = []
    for i in range(1, 169):
        p = 100.0 * math.exp(0.0004 * i)
        bars.append({"open_ms": (4 + i) * HOUR, "high": p * 1.001, "low": p * 0.999, "close": p})
    lab = label_candidate(_label_event(), bars)
    assert lab["outcome"] == "CONTINUES"
    assert lab["mfe_S"] is not None and lab["mfe_S"] >= 2.0
    assert lab["label_contract"] == contracts.LABEL_CONTRACT_VERSION


def test_label_fails_then_timeout_and_unknown():
    down = []
    for i in range(1, 169):
        p = 100.0 * math.exp(-0.0004 * i)
        down.append({"open_ms": (4 + i) * HOUR, "high": p * 1.001, "low": p * 0.999, "close": p})
    assert label_candidate(_label_event(), down)["outcome"] == "FAILS"
    flat = [{"open_ms": (4 + i) * HOUR, "high": 100.1, "low": 99.9, "close": 100.0} for i in range(1, 169)]
    assert label_candidate(_label_event(), flat)["outcome"] == "TIMEOUT"
    both = [{"open_ms": (4 + i) * HOUR, "high": 110.0, "low": 90.0, "close": 100.0} for i in range(1, 169)]
    assert label_candidate(_label_event(), both)["outcome"] == "UNKNOWN"
    short = flat[:100]
    assert label_candidate(_label_event(), short)["outcome"] == "UNKNOWN"


def test_label_excludes_first_hour_bar():
    # A barrier touch inside [cutoff, cutoff+1h) must not resolve.
    bars = [{"open_ms": 4 * HOUR + 30 * 60 * 1000, "high": 110.0, "low": 99.0, "close": 105.0}]
    bars += [{"open_ms": (4 + i) * HOUR, "high": 100.1, "low": 99.9, "close": 100.0} for i in range(1, 169)]
    lab = label_candidate(_label_event(), bars)
    assert lab["outcome"] == "TIMEOUT"


def test_excursions_full_window_despite_early_resolution():
    event = _label_event()
    window = [{"high": 110.0, "low": 99.0, "close": 105.0, "open_ms": 5 * HOUR}]
    window += [{"high": 106.0, "low": 104.0, "close": 105.5, "open_ms": (5 + i) * HOUR} for i in range(1, 168)]
    exc = full_window_excursions(event, window)
    assert exc["window_bars"] == 168
    assert exc["mfe_S"] is not None


def test_overlap_components_and_kish():
    events = [{"cutoff_ms": i * 24 * HOUR} for i in range(10)]
    comps = overlap_components(events, horizon_days=7)
    assert len(comps) == 1  # daily cutoffs chain through 7d horizons.
    spaced = [{"cutoff_ms": i * 14 * 24 * HOUR} for i in range(4)]
    comps = overlap_components(spaced, horizon_days=7)
    assert len(comps) == 4
    assert kish_effective_n([10, 10, 10]) == 3.0


def test_segment_legs_marks_large_and_censors_last():
    bars = []
    p = 100.0
    for i in range(400):
        p *= 1.0008
        bars.append({"open_ms": i * 4 * HOUR, "close": p, "high": p, "low": p})
    for i in range(400):
        p *= 0.9995
        bars.append({"open_ms": (400 + i) * 4 * HOUR, "close": p, "high": p, "low": p})
    legs = segment_legs(bars)
    assert legs and legs[-1]["censored"] is True
    assert any(lg["large"] for lg in legs)


def test_folds_purge_and_embargo():
    events = [{"cutoff_ms": (365 + i) * 24 * HOUR} for i in range(0, 900, 5)]
    folds = build_folds(events, horizon_days=7)
    assert folds, "two-plus years of dense events should fold"
    for fold in folds:
        for train in fold["train"]:
            assert train["cutoff_ms"] + 7 * 24 * HOUR < fold["test_start_ms"]
            assert train["cutoff_ms"] < fold["test_start_ms"] - 14 * 24 * HOUR
        for test in fold["test"]:
            assert fold["test_start_ms"] <= test["cutoff_ms"] < fold["test_end_ms"]


def test_contract_version_identity():
    assert contracts.CANDIDATE_GENERATOR_VERSION == "candgen-v1"
    assert contracts.LABEL_CONTRACT_VERSION == "label-v1"
    assert contracts.FEATURE_SCHEMA_VERSION == "feat-v1"
    assert contracts.MODEL_VERSION == "m1-logreg-c1"
    assert sample_sd([1.0, 2.0, 3.0]) is not None
