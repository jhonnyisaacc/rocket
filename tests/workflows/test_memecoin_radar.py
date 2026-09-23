import json
from datetime import UTC, datetime, timedelta

import httpx

from rocket.capture.spool import RawCaptureSpool
from rocket.models import OperationalStatus, ResearchStatus
from rocket.workflows.memecoin import canonical_identity
from rocket.workflows.memecoin_radar import (
    AGE_FLOOR_SECONDS,
    LIQUIDITY_FLOOR_USD,
    PUMP_COINS_URL,
    SAFETY_SENTENCE,
    collect_snapshot,
    confirm_helius,
    discover,
    normalize_pump_coin,
    scan_feed,
    scan_spool,
)
from tests.harness import assert_research_result

NOW = datetime(2026, 9, 23, 7, 15, tzinfo=UTC)
MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
TOKEN_PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"


def _row(**overrides):
    base = {
        "schema": "rocket.memecoin-intake.v0",
        "chain_id": "solana:mainnet",
        "mint": MINT,
        "asset": "LABEL",
        "source": "browser:pump.fun",
        "sources": ["browser:pump.fun"],
        "source_urls": ["https://pump.fun/explore"],
        "event_time": (NOW - timedelta(hours=2)).isoformat(),
        "available_at": NOW.isoformat(),
        "discovered_at": (NOW - timedelta(hours=2)).isoformat(),
        "graduation_status": "graduated",
        "window_state": "closed",
        "liquidity_usd": LIQUIDITY_FLOOR_USD,
        "social_heat": "unknown",
        "bundle_or_dev_hold": "UNKNOWN",
    }
    base.update(overrides)
    return base


def _confirmed(**overrides):
    row = _row(**overrides)
    row["helius"] = {"mint_exists": True, "pool_exists": True, "top1_holder_bps": 250, "dev_hold": "UNKNOWN"}
    row["sources"] = ["browser:pump.fun", "helius"]
    row["bundle_or_dev_hold"] = {"top1_holder_bps": 250, "dev_hold": "UNKNOWN"}
    return row


def test_identity_fixture_is_solana_mainnet():
    assert canonical_identity(_row()) == "solana:mainnet:" + MINT


def test_empty_intake_is_healthy_and_selects_nothing():
    result = scan_feed([], now=NOW)
    assert_research_result(result)
    assert result.operational.status is OperationalStatus.HEALTHY
    assert result.payload["selected"] == []
    assert result.payload["edge"] == "NO_EDGE_VALIDATED"
    assert result.payload["execution_enabled"] is False
    assert result.payload["safety"] == SAFETY_SENTENCE
    assert result.payload["coverage_status"] == "EMPTY_INTAKE"
    text = json.dumps(result.to_dict())
    assert "not evidence that no memecoins exist" in text


def test_bad_mint_is_rejected():
    result = scan_feed([_row(mint="not-a-mint")], now=NOW)
    assert_research_result(result)
    assert result.payload["selected"] == []
    assert any(row.get("reason") == "unknown_identity" for row in result.payload["rejected"])


def test_future_available_at_is_ineligible():
    result = scan_feed([_confirmed(available_at=(NOW + timedelta(seconds=5)).isoformat())], now=NOW)
    assert_research_result(result)
    assert result.payload["selected"] == []
    assert any(row.get("reason") == "future_available_at" for row in result.payload["rejected"])


def test_edge_field_present_and_execution_disabled():
    result = scan_feed([_confirmed()], now=NOW)
    assert_research_result(result)
    assert result.payload["edge"] == "NO_EDGE_VALIDATED"
    assert result.payload["execution_enabled"] is False
    assert result.status is ResearchStatus.INSUFFICIENT_EVIDENCE


