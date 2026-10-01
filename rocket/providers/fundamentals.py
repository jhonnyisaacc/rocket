"""One fundamentals capability shared by equity research workflows."""

from rocket.providers.fmp import FMPClient
from rocket.providers.massive import MassiveFundamentals
from rocket.providers.registry import Registry


def acquire_fundamentals(symbol, *, fmp=None, massive=None, registry=None):
    registry = registry or Registry()
    fmp = fmp or FMPClient()
    massive = massive or MassiveFundamentals()
    registry.register("fundamentals", "fmp", lambda: fmp.fundamentals(symbol))
    registry.register("fundamentals", "massive", lambda: massive.fetch(symbol))
    return registry.acquire("fundamentals", sufficient=lambda r: bool(r.records)
                            and r.records[0].get("company_fundamentals") is not None)


def fundamentals_row(symbol):
    acquired = acquire_fundamentals(symbol)
    row = dict(acquired.result.records[0]) if acquired.result else {}
    row["provider_attempts"] = [p.to_dict() for p in acquired.attempts] + row.get("provider_attempts", [])
    return row
