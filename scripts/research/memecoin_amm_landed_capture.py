"""MC-020 bounded read-only index and signed PumpSwap transaction capture."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

from scripts.research.memecoin_amm_fee_capture import MC017_ROUTE_SHA256

RPC = "https://api.mainnet-beta.solana.com"


def stamp() -> str:
    return datetime.now(UTC).isoformat()


def frozen_pools(route_path: Path) -> list[dict]:
    if hashlib.sha256(route_path.read_bytes()).hexdigest() != MC017_ROUTE_SHA256:
        raise ValueError("MC-017 route fingerprint mismatch")
    route = json.loads(route_path.read_text())
    pools = []
    for row in route["rows"]:
        if row["status"] != "CANONICAL_POOL_VAULTS_DECODED":
            continue
        pools.append({"mint": row["mint"], "pool": row["pool"],
                      "boundary_slot": row["second"]["context_slot"],
                      "base_vault": row["second"]["pool"]["base_vault"],
                      "quote_vault": row["second"]["pool"]["quote_vault"]})
    if len(pools) != 3 or len({row["pool"] for row in pools}) != 3:
        raise ValueError("MC-017 pool selection mismatch")
    return sorted(pools, key=lambda row: row["mint"])


def rpc(client: httpx.Client, method: str, params: list, rpc_url: str,
        request_id: int) -> dict:
    request = {"jsonrpc": "2.0", "id": request_id,
               "method": method, "params": params}
    dispatch_at = stamp()
    try:
        response = client.post(rpc_url, json=request)
        raw = response.content
        result = {"http_status": response.status_code,
                  "raw_response_sha256": hashlib.sha256(raw).hexdigest(),
                  "raw_response_base64": base64.b64encode(raw).decode(),
                  "body": response.json()}
    except (httpx.HTTPError, ValueError) as exc:
        result = {"error": type(exc).__name__}
    return {"request": request, "dispatch_at": dispatch_at,
            "received_at": stamp(), **result}


def capture(route_path: Path, out: Path, rpc_url: str = RPC,
            pace_seconds: float = 0.5) -> dict:
    if out.exists():
        raise ValueError("output directory exists")
    pools = frozen_pools(route_path)
    out.mkdir(parents=True)
    index_dir, transaction_dir = out / "index", out / "transactions"
    index_dir.mkdir()
    transaction_dir.mkdir()
    selection = []
    pools_status = []
    request_id = 1
    with httpx.Client(timeout=20) as client:
        for pool in pools:
            before = None
            seen = set()
            signatures = []
            reached = False
            pages = 0
            errors = []
            for page in range(5):  # 5 * 100 = frozen 500-signature bound
                options = {"limit": 100, "commitment": "confirmed"}
                if before:
                    options["before"] = before
                record = rpc(client, "getSignaturesForAddress",
                             [pool["pool"], options], rpc_url, request_id)
                request_id += 1
                (index_dir / f"{pool['mint']}-{page:02d}.json").write_text(
                    json.dumps(record, sort_keys=True) + "\n")
                pages += 1
                body = record.get("body", {})
                entries = body.get("result") if isinstance(body, dict) else None
                if record.get("http_status") != 200 or not isinstance(entries, list):
                    errors.append("INDEX_RESPONSE_FAILED")
                    break
                if not entries:
                    reached = True
                    break
                for item in entries:
                    signature = item.get("signature")
                    if not isinstance(signature, str) or signature in seen:
                        errors.append("INDEX_DUPLICATE_OR_BAD_SIGNATURE")
                        continue
                    seen.add(signature)
                    signatures.append(item)
                if any(isinstance(item.get("slot"), int) and item["slot"] <=
                       pool["boundary_slot"] for item in entries):
                    reached = True
                    break
                before = entries[-1]["signature"]
                time.sleep(pace_seconds)
            eligible = sorted((item for item in signatures if item.get("err") is None
                               and isinstance(item.get("slot"), int) and item["slot"] >
                               pool["boundary_slot"]),
                              key=lambda item: (item["slot"], item["signature"]))
            chosen = eligible[:20] if reached and not errors else []
            for item in chosen:
                selection.append({"mint": pool["mint"], "pool": pool["pool"],
                                  "signature": item["signature"], "slot": item["slot"]})
            pools_status.append({**pool, "pages": pages, "indexed_signatures": len(signatures),
                                 "boundary_reached": reached, "errors": errors,
                                 "eligible_success_count": len(eligible),
                                 "indexed_failure_count": sum(item.get("err") is not None
                                                              for item in signatures),
                                 "selected_count": len(chosen)})
            time.sleep(pace_seconds)
        (out / "selection.json").write_text(json.dumps({
            "schema": "rocket.memecoin.mc020-selection.v1",
            "pools": pools_status, "selected": selection}, indent=2) + "\n")
        for item in selection:
            record = rpc(client, "getTransaction", [item["signature"],
                         {"encoding": "json", "commitment": "confirmed",
                          "maxSupportedTransactionVersion": 0}], rpc_url, request_id)
            request_id += 1
            (transaction_dir / f"{item['signature']}.json").write_text(
                json.dumps({"selected": item, **record}, sort_keys=True) + "\n")
            time.sleep(pace_seconds)
    manifest = {"schema": "rocket.memecoin.mc020-capture.v1",
                "source_route_sha256": MC017_ROUTE_SHA256,
                "rpc_url": rpc_url, "pace_seconds": pace_seconds,
                "pools": pools_status, "selected_count": len(selection),
                "saved_transaction_count": len(list(transaction_dir.glob("*.json")))}
    (out / "capture-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("route", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--rpc-url", default=RPC)
    parser.add_argument("--pace-seconds", type=float, default=0.5)
    args = parser.parse_args()
    if not 0.2 <= args.pace_seconds <= 5:
        parser.error("pace-seconds must be 0.2..5")
    print(json.dumps(capture(args.route, args.out, args.rpc_url,
                             args.pace_seconds), indent=2))
