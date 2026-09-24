"""Bounded, read-only Pump block subscription with original receive clocks."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
import websockets

from rocket.capture.spool import RawCaptureSpool

PROGRAM = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
WS_URL = "wss://solana-rpc.publicnode.com"
INDEX_URL = "https://api.mainnet-beta.solana.com"


def now() -> datetime:
    return datetime.now(UTC)


async def rpc(method: str, params: list) -> object:
    async with httpx.AsyncClient(timeout=12) as client:
        response = await client.post(INDEX_URL, json={"jsonrpc": "2.0", "id": 1,
                                                     "method": method, "params": params})
        response.raise_for_status()
        body = response.json()
    if "error" in body:
        raise ValueError(f"{method}: {body['error']}")
    return body["result"]


async def capture(out: Path, seconds: int, max_bytes: int) -> dict:
    if out.exists():
        raise FileExistsError(out)
    out.mkdir(parents=True)
    errors: list[str] = []
    try:
        start_slot = await rpc("getSlot", [{"commitment": "confirmed"}])
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        start_slot = None
        errors.append(f"start_slot_{type(exc).__name__}")
    started_at = now()
    first_slot = last_slot = None
    frames = blocks = transactions = 0
    ack_at = None
    end_reason = "unknown"
    spool = RawCaptureSpool(out, max_bytes=max_bytes, reserve_bytes=0,
                            segment_bytes=max_bytes)
    try:
        async with websockets.connect(WS_URL, open_timeout=12, max_size=16 * 1024 * 1024,
                                      ping_interval=20) as ws:
            request = {"jsonrpc": "2.0", "id": 1, "method": "blockSubscribe", "params": [
                {"mentionsAccountOrProgram": PROGRAM},
                {"commitment": "confirmed", "encoding": "base64", "transactionDetails": "full",
                 "maxSupportedTransactionVersion": 1, "showRewards": False}]}
            await ws.send(json.dumps(request, separators=(",", ":")))
            deadline = time.monotonic() + 12
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    end_reason = "duration_elapsed" if ack_at else "subscription_timeout"
                    break
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
                except TimeoutError:
                    end_reason = "duration_elapsed" if ack_at else "subscription_timeout"
                    break
                received_at = now()
                if not isinstance(raw, str):
                    raise ValueError("nontext websocket frame")
                spool.append_batch([(raw.encode(), received_at)])
                frames += 1
                message = json.loads(raw)
                if message.get("id") == 1:
                    if not isinstance(message.get("result"), int):
                        raise ValueError(f"block subscription rejected: {message.get('error')}")
                    ack_at = received_at
                    deadline = time.monotonic() + seconds
                elif message.get("method") == "blockNotification":
                    value = message["params"]["result"]["value"]
                    slot = value["slot"]
                    if not isinstance(slot, int):
                        raise ValueError("block slot missing")
                    blocks += 1
                    first_slot = slot if first_slot is None else min(first_slot, slot)
                    last_slot = slot if last_slot is None else max(last_slot, slot)
                    if value.get("err") is not None or value.get("block") is None:
                        errors.append(f"block_{slot}_{value.get('err')}")
                    else:
                        transactions += len(value["block"]["transactions"])
    except Exception as exc:
        end_reason = "stream_or_disk_error"
        errors.append(f"{type(exc).__name__}:{exc}")
    finally:
        spool.close()
    ended_at = now()
    try:
        end_slot = await rpc("getSlot", [{"commitment": "confirmed"}])
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        end_slot = None
        errors.append(f"end_slot_{type(exc).__name__}")
    try:
        anchor = (await rpc("getSignaturesForAddress", [PROGRAM, {"limit": 1,
                                                                  "commitment": "confirmed"}]))[0]
    except (httpx.HTTPError, ValueError, KeyError, IndexError) as exc:
        anchor = None
        errors.append(f"end_anchor_{type(exc).__name__}")
    segment = out / "segment-000000000000.jsonl"
    manifest = {"schema": "rocket.memecoin.block-capture.v1", "program_id": PROGRAM,
                "commitment": "confirmed", "endpoint_host": "solana-rpc.publicnode.com",
                "index_provider_host": "api.mainnet-beta.solana.com",
                "started_at": started_at.isoformat(),
                "subscription_ack_at": ack_at.isoformat() if ack_at else None,
                "ended_at": ended_at.isoformat(), "start_slot": start_slot,
                "end_slot": end_slot, "end_index_anchor": anchor,
                "first_notification_slot": first_slot, "last_notification_slot": last_slot,
                "requested_seconds": seconds, "max_bytes": max_bytes,
                "segment": segment.name, "segment_sha256": hashlib.sha256(segment.read_bytes()).hexdigest()
                if segment.exists() else None, "frames": frames, "blocks": blocks,
                "transactions": transactions, "end_reason": end_reason, "errors": errors,
                "coverage_status": "UNVERIFIED"}
    (out / "capture-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seconds", type=int, required=True)
    parser.add_argument("--max-bytes", type=int, required=True)
    args = parser.parse_args()
    if not 5 <= args.seconds <= 900 or not 1024 <= args.max_bytes <= 536870912:
        parser.error("seconds must be 5..900 and max-bytes 1024..536870912")
    result = asyncio.run(capture(args.out, args.seconds, args.max_bytes))
    print(json.dumps(result, indent=2))
    if result["end_reason"] != "duration_elapsed" or result["errors"]:
        raise SystemExit(1)
