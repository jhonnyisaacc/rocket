"""Offline MC-020 landed PumpSwap sell event and transaction accounting audit."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

from rocket.research.solana_pda import PUMP_AMM_PROGRAM, encode_base58
from scripts.research.memecoin_amm_landed_amended import successful_page
from scripts.research.memecoin_amm_landed_capture import frozen_pools
from scripts.research.memecoin_route_snapshot_capture import AMM_IDL_PATH

INVOKE = re.compile(r"Program (\S+) invoke \[\d+\]$")
DONE = re.compile(r"Program (\S+) (?:success|failed:.*)$")
WSOL = "So11111111111111111111111111111111111111112"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_reply(reply: dict) -> None:
    raw = base64.b64decode(reply["raw_response_base64"], validate=True)
    if (hashlib.sha256(raw).hexdigest() != reply["raw_response_sha256"]
            or json.loads(raw) != reply["body"]):
        raise ValueError("RPC response byte/body mismatch")
    if datetime.fromisoformat(reply["dispatch_at"]) > datetime.fromisoformat(
            reply["received_at"]):
        raise ValueError("RPC response clock inversion")


def event_layout() -> tuple[bytes, list[dict]]:
    idl = json.loads(AMM_IDL_PATH.read_text())
    discriminator = bytes(next(event["discriminator"] for event in idl["events"]
                               if event["name"] == "SellEvent"))
    fields = next(item["type"]["fields"] for item in idl["types"]
                  if item["name"] == "SellEvent")
    return discriminator, fields


def decode_sell(data: bytes, fields: list[dict]) -> dict:
    offset = 8
    decoded = {}
    sizes = {"u64": 8, "i64": 8, "i128": 16, "pubkey": 32, "bool": 1}
    for field in fields:
        kind = field["type"]
        if kind not in sizes or offset + sizes[kind] > len(data):
            raise ValueError("unsupported/truncated sell event")
        raw = data[offset:offset + sizes[kind]]
        offset += sizes[kind]
        if kind == "pubkey":
            value = encode_base58(raw)
        elif kind == "bool":
            if raw[0] not in (0, 1):
                raise ValueError("invalid event bool")
            value = bool(raw[0])
        else:
            value = int.from_bytes(raw, "little", signed=kind.startswith("i"))
        decoded[field["name"]] = value
    if offset != len(data):
        raise ValueError("unknown sell event trailing bytes")
    return decoded


def sell_events(logs: list[str]) -> tuple[list[dict], list[str]]:
    discriminator, fields = event_layout()
    stack = []
    events = []
    errors = []
    for line in logs:
        invoked = INVOKE.fullmatch(line)
        if invoked:
            stack.append(invoked.group(1))
            continue
        done = DONE.fullmatch(line)
        if done:
            if not stack or stack[-1] != done.group(1):
                errors.append("PROGRAM_STACK_MISMATCH")
            else:
                stack.pop()
            continue
        if not line.startswith("Program data: "):
            continue
        try:
            raw = base64.b64decode(line.split(": ", 1)[1], validate=True)
        except ValueError:
            errors.append("INVALID_EVENT_BASE64")
            continue
        if raw[:8] != discriminator:
            continue
        if not stack or stack[-1] != PUMP_AMM_PROGRAM:
            errors.append("SELL_EVENT_NOT_ATTRIBUTED_TO_AMM")
            continue
        try:
            decoded = decode_sell(raw, fields)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        events.append({"fields": decoded, "raw_sha256": hashlib.sha256(raw).hexdigest()})
    if stack:
        errors.append("PROGRAM_STACK_NOT_CLOSED")
    return events, errors


def account_keys(result: dict) -> list[str]:
    keys = [entry if isinstance(entry, str) else entry["pubkey"]
            for entry in result["transaction"]["message"]["accountKeys"]]
    loaded = result["meta"].get("loadedAddresses") or {}
    return keys + loaded.get("writable", []) + loaded.get("readonly", [])


def token_balances(result: dict, field: str) -> dict[str, dict]:
    keys = account_keys(result)
    found = {}
    for row in result["meta"].get(field) or []:
        index = row["accountIndex"]
        if index >= len(keys):
            raise ValueError("token balance account index out of range")
        found[keys[index]] = {"mint": row["mint"],
                              "owner": row.get("owner"),
                              "amount": int(row["uiTokenAmount"]["amount"])}
    return found


def transaction_result(item: dict, amended: Path, supplemental: Path) -> tuple[dict | None,
                                                                                str, int]:
    source = amended / "transactions" / f"{item['signature']}.json"
    record = json.loads(source.read_text())
    if record["selected"] != item:
        raise ValueError("transaction selection mismatch")
    for reply in record["attempts"]:
        verify_reply(reply)
        if (reply["request"]["method"] != "getTransaction"
                or reply["request"]["params"][0] != item["signature"]
                or reply["request"]["params"][1]["maxSupportedTransactionVersion"] != 0):
            raise ValueError("primary transaction request mismatch")
    result = next((reply["body"]["result"] for reply in record["attempts"]
                   if isinstance(reply.get("body", {}).get("result"), dict)), None)
    if result is not None:
        return result, "PRIMARY_V0", len(record["attempts"])
    supplement_path = supplemental / f"{item['signature']}.json"
    if not supplement_path.exists():
        return None, "UNAVAILABLE", len(record["attempts"])
    errors = [reply.get("body", {}).get("error") for reply in record["attempts"]]
    if not (len(errors) == 3 and all(isinstance(error, dict) and
            error.get("code") == -32015 and "version (1)" in error.get("message", "")
            for error in errors)):
        raise ValueError("supplement not authorized by version error")
    supplement = json.loads(supplement_path.read_text())
    if supplement["selected"] != item:
        raise ValueError("supplement selection mismatch")
    for reply in supplement["attempts"]:
        verify_reply(reply)
        if (reply["request"]["method"] != "getTransaction"
                or reply["request"]["params"][0] != item["signature"]
                or reply["request"]["params"][1]["maxSupportedTransactionVersion"] != 1):
            raise ValueError("supplement wrong transaction version")
    result = next((reply["body"]["result"] for reply in supplement["attempts"]
                   if isinstance(reply.get("body", {}).get("result"), dict)), None)
    return result, "SUPPLEMENT_V1" if result else "UNAVAILABLE", (
        len(record["attempts"]) + len(supplement["attempts"]))


def audit(route: Path, original: Path, amended: Path, supplemental: Path) -> dict:
    pools = frozen_pools(route)
    selection = json.loads((amended / "selection.json").read_text())
    if selection["source_route_sha256"] != digest(route):
        raise ValueError("selection route fingerprint mismatch")
    original_manifest = original / "capture-manifest.json"
    if selection["original_manifest_sha256"] != digest(original_manifest):
        raise ValueError("original manifest fingerprint mismatch")
    expected = []
    pages = []
    for pool, page_record in zip(pools, selection["pages"], strict=True):
        if page_record["mint"] != pool["mint"]:
            raise ValueError("page/pool mismatch")
        original_page = original / "index" / f"{pool['mint']}-00.json"
        if digest(original_page) != page_record["original_page_sha256"]:
            raise ValueError("original page fingerprint mismatch")
        record = json.loads(original_page.read_text())
        verify_reply(record)
        if (record["request"]["method"] != "getSignaturesForAddress"
                or record["request"]["params"][0] != pool["pool"]
                or record["request"]["params"][1].get("before") is not None):
            raise ValueError("original page request mismatch")
        page = successful_page(record)
        for retry in page_record["retry_attempts"]:
            path = amended / retry["path"]
            if digest(path) != retry["sha256"]:
                raise ValueError("retry fingerprint mismatch")
            reply = json.loads(path.read_text())
            verify_reply(reply)
            if (reply["request"]["method"] != "getSignaturesForAddress"
                    or reply["request"]["params"][0] != pool["pool"]
                    or reply["request"]["params"][1].get("before") is not None):
                raise ValueError("retry page request mismatch")
            candidate = successful_page(reply)
            if candidate is not None:
                page = candidate
        if page is None or len(page) != 100:
            raise ValueError("amended page missing/incomplete")
        if len({item["signature"] for item in page}) != len(page):
            raise ValueError("duplicate page signature")
        eligible = [item for item in page if item.get("err") is None and
                    item["slot"] > pool["boundary_slot"]]
        chosen = sorted(eligible, key=lambda item: (
            hashlib.sha256(f"mc020-v2:{item['signature']}".encode()).hexdigest(),
            item["signature"]))[:12]
        expected.extend({"mint": pool["mint"], "pool": pool["pool"],
                         "signature": item["signature"], "slot": item["slot"]}
                        for item in chosen)
        pages.append({"mint": pool["mint"], "rows": len(page),
                      "eligible_success": len(eligible),
                      "failed_signatures": sum(item.get("err") is not None for item in page),
                      "selected": len(chosen)})
    if expected != selection["selected"]:
        raise ValueError("hash selection mismatch")
    pool_by_mint = {pool["mint"]: pool for pool in pools}
    rows = []
    for item in expected:
        result, source, attempts = transaction_result(item, amended, supplemental)
        row = {**item, "retrieval_source": source, "attempts": attempts}
        if result is None:
            rows.append({**row, "status": "TX_UNAVAILABLE"})
            continue
        if (result["slot"] != item["slot"] or result["transaction"]["signatures"][0]
                != item["signature"] or result["meta"]["err"] is not None):
            rows.append({**row, "status": "SIGNED_IDENTITY_OR_SUCCESS_MISMATCH"})
            continue
        events, errors = sell_events(result["meta"].get("logMessages") or [])
        matching = [event for event in events if event["fields"]["pool"] == item["pool"]]
        row.update({"network_fee_lamports": result["meta"].get("fee"),
                    "compute_units_consumed": result["meta"].get("computeUnitsConsumed"),
                    "transaction_version": result.get("version"),
                    "sell_event_count": len(matching), "event_errors": errors})
        if errors:
            rows.append({**row, "status": "EVENT_DECODE_OR_ATTRIBUTION_ERROR"})
            continue
        if not matching:
            rows.append({**row, "status": "NO_SELECTED_POOL_SELL"})
            continue
        pre = token_balances(result, "preTokenBalances")
        post = token_balances(result, "postTokenBalances")
        selected_pool = pool_by_mint[item["mint"]]
        balances = {}
        for side, address, mint in (("base", selected_pool["base_vault"], item["mint"]),
                                    ("quote", selected_pool["quote_vault"], WSOL)):
            before, after = pre.get(address), post.get(address)
            if before is None or after is None or before["mint"] != mint or after[
                    "mint"] != mint:
                balances[side] = None
            else:
                balances[side] = {"pre": before["amount"], "post": after["amount"],
                                  "delta": after["amount"] - before["amount"]}
        event_rows = []
        for event in matching:
            f = event["fields"]
            gross = (f["base_amount_in"] * (f["pool_quote_token_reserves"] +
                     f["virtual_quote_reserves"]) // (f["pool_base_token_reserves"] +
                     f["base_amount_in"])) if f["pool_base_token_reserves"] + f[
                         "base_amount_in"] > 0 else None
            user_balances = {}
            for side, address, mint in (("base", f["user_base_token_account"], item["mint"]),
                                        ("quote", f["user_quote_token_account"], WSOL)):
                before, after = pre.get(address), post.get(address)
                if before is None or after is None or before["mint"] != mint or after[
                        "mint"] != mint:
                    user_balances[side] = None
                else:
                    user_balances[side] = {"pre": before["amount"],
                                           "post": after["amount"],
                                           "delta": after["amount"] - before["amount"]}
            event_rows.append({"fields": f, "raw_sha256": event["raw_sha256"],
                               "constant_product_gross": gross,
                               "gross_matches": gross == f["quote_amount_out"],
                               "fee_rounding_matches": all(
                                   f[fee] == (f["quote_amount_out"] * f[bps] + 9999) // 10_000
                                   for fee, bps in (("lp_fee", "lp_fee_basis_points"),
                                                    ("protocol_fee",
                                                     "protocol_fee_basis_points"),
                                                    ("coin_creator_fee",
                                                     "coin_creator_fee_basis_points"))),
                               "lp_identity_matches": f["quote_amount_out"] - f[
                                   "lp_fee"] == f["quote_amount_out_without_lp_fee"],
                               "net_identity_matches": f[
                                   "quote_amount_out_without_lp_fee"] - f[
                                       "protocol_fee"] - f["coin_creator_fee"] == f[
                                           "user_quote_amount_out"],
                               "user_balances": user_balances,
                               "user_base_delta_matches": (user_balances["base"] is not None
                                                           and user_balances["base"]["delta"] ==
                                                           -f["base_amount_in"]),
                               "user_quote_delta_matches": (user_balances["quote"] is not None
                                                            and user_balances["quote"]["delta"] ==
                                                            f["user_quote_amount_out"])})
        row.update({"events": event_rows, "vault_balances": balances})
        if len(event_rows) == 1 and all(balances.values()):
            f = event_rows[0]["fields"]
            row["vault_accounting_matches"] = (
                balances["base"]["pre"] == f["pool_base_token_reserves"]
                and balances["quote"]["pre"] == f["pool_quote_token_reserves"]
                and balances["base"]["delta"] == f["base_amount_in"]
                and balances["quote"]["delta"] == -f[
                    "quote_amount_out_without_lp_fee"])
            row["status"] = ("SELL_ACCOUNTING_MATCH" if row["vault_accounting_matches"]
                             and all(event_rows[0][key] for key in (
                                 "gross_matches", "fee_rounding_matches",
                                 "lp_identity_matches", "net_identity_matches"))
                             else "SELL_ACCOUNTING_MISMATCH")
        else:
            row["status"] = "SELL_VAULT_ACCOUNTING_AMBIGUOUS"
        rows.append(row)
    status_counts = dict(Counter(row["status"] for row in rows))
    return {"schema": "rocket.memecoin.mc020-landed-audit.v1",
            "route_sha256": digest(route),
            "original_manifest_sha256": digest(original_manifest),
            "amended_selection_sha256": digest(amended / "selection.json"),
            "pump_amm_idl_sha256": digest(AMM_IDL_PATH),
            "pages": pages, "selected_count": len(expected),
            "primary_v0_retrieved": sum(row["retrieval_source"] == "PRIMARY_V0"
                                        for row in rows),
            "supplement_v1_retrieved": sum(row["retrieval_source"] == "SUPPLEMENT_V1"
                                           for row in rows),
            "status_counts": status_counts,
            "sell_event_count": sum(row.get("sell_event_count", 0) for row in rows),
            "rows": rows,
            "scope": "Hash-selected landed transactions from one recent index page per pool;"
                     " no Rocket simulation, inclusion or strategy cash recovery."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("route", type=Path)
    parser.add_argument("original", type=Path)
    parser.add_argument("amended", type=Path)
    parser.add_argument("supplemental", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.route, args.original, args.amended, args.supplemental)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: report[key] for key in (
        "selected_count", "primary_v0_retrieved", "supplement_v1_retrieved",
        "sell_event_count", "status_counts")}, indent=2))
