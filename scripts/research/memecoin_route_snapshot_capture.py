"""MC-017 bounded canonical PumpSwap route reads near create receipt +67 seconds."""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import heapq
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

import httpx

from rocket.research.pump_events import EventDecodeError, PumpEventDecoder
from rocket.research.solana_pda import (
    PUMP_AMM_PROGRAM,
    WSOL_MINT,
    canonical_pump_pool,
    encode_base58,
)
from scripts.research.memecoin_audit import IDL_PATH, NATIVE_QUOTE
from scripts.research.memecoin_curve_snapshot_capture import creates_in_frame

RPC = "https://solana-rpc.publicnode.com"
AMM_IDL_PATH = Path(__file__).resolve().parents[2] / (
    "docs/research/memecoin/protocol/pump-amm-81091419.json")
AMM_CONFIG = "ADyA8hdefvWN2dbGGWFotbzWxrAvLW83WG6QCVXvJKqw"
POOL_DISCRIMINATOR = bytes([241, 154, 109, 4, 17, 177, 109, 188])


def stamp() -> str:
    return datetime.now(UTC).isoformat()


def pool_vaults(account: dict | None, mint: str) -> tuple[str, str] | None:
    if account is None or account.get("owner") != PUMP_AMM_PROGRAM:
        return None
    data = account.get("data")
    if not isinstance(data, list) or len(data) != 2 or data[1] != "base64":
        return None
    raw = base64.b64decode(data[0])
    if (len(raw) < 203 or raw[:8] != POOL_DISCRIMINATOR
            or encode_base58(raw[43:75]) != mint
            or encode_base58(raw[75:107]) != WSOL_MINT):
        return None
    return encode_base58(raw[139:171]), encode_base58(raw[171:203])


