"""Bounded Pump log capture using a pinged Python websocket transport."""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
import websockets

PROGRAM = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
WS_URL = "wss://api.mainnet-beta.solana.com/"
RPC_URL = "https://api.mainnet-beta.solana.com/"


def now() -> datetime:
    return datetime.now(UTC)


async def rpc(client: httpx.AsyncClient, method: str, params: list) -> object:
    response = await client.post(RPC_URL, json={"jsonrpc": "2.0", "id": 1,
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
    segment = out / "segment-000000000000.jsonl"
    fd = os.open(segment, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    sha = hashlib.sha256()
    bytes_written = frames = notifications = sync_count = create_hints = 0
    last_sync = time.monotonic()
    first_slot = last_slot = ack = None
    errors = []
    end_reason = "unknown"
    stream_ended = None
    async with httpx.AsyncClient(timeout=12) as client:
        try:
            start_slot = await rpc(client, "getSlot", [{"commitment": "confirmed"}])
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            start_slot = None
            errors.append(f"start_slot_{type(exc).__name__}")
        started = now()

        def append(raw: str, received: datetime) -> None:
            nonlocal bytes_written, frames, sync_count, last_sync
            raw_bytes = raw.encode()
            stamp = received.isoformat()
            record = {"schema": "rocket.raw-capture.v1", "received_at": stamp,
                      "available_at": stamp, "event_id": hashlib.sha256(raw_bytes).hexdigest(),
                      "raw_base64": base64.b64encode(raw_bytes).decode()}
            line = (json.dumps(record, separators=(",", ":")) + "\n").encode()
            if bytes_written + len(line) > max_bytes:
                raise ValueError("CAPTURE_DISK_BOUND")
            offset = 0
            while offset < len(line):
                offset += os.write(fd, line[offset:])
            sha.update(line)
            bytes_written += len(line)
            frames += 1
            if frames % 64 == 0 or time.monotonic() - last_sync >= 0.25:
                os.fsync(fd)
                sync_count += 1
                last_sync = time.monotonic()

        try:
            async with websockets.connect(WS_URL, open_timeout=12, ping_interval=20,
                                          ping_timeout=20, close_timeout=1,
                                          max_size=8 * 1024 * 1024) as ws:
                await ws.send(json.dumps({"jsonrpc": "2.0", "id": 1,
                                          "method": "logsSubscribe", "params": [
                                              {"mentions": [PROGRAM]},
                                              {"commitment": "confirmed"}]}))
                deadline = time.monotonic() + 12
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        end_reason = "duration_elapsed" if ack else "subscription_timeout"
                        stream_ended = now()
                        break
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
                    except TimeoutError:
                        end_reason = "duration_elapsed" if ack else "subscription_timeout"
                        stream_ended = now()
                        break
                    received = now()
                    if not isinstance(raw, str):
                        raise ValueError("nontext websocket message")
                    append(raw, received)
                    message = json.loads(raw)
                    if message.get("id") == 1:
                        if not isinstance(message.get("result"), int):
                            raise ValueError(f"subscription rejected: {message.get('error')}")
                        ack = received
                        deadline = time.monotonic() + seconds
                    elif message.get("method") == "logsNotification":
                        notifications += 1
                        result = message["params"]["result"]
                        slot = result["context"]["slot"]
                        if not isinstance(slot, int):
                            raise ValueError("notification slot missing")
                        first_slot = slot if first_slot is None else min(first_slot, slot)
                        last_slot = slot if last_slot is None else max(last_slot, slot)
                        value = result["value"]
                        if value.get("err") is None and any(line.endswith((
                                "Instruction: Create", "Instruction: CreateV2"))
                                for line in value.get("logs", [])):
                            create_hints += 1
        except Exception as exc:
            end_reason = "stream_or_disk_error"
            stream_ended = now()
            errors.append(f"{type(exc).__name__}:{exc}")
        finally:
            os.fsync(fd)
            sync_count += 1
            os.close(fd)
        ended = stream_ended or now()
        try:
            end_slot = await rpc(client, "getSlot", [{"commitment": "confirmed"}])
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            end_slot = None
            errors.append(f"end_slot_{type(exc).__name__}")
        try:
            anchor = (await rpc(client, "getSignaturesForAddress", [PROGRAM, {
                "limit": 1, "commitment": "confirmed"}]))[0]
        except (httpx.HTTPError, ValueError, KeyError, IndexError) as exc:
            anchor = None
            errors.append(f"end_anchor_{type(exc).__name__}")
    manifest = {"schema": "rocket.memecoin.capture-session.v2",
                "program_id": PROGRAM, "commitment": "confirmed",
                "endpoint_host": "api.mainnet-beta.solana.com",
                "started_at": started.isoformat(),
                "subscription_ack_at": ack.isoformat() if ack else None,
                "ended_at": ended.isoformat(), "start_slot": start_slot,
                "end_slot": end_slot, "end_index_anchor": anchor,
                "first_notification_slot": first_slot, "last_notification_slot": last_slot,
                "requested_seconds": seconds, "max_bytes": max_bytes,
                "segment": segment.name, "segment_sha256": sha.hexdigest(),
                "frames": frames, "fsync_policy": "every 64 frames or 250 ms on append, plus final sync",
                "fsync_count": sync_count, "notifications": notifications,
                "create_log_hints": create_hints, "create_transaction_responses": 0,
                "end_reason": end_reason, "errors": errors,
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
