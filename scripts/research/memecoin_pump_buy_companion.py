"""MC-022 tail a raw Pump capture and schedule five unsigned buy simulations."""

from __future__ import annotations

import argparse
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
    tasks: set[asyncio.Task] = set()
    errors = []
    node_script = Path(__file__).with_name("memecoin_pump_unsigned_buy.cjs")

    def persist() -> None:
        (out / "selection.json").write_text(json.dumps({
            "schema": "rocket.memecoin.mc022-selection.v1",
            "started_at": started.isoformat(), "updated_at": stamp(), "source_session": str(session),
            "frames_seen": frames, "creates": creates, "selected": selected, "errors": errors,
            "idl_sha256": decoder.idl_sha256,
        }, indent=2, sort_keys=True) + "\n")

    def run_one(row: dict, index: int) -> None:
        target = out / f"simulation-{index:02d}.json"
        row["subprocess_started_at"] = stamp()
        try:
            result = subprocess.run(["node", str(node_script), row["mint"], str(target)],
                                    capture_output=True, text=True, timeout=30, check=False,
                                    env=os.environ.copy())
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
                        if reason is None and len(selected) >= 5:
                            reason = "AFTER_FIRST_FIVE_ELIGIBLE"
                        created["selection_status"] = reason or "SELECTED"
                        creates.append(created)
                        if reason is None:
                            created["target_at"] = (
                                datetime.fromisoformat(created["create_received_at"])
                                + timedelta(seconds=5)).isoformat()
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
    result = {"schema": "rocket.memecoin.mc022-companion.v1", "started_at": started.isoformat(),
              "ended_at": stamp(), "frames_seen": frames, "decoded_create_count": len(creates),
              "selected_count": len(selected), "simulation_files":
              sorted(path.name for path in out.glob("simulation-*.json")), "errors": errors}
    (out / "companion-manifest.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("session", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--max-seconds", type=int, default=240)
    args = parser.parse_args()
    if not 60 <= args.max_seconds <= 360:
        parser.error("max-seconds must be 60..360")
    print(json.dumps(asyncio.run(capture(args.session, args.out,
                                         max_seconds=args.max_seconds)), indent=2))
