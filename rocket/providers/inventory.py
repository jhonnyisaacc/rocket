"""Read-only Solana/ONDO inventory. Never signs. Never creates positions."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import httpx

from rocket.config import env
from rocket.models import OperationalStatus
from rocket.providers.protocols import ProviderResult

# Officially mapped ONDO mints. Unknown *ondo mints stay pending_review.
KNOWN_ONDO = {
    "14Tqdo8V1FhzKsE3W2pFsZCzYPQxxupXRcqw9jv6ondo": ("AMZNON", "AMZN"),
    "fDxs5y12E7x7jBwCKBXGqt71uJmCWsAQ3Srkte6ondo": ("METAON", "META"),
    "FRmH6iRkMr33DLG6zVLR7EM4LojBFAuq6NtFzG6ondo": ("MSFTON", "MSFT"),
    "Wk8gC6iTNp8dqd4ghkJ3h1giiUnyhykwHh7tYWjondo": ("BACON", "BAC"),
    "6btaz134wjHkR8sqhAYrtSM6tavftfxnRvnyMd8ondo": ("COSTON", "COST"),
    "CY8ttw5rYCT6fFBJwqXofefqa7Ji9E8zfLmhRLmondo": ("FCXON", "FCX"),
    "KeGv7bsfR4MheC1CkmnAVceoApjrkvBhHYjWb67ondo": ("TSLAON", "TSLA"),
    "k18WJUULWheRkSpSquYGdNNmtuE2Vbw1hpuUi92ondo": ("SPYon", "SPY"),
}


class FileInventory:
    def __init__(self, records: tuple[Mapping[str, Any], ...] = ()):
        self.records = records

    def fetch(self, *, address: str, now: datetime | None = None) -> ProviderResult:
        del address
        return ProviderResult(
            status=OperationalStatus.HEALTHY,
            records=self.records,
            retrieved_at=now or datetime.now(UTC),
            source="caller.inventory",
        )


class SolanaOndoInventory:
    def __init__(self, *, http: httpx.Client | None = None):
        self.http = http

    def fetch(self, *, address: str, now: datetime | None = None) -> ProviderResult:
        key = env("HELIUS_API_KEY")
        url = f"https://mainnet.helius-rpc.com/?api-key={key}" if key else "https://api.mainnet-beta.solana.com"
        owns = self.http is None
        client = self.http or httpx.Client(timeout=20.0)
        try:
            response = client.post(
                url,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getTokenAccountsByOwner",
                    "params": [address, {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"}, {"encoding": "jsonParsed"}],
                },
            )
            response.raise_for_status()
            rows = response.json()["result"]["value"]
        except Exception as exc:
            if owns:
                client.close()
            return ProviderResult(
                status=OperationalStatus.UNAVAILABLE,
                failure_kind=type(exc).__name__,
                source="solana",
            )
        if owns:
            client.close()
        records = []
        for row in rows:
            try:
                info = row["account"]["data"]["parsed"]["info"]
                mint = info["mint"]
                amount = float(info["tokenAmount"]["uiAmount"] or 0)
            except (KeyError, TypeError, ValueError):
                continue
            ticker = KNOWN_ONDO.get(mint, (None, "UNKNOWN"))[1]
            records.append(
                {
                    "mint": mint,
                    "ticker": ticker,
                    "quantity": amount,
                    "pending_review": mint not in KNOWN_ONDO,
                }
            )
        return ProviderResult(
            status=OperationalStatus.HEALTHY,
            records=tuple(records),
            retrieved_at=now or datetime.now(UTC),
            source="solana",
        )
