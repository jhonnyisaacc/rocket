"""Momentum PIT integrity: features, models, shadow log.

Covers no-future-feature-leakage (post-decision mutation invariance),
UNKNOWN handling, feature schema identity, model determinism and
degeneracy, B3 null structure, shadow-log append-only immutability and
enrichment separation, deterministic replay.
"""

from __future__ import annotations

import copy
import json

from rocket.momentum import contracts
from rocket.momentum.census import run_census
from rocket.momentum.features import feature_row, tier_a, tier_b
from rocket.momentum.metrics import brier_logloss, precision_recall
from rocket.momentum.models import climatology, fit_predict_fold, null_shift_pvalues
from rocket.momentum.shadow import append_forecast, append_outcome, read_forecasts, verify_log

HOUR = 3600 * 1000


def _bars_4h(n, start_ms=12 * HOUR, price=100.0, drift=0.0, vol=1.0):
    out = []
    for i in range(n):
        p = price * (1 + drift * i)
        out.append(
            {"open_ms": start_ms + i * 4 * HOUR, "open": p, "high": p * 1.002,
             "low": p * 0.998, "close": p, "volume": vol, "quote_volume": 100.0,
             "trades": 5}
        )
    return out


def _bars_1h(n, start_ms=13 * HOUR, price=100.0, drift=0.0):
    out = []
    for i in range(n):
        p = price * (1 + drift * i)
        out.append({"open_ms": start_ms + i * HOUR, "high": p * 1.001,
                    "low": p * 0.999, "close": p})
    return out


def test_tier_a_only_uses_closed_bars_mutation_invariance():
    bars = _bars_4h(300, drift=0.0002, vol=2.0)
    cutoff = bars[-100]["open_ms"] + 4 * HOUR
    sig = 0.01
    before = tier_a(bars, cutoff, sigma=sig)
    mutated = copy.deepcopy(bars)
    for b in mutated:
        if b["open_ms"] >= cutoff:
            b["close"] *= 1.5
            b["volume"] *= 10
    after = tier_a(mutated, cutoff, sigma=sig)
    assert before == after


def test_tier_a_unknown_without_history():
    assert tier_a(_bars_4h(100), 10**12, sigma=0.01)["missing"] == list(
        __import__("rocket.momentum.features", fromlist=["TIER_A"]).TIER_A)
    assert tier_a(_bars_4h(300), 10**12, sigma=0.0)["missing"]


def test_tier_b_unknown_when_inputs_absent():
    bars = _bars_4h(300)
    cutoff = bars[-1]["open_ms"] + 4 * HOUR
    out = tier_b([], [], bars, [], cutoff)
    assert out["missing"] == ["funding_24h_signed", "oi_change_24h", "spot_perp_volume_ratio"]
    assert out["schema"] == contracts.FEATURE_SCHEMA_VERSION


def test_tier_b_funding_sum_and_ratio():
    bars = _bars_4h(300)
    cutoff = bars[-1]["open_ms"] + 4 * HOUR
    funding = [{"ts_ms": cutoff - (i + 1) * HOUR, "rate": 0.0001} for i in range(24)]
    perp = [dict(b, quote_volume=50.0) for b in bars]
    out = tier_b(funding, [], bars, perp, cutoff)
    assert out["funding_24h_signed"] is not None
    assert abs(out["funding_24h_signed"] - 24 * 0.0001) < 1e-12
    assert out["spot_perp_volume_ratio"] is not None
    # A funding row after decision_time must not leak in.
    late = funding + [{"ts_ms": cutoff + HOUR, "rate": 1.0}]
    assert tier_b(late, [], bars, perp, cutoff) == out


def test_feature_row_never_drops_missingness():
    event = {"cutoff_ms": 10**12, "direction": "UP"}
    a = {"ret24_norm": 1.0, "rv_ratio_6_180": None, "rel_volume_24h": 2.0}
    b = {"funding_24h_signed": None, "oi_change_24h": None, "spot_perp_volume_ratio": 1.5}
    row = feature_row(event, a, b)
    assert "rv_ratio_6_180" in row["missing"]
    assert row["schema"] == "feat-v1"


def test_logreg_deterministic_and_degenerate_safe():
    train = [{"x": float(i), "success": 1 if i > 5 else 0} for i in range(12)]
    test = [{"x": 2.0}, {"x": 9.0}]
    p1, _ = fit_predict_fold(train, test, ["x"])
    p2, _ = fit_predict_fold(train, test, ["x"])
    assert p1 == p2
    assert p1[0] is not None and p1[1] is not None
    assert p1[1] > p1[0]
    one_sided = [{"x": 1.0, "success": 1} for _ in range(12)]
    probs, info = fit_predict_fold(one_sided, test, ["x"])
    assert probs == [None, None] and info["degenerate"]
    missing_test = [{"x": None}, {}]
    probs, info = fit_predict_fold(train, missing_test, ["x"])
    assert probs == [None, None] and info["test_missing"] == 2


