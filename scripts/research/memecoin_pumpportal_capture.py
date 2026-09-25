"""Bounded read-only new-token notifications with original receive clocks."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import websockets

from rocket.capture.spool import RawCaptureSpool

WS_URL = "wss://pumpportal.fun/api/data"


async def capture(out: Path, seconds: int, max_bytes: int) -> dict:
    if out.exists():
        raise FileExistsError(out)
    out.mkdir(parents=True)
    started_at = datetime.now(UTC)
    spool = RawCaptureSpool(out, max_bytes=max_bytes, reserve_bytes=0,
                            segment_bytes=max_bytes)
    ack_at = None
    candidates = frames = 0
    errors: list[str] = []
    end_reason = "unknown"
    try:
        async with websockets.connect(WS_URL, open_timeout=12, max_size=2 * 1024 * 1024,
                                      ping_interval=20) as ws:
            await ws.send(json.dumps({"method": "subscribeNewToken"}))
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
                received_at = datetime.now(UTC)
                if not isinstance(raw, str):
                    raise ValueError("nontext websocket frame")
                spool.append_batch([(raw.encode(), received_at)])
                frames += 1
                message = json.loads(raw)
                if message.get("message") == "Successfully subscribed to token creation events.":
                    if ack_at is not None:
                        raise ValueError("duplicate subscription acknowledgement")
                    ack_at = received_at
                    deadline = time.monotonic() + seconds
                elif message.get("txType") == "create":
                    if not isinstance(message.get("signature"), str) or not isinstance(
                            message.get("mint"), str):
                        raise ValueError("create notification lacks signature or mint")
                    candidates += 1
                elif "error" in message:
                    raise ValueError(f"provider error: {message['error']}")
    except Exception as exc:
        end_reason = "stream_or_disk_error"
        errors.append(f"{type(exc).__name__}:{exc}")
    finally:
        spool.close()
    ended_at = datetime.now(UTC)
    segment = out / "segment-000000000000.jsonl"
    manifest = {
        "schema": "rocket.memecoin.third-party-create-capture.v1",
        "endpoint_host": "pumpportal.fun", "subscription": "subscribeNewToken",
        "started_at": started_at.isoformat(),
        "subscription_ack_at": ack_at.isoformat() if ack_at else None,
        "ended_at": ended_at.isoformat(), "requested_seconds": seconds,
        "max_bytes": max_bytes, "segment": segment.name,
        "segment_sha256": hashlib.sha256(segment.read_bytes()).hexdigest()
        if segment.exists() else None,
        "frames": frames, "create_notifications": candidates,
        "end_reason": end_reason, "errors": errors,
        "coverage_status": "UNVERIFIED",
    }
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
