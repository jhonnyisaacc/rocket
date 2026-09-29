"""Point-in-time SEC company facts and filings. Filing date is availability."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from rocket.models import OperationalStatus
from rocket.pit import parse_datetime
from rocket.providers.http import get_read
from rocket.providers.protocols import ProviderResult
from rocket.providers.short_events import from_sec_filing
from rocket.providers.short_quality import _finite, cash_flow_quality

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_HEADERS = {
    "User-Agent": "Rocket Research AdminContact@example.com",
    "Accept-Encoding": "gzip, deflate",
}
OCF_CONCEPTS = (
    "NetCashProvidedByUsedInOperatingActivities",
    "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
)
NI_CONCEPTS = ("NetIncomeLoss", "ProfitLoss", "NetIncomeLossAvailableToCommonStockholdersBasic")
EPS_CONCEPTS = ("EarningsPerShareDiluted", "EarningsPerShareBasic")
SHARE_CONCEPTS = (
    "WeightedAverageNumberOfDilutedSharesOutstanding",
    "WeightedAverageNumberOfSharesOutstandingDiluted",
)
REVENUE_CONCEPTS = (
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
)
OPERATING_INCOME_CONCEPTS = ("OperatingIncomeLoss",)


def _cik10(value: Any) -> str:
    return str(int(value)).zfill(10)


def ticker_cik_map(payload: Mapping[str, Any] | Sequence[Any]) -> dict[str, str]:
    rows = payload.values() if isinstance(payload, Mapping) else payload
    mapping = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        ticker = str(row.get("ticker") or "").strip().upper()
        if ticker and row.get("cik_str") is not None:
            mapping[ticker] = _cik10(row["cik_str"])
    return mapping


def _filed_at(raw: str) -> datetime | None:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        if "T" in text:
            return parse_datetime(text if text.endswith("Z") or "+" in text[10:] else text + "+00:00")
        return parse_datetime(text + "T21:00:00+00:00")
    except ValueError:
        return None


def iter_annual_facts(payload: Mapping[str, Any], concepts: Sequence[str], *, unit: str) -> list[dict[str, Any]]:
    facts = (payload.get("facts") or {}).get("us-gaap") or {}
    rows = []
    for concept in concepts:
        node = facts.get(concept) or {}
        for row in (node.get("units") or {}).get(unit) or []:
            if not isinstance(row, Mapping):
                continue
            form = str(row.get("form") or "")
            fp = str(row.get("fp") or "")
            if form not in {"10-K", "10-K/A"} or fp not in {"FY", ""}:
                continue
            filed = _filed_at(str(row.get("filed") or ""))
            end = str(row.get("end") or "")
            value = _finite(row.get("val"))
            if filed is None or not end or value is None:
                continue
            rows.append({
                "period_end": end,
                "filed": filed.isoformat(),
                "form": form,
                "fy": row.get("fy"),
                "value": value,
                "concept": concept,
                "accn": row.get("accn"),
            })
    return rows


def annual_facts(
    payload: Mapping[str, Any],
    concepts: Sequence[str],
    *,
    now: datetime,
    unit: str,
) -> list[dict[str, Any]]:
    by_period: dict[str, dict[str, Any]] = {}
    for row in iter_annual_facts(payload, concepts, unit=unit):
        filed = parse_datetime(row["filed"])
        if filed is None or filed > now:
            continue
        current = by_period.get(row["period_end"])
        if current is None or filed > parse_datetime(current["filed"]):
            by_period[row["period_end"]] = row
    return sorted(by_period.values(), key=lambda item: item["period_end"])


def compact_companyfacts(payload: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    return {
        "operating_cash_flow": iter_annual_facts(payload, OCF_CONCEPTS, unit="USD"),
        "net_income": iter_annual_facts(payload, NI_CONCEPTS, unit="USD"),
        "eps": iter_annual_facts(payload, EPS_CONCEPTS, unit="USD/shares"),
        "diluted_shares": iter_annual_facts(payload, SHARE_CONCEPTS, unit="shares"),
        "revenue": iter_annual_facts(payload, REVENUE_CONCEPTS, unit="USD"),
        "operating_income": iter_annual_facts(payload, OPERATING_INCOME_CONCEPTS, unit="USD"),
    }


def statement_pair_from_compact(compact: Mapping[str, Sequence[Mapping[str, Any]]], *, now: datetime) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    def latest(name):
        by_period = {}
        for row in compact.get(name) or ():
            filed = parse_datetime(row.get("filed"))
            if filed is None or filed > now:
                continue
            current = by_period.get(row["period_end"])
            if current is None or filed > parse_datetime(current["filed"]):
                by_period[row["period_end"]] = row
        return {row["period_end"]: row for row in by_period.values()}

    ocf, ni, eps = latest("operating_cash_flow"), latest("net_income"), latest("eps")
    shares, revenue, operating = latest("diluted_shares"), latest("revenue"), latest("operating_income")
    periods = sorted(set(ocf) | set(ni) | set(eps))
    if not periods:
        return None, None
    def pack(end: str) -> dict[str, Any]:
        rev = (revenue.get(end) or {}).get("value")
        op = (operating.get(end) or {}).get("value")
        margin = None if rev in (None, 0) or op is None else op / rev
        filed = next((row.get("filed") for row in (ocf.get(end), ni.get(end), eps.get(end)) if row), None)
        return {
            "period_end": end,
            "fiscal_year": (ocf.get(end) or ni.get(end) or eps.get(end) or {}).get("fy"),
            "operating_cash_flow": (ocf.get(end) or {}).get("value"),
            "net_income": (ni.get(end) or {}).get("value"),
            "eps": (eps.get(end) or {}).get("value"),
            "diluted_shares": (shares.get(end) or {}).get("value"),
            "revenue": rev,
            "operating_income": op,
            "operating_margin": margin,
            "filed": filed,
            "available_at": filed,
            "source": "sec.companyfacts",
        }
    latest_row = pack(periods[-1])
    prior_row = pack(periods[-2]) if len(periods) > 1 else None
    return latest_row, prior_row


def statement_pair(payload: Mapping[str, Any], *, now: datetime) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    return statement_pair_from_compact(compact_companyfacts(payload), now=now)


def reported_fundamentals(latest: Mapping[str, Any] | None, prior: Mapping[str, Any] | None) -> dict[str, Any]:
    if not latest or not prior:
        return {
            "company_fundamentals": None,
            "eps_growth": None,
            "eps_growth_basis": None,
            "cash_flow_quality": cash_flow_quality(latest, prior),
        }
    eps_latest, eps_prior = _finite(latest.get("eps")), _finite(prior.get("eps"))
    if eps_latest is None or eps_prior is None or eps_prior == 0:
        growth, basis = None, None
        if _finite(latest.get("net_income")) is not None and _finite(prior.get("net_income")) not in (None, 0):
            growth = (latest["net_income"] - prior["net_income"]) / abs(prior["net_income"])
            basis = "reported annual net income; diluted EPS unavailable"
    else:
        growth = (eps_latest - eps_prior) / abs(eps_prior)
        basis = "reported annual diluted EPS from 10-K facts"
    return {
        "company_fundamentals": None if growth is None else growth < 0,
        "eps_growth": growth,
        "eps_growth_basis": basis,
        "cash_flow_quality": cash_flow_quality(latest, prior),
        "fundamentals_source": "sec.companyfacts",
        "available_at": latest.get("available_at"),
        "event_time": latest.get("filed"),
        "availability_basis": "10-K filed date; restatements after decision_time are excluded",
    }


def filings_from_submissions(payload: Mapping[str, Any], *, now: datetime) -> list[dict[str, Any]]:
    recent = (payload.get("filings") or {}).get("recent") or {}
    forms = recent.get("form") or []
    filed = recent.get("filingDate") or []
    accession = recent.get("accessionNumber") or []
    items = recent.get("items") or []
    rows = []
    for index, form in enumerate(forms):
        row = {
            "form": form,
            "filingDate": filed[index] if index < len(filed) else None,
            "accessionNumber": accession[index] if index < len(accession) else None,
            "items": items[index] if index < len(items) else "",
            "source": "sec.submissions",
        }
        record = from_sec_filing(row, now=now)
        if record:
            rows.append(record)
    return rows


class SecFacts:
    def __init__(self, *, http: httpx.Client | None = None, tickers: Mapping[str, str] | None = None):
        self.http = http
        self.tickers = dict(tickers or {})

    def _client(self):
        return self.http or httpx.Client(timeout=20.0, headers=SEC_HEADERS, follow_redirects=True)

    def _load_tickers(self, client: httpx.Client) -> None:
        if self.tickers:
            return
        response = get_read(client, SEC_TICKERS_URL)
        self.tickers = ticker_cik_map(response.json())

    def fundamentals(self, symbol: str, *, now: datetime | None = None) -> ProviderResult:
        retrieved = now or datetime.now(UTC)
        owns = self.http is None
        client = self._client()
        try:
            self._load_tickers(client)
            cik = self.tickers.get(symbol.strip().upper())
            if not cik:
                return ProviderResult(OperationalStatus.UNAVAILABLE, source="sec.companyfacts",
                                      failure_kind="UnknownTicker", retrieved_at=retrieved)
            response = get_read(client, SEC_FACTS_URL.format(cik=cik))
            latest, prior = statement_pair(response.json(), now=retrieved)
            row = reported_fundamentals(latest, prior)
            row.update(symbol=symbol.upper(), cik=cik, latest_statement=latest, prior_statement=prior)
            observed = row.get("company_fundamentals") is not None or row.get("cash_flow_quality", {}).get("state") != "UNKNOWN"
            return ProviderResult(
                OperationalStatus.HEALTHY if observed else OperationalStatus.PARTIAL,
                (row,),
                retrieved,
                source="sec.companyfacts",
            )
        except Exception as exc:
            from rocket.providers.dispatch import failure_kind
            return ProviderResult(OperationalStatus.UNAVAILABLE, source="sec.companyfacts",
                                  failure_kind=failure_kind(exc), retrieved_at=retrieved)
        finally:
            if owns:
                client.close()

    def catalysts(self, symbol: str, *, now: datetime | None = None) -> ProviderResult:
        retrieved = now or datetime.now(UTC)
        owns = self.http is None
        client = self._client()
        try:
            self._load_tickers(client)
            cik = self.tickers.get(symbol.strip().upper())
            if not cik:
                return ProviderResult(OperationalStatus.UNAVAILABLE, source="sec.submissions",
                                      failure_kind="UnknownTicker", retrieved_at=retrieved)
            response = get_read(client, SEC_SUBMISSIONS_URL.format(cik=cik))
            rows = filings_from_submissions(response.json(), now=retrieved)
            recent = [row for row in rows if timedelta(0) <= retrieved - parse_datetime(row["available_at"]) <= timedelta(days=45)]
            return ProviderResult(
                OperationalStatus.HEALTHY if rows else OperationalStatus.PARTIAL,
                tuple(recent),
                retrieved,
                source="sec.submissions",
            )
        except Exception as exc:
            from rocket.providers.dispatch import failure_kind
            return ProviderResult(OperationalStatus.UNAVAILABLE, source="sec.submissions",
                                  failure_kind=failure_kind(exc), retrieved_at=retrieved)
        finally:
            if owns:
                client.close()
