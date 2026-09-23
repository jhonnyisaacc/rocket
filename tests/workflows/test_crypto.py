from datetime import UTC, datetime, timedelta

from rocket.models import Mode, OperationalStatus, ResearchStatus
from rocket.providers.protocols import ProviderResult
from rocket.workflows.crypto import (
    CryptoWorkflow,
    assess_live_liquidity,
    build_funnel,
    build_live_observation,
    cot_regime_passes,
    setup_from_candles,
    trade_decision,
)
from rocket.workflows.macro import MacroWorkflow
from tests.harness import assert_research_result, is_registered

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def _macro():
    def fetcher(symbol: str):
        records = [
            {"date": (NOW - timedelta(days=28)).date().isoformat(), "value": 10},
            {"date": NOW.date().isoformat(), "value": 10},
        ]
        return {"records": records, "retrieved_at": NOW.isoformat()}, "fixture"

    return MacroWorkflow(fetcher=fetcher).run(now=NOW).payload


def candidate(*, symbol="ALT", rank=90, liquidity="PASS", setup_valid=True, direction="long"):
    return {
        "symbol": symbol,
        "canonical_asset_id": symbol.lower(),
        "ranking_state": "ELIGIBLE" if rank >= 80 else "BELOW_RANK_THRESHOLD",
        "rank_score": rank,
        "features": {"data_timestamp": NOW.isoformat(), "data_source": "fixture"},
        "liquidity": {"state": liquidity},
        "setup_validation": {
            "valid": setup_valid,
            "direction": direction,
            "entry_zone": [100.0, 101.0],
            "invalidation": 95.0,
        },
        "observation_timestamp": NOW.isoformat(),
    }


def replay(*candidates):
    return {
        "observations": [
            {
                "observation_timestamp": NOW.isoformat(),
                "source": "fixture",
                "source_timestamp": NOW.isoformat(),
                "universe_members_deduplicated": [
                    {"symbol": item["symbol"], "canonical_asset_id": item["canonical_asset_id"]}
                    for item in candidates
                ],
                "candidates": list(candidates),
            }
        ]
    }


def test_crypto_is_registered():
    assert is_registered("crypto.scan")


def test_trade_decision_normalizes_single_direction():
    assert trade_decision(
        [{"direction": "long"}],
        research=ResearchStatus.SETUP_FOUND,
        operational=OperationalStatus.HEALTHY,
    ) == {
        "direction": "LONG",
        "reason": "eligible_funnel_setup",
        "candidate_count": 1,
    }


def test_trade_decision_fails_closed_for_ambiguity_or_partial_data():
    assert trade_decision(
        [{"direction": "long"}, {"direction": "short"}],
        research=ResearchStatus.SETUP_FOUND,
        operational=OperationalStatus.HEALTHY,
    )["direction"] == "NO_TRADE"
    assert trade_decision(
        [{"direction": "short"}],
        research=ResearchStatus.SETUP_FOUND,
        operational=OperationalStatus.PARTIAL,
    )["reason"] == "operational_data_not_healthy"


def test_cot_is_market_regime_not_alt_signal():
    assert cot_regime_passes("bullish", "long") is True
    assert cot_regime_passes("bearish", "long") is False
    assert cot_regime_passes("neutral", "short") is True
    assert cot_regime_passes("bullish", None) is False


def test_funnel_suppresses_without_macro():
    funnel, final, _ = build_funnel(replay(candidate()), cot_regime="neutral")
    assert funnel["universe"] == 1
    assert funnel["universe_size_target"] == 100
    assert funnel["eligible"] == 1
    assert funnel["final_candidates"] == 0
    assert final == []


def test_macro_and_cot_produce_candidate(tmp_path):
    from rocket.store import ResearchStore

    result = CryptoWorkflow(store=ResearchStore(tmp_path)).scan_payload(
        replay(candidate()),
        macro_context=_macro(),
        cot_regime="neutral",
        mode=Mode.REPLAY,
        now=NOW,
    )
    assert_research_result(result)
    assert result.status is ResearchStatus.SETUP_FOUND
    assert result.payload["funnel"]["final_candidates"] == 1
    assert result.payload["funnel"]["universe_policy"] == "top_100_market_cap_intersect_hyperliquid_perps"
    assert result.payload["trade_decision"]["direction"] == "LONG"
    assert result.payload["final_candidates"][0]["mark_price"] is None


