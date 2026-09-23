import base64
import json
from datetime import UTC, datetime, timedelta

import httpx

from rocket.capture.spool import RawCaptureSpool
from rocket.models import OperationalStatus, ResearchStatus
from rocket.workflows.memecoin import canonical_identity
from rocket.workflows.memecoin_radar import (
    AGE_FLOOR_SECONDS,
    LIQUIDITY_FLOOR_USD,
    POOL_DISCRIMINATOR,
    POOL_QUOTE_MINT_OFFSET,
    POOL_QUOTE_VAULT_OFFSET,
    PUMP_COINS_URL,
    PUMP_OFFSET_CAP,
    PUMP_SWAP_PROGRAM,
    RPC_BATCH_CAP,
    SAFETY_SENTENCE,
    SELECTED_CAP,
    WSOL_MINT,
    bound_spool,
    collect_snapshot,
    confirm_helius,
    decode_base58_pubkey,
    decode_pump_swap_quote_vault,
    discover,
    encode_base58,
    normalize_pump_coin,
    scan_feed,
    scan_spool,
)

POOL = "B973QMT3E6AFKJY8SSSsYib5MJzCBWa6xSNQs4zPAzgy"
GRADUATION_LAMPORTS = 85_005_359_057
QUOTE_LAMPORTS = 30_000_000_000
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
    assert result.payload["selected"][0]["state"] == "SKIP"
    assert "helius_confirm_missing" in result.payload["selected"][0]["reasons"]
    assert all(row["state"] != "WATCH_ENTER" for row in result.payload["selected"])


def test_confirmed_row_meeting_floors_is_watch_and_not_an_entry():
    result = scan_feed([_confirmed()], now=NOW)
    assert_research_result(result)
    row = result.payload["selected"][0]
    assert row["state"] == "WATCH_ENTER"
    assert row["age_seconds"] >= AGE_FLOOR_SECONDS
    assert row["liquidity_usd"] >= LIQUIDITY_FLOOR_USD
    assert "floors_met_not_an_entry" in row["reasons"]
    assert result.payload["notice"] == "A WATCH_ENTER row is not a buy."
    assert "not a buy" in result.payload["notice"]


def test_too_new_confirmed_row_is_not_watch():
    fresh = _confirmed(event_time=(NOW - timedelta(seconds=10)).isoformat())
    result = scan_feed([fresh], now=NOW)
    assert result.payload["selected"][0]["state"] == "TOO_EARLY"
    assert result.payload["selected"][0]["state"] != "WATCH_ENTER"
    assert "below_age_floor" in result.payload["selected"][0]["reasons"]


def test_confirmed_liquidity_under_floor_is_avoid():
    result = scan_feed([_confirmed(liquidity_usd=LIQUIDITY_FLOOR_USD - 1)], now=NOW)
    row = result.payload["selected"][0]
    assert row["state"] == "AVOID"
    assert row["state"] != "WATCH_ENTER"
    assert "liquidity_below_floor" in row["reasons"]


def test_confirmed_bonding_curve_is_avoid():
    result = scan_feed([_confirmed(graduation_status="still_on_curve", window_state="closed")], now=NOW)
    row = result.payload["selected"][0]
    assert row["state"] == "AVOID"
    assert "still_on_curve" in row["reasons"]


def test_unconfirmed_young_row_is_skip_not_too_early():
    fresh = _row(event_time=(NOW - timedelta(seconds=10)).isoformat())
    result = scan_feed([fresh], now=NOW)
    row = result.payload["selected"][0]
    assert row["state"] == "SKIP"
    assert row["state"] != "TOO_EARLY"
    assert "helius_confirm_missing" in row["reasons"]


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
    funded = dict(graduated, real_quote_reserves=GRADUATION_LAMPORTS)
    liquid = normalize_pump_coin(funded, now=NOW, sol_usd=200)
    assert liquid["liquidity_usd"] is None
    assert round(GRADUATION_LAMPORTS / 1_000_000_000 * 200, 2) != liquid["liquidity_usd"]


