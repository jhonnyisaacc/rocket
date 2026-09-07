"""Append-only run journal plus small context/state snapshots."""

from __future__ import annotations

import os
import re
import tempfile
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import orjson

from rocket.config import rocket_home
from rocket.models import ResearchResult
from rocket.pit import iso


def _safe_name(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_.-]+", "_", value.strip())
    if not cleaned or cleaned in {".", ".."}:
        raise ValueError("state name must contain at least one safe character")
    return cleaned


class ResearchStore:
    def __init__(self, root: Path | None = None):
        self.root = (root or rocket_home()).expanduser()
        self.runs_root = self.root / "runs"
        self.context_root = self.root / "contexts"
        self.state_root = self.root / "state"

    @staticmethod
    def _atomic_write(path: Path, payload: Mapping[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(orjson.dumps(dict(payload), option=orjson.OPT_INDENT_2))
                handle.write(b"\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)

    def save_result(self, result: ResearchResult) -> Path:
        payload = result.to_dict()
        day = result.decision_time.astimezone(UTC).date().isoformat()
        run_dir = self.runs_root / day / result.run_id
        if run_dir.exists():
            raise ValueError(f"run_id already exists: {result.run_id}")
        path = run_dir / "result.json"
        self._atomic_write(path, payload)
        latest = self.runs_root / "latest" / f"{_safe_name(result.workflow)}.json"
        self._atomic_write(
            latest,
            {
                "workflow": result.workflow,
                "run_id": result.run_id,
                "path": str(path),
                "status": result.status.value,
                "operational": result.operational.status.value,
                "decision_time": iso(result.decision_time),
            },
        )
        return path

    def load_result(self, workflow: str) -> ResearchResult | None:
        pointer = self.runs_root / "latest" / f"{_safe_name(workflow)}.json"
        if not pointer.exists():
            return None
        meta = orjson.loads(pointer.read_bytes())
        path = Path(meta["path"])
        if not path.exists():
            return None
        return ResearchResult.from_dict(orjson.loads(path.read_bytes()))

    def list_latest(self) -> list[dict[str, Any]]:
        latest = self.runs_root / "latest"
        if not latest.exists():
            return []
        rows = []
        for path in sorted(latest.glob("*.json")):
            rows.append(orjson.loads(path.read_bytes()))
        return rows

    def save_context(self, name: str, payload: Mapping[str, Any]) -> Path:
        path = self.context_root / f"{_safe_name(name)}.json"
        self._atomic_write(path, payload)
        return path

    def load_context(self, name: str) -> Mapping[str, Any] | None:
        path = self.context_root / f"{_safe_name(name)}.json"
        if not path.exists():
            return None
        value = orjson.loads(path.read_bytes())
        if not isinstance(value, Mapping):
            raise ValueError(f"context {name!r} must contain a JSON object")
        return value

    def save_state(self, name: str, payload: Mapping[str, Any]) -> Path:
        path = self.state_root / f"{_safe_name(name)}.json"
        self._atomic_write(path, payload)
        return path

    def load_state(self, name: str) -> Mapping[str, Any] | None:
        path = self.state_root / f"{_safe_name(name)}.json"
        if not path.exists():
            return None
        value = orjson.loads(path.read_bytes())
        if not isinstance(value, Mapping):
            raise ValueError(f"state {name!r} must contain a JSON object")
        return value


def now_utc() -> datetime:
    return datetime.now(UTC)
