"""Keyless SEC companyfacts snapshots. Date-based periods, never filing FY labels."""

from __future__ import annotations

import json
import math
import threading
import time
from datetime import UTC, date, datetime, timedelta
from itertools import pairwise
from pathlib import Path

import httpx

from rocket.config import env, rocket_home
from rocket.models import OperationalStatus as O
from rocket.providers.fmp import endpoint_attempt
from rocket.providers.protocols import ProviderResult

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
DEFAULT_USER_AGENT = "rocket research (https://github.com/jhonnyisaacc/rocket/issues)"
_LOCK = threading.Lock()
_LAST_REQUEST = 0.0


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        return None
    return float(value) if math.isfinite(value) else None


def _growth(current, prior):
    return (
        (current - prior) / abs(prior) if current is not None and prior not in (None, 0) else None
    )


def _facts(data, namespace, tag, unit, now):
    rows = data.get("facts", {}).get(namespace, {}).get(tag, {}).get("units", {}).get(unit, [])
    periods = {}
    for raw in rows:
        try:
            if raw.get("form") not in {"10-K", "10-Q", "10-K/A", "10-Q/A"}:
                continue
            end, filed = date.fromisoformat(raw["end"]), date.fromisoformat(raw["filed"])
            start = date.fromisoformat(raw["start"]) if "start" in raw else None
            value = _number(raw.get("val"))
            if value is None or filed > now.date() or end > now.date() or (start and end < start):
                continue
            row = {
                "start": start,
                "end": end,
                "value": value,
                "filed": filed,
                "accession": raw.get("accn", ""),
                "derived": False,
            }
            key = (start, end)
            previous = periods.get(key)
            if previous is None or (filed, row["accession"]) > (
                previous["filed"],
                previous["accession"],
            ):
                periods[key] = row
        except (ValueError, KeyError, TypeError):
            continue
    return list(periods.values())


def _quarters(rows):
    quarters = {
        (r["start"], r["end"]): r
        for r in rows
        if r["start"] and 60 <= (r["end"] - r["start"]).days <= 120
    }
    # Subtract cumulative YTD intervals with the SAME start. This also derives Q4
    # from FY minus nine months, without relying on misleading comparative fy/fp.
    for row in rows:
        if not row["start"] or not 120 < (row["end"] - row["start"]).days <= 400:
            continue
        previous = [
            r
            for r in rows
            if r["start"] == row["start"] and 60 <= (row["end"] - r["end"]).days <= 120
        ]
        if not previous:
            continue
        prior = max(previous, key=lambda r: r["end"])
        start = prior["end"] + timedelta(days=1)
        quarters.setdefault(
            (start, row["end"]),
            {
                **row,
                "start": start,
                "value": row["value"] - prior["value"],
                "filed": max(row["filed"], prior["filed"]),
                "derived": True,
            },
        )
    for annual in rows:
        if not annual["start"] or not 330 <= (annual["end"] - annual["start"]).days <= 400:
            continue
        first_three = sorted(
            (
                r
                for r in quarters.values()
                if annual["start"] <= r["start"] and r["end"] < annual["end"]
            ),
            key=lambda r: r["start"],
        )
        if (
            len(first_three) == 3
            and first_three[0]["start"] == annual["start"]
            and 60 <= (annual["end"] - first_three[-1]["end"]).days <= 120
            and all((b["start"] - a["end"]).days == 1 for a, b in pairwise(first_three))
        ):
            start = first_three[-1]["end"] + timedelta(days=1)
            quarters.setdefault(
                (start, annual["end"]),
                {
                    **annual,
                    "start": start,
                    "derived": True,
                    "value": annual["value"] - sum(r["value"] for r in first_three),
                    "filed": max(annual["filed"], *(r["filed"] for r in first_three)),
                },
            )
    return sorted(quarters.values(), key=lambda r: (r["end"], r["start"]))


def _window(quarters, end):
    rows = [r for r in quarters if r["end"] <= end][-4:]
    if len(rows) != 4 or rows[-1]["end"] != end:
        return None
    if not 330 <= (rows[-1]["end"] - rows[0]["start"]).days <= 400:
        return None
    if any((b["start"] - a["end"]).days != 1 for a, b in pairwise(rows)):
        return None
    return sum(r["value"] for r in rows)