def test_cava_missing_does_not_block_scan(tmp_path):
    from rocket.store import ResearchStore

    result = CryptoWorkflow(store=ResearchStore(tmp_path)).scan_payload(
        replay(candidate()),
        macro_context=_macro(),
        cot_regime="neutral",
        cava_context={"validated": False},
        mode=Mode.REPLAY,
        now=NOW,
    )
    assert_research_result(result)
    assert result.status is ResearchStatus.SETUP_FOUND
    assert result.payload["cava_context_status"] == "insufficient"


def _cap(symbol, canonical, rank):
    return {
        "symbol": symbol,
        "canonical_asset_id": canonical,
        "rank": rank,
        "universe_source": "current_top_market_cap",
    }


def _perp(name, *, volume=1_500_000_000, oi=2_000_000_000, spread=0.5, **extra):
    row = {
        "name": name,
        "day_notional_volume": volume,
        "open_interest_usd": oi,
        "spread_bps": spread,
        "slippage_bps": (spread / 2) if isinstance(spread, (int, float)) and not isinstance(spread, bool) else None,
        "mark_px": 100.0,
        "funding": 0.0,
    }
    row.update(extra)
    return row


def test_join_requires_unambiguous_ticker():
    observation = build_live_observation(
        [
            _cap("BTC", "bitcoin", 1),
            _cap("ALT", "alt-one", 2),
            _cap("ALT", "alt-two", 3),
        ],
        [_perp("BTC"), _perp("ALT"), _perp("KPEPE")],
        now=NOW,
    )
    assert [row["symbol"] for row in observation["candidates"]] == ["BTC"]
    btc = observation["candidates"][0]
    assert btc["ranking_state"] == "ELIGIBLE"
    assert btc["venue"] == "hyperliquid"
    assert btc["liquidity"]["state"] == "PASS"
    assert btc["setup_validation"]["valid"] is False
    assert all(row["symbol"] != "KPEPE" for row in observation["universe_members_deduplicated"])
    assert observation["join"]["joined_count"] == 1
    assert observation["join"]["top100_count"] == 3
    assert {item["reason"] for item in observation["join"]["perp_gap"]} == {"ambiguous_symbol"}
    assert [item["symbol"] for item in observation["join"]["perp_gap"]] == ["ALT", "ALT"]


def test_unique_k_prefix_is_a_perp_and_unlisted_names_are_gaps():
    observation = build_live_observation(
        [_cap("PEPE", "pepe", 50), _cap("USDT", "tether", 3)],
        [_perp("KPEPE"), _perp("BTC")],
        now=NOW,
    )
    assert [row["symbol"] for row in observation["candidates"]] == ["PEPE"]
    assert observation["candidates"][0]["contract_symbol"] == "KPEPE"
    assert observation["candidates"][0]["ranking_state"] == "ELIGIBLE"
    assert observation["join"]["mapped_perp_count"] == 1
    assert observation["join"]["perp_gap"] == [
        {
            "symbol": "USDT",
            "canonical_asset_id": "tether",
            "rank": 3,
            "reason": "no_hyperliquid_perp",
        }
    ]


def test_liquidity_unknown_when_spread_missing():
    assessment = assess_live_liquidity(_perp("BTC", spread=None))
    assert assessment["state"] == "UNKNOWN"
    assert "spread_bps" in assessment["reasons"]


def test_liquidity_rejects_thin_book():
    assessment = assess_live_liquidity(_perp("THIN", volume=100.0, oi=100.0, spread=1.0))
    assert assessment["state"] == "REJECT"
    assert "quote_volume_below_minimum" in assessment["reasons"]


