"""MC-014 bounded read-only signed buy retrieval at the five-second decision clock."""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import json
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

import httpx

from rocket.research.pump_events import EventDecodeError, PumpEventDecoder
from scripts.research.memecoin_audit import IDL_PATH, NATIVE_QUOTE, pump_data_logs

RPC = "https://solana-rpc.publicnode.com"


def stamp() -> str:
    return datetime.now(UTC).isoformat()


def events_in_frame(record: dict, decoder: PumpEventDecoder) -> list[dict]:
    raw = base64.b64decode(record["raw_base64"])
    message = json.loads(raw)
    if message.get("method") != "logsNotification":
        return []
    notification = message["params"]["result"]
    value = notification["value"]
    if value.get("err") is not None:
        return []
    events = []
    for _, encoded in pump_data_logs(value.get("logs", [])):
        if " " in encoded:
            continue
        event = decoder.decode(encoded)
        if event and event["event_type"] in ("CreateEvent", "TradeEvent"):
            events.append({"signature": value["signature"],
                           "slot": notification["context"]["slot"],
                           "event_type": event["event_type"],
                           "fields": event["fields"],
                           "event_sha256": event["event_sha256"],
                           "frame_source_hash": hashlib.sha256(raw).hexdigest(),
                           "received_at": record["received_at"]})
    return events


