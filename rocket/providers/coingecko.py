"""Current top-universe by market cap. Live only; not a historical vintage."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx

from rocket.models import OperationalStatus
from rocket.providers.protocols import ProviderResult
from rocket.workflows.crypto import UNIVERSE_SIZE

COINGECKO_MARKETS_URL = "https://api.coingecko.com/api/v3/coins/markets"


def fetch_top_universe(*, size: int = UNIVERSE_SIZE, http: httpx.Client | None = None) -> ProviderResult:
    owns = http is None
    client = http or httpx.Client(timeout=20.0, headers={"User-Agent": "rocket-research"})
    try:
        response = client.get(
            COINGECKO_MARKETS_URL,
            params={"vs_currency": "usd", "order": "market_cap_desc", "per_page": size, "page": 1},
        )
        response.raise_for_status()
        rows = response.json()
    except Exception as exc:
        if owns:
            client.close()
        return ProviderResult(status=OperationalStatus.UNAVAILABLE, failure_kind=type(exc).__name__, source="coingecko")
    if owns:
        client.close()
    now = datetime.now(UTC)
    members = []
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            continue
        members.append(
            {
                "symbol": str(row.get("symbol") or "").upper(),
                "canonical_asset_id": row.get("id"),
                "rank": index,
                "universe_source": "current_top_market_cap",
            }
        )
    return ProviderResult(
        status=OperationalStatus.HEALTHY if members else OperationalStatus.UNAVAILABLE,
        records=tuple(members),
        retrieved_at=now,
        source="coingecko",
        extras={"universe_size": size},
    )
