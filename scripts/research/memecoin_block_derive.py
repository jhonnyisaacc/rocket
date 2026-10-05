"""Derive auditable Pump log observations from saved full block transactions."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path

from rocket.capture.spool import RawCaptureSpool, replay_segment

ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def base58_encode(raw: bytes) -> str:
    number = int.from_bytes(raw, "big")
    result = ""
    while number:
        number, digit = divmod(number, 58)
        result = ALPHABET[digit] + result
    return "1" * (len(raw) - len(raw.lstrip(b"\0"))) + result


def short_vec(data: bytes) -> tuple[int, int]:
    value = shift = offset = 0
    while offset < min(len(data), 3):
        byte = data[offset]
        value |= (byte & 0x7f) << shift
        offset += 1
        if byte < 128:
            return value, offset
        shift += 7
    raise ValueError("invalid short_vec signature count")


def first_signature(encoded: list, version: int | str) -> str:
    if not isinstance(encoded, list) or len(encoded) != 2 or encoded[1] != "base64":
        raise ValueError("transaction is not base64 encoded")
    raw = base64.b64decode(encoded[0], validate=True)
    if version == 1:
        if len(raw) < 2 or raw[0] != 0x81:
            raise ValueError("version-1 message prefix invalid")
        count = raw[1]
        start = len(raw) - 64 * count
        if not 1 <= count <= 64 or start <= 2:
            raise ValueError("version-1 signature tail invalid")
    elif version in (0, "legacy"):
        count, start = short_vec(raw)
        if not 1 <= count <= 64 or start + count * 64 >= len(raw):
            raise ValueError("legacy/version-0 signature prefix invalid")
    else:
        raise ValueError(f"unsupported transaction version: {version}")
    signature = raw[start:start + 64]
    if len(signature) != 64 or signature == bytes(64):
        raise ValueError("invalid or placeholder transaction signature")
    return base58_encode(signature)


def derive(source: Path, out: Path) -> dict:
    if out.exists():
        raise FileExistsError(out)
    manifest = json.loads((source / "capture-manifest.json").read_text())
    segment = source / manifest["segment"]
    if hashlib.sha256(segment.read_bytes()).hexdigest() != manifest["segment_sha256"]:
        raise ValueError("raw block segment checksum mismatch")
    out.mkdir(parents=True)
    spool = RawCaptureSpool(out, max_bytes=536870912, reserve_bytes=0,
                            segment_bytes=536870912)
    blocks = notifications = frames = 0
    errors: list[dict] = []
    seen: dict[str, int] = {}
    first_slot = last_slot = None
    try:
        for raw, received_at, _ in replay_segment(segment):
            message = json.loads(raw)
            if message.get("id") == 1:
                spool.append_batch([(raw, received_at)])
                frames += 1
                continue
            if message.get("method") != "blockNotification":
                continue
            frame_hash = hashlib.sha256(raw).hexdigest()
            value = message["params"]["result"]["value"]
            slot = value["slot"]
            blocks += 1
            first_slot = slot if first_slot is None else min(first_slot, slot)
            last_slot = slot if last_slot is None else max(last_slot, slot)
            block = value.get("block")
            if value.get("err") is not None or block is None:
                errors.append({"slot": slot, "reason": "block_unavailable", "value": value.get("err")})
                continue
            derived = []
            for index, transaction in enumerate(block["transactions"]):
                try:
                    signature = first_signature(transaction["transaction"], transaction["version"])
                    meta = transaction["meta"]
                    if signature in seen:
                        raise ValueError(f"duplicate signature at slots {seen[signature]} and {slot}")
                    seen[signature] = slot
                    if not isinstance(meta.get("logMessages"), list):
                        raise ValueError("transaction log messages unavailable")
                    notification = {
                        "jsonrpc": "2.0", "method": "logsNotification",
                        "source": "derived:blockSubscribe",
                        "block_frame_sha256": frame_hash,
                        "transaction_index_in_filtered_block": index,
                        "transaction_version": transaction["version"],
                        "block_time": block.get("blockTime"),
                        "params": {"result": {"context": {"slot": slot},
                                              "value": {"signature": signature,
                                                        "err": meta["err"],
                                                        "logs": meta["logMessages"]}}},
                    }
                    derived.append((json.dumps(notification, separators=(",", ":")).encode(),
                                    received_at))
                except (KeyError, TypeError, ValueError) as exc:
                    errors.append({"slot": slot, "transaction_index": index,
                                   "reason": f"{type(exc).__name__}:{exc}"})
            if derived:
                spool.append_batch(derived)
                notifications += len(derived)
                frames += len(derived)
    finally:
        spool.close()
    derived_segment = out / "segment-000000000000.jsonl"
    derived_manifest = {
        "schema": "rocket.memecoin.capture-session.v2",
        "program_id": manifest["program_id"], "commitment": manifest["commitment"],
        "source_mode": "derived_from_full_block_subscribe",
        "source_manifest_sha256": hashlib.sha256((source / "capture-manifest.json").read_bytes()).hexdigest(),
        "source_segment_sha256": manifest["segment_sha256"],
        "endpoint_host": manifest["endpoint_host"],
        "started_at": manifest["started_at"],
        "subscription_ack_at": manifest["subscription_ack_at"],
        "ended_at": manifest["ended_at"],
        "start_slot": manifest["start_slot"], "end_slot": manifest["end_slot"],
        "end_index_anchor": manifest["end_index_anchor"],
        "first_notification_slot": first_slot, "last_notification_slot": last_slot,
        "requested_seconds": manifest["requested_seconds"],
        "max_bytes": 536870912, "segment": derived_segment.name,
        "segment_sha256": hashlib.sha256(derived_segment.read_bytes()).hexdigest()
        if derived_segment.exists() else None,
        "frames": frames, "blocks": blocks, "notifications": notifications,
        "end_reason": manifest["end_reason"],
        "errors": [*manifest["errors"], *errors],
        "coverage_status": "UNVERIFIED",
    }
    (out / "capture-manifest.json").write_text(json.dumps(derived_manifest, indent=2) + "\n")
    return derived_manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    result = derive(args.source, args.out)
    print(json.dumps(result, indent=2))
    if result["errors"]:
        raise SystemExit(1)
