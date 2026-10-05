"""MC-020 exact version-1 supplement for selected -32015 RPC replies."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import httpx

from scripts.research.memecoin_amm_landed_capture import RPC, rpc


def candidates(amended: Path) -> list[dict]:
    selected = json.loads((amended / "selection.json").read_text())["selected"]
    candidates = []
    for item in selected:
        path = amended / "transactions" / f"{item['signature']}.json"
        record = json.loads(path.read_text())
        if record["selected"] != item:
            raise ValueError("selected transaction mismatch")
        attempts = record["attempts"]
        if len(attempts) != 3:
            continue
        errors = [attempt.get("body", {}).get("error") for attempt in attempts]
        if all(isinstance(error, dict) and error.get("code") == -32015
               and "version (1)" in error.get("message", "") for error in errors):
            candidates.append(item)
    if len(candidates) != 2:
        raise ValueError("frozen version-1 candidate count changed")
    return candidates


def capture(amended: Path, out: Path, rpc_url: str = RPC) -> dict:
    if out.exists():
        raise ValueError("output directory exists")
    chosen = candidates(amended)
    out.mkdir(parents=True)
    with httpx.Client(timeout=20) as client:
        for number, item in enumerate(chosen):
            attempts = []
            for attempt in range(1, 4):
                time.sleep(2 if attempt == 1 else 10)
                reply = rpc(client, "getTransaction", [item["signature"],
                    {"encoding": "json", "commitment": "confirmed",
                     "maxSupportedTransactionVersion": 1}], rpc_url,
                    2000 + number * 3 + attempt)
                attempts.append(reply)
                (out / f"{item['signature']}.json").write_text(json.dumps(
                    {"selected": item, "attempts": attempts}, sort_keys=True) + "\n")
                body = reply.get("body", {})
                if (reply.get("http_status") == 200 and isinstance(body, dict)
                        and isinstance(body.get("result"), dict)):
                    break
    return {"schema": "rocket.memecoin.mc020-version1-supplement.v1",
            "selected_count": len(chosen), "saved_files": len(list(out.glob("*.json")))}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("amended", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--rpc-url", default=RPC)
    args = parser.parse_args()
    print(json.dumps(capture(args.amended, args.out, args.rpc_url), indent=2))
