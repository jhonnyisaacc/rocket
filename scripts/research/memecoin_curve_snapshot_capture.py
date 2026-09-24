"""MC-013 bounded live companion: read Pump curve accounts at receipt +7/+67s."""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import heapq
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from rocket.research.pump_events import EventDecodeError, PumpEventDecoder
from scripts.research.memecoin_audit import IDL_PATH, pump_data_logs

RPC = "https://solana-rpc.publicnode.com"


def stamp() -> str:
    return datetime.now(UTC).isoformat()


def creates_in_frame(record: dict, decoder: PumpEventDecoder) -> list[dict]:
    raw = base64.b64decode(record["raw_base64"])
    message = json.loads(raw)
    if message.get("method") != "logsNotification":
        return []
    notification = message["params"]["result"]
    value = notification["value"]
    if value.get("err") is not None:
        return []
    result = []
    for _, encoded in pump_data_logs(value.get("logs", [])):
        if " " in encoded:
            continue
        event = decoder.decode(encoded)
        if event and event["event_type"] == "CreateEvent":
            fields = event["fields"]
            result.append({"signature": value["signature"],
                           "slot": notification["context"]["slot"],
                           "mint": fields["mint"],
                           "bonding_curve": fields["bonding_curve"],
                           "quote_mint": fields.get("quote_mint"),
                           "is_mayhem_mode": fields.get("is_mayhem_mode"),
                           "event_time": datetime.fromtimestamp(fields["timestamp"], UTC).isoformat(),
                           "create_received_at": record["received_at"],
                           "frame_source_hash": hashlib.sha256(raw).hexdigest(),
                           "event_sha256": event["event_sha256"]})
    return result


async def capture(session: Path, out: Path, *, max_seconds: int, max_bytes: int,
                  rpc_url: str) -> dict:
    if out.exists():
        raise ValueError("output directory already exists")
    out.mkdir(parents=True)
    responses = out / "responses"
    responses.mkdir()
    decoder = PumpEventDecoder(IDL_PATH)
    started = datetime.now(UTC)
    deadline = started + timedelta(seconds=max_seconds)
    segment = session / "segment-000000000000.jsonl"
    cursor = 0
    frames = 0
    decoded_creates: list[dict] = []
    seen = set()
    queue: list[tuple[datetime, int, dict]] = []
    pending: set[asyncio.Task] = set()
    errors: list[str] = []
    batches = 0
    saved_bytes = 0
    sequence = 0
    ended_reason = "unknown"
    lock = asyncio.Lock()

    async with httpx.AsyncClient(timeout=20) as client:

        async def request_batch(items: list[dict], number: int) -> None:
            nonlocal saved_bytes
            addresses = [item["bonding_curve"] for item in items]
            request = {"jsonrpc": "2.0", "id": number + 1,
                       "method": "getMultipleAccounts",
                       "params": [addresses, {"encoding": "base64", "commitment": "confirmed"}]}
            dispatch_at = stamp()
            try:
                response = await client.post(rpc_url, json=request)
                item = {"http_status": response.status_code,
                        "raw_response_sha256": hashlib.sha256(response.content).hexdigest(),
                        "body": response.json()}
            except (httpx.HTTPError, ValueError) as exc:
                item = {"error": type(exc).__name__}
            received_at = stamp()
            record = {"schema": "rocket.memecoin.mc013-curve-read.v1",
                      "batch_number": number, "requested": items,
                      "dispatch_at": dispatch_at, "received_at": received_at,
                      "rpc_host": "solana-rpc.publicnode.com", **item}
            data = (json.dumps(record, sort_keys=True) + "\n").encode()
            async with lock:
                if saved_bytes + len(data) > max_bytes:
                    errors.append("RESPONSE_DISK_BOUND")
                else:
                    (responses / f"batch-{number:06d}.json").write_bytes(data)
                    saved_bytes += len(data)

        while datetime.now(UTC) < deadline:
            if segment.exists():
                with segment.open("rb") as file:
                    file.seek(cursor)
                    for _ in range(1000):
                        line = file.readline()
                        if not line or not line.endswith(b"\n"):
                            break
                        cursor = file.tell()
                        frames += 1
                        try:
                            record = json.loads(line)
                            candidates = creates_in_frame(record, decoder)
                        except (KeyError, ValueError, EventDecodeError, json.JSONDecodeError) as exc:
                            errors.append(f"FRAME_{frames}_{type(exc).__name__}")
                            continue
                        for created in candidates:
                            if created["signature"] in seen:
                                continue
                            seen.add(created["signature"])
                            decoded_creates.append(created)
                            received = datetime.fromisoformat(created["create_received_at"])
                            for phase, delay in (("entry", 7), ("exit", 67)):
                                target = received + timedelta(seconds=delay)
                                scheduled = {"signature": created["signature"],
                                             "mint": created["mint"],
                                             "bonding_curve": created["bonding_curve"],
                                             "phase": phase, "target_at": target.isoformat(),
                                             "create_received_at": created["create_received_at"]}
                                heapq.heappush(queue, (target, sequence, scheduled))
                                sequence += 1
            now = datetime.now(UTC)
            due = []
            while queue and queue[0][0] <= now and len(due) < 30:
                due.append(heapq.heappop(queue)[2])
            if due:
                number = batches
                batches += 1
                task = asyncio.create_task(request_batch(due, number))
                pending.add(task)
                task.add_done_callback(pending.discard)
            manifest = session / "capture-manifest.json"
            if manifest.exists() and not queue and not pending and segment.exists() and (
                    cursor == segment.stat().st_size):
                ended_reason = "capture_finished_and_reads_attempted"
                break
            await asyncio.sleep(0.1)
        else:
            ended_reason = "companion_deadline"
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    creates_path = out / "creates.jsonl"
    creates_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n"
                                     for row in decoded_creates))
    source_manifest = session / "capture-manifest.json"
    source = json.loads(source_manifest.read_text()) if source_manifest.exists() else None
    summary = {"schema": "rocket.memecoin.mc013-curve-companion.v1",
               "started_at": started.isoformat(), "ended_at": stamp(),
               "end_reason": ended_reason, "max_seconds": max_seconds,
               "max_bytes": max_bytes, "saved_response_bytes": saved_bytes,
               "source_capture_manifest_sha256": (hashlib.sha256(source_manifest.read_bytes()).hexdigest()
                                                  if source else None),
               "source_segment_sha256": source.get("segment_sha256") if source else None,
               "parsed_frame_count": frames, "decoded_create_count": len(decoded_creates),
               "scheduled_read_count": sequence, "dispatched_batch_count": batches,
               "unattempted_read_count": len(queue), "errors": errors,
               "idl_sha256": decoder.idl_sha256,
               "creates_sha256": hashlib.sha256(creates_path.read_bytes()).hexdigest()}
    (out / "companion-manifest.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("session", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--max-seconds", type=int, default=720)
    parser.add_argument("--max-bytes", type=int, default=33554432)
    parser.add_argument("--rpc-url", default=RPC)
    args = parser.parse_args()
    if not 60 <= args.max_seconds <= 900 or not 1024 <= args.max_bytes <= 33554432:
        parser.error("max-seconds must be 60..900 and max-bytes 1024..33554432")
    print(json.dumps(asyncio.run(capture(args.session, args.out,
                                         max_seconds=args.max_seconds,
                                         max_bytes=args.max_bytes,
                                         rpc_url=args.rpc_url)), indent=2))
