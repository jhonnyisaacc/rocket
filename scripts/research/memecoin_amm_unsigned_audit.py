"""Offline MC-021 checks for the two saved unsigned sell simulations."""

from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path


def amount(account: dict | None) -> int | None:
    if account is None:
        return None
    data = base64.b64decode(account["data"][0])
    return int.from_bytes(data[64:72], "little")


def audit(first_path: Path, second_path: Path) -> dict:
    first = json.loads(first_path.read_text())
    second = json.loads(second_path.read_text())
    for item in (first, second):
        assert item["schema"] == "rocket.memecoin.mc021-unsigned-simulation.v1"
        assert item["baseAmount"] == "10000000000"
        assert item["slippagePercent"] == 1
        assert item["user"] == first["user"]
        assert item["pool"] == first["pool"]
        assert [call["request"]["method"] for call in item["calls"]] == [
            "getAccountInfo", "getAccountInfo", "getAccountInfo", "getMultipleAccounts",
            "getLatestBlockhash", "simulateTransaction",
        ]
        assert item["simulationSummary"]["err"] is None
        assert item["calls"][-1]["response"]["result"]["value"]["err"] is None
    assert first["bankState"]["poolBaseAmount"] == second["bankState"]["poolBaseAmount"]
    assert first["bankState"]["poolQuoteAmount"] == second["bankState"]["poolQuoteAmount"]
    quote_first = {key: int(value, 16) for key, value in first["sdkQuote"].items()}
    quote_second = {key: int(value) for key, value in second["sdkQuote"].items()}
    assert quote_first == quote_second
    assert quote_second["minQuote"] <= quote_second["uiQuote"]

    value = second["calls"][-1]["response"]["result"]["value"]
    accounts = value["accounts"]
    before = second["bankState"]
    base_in = int(second["baseAmount"])
    assert amount(accounts[0]) == int(before["userBaseAmount"]) - base_in
    assert amount(accounts[2]) == int(before["poolBaseAmount"]) + base_in
    quote_vault_debit = int(before["poolQuoteAmount"]) - amount(accounts[3])
    assert quote_vault_debit <= quote_second["internalQuoteAmountOut"]
    fee = value["fee"]
    user_native_delta = accounts[4]["lamports"] - before["userLamports"]
    assert user_native_delta + fee == quote_second["uiQuote"]
    assert quote_second["uiQuote"] >= quote_second["minQuote"]
    assert amount(accounts[1]) == 0  # temporary WSOL account was closed
    assert value["unitsConsumed"] == second["simulationSummary"]["unitsConsumed"]
    return {
        "first_bank_slot": first["bankSlot"],
        "first_simulation_slot": first["simulationSummary"]["contextSlot"],
        "second_bank_slot": second["bankSlot"],
        "second_simulation_slot": second["simulationSummary"]["contextSlot"],
        "base_in_raw": base_in,
        "gross_quote_lamports": quote_second["internalQuoteAmountOut"],
        "sdk_user_quote_lamports": quote_second["uiQuote"],
        "minimum_quote_lamports": quote_second["minQuote"],
        "pool_quote_vault_debit_lamports": quote_vault_debit,
        "simulated_fee_lamports": fee,
        "simulated_owner_native_delta_lamports": user_native_delta,
        "first_units": first["simulationSummary"]["unitsConsumed"],
        "second_units": value["unitsConsumed"],
        "first_err": first["simulationSummary"]["err"],
        "second_err": second["simulationSummary"]["err"],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("first", type=Path)
    parser.add_argument("second", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = audit(args.first, args.second)
    report = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.write_text(report)
    print(report, end="")