def test_spool_feed_ranks_browser_row_without_calling_helius(tmp_path, monkeypatch):
    monkeypatch.delenv("HELIUS_API_KEY", raising=False)
    spool = RawCaptureSpool(tmp_path / "spool", max_bytes=1024 * 1024, reserve_bytes=1)
    collected = collect_snapshot(spool, now=NOW, observations=[_row()])
    spool.close()
    assert_research_result(collected)
    assert collected.payload["edge"] == "NO_EDGE_VALIDATED"
    assert collected.payload["execution_enabled"] is False
    assert collected.payload["helius_key_present"] is False
    scanned = scan_spool(tmp_path / "spool", now=NOW)
    assert_research_result(scanned)
    assert scanned.payload["selected"][0]["state"] == "SKIP"
    assert scanned.payload["selected"][0]["state"] != "WATCH_ENTER"
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
    assert states[MINT] == "SKIP"
    assert "helius_confirm_missing" in result.payload["selected"][0]["reasons"] or any(
        "helius_confirm_missing" in row["reasons"] for row in result.payload["selected"]
    )
    assert all(row["state"] != "WATCH_ENTER" for row in result.payload["selected"])
    assert result.payload["edge"] == "NO_EDGE_VALIDATED"
    assert "x" in result.payload["universe_source"]


def _pool_account() -> tuple[str, str]:
    vault = bytes([7]) * 32
    data = bytearray(301)
    data[:8] = POOL_DISCRIMINATOR
    data[POOL_QUOTE_MINT_OFFSET:POOL_QUOTE_MINT_OFFSET + 32] = decode_base58_pubkey(WSOL_MINT)
    data[POOL_QUOTE_VAULT_OFFSET:POOL_QUOTE_VAULT_OFFSET + 32] = vault
    return base64.b64encode(bytes(data)).decode(), encode_base58(vault)


def _helius_handler(*, supply: int = 1_000_000, quote_raw: int = QUOTE_LAMPORTS, secret: str | None = None):
    encoded = _mint_account_b64(supply)
    pool_b64, _vault = _pool_account()

    def handler(request: httpx.Request) -> httpx.Response:
        if secret is not None:
            assert secret in str(request.url)
        calls = json.loads(request.content)
        body = []
        for call in calls:
            method = call["method"]
            call_id = str(call["id"])
            if method == "getAccountInfo" and call_id.startswith("m:"):
                body.append({"jsonrpc": "2.0", "id": call["id"], "result": {"value": {
                    "owner": TOKEN_PROGRAM,
                    "data": [encoded, "base64"],
                }}})
            elif method == "getAccountInfo" and call_id.startswith("p:"):
                body.append({"jsonrpc": "2.0", "id": call["id"], "result": {"value": {
                    "owner": PUMP_SWAP_PROGRAM,
                    "data": [pool_b64, "base64"],
                }}})
            elif method == "getTokenLargestAccounts":
                body.append({"jsonrpc": "2.0", "id": call["id"], "result": {"value": [
                    {"address": call_id, "amount": "25000", "decimals": 6},
                ]}})
            elif method == "getTokenAccountBalance":
                body.append({"jsonrpc": "2.0", "id": call["id"], "result": {"value": {
                    "amount": str(quote_raw),
                    "decimals": 9,
                    "uiAmount": quote_raw / 1_000_000_000,
                }}})
            else:
                body.append({"jsonrpc": "2.0", "id": call["id"], "result": {"value": []}})
        return httpx.Response(200, json=body)

    return handler


def _mint_account_b64(supply: int) -> str:
    data = bytearray(82)
    data[36:44] = supply.to_bytes(8, "little")
    data[44] = 6
    data[45] = 1
    return base64.b64encode(bytes(data)).decode()


def test_pool_reserve_decode_prices_two_sided_quote_liquidity(monkeypatch):
    secret = "heliustestkeyvalue"
    monkeypatch.setenv("HELIUS_API_KEY", secret)
    pool_b64, vault = _pool_account()
    quote_mint, quote_vault = decode_pump_swap_quote_vault(base64.b64decode(pool_b64))
    assert quote_mint == WSOL_MINT
    assert quote_vault == vault
    graduation_usd = round(GRADUATION_LAMPORTS / 1_000_000_000 * 200, 2)
    client = httpx.Client(transport=httpx.MockTransport(_helius_handler(secret=secret)))
    rows, health = confirm_helius(
        [_row(pool=POOL, liquidity_usd=graduation_usd)],
        client,
        now=NOW,
        sol_usd=200,
    )
    result = scan_feed(rows, now=NOW, providers=(health,))
    assert_research_result(result)
    assert secret not in result.to_json().decode()
    assert rows[0]["liquidity_usd"] == 12_000.00
    assert rows[0]["liquidity_usd"] != graduation_usd
    assert result.payload["selected"][0]["state"] == "WATCH_ENTER"
    assert result.payload["selected"][0]["bundle_or_dev_hold"]["dev_hold"] == "UNKNOWN"
    assert result.payload["selected"][0]["bundle_or_dev_hold"]["top1_holder_bps"] == 25000 * 10_000 // 1_000_000
    summary = result.payload["decision_summary"]
    assert summary["counts"]["WATCH_ENTER"] == 1
    assert summary["watch_enter"][0]["liquidity_usd"] == 12_000.00
    assert summary["watch_enter"][0]["mint"] == MINT


