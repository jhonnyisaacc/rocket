"""MC-019 one-bank, read-only PumpSwap fee and pool state capture."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx

from rocket.research.solana_pda import (
    PUMP_AMM_PROGRAM,
    canonical_pump_pool,
    decode_base58,
    find_program_address,
)
from scripts.research.memecoin_route_snapshot_capture import AMM_CONFIG, AMM_IDL_PATH

FEE_PROGRAM = "pfeeUxB6jkeY1Hxd7CsFCAjcbHA9rWtchMGdZ6VojVZ"
FEE_CONFIG = "5PHirr8joyTMp9JMm6nW7hNDVyEYdkzDqazxPD7RaTjx"
RPC = "https://solana-rpc.publicnode.com"


def selected(route_path: Path) -> tuple[list[dict], list[str]]:
    route = json.loads(route_path.read_text())
    if route.get("data_gate_pass") is not True:
        raise ValueError("MC-017 route gate did not pass")
    rows = sorted((row for row in route["rows"] if row["status"] ==
                   "CANONICAL_POOL_VAULTS_DECODED"), key=lambda row: row["mint"])
    if len(rows) != 3:
        raise ValueError("MC-017 known-pool selection changed")
    fee_address, _ = find_program_address(
        [b"fee_config", decode_base58(PUMP_AMM_PROGRAM)], FEE_PROGRAM)
    if fee_address != FEE_CONFIG:
        raise ValueError("fee config PDA mismatch")
    chosen = []
    addresses = [FEE_CONFIG, AMM_CONFIG]
    for row in rows:
        _, canonical = canonical_pump_pool(row["mint"])
        if row["pool"] != canonical:
            raise ValueError("canonical pool mismatch")
        second = row["second"]
        pool = second["pool"]
        item = {"mint": row["mint"], "pool": canonical,
                "base_vault": pool["base_vault"],
                "quote_vault": pool["quote_vault"]}
        chosen.append(item)
        addresses.extend([item["pool"], item["base_vault"],
                          item["quote_vault"], item["mint"]])
    if len(set(addresses)) != len(addresses):
        raise ValueError("duplicate selected account")
    return chosen, addresses


def capture(route_path: Path, out: Path, rpc_url: str = RPC) -> dict:
    if out.exists():
        raise ValueError("output file exists")
    chosen, addresses = selected(route_path)
    request = {"jsonrpc": "2.0", "id": 19, "method": "getMultipleAccounts",
               "params": [addresses, {"encoding": "base64", "commitment": "confirmed"}]}
    dispatch_at = datetime.now(UTC).isoformat()
    try:
        response = httpx.post(rpc_url, json=request, timeout=20)
        payload = {"http_status": response.status_code,
                   "raw_response_sha256": hashlib.sha256(response.content).hexdigest(),
                   "body": response.json()}
    except (httpx.HTTPError, ValueError) as exc:
        payload = {"error": type(exc).__name__}
    result = {"schema": "rocket.memecoin.mc019-one-bank-capture.v1",
              "source_route_sha256": hashlib.sha256(route_path.read_bytes()).hexdigest(),
              "pump_amm_idl_sha256": hashlib.sha256(AMM_IDL_PATH.read_bytes()).hexdigest(),
              "dispatch_at": dispatch_at, "received_at": datetime.now(UTC).isoformat(),
              "rpc_url": rpc_url, "request": request, "selected": chosen, **payload}
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return {key: result.get(key) for key in (
        "dispatch_at", "received_at", "http_status", "error",
        "raw_response_sha256")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("route", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--rpc-url", default=RPC)
    args = parser.parse_args()
    print(json.dumps(capture(args.route, args.out, args.rpc_url), indent=2))
