"""MC-020 amended bounded page-zero sample and signed transaction retrieval."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import httpx

from scripts.research.memecoin_amm_landed_capture import RPC, frozen_pools, rpc


def successful_page(record: dict) -> list[dict] | None:
    body = record.get("body", {})
    result = body.get("result") if isinstance(body, dict) else None
    if record.get("http_status") != 200 or not isinstance(result, list):
        return None
    return result


def capture(route_path: Path, original: Path, out: Path, rpc_url: str = RPC) -> dict:
    if out.exists():
        raise ValueError("output directory exists")
    pools = frozen_pools(route_path)
    out.mkdir(parents=True)
    (out / "index-retries").mkdir()
    (out / "transactions").mkdir()
    selected = []
    page_records = []
    with httpx.Client(timeout=20) as client:
        for pool in pools:
            source = original / "index" / f"{pool['mint']}-00.json"
            record = json.loads(source.read_text())
            page = successful_page(record)
            attempts = []
            if page is None:
                # The frozen amendment permits at most three identical retries.
                for number in range(1, 4):
                    time.sleep(10)
                    retry = rpc(client, "getSignaturesForAddress",
                                [pool["pool"], {"limit": 100,
                                                 "commitment": "confirmed"}],
                                rpc_url, 200 + number)
                    path = out / "index-retries" / f"{pool['mint']}-{number}.json"
                    path.write_text(json.dumps(retry, sort_keys=True) + "\n")
                    attempts.append({"path": str(path.relative_to(out)),
                                     "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                                     "http_status": retry.get("http_status")})
                    page = successful_page(retry)
                    if page is not None:
                        break
            page_records.append({**pool, "original_page_sha256": hashlib.sha256(
                source.read_bytes()).hexdigest(), "retry_attempts": attempts,
                "usable_page": page is not None,
                "page_count": len(page) if page is not None else None})
            if page is None:
                continue
            if any(not isinstance(item.get("slot"), int) or not isinstance(
                    item.get("signature"), str) for item in page):
                raise ValueError("malformed page entry")
            eligible = [item for item in page if item.get("err") is None
                        and item["slot"] > pool["boundary_slot"]]
            chosen = sorted(eligible, key=lambda item: (
                hashlib.sha256(f"mc020-v2:{item['signature']}".encode()).hexdigest(),
                item["signature"]))[:12]
            page_records[-1].update({"eligible_success_count": len(eligible),
                                     "failed_signature_count": sum(
                                         item.get("err") is not None for item in page),
                                     "selected_count": len(chosen)})
            selected.extend({"mint": pool["mint"], "pool": pool["pool"],
                             "signature": item["signature"], "slot": item["slot"]}
                            for item in chosen)
        selection = {"schema": "rocket.memecoin.mc020-amended-selection.v1",
                     "source_route_sha256": hashlib.sha256(route_path.read_bytes()).hexdigest(),
                     "original_manifest_sha256": hashlib.sha256((
                         original / "capture-manifest.json").read_bytes()).hexdigest(),
                     "pages": page_records, "selected": selected}
        (out / "selection.json").write_text(json.dumps(selection, indent=2) + "\n")
        for number, item in enumerate(selected):
            attempts = []
            for attempt in range(1, 4):
                time.sleep(2 if attempt == 1 else 10)
                reply = rpc(client, "getTransaction", [item["signature"],
                    {"encoding": "json", "commitment": "confirmed",
                     "maxSupportedTransactionVersion": 0}], rpc_url,
                    1000 + number * 3 + attempt)
                attempts.append(reply)
                path = out / "transactions" / f"{item['signature']}.json"
                path.write_text(json.dumps({"selected": item,
                                            "attempts": attempts}, sort_keys=True) + "\n")
                body = reply.get("body", {})
                if (reply.get("http_status") == 200 and isinstance(body, dict)
                        and isinstance(body.get("result"), dict)):
                    break
    summary = {"schema": "rocket.memecoin.mc020-amended-capture.v1",
               "selected_count": len(selected),
               "saved_transaction_files": len(list((out / "transactions").glob("*.json"))),
               "pages": page_records}
    (out / "capture-manifest.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("route", type=Path)
    parser.add_argument("original", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--rpc-url", default=RPC)
    args = parser.parse_args()
    print(json.dumps(capture(args.route, args.original, args.out, args.rpc_url), indent=2))
