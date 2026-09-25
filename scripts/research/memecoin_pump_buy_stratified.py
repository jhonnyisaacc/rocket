"""MC-023 stratified prospective unsigned Pump buy simulations."""

from __future__ import annotations

import argparse
import base64
import asyncio
import json
import os
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

from rocket.research.pump_events import EventDecodeError, PumpEventDecoder
from scripts.research.memecoin_audit import IDL_PATH, signature_structure_issue
from scripts.research.memecoin_curve_snapshot_capture import creates_in_frame

NATIVE_QUOTES = {None, "11111111111111111111111111111111",
                 "So11111111111111111111111111111111111111112"}


def stamp() -> str:
    return datetime.now(UTC).isoformat()


async def capture(session: Path, out: Path, *, max_seconds: int) -> dict:
    if out.exists():
        raise ValueError("output directory already exists")
    out.mkdir(parents=True)
    decoder = PumpEventDecoder(IDL_PATH)
    started = datetime.now(UTC)
    deadline = started + timedelta(seconds=max_seconds)
    segment = session / "segment-000000000000.jsonl"
    cursor = 0
    frames = 0
    creates = []
    selected = []
    seen = set()
    anchor_at: datetime | None = None
    bucket_counts = [0] * 5
    tasks: set[asyncio.Task] = set()
    errors = []
    node_script = Path(__file__).with_name("memecoin_pump_unsigned_buy.cjs")

    def persist() -> None:
        (out / "selection.json").write_text(json.dumps({
            "schema": "rocket.memecoin.mc023-selection.v1",
            "started_at": started.isoformat(), "updated_at": stamp(), "source_session": str(session),
            "frames_seen": frames, "subscription_ack_received_at": anchor_at.isoformat() if anchor_at else None,
            "bucket_counts": bucket_counts, "creates": creates, "selected": selected, "errors": errors,
            "idl_sha256": decoder.idl_sha256,
        }, indent=2, sort_keys=True) + "\n")

    def run_one(row: dict, index: int) -> None:
        target = out / f"simulation-{index:02d}.json"
        row["subprocess_started_at"] = stamp()
        try:
            env = {**os.environ, "MC_BUY_SCHEMA": "rocket.memecoin.mc023-unsigned-buy.v1"}
            result = subprocess.run(["node", str(node_script), row["mint"], str(target),
                                     str(row["budget_lamports"])],
                                    capture_output=True, text=True, timeout=30, check=False,
                                    env=env)
            row["exit_code"] = result.returncode
            row["stdout"] = result.stdout[-2000:]
            row["stderr"] = result.stderr[-2000:]
        except (OSError, subprocess.TimeoutExpired) as exc:
            row["subprocess_error"] = type(exc).__name__
        row["subprocess_ended_at"] = stamp()

    persist()
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
                        frame = json.loads(line)
                        raw = json.loads(base64.b64decode(frame["raw_base64"]))
                        if raw.get("id") == 1 and isinstance(raw.get("result"), int):
                            anchor_at = datetime.fromisoformat(frame["received_at"])
                        candidates = creates_in_frame(frame, decoder)
                    except (KeyError, ValueError, EventDecodeError, json.JSONDecodeError) as exc:
                        errors.append(f"FRAME_{frames}_{type(exc).__name__}")
                        continue
                    for created in candidates:
                        if created["signature"] in seen:
                            continue
                        seen.add(created["signature"])
                        reason = signature_structure_issue(created["signature"])
                        if reason is None and created["quote_mint"] not in NATIVE_QUOTES:
                            reason = "NON_NATIVE_QUOTE"
                        if reason is None and created["is_mayhem_mode"] is not False:
                            reason = "MAYHEM_OR_UNKNOWN_MODE"
                        bucket = (int((datetime.fromisoformat(created["create_received_at"])
                                       - anchor_at).total_seconds() // 60)
                                  if anchor_at else None)
                        created["bucket"] = bucket
                        if reason is None and (bucket is None or not 0 <= bucket < 5):
                            reason = "OUTSIDE_ACK_BUCKETS"
                        if reason is None and bucket_counts[bucket] >= 4:
                            reason = "AFTER_FIRST_FOUR_IN_BUCKET"
                        created["selection_status"] = reason or "SELECTED"
                        creates.append(created)
                        if reason is None:
                            position = bucket_counts[bucket]
                            bucket_counts[bucket] += 1
                            created["bucket_position"] = position
                            created["target_delay_seconds"] = (5, 5, 8, 8)[position]
                            created["budget_lamports"] = (10000000, 50000000,
                                                           10000000, 50000000)[position]
                            created["target_at"] = (
                                datetime.fromisoformat(created["create_received_at"])
                                + timedelta(seconds=created["target_delay_seconds"])).isoformat()
                            created["selection_index"] = len(selected)
                            selected.append(created)
            persist()
        now = datetime.now(UTC)
        for row in selected:
            if "scheduled_at" not in row and datetime.fromisoformat(row["target_at"]) <= now:
                row["scheduled_at"] = stamp()
                task = asyncio.create_task(asyncio.to_thread(run_one, row, row["selection_index"]))
                tasks.add(task)
                task.add_done_callback(tasks.discard)
        manifest = session / "capture-manifest.json"
        if manifest.exists() and not tasks and all("subprocess_ended_at" in row for row in selected):
            if not segment.exists() or cursor == segment.stat().st_size:
                break
        await asyncio.sleep(0.05)
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    persist()
    result = {"schema": "rocket.memecoin.mc023-companion.v1", "started_at": started.isoformat(),
              "ended_at": stamp(), "frames_seen": frames, "decoded_create_count": len(creates),
              "selected_count": len(selected), "bucket_counts": bucket_counts, "simulation_files":
              sorted(path.name for path in out.glob("simulation-*.json")), "errors": errors}
    (out / "companion-manifest.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("session", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--max-seconds", type=int, default=420)
    args = parser.parse_args()
    if not 300 <= args.max_seconds <= 600:
        parser.error("max-seconds must be 300..600")
    print(json.dumps(asyncio.run(capture(args.session, args.out,
                                         max_seconds=args.max_seconds)), indent=2))
