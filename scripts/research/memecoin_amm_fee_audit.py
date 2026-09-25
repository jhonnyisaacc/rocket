"""Offline MC-019 exact-response and same-bank PumpSwap fee-state audit."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import struct
from itertools import pairwise
from pathlib import Path

from scripts.research.memecoin_amm_fee_capture import FEE_PROGRAM, selected
from scripts.research.memecoin_route_snapshot_audit import (
    TOKEN_2022_PROGRAM,
    decode_config,
    decode_pool,
    decode_token_account,
)
from scripts.research.memecoin_route_snapshot_capture import AMM_IDL_PATH

FEE_DISCRIMINATOR = bytes([143, 52, 146, 187, 219, 123, 76, 155])


def fees(raw: bytes, offset: int) -> tuple[dict, int]:
    if offset + 24 > len(raw):
        raise ValueError("fee record truncated")
    lp, protocol, creator = struct.unpack_from("<QQQ", raw, offset)
    if max(lp, protocol, creator) > 10_000:
        raise ValueError("fee bps out of range")
    return {"lp_fee_bps": lp, "protocol_fee_bps": protocol,
            "creator_fee_bps": creator}, offset + 24


def fee_config(value: dict | None) -> dict:
    if value is None or value.get("owner") != FEE_PROGRAM:
        raise ValueError("fee config owner/missing")
    raw = base64.b64decode(value["data"][0], validate=True)
    if raw[:8] != FEE_DISCRIMINATOR or len(raw) < 69:
        raise ValueError("fee config discriminator/layout")
    offset = 41  # discriminator + bump + admin pubkey
    flat, offset = fees(raw, offset)

    def tiers(at: int) -> tuple[list[dict], int]:
        if at + 4 > len(raw):
            raise ValueError("fee tier vector truncated")
        count = struct.unpack_from("<I", raw, at)[0]
        if count > 100 or at + 4 + 40 * count > len(raw):
            raise ValueError("fee tier vector bound")
        at += 4
        found = []
        for _ in range(count):
            threshold = int.from_bytes(raw[at:at + 16], "little")
            selected_fees, at = fees(raw, at + 16)
            found.append({"market_cap_lamports_threshold": threshold,
                          **selected_fees})
        if any(a["market_cap_lamports_threshold"] >=
               b["market_cap_lamports_threshold"] for a, b in pairwise(found)):
            raise ValueError("fee thresholds not increasing")
        return found, at

    regular, offset = tiers(offset)
    stable, offset = tiers(offset)
    exotic, offset = fees(raw, offset)
    if not regular or any(raw[offset:]):
        raise ValueError("fee tiers missing or unknown nonzero extension")
    return {"flat_fees": flat, "fee_tiers": regular,
            "stable_fee_tiers": stable, "exotic_flat_fees": exotic,
            "account_data_sha256": hashlib.sha256(raw).hexdigest(),
            "account_data_len": len(raw)}


def mint_supply(value: dict | None) -> dict:
    if value is None or value.get("owner") != TOKEN_2022_PROGRAM:
        raise ValueError("base mint owner/missing")
    raw = base64.b64decode(value["data"][0], validate=True)
    if len(raw) < 82 or raw[45] != 1:
        raise ValueError("base mint layout/uninitialized")
    supply = struct.unpack_from("<Q", raw, 36)[0]
    if supply <= 0:
        raise ValueError("base mint zero supply")
    extension_types = extensions(raw, account_type=1, allowed={18, 19})
    return {"supply": supply, "decimals": raw[44],
            "extension_type_ids": extension_types,
            "account_data_sha256": hashlib.sha256(raw).hexdigest()}


def extensions(raw: bytes, *, account_type: int, allowed: set[int]) -> list[int]:
    if len(raw) == (82 if account_type == 1 else 165):
        return []
    if len(raw) < 170 or raw[165] != account_type:
        raise ValueError("Token-2022 extension account type/layout")
    offset = 166
    types = []
    while offset + 4 <= len(raw):
        kind, size = struct.unpack_from("<HH", raw, offset)
        if kind == 0 and size == 0 and not any(raw[offset:]):
            break
        offset += 4
        if kind not in allowed or offset + size > len(raw):
            raise ValueError(f"unsupported Token-2022 extension {kind}")
        types.append(kind)
        offset += size
    if any(raw[offset:]):
        raise ValueError("trailing Token-2022 extension data")
    return types


def audit(route_path: Path, capture_path: Path) -> dict:
    capture = json.loads(capture_path.read_text())
    chosen, addresses = selected(route_path)
    if (capture["selected"] != chosen or capture["request"]["params"][0] != addresses
            or capture["source_route_sha256"] != hashlib.sha256(
                route_path.read_bytes()).hexdigest()
            or capture["pump_amm_idl_sha256"] != hashlib.sha256(
                AMM_IDL_PATH.read_bytes()).hexdigest()):
        raise ValueError("frozen selection/source mismatch")
    raw_response = base64.b64decode(capture["raw_response_base64"], validate=True)
    if (hashlib.sha256(raw_response).hexdigest() != capture["raw_response_sha256"]
            or json.loads(raw_response) != capture["body"]):
        raise ValueError("raw response mismatch")
    body = capture["body"]
    if capture["http_status"] != 200 or "error" in body:
        raise ValueError("RPC response failed")
    result = body["result"]
    values = result["value"]
    slot = result["context"]["slot"]
    if len(values) != len(addresses) or not isinstance(slot, int):
        raise ValueError("RPC context/value count")
    dynamic = fee_config(values[0])
    global_config = decode_config(values[1])
    rows = []
    for index, item in enumerate(chosen):
        pool_value, base_value, quote_value, mint_value = values[2 + 4 * index:
                                                                 6 + 4 * index]
        # Canonical pool authority and address were independently checked in `selected`.
        route = next(row for row in json.loads(route_path.read_text())["rows"]
                     if row["mint"] == item["mint"])
        pool = decode_pool(pool_value, item["mint"], route["pool_authority"])
        if pool["base_vault"] != item["base_vault"] or pool["quote_vault"] != item[
                "quote_vault"]:
            raise ValueError("pool/vault mismatch")
        base = decode_token_account(base_value, item["mint"], item["pool"])
        base_raw = base64.b64decode(base_value["data"][0], validate=True)
        base["extension_type_ids"] = extensions(base_raw, account_type=2,
                                                  allowed={7})
        quote = decode_token_account(quote_value,
                                     "So11111111111111111111111111111111111111112",
                                     item["pool"])
        mint = mint_supply(mint_value)
        effective = quote["amount"] + pool["virtual_quote_reserves"]
        if base["amount"] <= 0 or effective <= 0:
            raise ValueError("nonpositive pool reserves")
        cap = effective * mint["supply"] // base["amount"]
        tier = dynamic["fee_tiers"][0]
        for candidate in dynamic["fee_tiers"]:
            if cap >= candidate["market_cap_lamports_threshold"]:
                tier = candidate
        rows.append({**item, "pool_state": pool, "base_vault_state": base,
                     "quote_vault_state": quote, "mint_state": mint,
                     "effective_quote_reserves": effective,
                     "market_cap_lamports": cap, "selected_fee_tier": tier})
    return {"schema": "rocket.memecoin.mc019-fee-state-audit.v1",
            "capture_sha256": hashlib.sha256(capture_path.read_bytes()).hexdigest(),
            "rpc_url": capture["rpc_url"], "dispatch_at": capture["dispatch_at"],
            "received_at": capture["received_at"], "context_slot": slot,
            "fee_config": dynamic, "global_config": global_config,
            "data_gate_pass": True, "rows": rows,
            "scope": "One later confirmed bank; no MC-017 exit backdating or execution claim."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("route", type=Path)
    parser.add_argument("capture", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.route, args.capture)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"data_gate_pass": report["data_gate_pass"],
                      "context_slot": report["context_slot"],
                      "rows": [{"mint": row["mint"],
                                "market_cap_lamports": row["market_cap_lamports"],
                                "selected_fee_tier": row["selected_fee_tier"]}
                               for row in report["rows"]]}, indent=2))
