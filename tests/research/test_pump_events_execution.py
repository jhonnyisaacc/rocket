from __future__ import annotations

import base64
import json
import struct
from pathlib import Path

import pytest

from rocket.research.pump_events import EventDecodeError, PumpEventDecoder
from rocket.research.pump_execution import (
    CurveState,
    FeeSchedule,
    buy_exact_input,
    buy_exact_output,
    pre_trade_state,
    sell,
)
from scripts.research.memecoin_audit import PUMP_PROGRAM, base58_decode, pump_data_logs

ROOT = Path(__file__).resolve().parents[2]
IDL = ROOT / "docs/research/memecoin/protocol/pump-81091419.json"
FIXTURES = json.loads((Path(__file__).parent / "fixtures/pump_events.json").read_text())


def test_only_pump_program_data_is_decoded_from_nested_logs():
    other = "LanMV9sAd7wArD4vJFi2qDdfnVhFxYSUg6eADduJ3uj"
    valid = FIXTURES["TradeEvent"]["encoded"]
    logs = [
        f"Program {PUMP_PROGRAM} invoke [1]",
        f"Program {other} invoke [2]",
        "Program data: invalid-other-program-event",
        f"Program {other} success",
        f"Program data: {valid}",
        f"Program {PUMP_PROGRAM} success",
    ]
    assert list(pump_data_logs(logs)) == [(4, valid)]


@pytest.mark.parametrize("name", ["CreateEvent", "TradeEvent"])
def test_pinned_idl_decodes_observed_event_bytes(name):
    row = FIXTURES[name]
    event = PumpEventDecoder(IDL).decode(row["encoded"])
    assert event["event_type"] == name
    assert event["fields"]["mint"] == row["mint"]
    assert event["event_sha256"] == row["event_sha256"]


def test_pinned_decoder_rejects_truncated_event():
    encoded = FIXTURES["TradeEvent"]["encoded"]
    with pytest.raises(EventDecodeError):
        PumpEventDecoder(IDL).decode(encoded[:-12])


def test_pinned_decoder_supports_explicit_curve_completion():
    idl = json.loads(IDL.read_text())
    discriminator = bytes(next(item["discriminator"] for item in idl["events"]
                               if item["name"] == "CompleteEvent"))
    mint = FIXTURES["CreateEvent"]["mint"]
    raw = (discriminator + base58_decode(mint) * 3 + struct.pack("<q", 1_790_261_800)
           + bytes(32))
    event = PumpEventDecoder(IDL).decode(base64.b64encode(raw).decode())
    assert event["event_type"] == "CompleteEvent"
    assert event["fields"]["mint"] == mint


def test_current_native_curve_quotes_reproduce_observed_fills():
    fees = FeeSchedule(95, 30)
    ordinary_buy = {
        "is_buy": True, "sol_amount": 683501144, "token_amount": 16589058157746,
        "virtual_sol_reserves": 36761618792, "virtual_token_reserves": 875641536696297,
        "real_sol_reserves": 6761618792, "real_token_reserves": 595741536696297,
    }
    quoted_buy = buy_exact_output(pre_trade_state(ordinary_buy),
                                  ordinary_buy["token_amount"], fees)
    assert quoted_buy == {"gross": 683501144, "tokens": 16589058157746,
                          "cash": 692044909}

    input_buy = {
        "is_buy": True, "sol_amount": 9876542, "token_amount": 332255681323,
        "virtual_sol_reserves": 30938271602, "virtual_token_reserves": 1040458898809343,
        "real_sol_reserves": 938271602, "real_token_reserves": 760558898809343,
    }
    quoted_input = buy_exact_input(pre_trade_state(input_buy), 10_000_000, fees)
    assert quoted_input["gross"] == 9876542
    assert quoted_input["tokens"] == 332255681323

    observed_sell = {
        "is_buy": False, "sol_amount": 19739520, "token_amount": 206213845122,
        "virtual_sol_reserves": 55499959019, "virtual_token_reserves": 580000433953858,
        "real_sol_reserves": 25499959019, "real_token_reserves": 300100433953858,
    }
    quoted_sell = sell(pre_trade_state(observed_sell), observed_sell["token_amount"], fees)
    assert quoted_sell == {"gross": 19739520, "tokens": 206213845122,
                           "cash": 19492775}


def test_quote_rejects_missing_exit_liquidity():
    with pytest.raises(ValueError, match="exit liquidity"):
        sell(CurveState(30_000_000_000, 1_000_000_000, 0, 1_000_000_000),
             100_000, FeeSchedule(95, 30))


def test_default_creator_waives_creator_fee_on_observed_exact_input_fill():
    event = {
        "is_buy": True, "sol_amount": 99058940, "token_amount": 3122091208843,
        "virtual_sol_reserves": 32007931376, "virtual_token_reserves": 1005688240982864,
        "real_sol_reserves": 2007931376, "real_token_reserves": 725788240982864,
    }
    quoted = buy_exact_input(pre_trade_state(event), 100_000_000,
                             FeeSchedule(95, 30, creator_enabled=False))
    assert quoted["gross"] == event["sol_amount"]
    assert quoted["tokens"] == event["token_amount"]
    assert quoted["cash"] == 100_000_000