def test_zero_or_missing_pool_liquidity_is_null_and_skip(monkeypatch):
    monkeypatch.setenv("HELIUS_API_KEY", "heliustestkeyvalue")
    client = httpx.Client(transport=httpx.MockTransport(_helius_handler(quote_raw=0)))
    zero_rows, zero_health = confirm_helius(
        [_row(pool=POOL, liquidity_usd=17_001.07)],
        client,
        now=NOW,
        sol_usd=200,
    )
    assert zero_rows[0]["liquidity_usd"] is None
    zero = scan_feed(zero_rows, now=NOW, providers=(zero_health,))
    assert zero.payload["selected"][0]["state"] == "SKIP"
    assert zero.payload["selected"][0]["state"] != "WATCH_ENTER"
    assert "liquidity_unknown" in zero.payload["selected"][0]["reasons"]
    missing_rows, missing_health = confirm_helius(
        [_row(liquidity_usd=17_001.07)],
        client,
        now=NOW,
        sol_usd=200,
    )
    assert missing_rows[0]["liquidity_usd"] is None
    missing = scan_feed(missing_rows, now=NOW, providers=(missing_health,))
    assert missing.payload["selected"][0]["state"] == "SKIP"
    assert "liquidity_unknown" in missing.payload["selected"][0]["reasons"]


def _mint_from_seed(seed: int) -> str:
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    raw = bytes([seed]) * 32
    number = int.from_bytes(raw, "big")
    chars = []
    while number:
        number, rem = divmod(number, 58)
        chars.append(alphabet[rem])
    return "".join(reversed(chars))


def test_helius_confirm_splits_batches_under_the_rate_cap(monkeypatch):
    monkeypatch.setenv("HELIUS_API_KEY", "heliustestkeyvalue")
    sizes = []
    inner = _helius_handler()

    def handler(request: httpx.Request) -> httpx.Response:
        sizes.append(len(json.loads(request.content)))
        return inner(request)

    rows = [
        _row(mint=_mint_from_seed(seed), asset=f"L{seed}", pool=POOL)
        for seed in range(1, 7)
    ]
    client = httpx.Client(transport=httpx.MockTransport(handler))
    confirmed, health = confirm_helius(rows, client, now=NOW, sol_usd=200)
    result = scan_feed(confirmed, now=NOW, providers=(health,))
    assert sizes and max(sizes) <= RPC_BATCH_CAP
    assert len(sizes) > 1
    assert result.payload["selected"]
    assert {row["state"] for row in result.payload["selected"]} == {"WATCH_ENTER"}
    assert {row["liquidity_usd"] for row in result.payload["selected"]} == {12_000.00}
    assert "heliustestkeyvalue" not in result.to_json().decode()


def _json_documents(text: str) -> list[dict]:
    decoder = json.JSONDecoder()
    index = 0
    documents = []
    while index < len(text):
        while index < len(text) and text[index].isspace():
            index += 1
        if index >= len(text):
            break
        document, index = decoder.raw_decode(text, index)
        documents.append(document)
    return documents


def test_age_eligible_rows_rank_ahead_of_too_early():
    young = [
        _confirmed(
            mint=_mint_from_seed(seed),
            asset=f"Y{seed}",
            event_time=(NOW - timedelta(seconds=60 + seed)).isoformat(),
        )
        for seed in range(1, 21)
    ]
    old = _confirmed(
        mint=_mint_from_seed(30),
        asset="OLD",
        event_time=(NOW - timedelta(hours=2)).isoformat(),
    )
    result = scan_feed([*young, old], now=NOW)
    assert result.payload["selected"][0]["asset"] == "OLD"
    assert result.payload["selected"][0]["state"] == "WATCH_ENTER"
    assert len(result.payload["selected"]) == SELECTED_CAP
    assert sum(row["state"] == "TOO_EARLY" for row in result.payload["selected"]) < SELECTED_CAP
    assert result.payload["decision_summary"]["counts"]["WATCH_ENTER"] == 1
    assert result.payload["decision_summary"]["counts"]["TOO_EARLY"] == SELECTED_CAP - 1


