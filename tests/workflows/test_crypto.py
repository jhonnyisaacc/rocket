from datetime import UTC, datetime, timedelta

from rocket.models import Mode, ResearchStatus
from rocket.workflows.crypto import CryptoWorkflow, build_funnel, cot_regime_passes
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
