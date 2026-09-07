"""FRED series via OpenBB when present, else the public CSV endpoint."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import httpx

from rocket.config import env
from rocket.models import OperationalStatus
from rocket.providers.protocols import ProviderResult

FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"


def _number(value: Any) -> float | None:
    try:
        if value in (None, "", ".") or isinstance(value, bool):
            return None
        import math

        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _record_date(record: Mapping[str, Any]) -> str | None:
    for key in ("date", "Date", "observation_date", "timestamp", "period"):
        value = record.get(key)
        if value:
            return str(value)
    return None


def _record_value(record: Mapping[str, Any], symbol: str | None = None) -> float | None:
    if symbol and symbol in record:
        parsed = _number(record[symbol])
        if parsed is not None:
            return parsed
    for key in ("value", "Value", "close", "Close", "last", "observation_value"):
        if key in record:
            parsed = _number(record[key])
            if parsed is not None:
                return parsed
    for value in reversed(list(record.values())):
        parsed = _number(value)
        if parsed is not None:
            return parsed
    return None


def parse_fred_csv(text: str, series_id: str) -> list[dict[str, Any]]:
    lines = text.splitlines()
    if not lines:
        raise RuntimeError("FRED returned an empty response")
    headers = [item.strip() for item in lines[0].split(",")]
    records: list[dict[str, Any]] = []
    for line in lines[1:]:
        values = [item.strip() for item in line.split(",")]
        if len(values) != len(headers):
            continue
        record = dict(zip(headers, values, strict=False))
        if _record_value(record, series_id) is not None:
            records.append(record)
    return records


def fetch_fred_csv(series_id: str, *, http: httpx.Client | None = None) -> Mapping[str, Any]:
    owns = http is None
    client = http or httpx.Client(timeout=15.0)
    params: dict[str, str] = {"id": series_id}
    api_key = env("FRED_API_KEY")
    if api_key:
        params["api_key"] = api_key
    try:
        response = client.get(FRED_CSV_URL, params=params)
        response.raise_for_status()
        records = parse_fred_csv(response.text, series_id)
    finally:
        if owns:
            client.close()
    observed = max((d for row in records if (d := _record_date(row))), default=None)
    retrieved = datetime.now(UTC).isoformat()
    return {
        "series_id": series_id,
        "records": records,
        "as_of": observed,
        "latest_observation_at": observed,
        "retrieved_at": retrieved,
        "source": "FRED direct",
    }


def fetch_openbb_fred(series_id: str) -> Mapping[str, Any]:
    from openbb import obb

    data = obb.economy.fred_series(symbol=series_id)
    frame = data.to_df() if hasattr(data, "to_df") else data
    if hasattr(frame, "reset_index"):
        if getattr(frame.index, "name", None) in {"date", "timestamp", None}:
            frame = frame.reset_index()
        records = [
            {str(key): value for key, value in row.items()}
            for row in frame.to_dict(orient="records")
        ]
    else:
        records = list(frame) if isinstance(frame, list) else []
    observed = max((d for row in records if (d := _record_date(row))), default=None)
    return {
        "series_id": series_id,
        "records": records,
        "as_of": observed,
        "latest_observation_at": observed,
        "retrieved_at": datetime.now(UTC).isoformat(),
        "source": "OpenBB/FRED",
    }


def fetch_series(series_id: str, *, http: httpx.Client | None = None) -> tuple[Mapping[str, Any], str]:
    try:
        payload = fetch_openbb_fred(series_id)
        return payload, str(payload.get("source") or "OpenBB/FRED")
    except Exception:
        payload = fetch_fred_csv(series_id, http=http)
        return payload, str(payload.get("source") or "FRED direct")


class FredMacroSeries:
    def __init__(self, *, fetcher=None, http: httpx.Client | None = None):
        self.fetcher = fetcher
        self.http = http

    def fetch(self, symbol: str, *, now: datetime | None = None) -> ProviderResult:
        del now
        try:
            if self.fetcher is not None:
                payload, source = self.fetcher(symbol)
            else:
                payload, source = fetch_series(symbol, http=self.http)
            records = tuple(payload.get("records") or ())
            retrieved = payload.get("retrieved_at")
            return ProviderResult(
                status=OperationalStatus.HEALTHY if records else OperationalStatus.UNAVAILABLE,
                records=records,
                retrieved_at=datetime.fromisoformat(str(retrieved).replace("Z", "+00:00"))
                if retrieved
                else datetime.now(UTC),
                source=source,
                extras={"series_id": symbol},
            )
        except Exception as exc:
            return ProviderResult(
                status=OperationalStatus.UNAVAILABLE,
                failure_kind=type(exc).__name__,
                source="fred",
                extras={"series_id": symbol},
            )