def test_helius_budget_prefers_the_age_window(monkeypatch):
    monkeypatch.setenv("HELIUS_API_KEY", "heliustestkeyvalue")
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls = json.loads(request.content)
        seen.extend(str(call["id"]) for call in calls if str(call["id"]).startswith("m:"))
        return httpx.Response(200, json=[
            {"jsonrpc": "2.0", "id": call["id"], "result": {"value": None}} for call in calls
        ])

    young = [
        _row(mint=_mint_from_seed(seed), event_time=(NOW - timedelta(seconds=30)).isoformat())
        for seed in range(1, 22)
    ]
    old_mint = _mint_from_seed(40)
    old = _row(mint=old_mint, pool=POOL, event_time=(NOW - timedelta(hours=2)).isoformat())
    client = httpx.Client(transport=httpx.MockTransport(handler))
    confirm_helius([*young, old], client, now=NOW, sol_usd=200)
    assert f"m:{old_mint}" in seen
    assert len(seen) == SELECTED_CAP
    skipped = {f"m:{_mint_from_seed(seed)}" for seed in range(1, 22)} - set(seen)
    assert skipped


def test_second_pump_page_reaches_past_the_age_floor(monkeypatch):
    monkeypatch.delenv("HELIUS_API_KEY", raising=False)
    urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        urls.append(str(request.url))
        if request.url.host == "frontend-api-v3.pump.fun":
            offset = int(request.url.params.get("offset", "0"))
            created = int((NOW - timedelta(seconds=10)).timestamp() * 1000)
            base = 1 if offset == 0 else 50
            page = [{
                "mint": _mint_from_seed(base + index),
                "symbol": f"P{base + index}",
                "complete": True,
                "chain_id": "solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp",
                "created_timestamp": created,
                "usd_market_cap": 50_000,
                "real_quote_reserves": GRADUATION_LAMPORTS,
                "quote_mint": "11111111111111111111111111111111",
                "pump_swap_pool": POOL,
            } for index in range(20)]
            return httpx.Response(200, json=page)
        if request.url.host == "pump.family":
            return httpx.Response(200, json={"solUsd": 200, "sales": []})
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    found = discover(client, now=NOW)
    pump_urls = [url for url in urls if "frontend-api-v3.pump.fun" in url]
    assert len(pump_urls) == 2
    assert "offset=0" in pump_urls[0]
    second_offset = int(pump_urls[1].split("offset=")[1].split("&")[0])
    assert 0 < second_offset <= PUMP_OFFSET_CAP
    assert len(found["observations"]) <= 40
    assert all(row["liquidity_usd"] is None for row in found["observations"])
    assert all(
        round(GRADUATION_LAMPORTS / 1_000_000_000 * 200, 2) != row["liquidity_usd"]
        for row in found["observations"]
    )


def test_scan_reads_only_the_latest_snapshot(tmp_path):
    root = tmp_path / "spool"
    first = RawCaptureSpool(root, max_bytes=1024 * 1024, reserve_bytes=1)
    collect_snapshot(first, now=NOW, observations=[_row(asset="OLD")])
    first.close()
    second = RawCaptureSpool(root, max_bytes=1024 * 1024, reserve_bytes=1)
    fresh = _confirmed(mint=_mint_from_seed(9), asset="NEW")
    collect_snapshot(second, now=NOW, observations=[fresh])
    second.close()
    scanned = scan_spool(root, now=NOW)
    assert {row["asset"] for row in scanned.payload["selected"]} == {"NEW"}
    assert bound_spool(root) == 1
    assert len(list(root.glob("segment-*.jsonl"))) == 1
    again = scan_spool(root, now=NOW)
    assert {row["asset"] for row in again.payload["selected"]} == {"NEW"}