def test_scan_live_joins_hyperliquid_without_imputing_setups(tmp_path):
    from rocket.store import ResearchStore

    universe = ProviderResult(
        status=OperationalStatus.HEALTHY,
        records=(_cap("BTC", "bitcoin", 1), _cap("ETH", "ethereum", 2)),
        source="coingecko",
    )
    perps = ProviderResult(
        status=OperationalStatus.HEALTHY,
        records=(_perp("BTC"), _perp("ETH", volume=100.0, oi=100.0)),
        source="hyperliquid",
    )
    result = CryptoWorkflow(store=ResearchStore(tmp_path)).scan_live(
        universe=universe,
        perps=perps,
        candles={},
        macro_context=_macro(),
        cot_regime="neutral",
        now=NOW,
    )
    assert_research_result(result)
    assert result.status is ResearchStatus.INSUFFICIENT_EVIDENCE
    assert result.payload["funnel"]["incomplete_evaluations"] == 1
    assert any(p.name == "hyperliquid.candles:BTC" and p.status is OperationalStatus.UNAVAILABLE for p in result.operational.providers)
    assert result.reasons[0].code.value == "REQUIRED_PROVIDER_UNAVAILABLE"
    assert "hyperliquid.candles:BTC" in result.reasons[0].missing
    assert result.operational.status is OperationalStatus.PARTIAL
    funnel = result.payload["funnel"]
    assert funnel["universe"] == 2
    assert funnel["eligible"] == 2
    assert funnel["liquid"] == 1
    assert funnel["momentum_pass"] == 0
    assert funnel["final_candidates"] == 0
    observation = result.payload["observations"][0]
    assert observation["source"] == "live:CoinGecko+Hyperliquid"
    assert observation["candidates"][0]["setup_validation"]["valid"] is False
    names = {item.name for item in result.operational.providers}
    assert {"coingecko", "hyperliquid", "macro"} <= names


def test_scan_live_hyperliquid_down_is_partial(tmp_path):
    from rocket.store import ResearchStore

    universe = ProviderResult(
        status=OperationalStatus.HEALTHY,
        records=(_cap("BTC", "bitcoin", 1),),
        source="coingecko",
    )
    perps = ProviderResult(status=OperationalStatus.UNAVAILABLE, failure_kind="HTTPError", source="hyperliquid")
    result = CryptoWorkflow(store=ResearchStore(tmp_path)).scan_live(
        universe=universe,
        perps=perps,
        candles={},
        macro_context=_macro(),
        cot_regime="neutral",
        now=NOW,
    )
    assert_research_result(result)
    assert result.operational.status is OperationalStatus.PARTIAL
    assert result.status is ResearchStatus.INSUFFICIENT_EVIDENCE
    assert "hyperliquid perpetual metadata unavailable" in result.warnings
    assert result.payload["funnel"]["eligible"] == 0
    assert result.payload["observations"][0]["candidates"] == []
    assert result.payload["perp_gap"][0]["reason"] == "perpetual_metadata_unavailable"
    assert result.payload["perp_gap_count"] == 1


def _rising_4h(n=30):
    start_ms = int(NOW.timestamp() * 1000) - n * 4 * 3600 * 1000
    rows = []
    for index in range(n):
        base = 100.0 + index
        ts = start_ms + index * 4 * 3600 * 1000
        rows.append(
            {
                "timestamp_ms": ts,
                "timestamp": datetime.fromtimestamp(ts / 1000, UTC).isoformat(),
                "open": base,
                "high": base + 2,
                "low": base - 0.4,
                "close": base + 1,
                "volume": 10.0,
            }
        )
    return rows


def test_setup_from_rising_structure_is_long():
    setup = setup_from_candles(_rising_4h())
    assert setup["valid"] is True
    assert setup["direction"] == "long"
    assert setup["entry_zone"][0] < setup["entry_zone"][1]


def test_setup_without_history_stays_invalid():
    setup = setup_from_candles(_rising_4h(3))
    assert setup["valid"] is False
    assert setup["reason"] == "insufficient_4h_history"