async def capture(session: Path, out: Path, *, max_seconds: int, max_bytes: int,
                  max_selected: int, rpc_url: str) -> dict:
    if out.exists():
        raise ValueError("output directory already exists")
    out.mkdir(parents=True)
    responses = out / "responses"
    responses.mkdir()
    started = datetime.now(UTC)
    deadline = started + timedelta(seconds=max_seconds)
    decoder = PumpEventDecoder(IDL_PATH)
    segment = session / "segment-000000000000.jsonl"
    cursor = frames = selected_count = saved_bytes = 0
    creates: list[dict] = []
    selected: list[dict] = []
    active_mints: dict[str, dict] = {}
    per_mint: dict[str, set[str]] = defaultdict(set)
    pending: set[asyncio.Task] = set()
    errors: list[str] = []
    semaphore = asyncio.Semaphore(8)
    write_lock = asyncio.Lock()
    end_reason = "unknown"

    async with httpx.AsyncClient(timeout=4, limits=httpx.Limits(max_connections=8)) as client:

        async def fetch(chosen: dict) -> None:
            nonlocal saved_bytes
            attempts = []
            async with semaphore:
                for number in range(3):
                    if number:
                        await asyncio.sleep((0.5, 1.0)[number - 1])
                    requested_at = stamp()
                    try:
                        response = await client.post(rpc_url, json={
                            "jsonrpc": "2.0", "id": number + 1,
                            "method": "getTransaction", "params": [chosen["signature"],
                                                                   {"encoding": "jsonParsed",
                                                                    "commitment": "confirmed",
                                                                    "maxSupportedTransactionVersion": 1}]})
                        item = {"requested_at": requested_at,
                                "received_at": stamp(),
                                "http_status": response.status_code,
                                "raw_response_sha256": hashlib.sha256(response.content).hexdigest(),
                                "body": response.json()}
                    except (httpx.HTTPError, ValueError) as exc:
                        item = {"requested_at": requested_at, "received_at": stamp(),
                                "error": type(exc).__name__}
                    attempts.append(item)
                    if item.get("http_status") == 200 and item.get("body", {}).get("result"):
                        break
            saved = {"schema": "rocket.memecoin.mc014-signed-buy-response.v1",
                     "signature": chosen["signature"],
                     "rpc_host": urlparse(rpc_url).hostname,
                     "attempts": attempts}
            raw = (json.dumps(saved, sort_keys=True) + "\n").encode()
            async with write_lock:
                if saved_bytes + len(raw) > max_bytes:
                    errors.append("RESPONSE_DISK_BOUND")
                else:
                    (responses / f"{chosen['signature']}.json").write_bytes(raw)
                    saved_bytes += len(raw)

        while datetime.now(UTC) < deadline:
            if segment.exists():
                with segment.open("rb") as file:
                    file.seek(cursor)
                    for _ in range(2000):
                        line = file.readline()
                        if not line or not line.endswith(b"\n"):
                            break
                        cursor = file.tell()
                        frames += 1
                        try:
                            record = json.loads(line)
                            events = events_in_frame(record, decoder)
                        except (KeyError, ValueError, EventDecodeError,
                                json.JSONDecodeError) as exc:
                            errors.append(f"FRAME_{frames}_{type(exc).__name__}")
                            continue
                        for event in events:
                            fields = event["fields"]
                            if event["event_type"] == "CreateEvent":
                                created = {"signature": event["signature"],
                                           "slot": event["slot"],
                                           "mint": fields["mint"],
                                           "quote_mint": fields.get("quote_mint"),
                                           "is_mayhem_mode": fields.get("is_mayhem_mode"),
                                           "received_at": event["received_at"],
                                           "event_sha256": event["event_sha256"],
                                           "frame_source_hash": event["frame_source_hash"]}
                                creates.append(created)
                                if (created["quote_mint"] == NATIVE_QUOTE
                                        and not created["is_mayhem_mode"]):
                                    active_mints[created["mint"]] = created
                            elif fields.get("is_buy") and (created := active_mints.get(
                                    fields["mint"])):
                                received = datetime.fromisoformat(event["received_at"])
                                start = datetime.fromisoformat(created["received_at"])
                                if not start <= received <= start + timedelta(seconds=5):
                                    continue
                                seen = per_mint[created["mint"]]
                                if event["signature"] in seen or len(seen) >= 3:
                                    continue
                                seen.add(event["signature"])
                                if selected_count >= max_selected:
                                    if "SELECTION_BOUND" not in errors:
                                        errors.append("SELECTION_BOUND")
                                    continue
                                selected_count += 1
                                chosen = {"signature": event["signature"],
                                          "slot": event["slot"], "mint": fields["mint"],
                                          "create_signature": created["signature"],
                                          "create_received_at": created["received_at"],
                                          "event_received_at": event["received_at"],
                                          "checkpoint_at": (start + timedelta(seconds=5)).isoformat(),
                                          "event_user": fields["user"],
                                          "event_token_amount": fields["token_amount"],
                                          "event_sha256": event["event_sha256"],
                                          "frame_source_hash": event["frame_source_hash"]}
                                selected.append(chosen)
                                task = asyncio.create_task(fetch(chosen))
                                pending.add(task)
                                task.add_done_callback(pending.discard)
            manifest = session / "capture-manifest.json"
            if manifest.exists() and not pending and segment.exists() and (
                    cursor == segment.stat().st_size):
                end_reason = "capture_finished_and_requests_attempted"
                break
            await asyncio.sleep(0.1)
        else:
            end_reason = "companion_deadline"
        if pending:
            outcomes = await asyncio.gather(*pending, return_exceptions=True)
            errors.extend(f"TASK_{type(item).__name__}" for item in outcomes
                          if isinstance(item, BaseException))

    creates_path = out / "creates.jsonl"
    selected_path = out / "selected.jsonl"
    creates_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n"
                                     for row in creates))
    selected_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n"
                                      for row in selected))
    source_manifest = session / "capture-manifest.json"
    source = json.loads(source_manifest.read_text()) if source_manifest.exists() else None
    summary = {"schema": "rocket.memecoin.mc014-live-actor-companion.v1",
               "started_at": started.isoformat(), "ended_at": stamp(),
               "end_reason": end_reason, "max_seconds": max_seconds,
               "max_bytes": max_bytes, "max_selected": max_selected,
               "saved_response_bytes": saved_bytes,
               "parsed_frame_count": frames, "decoded_create_count": len(creates),
               "selected_buy_count": len(selected), "response_file_count": len(list(
                   responses.glob("*.json"))), "errors": errors,
               "source_capture_manifest_sha256": (
                   hashlib.sha256(source_manifest.read_bytes()).hexdigest() if source else None),
               "source_segment_sha256": source.get("segment_sha256") if source else None,
               "idl_sha256": decoder.idl_sha256,
               "creates_sha256": hashlib.sha256(creates_path.read_bytes()).hexdigest(),
               "selected_sha256": hashlib.sha256(selected_path.read_bytes()).hexdigest()}
    (out / "companion-manifest.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("session", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--max-seconds", type=int, default=240)
    parser.add_argument("--max-bytes", type=int, default=33554432)
    parser.add_argument("--max-selected", type=int, default=400)
    parser.add_argument("--rpc-url", default=RPC)
    args = parser.parse_args()
    if not 180 <= args.max_seconds <= 300 or not 1024 <= args.max_bytes <= 33554432 or not (
            1 <= args.max_selected <= 400):
        parser.error("bounds: seconds 180..300, bytes 1024..33554432, selected 1..400")
    print(json.dumps(asyncio.run(capture(args.session, args.out,
                                         max_seconds=args.max_seconds,
                                         max_bytes=args.max_bytes,
                                         max_selected=args.max_selected,
                                         rpc_url=args.rpc_url)), indent=2))