def test_decision_summary_counts_each_state():
    rows = [
        _confirmed(),
        _confirmed(mint=_mint_from_seed(2), liquidity_usd=1),
        _confirmed(mint=_mint_from_seed(3), event_time=(NOW - timedelta(seconds=10)).isoformat()),
        _row(mint=_mint_from_seed(4)),
    ]
    result = scan_feed(rows, now=NOW)
    summary = result.payload["decision_summary"]
    assert summary["counts"] == {"WATCH_ENTER": 1, "SKIP": 1, "TOO_EARLY": 1, "AVOID": 1}
    assert summary["coverage_status"] == "OBSERVED"
    assert summary["watch_enter"] == [{
        "identity": "solana:mainnet:" + MINT,
        "mint": MINT,
        "liquidity_usd": LIQUIDITY_FLOOR_USD,
        "age_seconds": result.payload["selected"][0]["age_seconds"],
    }]
    assert result.payload["edge"] == "NO_EDGE_VALIDATED"
    assert result.payload["execution_enabled"] is False
    assert result.payload["notice"] == "A WATCH_ENTER row is not a buy."


def test_memecoin_scan_emits_one_json_document_per_path(tmp_path):
    from typer.testing import CliRunner

    from rocket.cli import app

    runner = CliRunner()
    legacy = {
        "rows": [{
            "asset": "SAME",
            "chain_id": "eip155:1",
            "contract_address": "0x" + "1" * 40,
            "decision_time": NOW.isoformat(),
            "available_at": NOW.isoformat(),
            "features": {"volume_acceleration": 3, "liquidity_usd": 50_000},
        }],
    }
    legacy_path = tmp_path / "legacy.json"
    legacy_path.write_text(json.dumps(legacy), encoding="utf-8")
    radar_path = tmp_path / "radar.json"
    radar_path.write_text("[]", encoding="utf-8")
    missing = tmp_path / "missing-spool"
    cases = [
        (["--input", str(legacy_path)], "legacy"),
        (["--input", str(radar_path)], "radar"),
        ([], "spool"),
    ]
    for extra, kind in cases:
        result = runner.invoke(app, [
            "memecoin", "scan", "--state-dir", str(tmp_path / kind), "--spool", str(missing), *extra,
        ])
        documents = _json_documents(result.stdout)
        assert len(documents) == 1
        payload = documents[0]["payload"]
        assert payload["edge"] == "NO_EDGE_VALIDATED"
        assert payload["execution_enabled"] is False
        if kind == "legacy":
            assert "coverage_status" not in payload
            assert payload["selected"][0]["asset"] == "SAME"
            assert "state" not in payload["selected"][0]
        elif kind == "radar":
            assert payload["coverage_status"] == "EMPTY_INTAKE"
            assert payload["selected"] == []
            assert result.exit_code == 0
            assert documents[0]["decision_summary"]["counts"]["WATCH_ENTER"] == 0
        else:
            assert payload["coverage_status"] == "DATA_UNAVAILABLE"
            assert documents[0]["operational"]["status"] == "UNAVAILABLE"
            assert result.exit_code == 2


def test_radar_command_one_json_and_zero_watch_exits_zero(tmp_path, monkeypatch):
    monkeypatch.delenv("HELIUS_API_KEY", raising=False)
    from typer.testing import CliRunner

    from rocket.cli import app

    path = tmp_path / "observations.json"
    path.write_text(json.dumps({"observations": []}), encoding="utf-8")
    result = CliRunner().invoke(app, [
        "memecoin", "radar",
        "--input", str(path),
        "--state-dir", str(tmp_path / "state"),
        "--spool", str(tmp_path / "spool"),
    ])
    documents = _json_documents(result.stdout)
    assert result.exit_code == 0
    assert len(documents) == 1
    assert documents[0]["workflow"] == "memecoin.radar"
    summary = documents[0]["decision_summary"]
    assert summary["counts"] == {"WATCH_ENTER": 0, "SKIP": 0, "TOO_EARLY": 0, "AVOID": 0}
    assert summary["watch_enter"] == []
    assert summary["coverage_status"] == "EMPTY_INTAKE"
    assert documents[0]["payload"]["decision_summary"]["counts"]["WATCH_ENTER"] == 0
    assert documents[0]["payload"]["edge"] == "NO_EDGE_VALIDATED"
    assert documents[0]["payload"]["execution_enabled"] is False
    assert documents[0]["payload"]["notice"] == "A WATCH_ENTER row is not a buy."
    assert "api-key=" not in result.stdout
    assert len(list((tmp_path / "spool").glob("segment-*.jsonl"))) == 1