def test_scan_live_uses_injected_candles_for_setup(tmp_path):
    from rocket.store import ResearchStore

    universe = ProviderResult(
        status=OperationalStatus.HEALTHY,
        records=(_cap("BTC", "bitcoin", 1),),
        source="coingecko",
    )
    perps = ProviderResult(status=OperationalStatus.HEALTHY, records=(_perp("BTC"),), source="hyperliquid")
    result = CryptoWorkflow(store=ResearchStore(tmp_path)).scan_live(
        universe=universe,
        perps=perps,
        candles={"BTC": _rising_4h()},
        macro_context=_macro(),
        cot_regime="neutral",
        now=NOW,
    )
    assert_research_result(result)
    assert result.status is ResearchStatus.SETUP_FOUND
    assert result.payload["funnel"]["momentum_pass"] == 1
    assert result.payload["funnel"]["derivatives_pass"] == 1
    assert result.payload["final_candidates"][0]["direction"] == "long"
    assert result.payload["trade_decision"]["direction"] == "LONG"
    assert result.payload["final_candidates"][0]["mark_price"] == 100.0


def test_unknown_cot_does_not_veto_valid_setup():
    funnel, final, _ = build_funnel(replay(candidate()), macro_context=_macro(), cot_regime="unknown")
    assert funnel["cot_regime"] == "unknown"
    assert funnel["final_candidates"] == 1
    assert final


def test_stale_cot_context_fails_open(tmp_path):
    from rocket.store import ResearchStore

    result = CryptoWorkflow(store=ResearchStore(tmp_path)).scan_payload(
        replay(candidate()),
        macro_context=_macro(),
        cot_context={"status": "STALE", "regime": "bearish", "warnings": ["COT report is stale; no directional COT gate was applied"]},
        mode=Mode.REPLAY,
        now=NOW,
    )
    assert_research_result(result)
    assert result.status is ResearchStatus.SETUP_FOUND
    assert any("COT is not applied as an asset-level signal" in warning for warning in result.warnings)


def test_setup_rejects_extended_print():
    bars = _rising_4h()
    last = dict(bars[-1])
    last["close"] = last["high"] * 1.05
    last["high"] = last["close"]
    setup = setup_from_candles([*bars[:-1], last])
    assert setup["valid"] is False
    assert setup["reason"] == "extended_beyond_retest_band"


def _timed_bars(closes, *, interval_ms, decision=NOW, highs=None, lows=None):
    rows = []
    count = len(closes)
    end_ms = int(decision.timestamp() * 1000)
    for index, close in enumerate(closes):
        open_ms = end_ms - (count - index) * interval_ms
        high = highs[index] if highs is not None else close + 1
        low = lows[index] if lows is not None else max(close - 1, 0.1)
        rows.append(
            {
                "timestamp_ms": open_ms,
                "timestamp": datetime.fromtimestamp(open_ms / 1000, UTC).isoformat(),
                "open": close,
                "high": high,
                "low": low,
                "close": close,
                "volume": 1.0,
            }
        )
    return rows


def _bias_bars(direction, *, interval_ms, count):
    if direction == "long":
        closes = [100 + index * 5 for index in range(count)]
    else:
        closes = [100 + (count - index) * 5 for index in range(count)]
    return _timed_bars(closes, interval_ms=interval_ms)


def _impulse_4h(last_close, *, last_high=None, last_low=None):
    highs = [120, 130, 140, 150, 160, 170, 180, 190, 200, 190, 180, 170, 175, 160, 165, 155]
    lows = [100, 110, 115, 120, 125, 130, 135, 140, 150, 155, 140, 145, 130, 135, 125, 120]
    closes = [110, 120, 130, 140, 150, 160, 170, 180, 190, 170, 160, 155, 150, 145, 140, last_close]
    highs = highs[:-1] + [last_close + 5 if last_high is None else last_high]
    lows = lows[:-1] + [max(last_close - 5, 1) if last_low is None else last_low]
    return _timed_bars(closes, interval_ms=4 * 3600 * 1000, highs=highs, lows=lows)


