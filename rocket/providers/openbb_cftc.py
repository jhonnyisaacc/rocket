"""OpenBB CFTC legacy futures-only fallback, never a corroboration vote."""

from datetime import UTC, datetime

from rocket.models import OperationalStatus
from rocket.providers.cftc import MARKET_NAMES, bias_from_speculator_pct
from rocket.providers.dispatch import failure_kind
from rocket.providers.protocols import ProviderResult

CODES = {"BTC": "133741", "ETH": "146021"}


class OpenBBCFTC:
    def __init__(self, *, fetcher=None):
        self.fetcher = fetcher

    def fetch(self, *, now=None):
        try:
            fetcher = self.fetcher
            if fetcher is None:
                from rocket.providers.openbb_bridge import read_openbb
                fetcher = lambda **params: read_openbb("cftc.cot", **params)
            records = []
            for asset, code in CODES.items():
                data = fetcher(code=f"CFTC_{code}", report_type="legacy", futures_only=True,
                               measure="all", limit=1, provider="cftc")
                raw = data.results if hasattr(data, "results") else data
                if not isinstance(raw, list) or len(raw) != 1:
                    raise ValueError("COT coverage")
                row = raw[0].model_dump() if hasattr(raw[0], "model_dump") else raw[0]
                if str(row.get("cftc_contract_market_code")) != code:
                    raise ValueError("COT identity mismatch")
                if str(row.get("futonly_or_combined", "")).lower() not in {"futonly", "futures only", "futures-only"}:
                    raise ValueError("COT futures-only identity unknown")
                oi = int(row["open_interest_all"])
                long = int(row["non_commercial_positions_long_all"])
                short = int(row["non_commercial_positions_short_all"])
                day = datetime.fromisoformat(str(row["date"])[:10]).date()
                if oi <= 0 or min(long, short) < 0 or max(long, short) > oi:
                    raise ValueError("invalid COT positions")
                if not 0 <= ((now or datetime.now(UTC)).date() - day).days <= 14:
                    raise ValueError("stale or future COT")
                pct = (long - short) / oi * 100
                records.append({"asset": asset, "market": MARKET_NAMES[asset],
                                "open_interest": oi, "noncomm_long": long, "noncomm_short": short,
                                "net_non_commercial": long - short, "pct_oi_non_com": pct,
                                "bias": bias_from_speculator_pct(pct), "as_of_date": day.isoformat(),
                                "release_date": None, "source": "OpenBB/CFTC",
                                "citation": "https://publicreporting.cftc.gov/",
                                "available_at": (now or datetime.now(UTC)).isoformat(),
                                "availability_basis": "first observed retrieval; report date is positions as-of, not release"})
            return ProviderResult(OperationalStatus.HEALTHY, tuple(records), now or datetime.now(UTC),
                                  source="OpenBB/CFTC")
        except Exception as exc:
            return ProviderResult(OperationalStatus.UNAVAILABLE, retrieved_at=now or datetime.now(UTC),
                                  source="OpenBB/CFTC", failure_kind=failure_kind(exc))
