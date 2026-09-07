from datetime import UTC, datetime
from pathlib import Path

import pytest

from rocket.models import OperationalStatus
from rocket.providers.hyperliquid import (
    HyperliquidPerps,
    fetch_perp_markets,
    overlay_l2_spread,
    parse_candles,
    parse_meta_and_asset_ctxs,
    spread_bps_from_book,
    spread_bps_from_impact,
)

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)
ROOT = Path(__file__).resolve().parents[2] / "rocket" / "providers" / "hyperliquid.py"


def sample_payload():
    return [
        {
            "universe": [
                {"name": "BTC", "szDecimals": 5, "maxLeverage": 40},
                {"name": "ALT", "szDecimals": 2, "maxLeverage": 10, "isDelisted": True},
                {"name": "ETH", "szDecimals": 4, "maxLeverage": 25},
            ]
        },
        [
            {
                "funding": "0.0001",
                "openInterest": "10",
                "dayNtlVlm": "1500000000",
                "markPx": "80000",
                "midPx": "80000.5",
                "impactPxs": ["79999", "80001"],
            },
            {
                "funding": "0",
                "openInterest": "1",
                "dayNtlVlm": "1",
                "markPx": "1",
                "midPx": "1",
                "impactPxs": ["1", "1.1"],
            },
            {
                "funding": "-0.00001",
                "openInterest": "20",
                "dayNtlVlm": "900000000",
                "markPx": "4000",
                "midPx": "4000",
                "impactPxs": ["3999.5", "4000.5"],
            },
        ],
    ]


def test_parse_skips_delisted_and_converts_open_interest_to_usd():
    records = parse_meta_and_asset_ctxs(sample_payload(), retrieved_at=NOW)
    names = [row["name"] for row in records]
    assert names == ["BTC", "ETH"]
    btc = records[0]
    assert btc["open_interest_usd"] == 800_000.0
    assert btc["day_notional_volume"] == 1_500_000_000.0
    assert btc["spread_bps"] == pytest.approx(0.25, rel=1e-6)
    assert btc["slippage_bps"] == pytest.approx(0.125, rel=1e-6)


def test_spread_helpers():
    assert spread_bps_from_impact(["100", "100.2"]) == pytest.approx(19.98001998, rel=1e-9)
    assert spread_bps_from_impact(["100", "90"]) is None
    book = {"levels": [[{"px": "99.99", "sz": "1"}], [{"px": "100.01", "sz": "1"}]]}
    assert spread_bps_from_book(book) == pytest.approx(2.0, rel=1e-3)


def test_l2_overlay_replaces_impact_spread():
    records = parse_meta_and_asset_ctxs(sample_payload(), retrieved_at=NOW)
    overlaid = overlay_l2_spread(
        records,
        {"BTC": {"levels": [[{"px": "100"}], [{"px": "100.1"}]]}},
    )
    assert overlaid[0]["spread_source"] == "l2Book"
    assert overlaid[0]["spread_bps"] == pytest.approx(9.995, rel=1e-3)


def test_fetch_uses_injected_http():
    class _Response:
        def raise_for_status(self):
            return None

        def json(self):
            return sample_payload()

    class _Client:
        def post(self, url, json):
            assert url.endswith("/info")
            assert json == {"type": "metaAndAssetCtxs"}
            return _Response()

        def close(self):
            raise AssertionError("injected client must not be closed")

    result = fetch_perp_markets(http=_Client(), now=NOW)
    assert result.status is OperationalStatus.HEALTHY
    assert result.source == "hyperliquid"
    assert result.extras["signing"] is False
    assert HyperliquidPerps(http=_Client()).fetch(now=NOW).status is OperationalStatus.HEALTHY


def test_fetch_failure_is_unavailable():
    class _Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"unexpected": True}

    class _Client:
        def post(self, url, json):
            return _Response()

    result = fetch_perp_markets(http=_Client(), now=NOW)
    assert result.status is OperationalStatus.UNAVAILABLE
    assert result.failure_kind == "ValueError"


def test_parse_candles_sorts_and_drops_invalid():
    rows = parse_candles(
        [
            {"t": 2_000, "o": "2", "h": "3", "l": "1", "c": "2.5", "v": "10", "s": "BTC", "i": "4h"},
            {"t": 1_000, "o": "1", "h": "1.5", "l": "0.5", "c": "1.2", "v": "8", "s": "BTC", "i": "4h"},
            {"t": 3_000, "o": "0", "h": "0", "l": "0", "c": "0", "v": "1"},
        ]
    )
    assert [row["timestamp_ms"] for row in rows] == [1_000, 2_000]
    assert rows[0]["source"] == "hyperliquid"


def test_module_never_signs():
    text = ROOT.read_text(encoding="utf-8")
    for marker in ("private_key", "eth_account", "wallet_name", "HL_WALLET", "Exchange("):
        assert marker not in text


@pytest.mark.integration
def test_hyperliquid_mainnet_info_smoke():
    result = fetch_perp_markets()
    assert result.status is OperationalStatus.HEALTHY
    assert any(row["name"] == "BTC" for row in result.records)