def _ttm(facts, quarters, end):
    # Prefer the reported FY, or FY + current YTD - comparable prior YTD.
    # EPS is rounded and uses period-specific weighted shares, so a trailing
    # figure assembled from periods is an approximation (never net income /
    # instantaneous shares, especially for multiple share classes).
    annuals = [
        r
        for r in facts
        if r["start"] and 330 <= (r["end"] - r["start"]).days <= 400 and r["end"] <= end
    ]
    annual = max(annuals, key=lambda r: r["end"]) if annuals else None
    if annual:
        if annual["end"] == end:
            return annual["value"]
        current = [
            r for r in facts if r["start"] == annual["end"] + timedelta(days=1) and r["end"] == end
        ]
        if current:
            current = current[0]
            prior = [
                r
                for r in facts
                if r["start"] == annual["start"]
                and 350 <= (end - r["end"]).days <= 380
                and abs((current["end"] - current["start"]).days - (r["end"] - r["start"]).days)
                <= 14
            ]
            if prior:
                return annual["value"] + current["value"] - prior[-1]["value"]
    return _window(quarters, end)


def _metric(data, tags, unit, now):
    for tag in tags:
        facts = _facts(data, "us-gaap", tag, unit, now)
        quarters = _quarters(facts)
        if not quarters:
            continue
        latest = quarters[-1]
        if (now.date() - latest["end"]).days > 200:
            continue
        previous = [
            r
            for r in quarters
            if 350 <= (latest["end"] - r["end"]).days <= 380
            and abs((latest["end"] - latest["start"]).days - (r["end"] - r["start"]).days) <= 14
        ]
        prior = max(previous, key=lambda r: r["end"]) if previous else None
        ttm = _ttm(facts, quarters, latest["end"])
        prior_ttm = _ttm(facts, quarters, prior["end"]) if prior else None
        return {
            "tag": tag,
            "unit": unit,
            "latest_quarter": latest["value"],
            "ttm": ttm,
            "prior_ttm": prior_ttm,
            "ttm_yoy_growth": _growth(ttm, prior_ttm),
            "quarter_yoy_growth": _growth(latest["value"], prior["value"] if prior else None),
            "periods": [
                {
                    **r,
                    "start": r["start"].isoformat(),
                    "end": r["end"].isoformat(),
                    "filed": r["filed"].isoformat(),
                }
                for r in quarters[-8:]
            ],
        }
    return None


def parse_companyfacts(data, *, now):
    eps = _metric(data, ("EarningsPerShareDiluted", "EarningsPerShareBasic"), "USD/shares", now)
    revenue = _metric(
        data,
        (
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "Revenues",
            "SalesRevenueNet",
            "RevenuesNetOfInterestExpense",
        ),
        "USD",
        now,
    )
    income = _metric(data, ("NetIncomeLoss", "ProfitLoss"), "USD", now)
    shares = _facts(data, "dei", "EntityCommonStockSharesOutstanding", "shares", now)
    shares = max(shares, key=lambda r: (r["end"], r["filed"])) if shares else None
    if shares and (now.date() - shares["end"]).days > 200:
        shares = None
    growth = eps["ttm_yoy_growth"] if eps else None
    basis = "reported TTM EPS YoY (FY plus comparable YTD; quarter sum fallback)"
    if growth is None and eps:
        growth = eps["quarter_yoy_growth"]
        basis = "reported latest fiscal quarter EPS YoY"
    return {
        "company_fundamentals": growth < 0 if growth is not None else None,
        "eps_growth": growth,
        "eps_growth_basis": basis if growth is not None else None,
        "eps_kind": "REPORTED" if growth is not None else "UNKNOWN",
        "eps_latest_quarter": eps["latest_quarter"] if eps else None,
        "eps_ttm": eps["ttm"] if eps else None,
        "eps_quarter_yoy_growth": eps["quarter_yoy_growth"] if eps else None,
        "eps_ttm_yoy_growth": eps["ttm_yoy_growth"] if eps else None,
        "revenue": revenue,
        "net_income": income,
        "shares_outstanding": shares["value"] if shares else None,
        "shares_outstanding_unit": "shares" if shares else None,
        "shares_outstanding_date": shares["end"].isoformat() if shares else None,
        "metrics": {"eps": eps, "revenue": revenue, "net_income": income},
        "metric_states": {
            k: "OBSERVED" if v else "UNKNOWN"
            for k, v in (
                ("eps", eps),
                ("revenue", revenue),
                ("net_income", income),
                ("shares_outstanding", shares),
            )
        },
        "periods": eps["periods"] if eps else [],
        "event_time": eps["periods"][-1]["end"] if eps else None,
        "pe_ttm": None,
        "valuation_support": None,
        "earnings_revision_deterioration": None,
    }


def apply_price_valuation(row, price):
    """Same positive trailing P/E <= 15 veto as FMP; retain existing valuation."""
    row = dict(row)
    eps = _number(row.get("eps_ttm"))
    price = _number(price)
    if (
        row.get("pe_ttm") is None
        and eps is not None
        and eps > 0
        and price is not None
        and price > 0
    ):
        row["pe_ttm"] = price / eps
        provenance = dict(row.get("field_provenance", {}))
        provenance["pe_ttm"] = "sec.edgar+yahoo"
        if row.get("valuation_support") is None:
            row["valuation_support"] = row["pe_ttm"] <= 15
            provenance["valuation_support"] = "sec.edgar+yahoo"
        row["field_provenance"] = provenance
        row["valuation_basis"] = "Yahoo price / SEC reported TTM EPS; positive earnings only"
    return row