def test_browser_only_row_cannot_be_watch():
    result = scan_feed([_row()], now=NOW)
    assert_research_result(result)
    assert result.payload["selected"]
    assert result.payload["selected"][0]["state"] == "UNKNOWN"
    assert "helius_confirm_missing" in result.payload["selected"][0]["reasons"]
    assert all(row["state"] != "WATCH" for row in result.payload["selected"])


def test_confirmed_row_meeting_floors_is_watch_and_not_an_entry():
    result = scan_feed([_confirmed()], now=NOW)
    assert_research_result(result)
    row = result.payload["selected"][0]
    assert row["state"] == "WATCH"
    assert row["age_seconds"] >= AGE_FLOOR_SECONDS
    assert row["liquidity_usd"] >= LIQUIDITY_FLOOR_USD
    assert "floors_met_not_an_entry" in row["reasons"]
    assert result.payload["notice"] == "A WATCH row is not a buy."


def test_too_new_confirmed_row_is_not_watch():
    fresh = _confirmed(event_time=(NOW - timedelta(seconds=10)).isoformat())
    result = scan_feed([fresh], now=NOW)
    assert result.payload["selected"][0]["state"] == "AVOID"
    assert "below_age_floor" in result.payload["selected"][0]["reasons"]


def test_market_cap_is_not_liquidity_and_zero_reserves_stay_unknown():
    graduated = {
        "mint": MINT,
        "symbol": "LABEL",
        "complete": True,
        "chain_id": "solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp",
        "created_timestamp": int((NOW - timedelta(hours=3)).timestamp() * 1000),
        "usd_market_cap": 9_000_000,
        "real_quote_reserves": 0,
        "quote_mint": "So11111111111111111111111111111111111111112",
        "pump_swap_pool": "B973QMT3E6AFKJY8SSSsYib5MJzCBWa6xSNQs4zPAzgy",
    }
    row = normalize_pump_coin(graduated, now=NOW, sol_usd=200)
    assert row["liquidity_usd"] is None
    assert row["advertised_market_cap_usd"] == 9_000_000
    assert row["chain_id"] == "solana:mainnet"
    funded = dict(graduated, real_quote_reserves=85_005_359_057)
    liquid = normalize_pump_coin(funded, now=NOW, sol_usd=200)
    assert liquid["liquidity_usd"] == round(85_005_359_057 / 1_000_000_000 * 200, 2)
    assert liquid["liquidity_usd"] > LIQUIDITY_FLOOR_USD


def test_spool_feed_ranks_browser_row_without_calling_helius(tmp_path):
    spool = RawCaptureSpool(tmp_path / "spool", max_bytes=1024 * 1024, reserve_bytes=1)
    collected = collect_snapshot(spool, now=NOW, observations=[_row()])
    spool.close()
    assert_research_result(collected)
    assert collected.payload["edge"] == "NO_EDGE_VALIDATED"
    assert collected.payload["execution_enabled"] is False
    assert collected.payload["helius_key_present"] is False
    scanned = scan_spool(tmp_path / "spool", now=NOW)
    assert_research_result(scanned)
    assert scanned.payload["selected"][0]["state"] != "WATCH"
    assert scanned.payload["coverage_status"] != "DATA_UNAVAILABLE"


def test_missing_spool_is_data_unavailable_not_an_empty_market(tmp_path):
    result = scan_spool(tmp_path / "missing", now=NOW)
    assert_research_result(result)
    assert result.operational.status is OperationalStatus.UNAVAILABLE
    assert result.status is ResearchStatus.INSUFFICIENT_EVIDENCE
    assert result.payload["coverage_status"] == "DATA_UNAVAILABLE"
    assert result.payload["selected"] == []
    assert "not evidence that no memecoins exist" in json.dumps(result.to_dict())


