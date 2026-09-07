from datetime import UTC, datetime, timedelta

from rocket.models import Mode, OperationalStatus, ResearchStatus
from rocket.providers.protocols import ProviderResult
from rocket.workflows.crypto import (
    CryptoWorkflow,
    assess_live_liquidity,
    build_funnel,
    build_live_observation,
    cot_regime_passes,
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
    assert result.payload["funnel"]["universe_policy"] == "top_100_market_cap_plus_liquid_perps"


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
    by_symbol = {row["symbol"]: row for row in observation["candidates"]}
    assert by_symbol["BTC"]["ranking_state"] == "ELIGIBLE"
    assert by_symbol["BTC"]["venue"] == "hyperliquid"
    assert by_symbol["BTC"]["liquidity"]["state"] == "PASS"
    assert by_symbol["BTC"]["setup_validation"]["valid"] is False
    assert by_symbol["ALT"]["ranking_state"] == "UNKNOWN"
    assert by_symbol["ALT"]["venue"] is None
    members = observation["universe_members_deduplicated"]
    assert any(row["symbol"] == "KPEPE" and row["universe_source"] == "liquid_perpetual" for row in members)
    assert observation["join"]["joined_count"] == 1


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
        macro_context=_macro(),
        cot_regime="neutral",
        now=NOW,
    )
    assert_research_result(result)
    assert result.status is ResearchStatus.NO_SETUP
    assert result.operational.status is OperationalStatus.HEALTHY
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
    assert names == {"coingecko", "hyperliquid"}


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
        macro_context=_macro(),
        cot_regime="neutral",
        now=NOW,
    )
    assert_research_result(result)
    assert result.operational.status is OperationalStatus.PARTIAL
    assert result.status is ResearchStatus.INSUFFICIENT_EVIDENCE
    assert "hyperliquid perpetual metadata unavailable" in result.warnings
    assert result.payload["funnel"]["eligible"] == 0
    assert result.payload["observations"][0]["candidates"][0]["liquidity"]["state"] == "REJECT"