def _staged_scan(tmp_path, *, candles, daily, weekly, cot_regime="neutral", cot_context=None, names=None):
    from rocket.store import ResearchStore

    symbols = names or list(candles)
    universe = ProviderResult(
        status=OperationalStatus.HEALTHY,
        records=tuple(_cap(name, name.lower(), index + 1) for index, name in enumerate(symbols)),
        source="coingecko",
    )
    perps = ProviderResult(
        status=OperationalStatus.HEALTHY,
        records=tuple(_perp(name) for name in symbols),
        source="hyperliquid",
    )
    return CryptoWorkflow(store=ResearchStore(tmp_path)).scan_live(
        universe=universe,
        perps=perps,
        candles=candles,
        daily_candles=daily,
        weekly_candles=weekly,
        macro_context=_macro(),
        cot_regime=cot_regime,
        cot_context=cot_context,
        now=NOW,
    )


def test_staged_scan_shows_zone_extended_in_play_and_no_bias(tmp_path):
    week = 7 * 24 * 3600 * 1000
    day = 24 * 3600 * 1000
    weekly_long = _bias_bars("long", interval_ms=week, count=6)
    future_open = int(NOW.timestamp() * 1000) + week
    in_progress_open = int(NOW.timestamp() * 1000) - day
    crash = {
        "timestamp_ms": future_open,
        "timestamp": datetime.fromtimestamp(future_open / 1000, UTC).isoformat(),
        "open": 1.0,
        "high": 1.2,
        "low": 0.8,
        "close": 1.0,
        "volume": 1.0,
    }
    forming = {**crash, "timestamp_ms": in_progress_open}
    weekly = weekly_long + [forming, crash]
    daily_long = _bias_bars("long", interval_ms=day, count=8)
    daily_short = _bias_bars("short", interval_ms=day, count=8)
    candles = {
        "BTC": _impulse_4h(130),
        "ETH": _impulse_4h(190, last_high=195, last_low=180),
        "XRP": _impulse_4h(105, last_high=140, last_low=100),
        "SOL": _impulse_4h(130),
    }
    daily = {name: daily_long for name in ("BTC", "ETH", "XRP")}
    daily["SOL"] = daily_short
    weekly_map = {name: weekly for name in candles}
    result = _staged_scan(
        tmp_path,
        candles=candles,
        daily=daily,
        weekly=weekly_map,
        cot_regime="bearish",
    )
    assert_research_result(result)
    assert result.payload["execution_enabled"] is False
    assert result.payload["cot_scope"] == "market/regime context; no per-altcoin COT signal"
    assert "PR #28" in result.payload["theory_note"]
    assert result.payload["funnel"]["cot_scope"] == result.payload["cot_scope"]
    book = {row["asset"]: row for row in result.payload["candidates"]}
    required = {
        "asset",
        "asset_key",
        "venue",
        "contract_symbol",
        "state",
        "direction",
        "reasons",
        "weekly_bias",
        "daily_bias",
        "momentum",
        "cot_regime",
        "cot_alignment",
        "structure_4h",
        "entry_research_zone",
        "invalidation",
        "mark_price",
        "funding",
        "quote_volume_24h",
        "open_interest_usd",
        "evaluated",
    }
    assert required <= set(book["BTC"])
    assert book["BTC"]["state"] == "ZONE"
    assert book["BTC"]["direction"] == "long"
    assert book["BTC"]["weekly_bias"] == "long"
    assert book["BTC"]["daily_bias"] == "long"
    assert book["BTC"]["structure_4h"] == "MIXED"
    assert book["BTC"]["cot_regime"] == "bearish"
    assert book["BTC"]["cot_alignment"] == "against"
    assert "action" not in book["BTC"]
    assert result.payload["bot_decision"]["action"] is None
    assert result.payload["bot_decision"]["reason"] == "cot_alignment_labeled"
    assert result.payload["bot_decision"]["cot_regime"] == "bearish"
    assert result.payload["cot_regime"] == "bearish"
    assert book["BTC"]["evaluated"] is True
    assert book["BTC"]["entry_research_zone"][0] < 130 < book["BTC"]["entry_research_zone"][1]
    assert "mixed_4h_structure" in book["BTC"]["reasons"]
    assert "research_interpretation_retracement_50_86" in book["BTC"]["reasons"]
    assert "weekly_close_change=" in book["BTC"]["momentum"]
    assert book["ETH"]["state"] == "EXTENDED"
    assert book["ETH"]["direction"] == "long"
    assert book["XRP"]["state"] == "IN_PLAY"
    assert book["XRP"]["direction"] == "long"
    assert book["SOL"]["state"] == "NO_BIAS"
    assert book["SOL"]["direction"] == "none"
    assert "weekly_daily_disagree" in book["SOL"]["reasons"]
    assert result.payload["funnel"]["staged_states"]["ZONE"] == 1
    assert result.payload["funnel"]["staged_states"]["EXTENDED"] == 1
    assert all(row["asset"] != "BTC" for row in result.payload["final_candidates"])