def test_public_page_json_is_a_feed_not_a_hand_built_watch(monkeypatch):
    monkeypatch.delenv("HELIUS_API_KEY", raising=False)
    created = int((NOW - timedelta(hours=2)).timestamp() * 1000)
    pump = [{
        "mint": MINT,
        "symbol": "LABEL",
        "complete": True,
        "chain_id": "solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp",
        "created_timestamp": created,
        "usd_market_cap": 50_000,
        "real_quote_reserves": 85_005_359_057,
        "quote_mint": "11111111111111111111111111111111",
        "pump_swap_pool": None,
    }]
    family = {
        "solUsd": 200,
        "sales": [
            {"mint": "not-a-mint", "symbol": "OPEN", "phase": "open", "marketCap": 10},
            {
                "mint": "FvMLDEUDKUr9C34e8Nynz5Aqfdk34a2RBKQxygLpfomo",
                "symbol": "FAMILY",
                "phase": "migrated",
                "marketState": "migrated",
                "marketCap": 400,
                "pool": "FdYPSUq2Zrw9vJXkA8uZFVNhNcCvUUuAcSWWVk6MZZhU",
                "windowEnd": int((NOW - timedelta(days=2)).timestamp()),
            },
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "frontend-api-v3.pump.fun":
            return httpx.Response(200, json=pump)
        if request.url.host == "pump.family":
            return httpx.Response(200, json=family)
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    found = discover(client, now=NOW)
    assert PUMP_COINS_URL.startswith("https://frontend-api-v3.pump.fun/coins")
    assert found["sol_usd"] == 200
    assert len(found["observations"]) == 2
    result = scan_feed(found["observations"], now=NOW, providers=found["providers"])
    assert_research_result(result)
    states = {row["mint"]: row["state"] for row in result.payload["selected"]}
    assert states[MINT] == "UNKNOWN"
    assert "helius_confirm_missing" in result.payload["selected"][0]["reasons"] or any(
        "helius_confirm_missing" in row["reasons"] for row in result.payload["selected"]
    )
    assert all(row["state"] != "WATCH" for row in result.payload["selected"])
    assert result.payload["edge"] == "NO_EDGE_VALIDATED"
    assert "x" in result.payload["universe_source"]


def test_helius_confirm_does_not_copy_the_key_into_the_result(monkeypatch):
    secret = "heliustestkeyvalue"
    monkeypatch.setenv("HELIUS_API_KEY", secret)
    supply = 1_000_000
    data = bytearray(82)
    data[36:44] = supply.to_bytes(8, "little")
    data[44] = 6
    data[45] = 1
    import base64

    encoded = base64.b64encode(bytes(data)).decode()

    def handler(request: httpx.Request) -> httpx.Response:
        assert secret in str(request.url)
        calls = json.loads(request.content)
        body = []
        for call in calls:
            if call["method"] == "getAccountInfo" and call["id"].startswith("m:"):
                body.append({"jsonrpc": "2.0", "id": call["id"], "result": {"value": {
                    "owner": TOKEN_PROGRAM,
                    "data": [encoded, "base64"],
                }}})
            elif call["method"] == "getTokenLargestAccounts":
                body.append({"jsonrpc": "2.0", "id": call["id"], "result": {"value": [
                    {"address": MINT, "amount": "25000", "decimals": 6},
                ]}})
            else:
                body.append({"jsonrpc": "2.0", "id": call["id"], "result": {"value": {"owner": TOKEN_PROGRAM, "lamports": 1}}})
        return httpx.Response(200, json=body)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    rows, health = confirm_helius([_row(pool="B973QMT3E6AFKJY8SSSsYib5MJzCBWa6xSNQs4zPAzgy")], client, now=NOW)
    result = scan_feed(rows, now=NOW, providers=(health,))
    assert_research_result(result)
    assert secret not in result.to_json().decode()
    assert result.payload["selected"][0]["state"] == "WATCH"
    assert result.payload["selected"][0]["bundle_or_dev_hold"]["dev_hold"] == "UNKNOWN"
    assert result.payload["selected"][0]["bundle_or_dev_hold"]["top1_holder_bps"] == 25000 * 10_000 // supply