async def capture(session: Path, out: Path, *, max_seconds: int, max_bytes: int,
                  rpc_url: str) -> dict:
    if out.exists():
        raise ValueError("output directory already exists")
    out.mkdir(parents=True)
    first_dir = out / "first"
    second_dir = out / "second"
    first_dir.mkdir()
    second_dir.mkdir()
    decoder = PumpEventDecoder(IDL_PATH)
    started = datetime.now(UTC)
    deadline = started + timedelta(seconds=max_seconds)
    segment = session / "segment-000000000000.jsonl"
    cursor = frames = batches = saved_bytes = second_count = sequence = 0
    decoded_creates: list[dict] = []
    selected: list[dict] = []
    seen = set()
    queue: list[tuple[datetime, int, dict]] = []
    pending: set[asyncio.Task] = set()
    errors: list[str] = []
    end_reason = "unknown"
    semaphore = asyncio.Semaphore(8)
    lock = asyncio.Lock()

    async with httpx.AsyncClient(timeout=15, limits=httpx.Limits(max_connections=8)) as client:

        async def rpc(addresses: list[str], number: int) -> dict:
            dispatch_at = stamp()
            try:
                async with semaphore:
                    response = await client.post(rpc_url, json={
                        "jsonrpc": "2.0", "id": number + 1,
                        "method": "getMultipleAccounts",
                        "params": [addresses, {"encoding": "base64", "commitment": "confirmed"}]})
                payload = {"http_status": response.status_code,
                           "raw_response_sha256": hashlib.sha256(response.content).hexdigest(),
                           "body": response.json()}
            except (httpx.HTTPError, ValueError) as exc:
                payload = {"error": type(exc).__name__}
            return {"dispatch_at": dispatch_at, "received_at": stamp(),
                    "rpc_host": urlparse(rpc_url).hostname,
                    "addresses": addresses, **payload}

        async def save(folder: Path, name: str, record: dict) -> None:
            nonlocal saved_bytes
            raw = (json.dumps(record, sort_keys=True) + "\n").encode()
            async with lock:
                if saved_bytes + len(raw) > max_bytes:
                    if "RESPONSE_DISK_BOUND" not in errors:
                        errors.append("RESPONSE_DISK_BOUND")
                else:
                    (folder / name).write_bytes(raw)
                    saved_bytes += len(raw)

        async def request_second(chosen: dict, vaults: tuple[str, str], number: int) -> None:
            addresses = [chosen["bonding_curve"], chosen["pool"],
                         *vaults, AMM_CONFIG]
            response = await rpc(addresses, number)
            await save(second_dir, f"{chosen['signature']}.json", {
                "schema": "rocket.memecoin.mc017-route-second.v1",
                "requested": chosen, **response})

        async def request_first(items: list[dict], number: int) -> None:
            nonlocal second_count
            addresses = [address for item in items for address in (
                item["bonding_curve"], item["pool"])] + [AMM_CONFIG]
            response = await rpc(addresses, number)
            record = {"schema": "rocket.memecoin.mc017-route-first.v1",
                      "batch_number": number, "requested": items, **response}
            await save(first_dir, f"batch-{number:06d}.json", record)
            body = response.get("body", {})
            values = body.get("result", {}).get("value") if isinstance(body, dict) else None
            if not isinstance(values, list) or len(values) != len(addresses):
                return
            for index, chosen in enumerate(items):
                account = values[2 * index + 1]
                if account is None:
                    continue
                vaults = pool_vaults(account, chosen["mint"])
                if vaults is None:
                    continue
                second_count += 1
                await request_second(chosen, vaults, 1000000 + second_count)

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
                            candidates = creates_in_frame(json.loads(line), decoder)
                        except (KeyError, ValueError, EventDecodeError,
                                json.JSONDecodeError) as exc:
                            errors.append(f"FRAME_{frames}_{type(exc).__name__}")
                            continue
                        for created in candidates:
                            if created["signature"] in seen:
                                continue
                            seen.add(created["signature"])
                            decoded_creates.append(created)
                            if created["quote_mint"] != NATIVE_QUOTE or created[
                                    "is_mayhem_mode"]:
                                continue
                            authority, pool = canonical_pump_pool(created["mint"])
                            target = datetime.fromisoformat(created[
                                "create_received_at"]) + timedelta(seconds=67)
                            chosen = {**created, "pool_authority": authority,
                                      "pool": pool, "target_at": target.isoformat()}
                            selected.append(chosen)
                            heapq.heappush(queue, (target, sequence, chosen))
                            sequence += 1
            due = []
            now = datetime.now(UTC)
            while queue and queue[0][0] <= now and len(due) < 20:
                due.append(heapq.heappop(queue)[2])
            if due:
                number = batches
                batches += 1
                task = asyncio.create_task(request_first(due, number))
                pending.add(task)
                task.add_done_callback(pending.discard)
            manifest = session / "capture-manifest.json"
            if (manifest.exists() and not queue and not pending and segment.exists()
                    and cursor == segment.stat().st_size):
                end_reason = "capture_finished_and_reads_attempted"
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
                                     for row in decoded_creates))
    selected_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n"
                                      for row in selected))
    source_path = session / "capture-manifest.json"
    source = json.loads(source_path.read_text()) if source_path.exists() else None
    summary = {"schema": "rocket.memecoin.mc017-route-companion.v1",
               "started_at": started.isoformat(), "ended_at": stamp(),
               "end_reason": end_reason, "max_seconds": max_seconds,
               "max_bytes": max_bytes, "saved_response_bytes": saved_bytes,
               "rpc_host": urlparse(rpc_url).hostname,
               "source_capture_manifest_sha256": (
                   hashlib.sha256(source_path.read_bytes()).hexdigest() if source else None),
               "source_segment_sha256": source.get("segment_sha256") if source else None,
               "parsed_frame_count": frames, "decoded_create_count": len(decoded_creates),
               "selected_create_count": len(selected),
               "first_read_count": sequence, "dispatched_first_batches": batches,
               "saved_first_batches": len(list(first_dir.glob("*.json"))),
               "dispatched_second_reads": second_count,
               "saved_second_reads": len(list(second_dir.glob("*.json"))),
               "unattempted_read_count": len(queue), "errors": errors,
               "pump_idl_sha256": decoder.idl_sha256,
               "pump_amm_idl_sha256": hashlib.sha256(AMM_IDL_PATH.read_bytes()).hexdigest(),
               "creates_sha256": hashlib.sha256(creates_path.read_bytes()).hexdigest(),
               "selected_sha256": hashlib.sha256(selected_path.read_bytes()).hexdigest()}
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
    if not 600 <= args.max_seconds <= 900 or not 1024 <= args.max_bytes <= 33554432:
        parser.error("bounds: seconds 600..900, bytes 1024..33554432")
    print(json.dumps(asyncio.run(capture(args.session, args.out,
                                         max_seconds=args.max_seconds,
                                         max_bytes=args.max_bytes,
                                         rpc_url=args.rpc_url)), indent=2))