def test_missing_candles_stay_unevaluated(tmp_path):
    result = _staged_scan(
        tmp_path,
        candles={},
        daily={},
        weekly={},
        names=["BTC"],
        cot_context={"status": "UNAVAILABLE", "regime": "bullish", "warnings": []},
    )
    assert_research_result(result)
    row = result.payload["candidates"][0]
    assert row["asset"] == "BTC"
    assert row["evaluated"] is False
    assert row["state"] == "NO_TRADE"
    assert row["weekly_bias"] == "UNKNOWN"
    assert row["daily_bias"] == "UNKNOWN"
    assert row["cot_regime"] == "unknown"
    assert row["cot_alignment"] == "unknown"
    assert result.payload["execution_enabled"] is False


def test_unknown_cot_does_not_wipe_staged_rows(tmp_path):
    week = 7 * 24 * 3600 * 1000
    day = 24 * 3600 * 1000
    result = _staged_scan(
        tmp_path,
        candles={"BTC": _impulse_4h(130)},
        daily={"BTC": _bias_bars("long", interval_ms=day, count=8)},
        weekly={"BTC": _bias_bars("long", interval_ms=week, count=6)},
        cot_context={"status": "STALE", "regime": "bearish", "warnings": ["stale"]},
    )
    assert_research_result(result)
    row = result.payload["candidates"][0]
    assert row["state"] == "ZONE"
    assert row["cot_regime"] == "unknown"
    assert row["cot_alignment"] == "unknown"
    assert row["action"] == "WAIT"
    assert "cot_regime_unknown" in row["reasons"]
    assert row["evaluated"] is True
    assert result.payload["bot_decision"]["action"] == "WAIT"
    assert result.payload["bot_decision"]["reason"] == "cot_regime_unknown"
    assert result.payload["bot_decision"]["regime_required"] is True
    assert result.payload["execution_enabled"] is False


def test_crypto_scan_does_not_import_cava():
    from pathlib import Path

    text = Path("rocket/workflows/crypto.py").read_text(encoding="utf-8")
    assert "import cava" not in text
    assert "workflows.cava" not in text
    assert "providers.cava" not in text
    assert "fetch_closed_candles" in text
    assert "fetch_setup_candles" in text


def test_scan_live_macro_down_is_not_healthy(tmp_path):
    from rocket.store import ResearchStore

    universe = ProviderResult(
        status=OperationalStatus.HEALTHY,
        records=(_cap("BTC", "bitcoin", 1),),
        source="coingecko",
    )
    perps = ProviderResult(status=OperationalStatus.HEALTHY, records=(_perp("BTC"),), source="hyperliquid")
    result = CryptoWorkflow(store=ResearchStore(tmp_path)).scan_live(
        universe=universe,
        perps=perps,
        candles={},
        macro_context={"contract": "current_macro_v1", "status": "UNAVAILABLE"},
        cot_regime="neutral",
        now=NOW,
    )
    assert_research_result(result)
    assert result.operational.status is OperationalStatus.PARTIAL
    assert result.status is ResearchStatus.INSUFFICIENT_EVIDENCE
    assert any(item.name == "macro" and item.status is OperationalStatus.UNAVAILABLE for item in result.operational.providers)