class SECEDGAR:
    def __init__(self, *, state_dir: Path | None = None, http: httpx.Client | None = None):
        self.cache = (state_dir or rocket_home()) / "cache" / "sec-edgar"
        self.http = http

    def _get(self, name, url, now):
        global _LAST_REQUEST
        path = self.cache / (name + ".json")
        try:
            cached = json.loads(path.read_text())
            if cached["day"] == now.date().isoformat():
                return cached
        except (OSError, ValueError, KeyError, TypeError):
            pass
        owns = self.http is None
        client = self.http or httpx.Client(timeout=20, follow_redirects=True)
        cached = {
            "day": now.date().isoformat(),
            "retrieved_at": now.isoformat(),
            "payload": None,
            "failure": None,
        }
        try:
            with _LOCK:
                time.sleep(max(0, 0.35 - (time.monotonic() - _LAST_REQUEST)))
                _LAST_REQUEST = time.monotonic()
                response = client.get(
                    url,
                    headers={
                        "User-Agent": env("ROCKET_SEC_USER_AGENT", DEFAULT_USER_AGENT),
                        "Accept": "application/json",
                    },
                )
            response.raise_for_status()
            cached["payload"] = response.json()
            if not isinstance(cached["payload"], dict):
                cached["failure"] = "HardError"
        except httpx.HTTPStatusError as exc:
            cached["failure"] = {429: "RateLimit", 403: "Entitlement", 404: "NotFound"}.get(
                exc.response.status_code, "HardError"
            )
        except (httpx.HTTPError, ValueError):
            cached["failure"] = "HardError"
        finally:
            if owns:
                client.close()
        try:
            self.cache.mkdir(parents=True, exist_ok=True)
            temp = path.with_suffix(".tmp")
            temp.write_text(json.dumps(cached))
            temp.replace(path)
        except OSError:
            pass  # Read-only state must not discard acquired evidence.
        return cached

    def fetch(self, symbol, *, now=None):
        now = now or datetime.now(UTC)
        attempts = []

        def get(name, url):
            cached = self._get(name, url, now)
            stamp = datetime.fromisoformat(cached["retrieved_at"])
            attempts.append(
                endpoint_attempt(
                    "sec.edgar",
                    symbol,
                    url,
                    name,
                    stamp,
                    count=1 if cached["failure"] is None else 0,
                    failure=cached["failure"],
                )
            )
            return cached

        def failed(kind):
            if attempts:
                attempts[-1].update(failure_kind=kind, status="UNAVAILABLE", coverage="0")
            return ProviderResult(
                O.UNAVAILABLE,
                retrieved_at=now,
                source="sec.edgar",
                failure_kind=kind,
                extras={"provider_attempts": attempts},
            )

        try:
            tickers = get("company_tickers", TICKERS_URL)
            if tickers["failure"]:
                return failed(tickers["failure"])
            match = next(
                (
                    r
                    for r in tickers["payload"].values()
                    if str(r.get("ticker", "")).upper().replace(".", "-")
                    == symbol.upper().replace(".", "-")
                ),
                None,
            )
            if match is None:
                attempts[-1].update(failure_kind="NotFound", status="UNAVAILABLE", coverage="0")
                return failed("NotFound")
            cik = f"{int(match['cik_str']):010d}"
            url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
            facts = get("CIK" + cik, url)
            if facts["failure"]:
                return failed(facts["failure"])
            if int(facts["payload"]["cik"]) != int(cik):
                return failed("HardError")
            row = parse_companyfacts(facts["payload"], now=now)
            row.update(
                symbol=symbol.upper(),
                cik=cik,
                citation=url,
                fundamentals_source="sec.edgar",
                retrieved_at=facts["retrieved_at"],
                available_at=now.isoformat(),
                historical_available_at=None,
                availability_basis="observed companyfacts snapshot; not historical replay",
            )
            eligible = row["company_fundamentals"] is not None
            attempts[-1].update(
                failure_kind=None if eligible else "Empty",
                status="HEALTHY" if eligible else "PARTIAL",
            )
            row["provider_attempts"] = attempts
            return ProviderResult(
                O.HEALTHY if eligible else O.PARTIAL,
                (row,),
                now,
                None if eligible else "Empty",
                "sec.edgar",
            )
        except (ValueError, KeyError, TypeError, AttributeError):
            return failed("HardError")
