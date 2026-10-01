"""Point-in-time panel. A read on day T cannot see a print dated after T."""

from __future__ import annotations

import bisect
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import orjson


def _as_date(value: date | str) -> date:
    return value if isinstance(value, date) else date.fromisoformat(str(value)[:10])


class SeriesPanel:
    """Sorted series. Values are floats; missing days are absent, never filled forward in storage."""

    def __init__(self, series: dict[str, dict[Any, float]], meta: dict[str, Any] | None = None):
        self.meta = dict(meta or {})
        self._series: dict[str, list[tuple[date, float]]] = {}
        for name, points in series.items():
            rows = [(_as_date(day), float(value)) for day, value in points.items()]
            rows.sort(key=lambda item: item[0])
            self._series[str(name)] = rows

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._series))

    def points(self, name: str) -> list[tuple[date, float]]:
        return list(self._series.get(name, ()))

    def dates(self, name: str) -> list[date]:
        return [day for day, _ in self._series.get(name, ())]

    def asof(self, day: date, lags: dict[str, int] | None = None) -> AsOfView:
        return AsOfView(self, day, lags or {})

    def copy_with(self, updates: dict[str, dict[Any, float]]) -> SeriesPanel:
        raw = {name: {day: value for day, value in rows} for name, rows in self._series.items()}
        for name, points in updates.items():
            bucket = raw.setdefault(name, {})
            for day, value in points.items():
                bucket[_as_date(day)] = float(value)
        return SeriesPanel(raw, self.meta)

    def to_obj(self) -> dict[str, Any]:
        series = {
            name: {day.isoformat(): value for day, value in rows}
            for name, rows in sorted(self._series.items())
        }
        return {"meta": self.meta, "series": series}

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(orjson.dumps(self.to_obj()))

    @classmethod
    def load(cls, path: Path) -> SeriesPanel:
        payload = orjson.loads(path.read_bytes())
        return cls(payload.get("series") or {}, payload.get("meta") or {})


class AsOfView:
    """History visible on `day` after publication lag. Later dates are not returned."""

    def __init__(self, panel: SeriesPanel, day: date, lags: dict[str, int]):
        self.panel = panel
        self.day = day
        self.lags = lags

    def cutoff(self, name: str) -> date:
        return self.day - timedelta(days=int(self.lags.get(name, 0)))

    def history(self, name: str, n: int | None = None) -> list[tuple[date, float]]:
        rows = self.panel._series.get(name, [])
        if not rows:
            return []
        cutoff = self.cutoff(name)
        index = bisect.bisect_right(rows, (cutoff, float("inf")))
        visible = rows[:index]
        if visible and visible[-1][0] > cutoff:
            raise AssertionError(f"as-of view leaked {name} {visible[-1][0]} past {cutoff}")
        if n is not None:
            return visible[-n:]
        return visible

    def latest(self, name: str) -> tuple[date, float] | None:
        rows = self.history(name, 1)
        return rows[-1] if rows else None

    def value(self, name: str) -> float | None:
        row = self.latest(name)
        return None if row is None else row[1]

    def closes(self, name: str, n: int | None = None) -> list[float]:
        return [value for _, value in self.history(name, n)]