def _book_row(*, cot_regime="unknown", direction="long", state="ZONE"):
    raw = candidate(symbol="BTC")
    raw["research_stage"] = {
        "asset": "BTC",
        "asset_key": "canonical:btc",
        "venue": "hyperliquid",
        "contract_symbol": "BTC",
        "state": state,
        "direction": direction,
        "reasons": ["inside_research_band"],
        "weekly_bias": direction if direction in {"long", "short"} else "UNKNOWN",
        "daily_bias": direction if direction in {"long", "short"} else "UNKNOWN",
        "momentum": "fixture",
        "cot_regime": cot_regime,
        "cot_alignment": "unknown",
        "structure_4h": "MIXED",
        "entry_research_zone": [1.0, 2.0],
        "invalidation": 0.5,
        "evaluated": True,
    }
    return raw


def test_replay_that_claims_regime_is_not_left_unknown(tmp_path):
    from rocket.store import ResearchStore

    result = CryptoWorkflow(store=ResearchStore(tmp_path)).scan_payload(
        replay(_book_row(cot_regime="unknown")),
        macro_context=_macro(),
        cot_regime="bearish",
        mode=Mode.REPLAY,
        now=NOW,
    )
    assert_research_result(result)
    row = result.payload["candidates"][0]
    assert row["state"] == "ZONE"
    assert row["cot_regime"] == "bearish"
    assert row["cot_alignment"] == "against"
    assert "action" not in row
    assert result.payload["cot_regime"] == "bearish"
    assert result.payload["funnel"]["cot_regime"] == "bearish"
    assert result.payload["bot_decision"]["reason"] == "cot_alignment_labeled"
    assert result.payload["bot_decision"]["action"] is None
    assert result.payload["execution_enabled"] is False
    assert "ENTER_LONG" not in str(result.payload["bot_decision"])
    assert "ENTER_SHORT" not in str(result.payload["bot_decision"])


def test_replay_row_keeps_a_regime_it_already_claimed(tmp_path):
    from rocket.store import ResearchStore

    result = CryptoWorkflow(store=ResearchStore(tmp_path)).scan_payload(
        replay(_book_row(cot_regime="bullish")),
        macro_context=_macro(),
        mode=Mode.REPLAY,
        now=NOW,
    )
    assert_research_result(result)
    row = result.payload["candidates"][0]
    assert row["cot_regime"] == "bullish"
    assert row["cot_alignment"] == "aligned"
    assert row["state"] == "ZONE"
    assert result.payload["cot_regime"] == "bullish"
    assert result.payload["bot_decision"]["cot_status"] == "CLAIMED"


def test_stale_report_waits_and_keeps_the_row(tmp_path):
    from rocket.store import ResearchStore

    result = CryptoWorkflow(store=ResearchStore(tmp_path)).scan_payload(
        replay(_book_row(cot_regime="bearish")),
        macro_context=_macro(),
        cot_context={
            "status": "STALE",
            "regime": "bearish",
            "warnings": ["COT report is stale; no directional COT gate was applied"],
        },
        mode=Mode.REPLAY,
        now=NOW,
    )
    assert_research_result(result)
    row = result.payload["candidates"][0]
    assert row["state"] == "ZONE"
    assert row["direction"] == "long"
    assert row["cot_regime"] == "unknown"
    assert row["cot_alignment"] == "unknown"
    assert row["action"] == "WAIT"
    assert "cot_regime_unknown" in row["reasons"]
    assert result.payload["candidates"]
    assert result.payload["bot_decision"] == {
        "action": "WAIT",
        "reason": "cot_regime_unknown",
        "regime_required": True,
        "cot_regime": "unknown",
        "cot_status": "STALE",
    }
    assert result.payload["execution_enabled"] is False
