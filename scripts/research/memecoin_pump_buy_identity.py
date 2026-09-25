"""Later signed identity checks for MC-022's fixed five selected creates."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx

from scripts.research.memecoin_audit import decode_create_v2

RPC = "https://solana-rpc.publicnode.com"


def capture(selection_path: Path, out: Path) -> dict:
    if out.exists():
        raise ValueError("output file exists")
    selection = json.loads(selection_path.read_text())
    rows = []
    with httpx.Client(timeout=20) as client:
        for chosen in selection["selected"]:
            signature = chosen["signature"]
            request = {"jsonrpc": "2.0", "id": len(rows) + 1,
                       "method": "getTransaction", "params": [signature, {
                           "encoding": "jsonParsed", "commitment": "confirmed",
                           "maxSupportedTransactionVersion": 1}]}
            row = {"signature": signature, "mint": chosen["mint"],
                   "create_slot": chosen["slot"], "request": request,
                   "dispatch_at": datetime.now(UTC).isoformat()}
            try:
                response = client.post(RPC, json=request)
                row.update({"received_at": datetime.now(UTC).isoformat(),
                            "http_status": response.status_code,
                            "raw_response_sha256": hashlib.sha256(response.content).hexdigest(),
                            "response": response.json()})
                if response.status_code != 200 or row["response"].get("error"):
                    row["status"] = "RPC_ERROR"
                else:
                    decoded = decode_create_v2(row["response"], signature)
                    if decoded["mint"] != chosen["mint"] or decoded["slot"] != chosen["slot"]:
                        raise ValueError("selected create mint or slot mismatch")
                    row["status"] = "STRICT_IDENTITY"
                    row["decoded"] = decoded
            except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
                row["status"] = "UNRESOLVED"
                row["error"] = f"{type(exc).__name__}:{exc}"
            rows.append(row)
            out.write_text(json.dumps({"schema": "rocket.memecoin.mc022-identity.v1",
                                       "selection_sha256": hashlib.sha256(
                                           selection_path.read_bytes()).hexdigest(),
                                       "rows": rows}, indent=2, sort_keys=True) + "\n")
    return {"selected": len(rows),
            "strict": sum(row["status"] == "STRICT_IDENTITY" for row in rows),
            "unresolved": sum(row["status"] != "STRICT_IDENTITY" for row in rows)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("selection", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(capture(args.selection, args.out), indent=2))