def test_climatology_and_metrics_shapes():
    train = [{"success": 1}, {"success": 0}, {"success": 0}, {"success": 0}]
    assert climatology(train, [{}, {}]) == [0.25, 0.25]
    pr = precision_recall([0.9, 0.1, 0.8, 0.2], [1, 0, 0, 1], 2)
    assert pr["k"] == 2 and pr["precision"] == 0.5
    bl = brier_logloss([0.9, 0.1, 0.8, 0.2], [1, 0, 0, 1])
    assert bl["brier_skill"] is not None
    null = null_shift_pvalues([0.9, 0.1, 0.8, 0.2], [1, 0, 0, 1], annual_count=2, shifts=50)
    assert null["null_n"] == 50 and 0 <= null["empirical_p"] <= 1


def test_shadow_append_only_and_enrichment_separation(tmp_path):
    directory = str(tmp_path)
    rec = append_forecast(
        directory, decision_time="2026-01-01T00:05:00+00:00", cutoff_ms=10**12,
        candidate_state={"active": True}, features={"ret24_norm": 1.2},
        missing=[], model_output=0.6, commit="abc", fingerprints={"spot": "ff"})
    assert "outcome" not in json.dumps(rec)
    status = verify_log(directory)
    assert status["n_forecasts"] == 1 and status["monotonic_unique"]
    sha_before = status["forecast_sha256"]
    append_outcome(directory, record=rec, outcome={"outcome": "CONTINUES"})
    status2 = verify_log(directory)
    assert status2["forecast_sha256"] == sha_before
    assert status2["n_outcomes"] == 1
    assert len(read_forecasts(directory)) == 1
    try:
        append_forecast(
            directory, decision_time="2026-01-01T04:05:00+00:00", cutoff_ms=10**12 + 1,
            candidate_state={"outcome": "CONTINUES"}, features={}, missing=[],
            model_output=None, commit="abc", fingerprints={})
    except ValueError:
        pass
    else:
        raise AssertionError("outcome field accepted in forecast")


def test_census_deterministic_replay():
    bars_1h = _bars_1h(6000, drift=0.00003)
    from rocket.momentum.bars import aggregate_4h

    bars_4h = aggregate_4h(
        [{"open_ms": b["open_ms"], "open": b["close"], "high": b["high"], "low": b["low"],
          "close": b["close"], "volume": 1.0, "quote_volume": 1.0, "trades": 1,
          "vintage": "t", "ingested_at": "t", "event_time": "t", "available_at": "t",
          "close_ms": b["open_ms"], "close_time": "t", "timestamp_unit": "ms",
          "taker_base_volume": 0.0, "taker_quote_volume": 0.0} for b in bars_1h]
    )
    r1 = run_census(bars_4h, bars_1h, source_fingerprint="t")
    r2 = run_census(bars_4h, bars_1h, source_fingerprint="t")
    assert json.dumps(r1, sort_keys=True) == json.dumps(r2, sort_keys=True)
    assert r1["candidate_generator"] == "candgen-v1"
    assert "gate" in r1 and "verdict" in r1["gate"]


def test_parse_metrics_csv_vendor_snake_case():
    from rocket.momentum.features import parse_metrics_csv

    text = (
        "create_time,symbol,sum_open_interest,sum_open_interest_value\n"
        "2024-01-15 00:00:00,BTCUSDT,120000.5,5400000000.0\n"
        "2024-01-16 00:00:00,BTCUSDT,121000.0,5450000000.0\n"
    )
    rows = parse_metrics_csv(text)
    assert len(rows) == 2
    assert rows[0]["open_interest"] == 120000.5
    assert rows[0]["day"] < rows[1]["day"]
    # camelCase era still accepted
    legacy = "calc_time,sumOpenInterest\n1705276800000,999.0\n"
    assert parse_metrics_csv(legacy)[0]["open_interest"] == 999.0
    # unknown schema stays empty, never raises
    assert parse_metrics_csv("a,b\n1,2\n") == []


def test_tier_b_oi_change_wires_parsed_metrics_days():
    import math

    from rocket.momentum.features import tier_b

    cutoff = 1705363200000  # 2024-01-16T00:00:00Z, a day boundary
    d1 = 1705276800000  # 2024-01-15T00:00:00Z midnight ms
    d2 = 1705190400000  # 2024-01-14T00:00:00Z midnight ms
    metrics = [
        {"day": d2, "open_interest": 100.0, "available_at": "2024-01-15T00:00:00+00:00"},
        {"day": d1, "open_interest": 100.0, "available_at": "2024-01-16T00:00:00+00:00"},
        {"day": d1, "open_interest": 105.0, "available_at": "2024-01-16T00:00:00+00:00"},
    ]
    out = tier_b([], metrics, [], [], cutoff)
    assert out["oi_change_24h"] is not None
    assert abs(out["oi_change_24h"] - math.log(1.05)) < 1e-12
    assert "oi_change_24h" not in out["missing"]
