"""Strict decoder for pinned Pump Anchor event layouts.

Only events whose bytes fully match the selected IDL are admitted. Decoding a
historical stream with a newer IDL must be validated before using its values.
"""

from __future__ import annotations

import base64
import hashlib
import json
import struct
from pathlib import Path
from typing import Any

ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


class EventDecodeError(ValueError):
    pass


def _base58(data: bytes) -> str:
    number = int.from_bytes(data, "big")
    chars = ""
    while number:
        number, digit = divmod(number, 58)
        chars = ALPHABET[digit] + chars
    return "1" * (len(data) - len(data.lstrip(b"\0"))) + chars


class _Reader:
    def __init__(self, data: bytes, types: dict[str, dict[str, Any]]):
        self.data = data
        self.pos = 0
        self.types = types

    def take(self, size: int) -> bytes:
        if size < 0 or self.pos + size > len(self.data):
            raise EventDecodeError("truncated event")
        chunk = self.data[self.pos:self.pos + size]
        self.pos += size
        return chunk

    def value(self, kind: Any) -> Any:
        if isinstance(kind, dict):
            if "vec" in kind:
                count = self.value("u32")
                if count > 1000:
                    raise EventDecodeError("unbounded vector")
                return [self.value(kind["vec"]) for _ in range(count)]
            if "defined" in kind:
                name = kind["defined"]["name"]
                if name not in self.types:
                    raise EventDecodeError("unknown defined type")
                return self.struct(self.types[name])
            raise EventDecodeError("unsupported type")
        if kind == "pubkey":
            return _base58(self.take(32))
        if kind == "bool":
            value = self.take(1)[0]
            if value not in (0, 1):
                raise EventDecodeError("invalid bool")
            return bool(value)
        if kind == "string":
            size = self.value("u32")
            if size > 1_000_000:
                raise EventDecodeError("unbounded string")
            try:
                return self.take(size).decode("utf-8")
            except UnicodeDecodeError as exc:
                raise EventDecodeError("invalid utf-8") from exc
        formats = {"u8": "B", "u16": "H", "u32": "I", "u64": "Q", "i64": "q"}
        if kind not in formats:
            raise EventDecodeError("unsupported primitive")
        fmt = "<" + formats[kind]
        return struct.unpack(fmt, self.take(struct.calcsize(fmt)))[0]

    def struct(self, definition: dict[str, Any]) -> dict[str, Any]:
        if definition.get("kind") != "struct":
            raise EventDecodeError("unsupported definition")
        return {field["name"]: self.value(field["type"]) for field in definition["fields"]}


class PumpEventDecoder:
    def __init__(self, idl_path: Path):
        raw = idl_path.read_bytes()
        self.idl_sha256 = hashlib.sha256(raw).hexdigest()
        idl = json.loads(raw)
        supported = {"CreateEvent", "TradeEvent", "CompleteEvent",
                     "CompletePumpAmmMigrationEvent"}
        self.events = {bytes(event["discriminator"]): event["name"]
                       for event in idl["events"] if event["name"] in supported}
        self.types = {item["name"]: item["type"] for item in idl["types"]}

    def decode(self, encoded: str) -> dict[str, Any] | None:
        try:
            data = base64.b64decode(encoded, validate=True)
        except (ValueError, base64.binascii.Error) as exc:
            raise EventDecodeError("invalid base64") from exc
        name = self.events.get(data[:8])
        if name is None:
            return None
        reader = _Reader(data[8:], self.types)
        value = reader.struct(self.types[name])
        if reader.pos != len(reader.data):
            raise EventDecodeError("event has unknown trailing bytes")
        return {"event_type": name, "fields": value, "event_sha256": hashlib.sha256(data).hexdigest(),
                "idl_sha256": self.idl_sha256}
