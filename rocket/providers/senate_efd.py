"""Official Senate eFD periodic transaction reports. Filing evidence, not orders."""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from html import unescape
from urllib.parse import urljoin, urlsplit

import httpx

from rocket.providers.disclosures import HOUSE_FILING_YEAR_LOOKBACK
from rocket.providers.open_cabinet import non_equity_type

SENATE_EFD_ORIGIN = "https://efdsearch.senate.gov"
SENATE_EFD_HOME_URL = f"{SENATE_EFD_ORIGIN}/search/home/"
SENATE_EFD_SEARCH_URL = f"{SENATE_EFD_ORIGIN}/search/"
SENATE_EFD_DATA_URL = f"{SENATE_EFD_ORIGIN}/search/report/data/"
SENATE_EFD_PTR_PATH = "/search/view/ptr/"
SENATE_EFD_PAPER_PATH = "/search/view/paper/"
SENATE_EFD_PTR_TYPE_ID = "11"
SENATE_EFD_USER_AGENT = "rocket-research/senate-efd (github.com/jhonnyisaacc/rocket)"
SENATE_EFD_PAGE_LENGTH = 100
SENATE_EFD_MAX_PAGES = 20
SENATE_EFD_RETRY_SLEEPS = (1, 2)
SENATE_EFD_PTR_PAUSE = 1.0
PROVIDER = "official_senate_efd"

_CSRF = re.compile(r'name="csrfmiddlewaretoken" value="([^"]+)"')
_HREF = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)
_AMENDMENT = re.compile(r"\(Amendment\s+(\d+)\)", re.IGNORECASE)
_UUID = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)
_EDGE_REFERENCE = re.compile(r"Reference\s*#\s*([0-9a-f.]+)", re.IGNORECASE)
_EQUITY_TICKER = re.compile(r"[A-Z][A-Z0-9.\-]{0,9}")
_BLANK_TICKER = {"", "--", "-", "—", "N/A", "NONE"}
_ROW = re.compile(r"<tr\b[^>]*>.*?</tr>", re.IGNORECASE | re.DOTALL)
_CELL = re.compile(r"<td\b[^>]*>(.*?)</td>", re.IGNORECASE | re.DOTALL)
_TABLE = re.compile(r"<table\b[^>]*>.*?</table>", re.IGNORECASE | re.DOTALL)


class SenateEFDBlocked(Exception):
    def __init__(self, edge_reference: str) -> None:
        self.edge_reference = edge_reference
        super().__init__("BLOCKED")


class SenateEFDRateLimit(Exception):
    pass


@dataclass(frozen=True)
class SenateEFDFetch:
    status: str
    records: tuple[dict, ...]
    edge_reference: str | None = None
    failure_kind: str | None = None


def submitted_window(now: datetime, lookback_years: int) -> tuple[str, str]:
    """Submitted-date bounds covering the same filing years as House search."""
    if lookback_years < 1:
        raise ValueError("lookback_years must be positive")
    day = now.astimezone(UTC).date()
    start_year = day.year - lookback_years + 1
    start = f"01/01/{start_year:04d} 00:00:00"
    end = f"{day.month:02d}/{day.day:02d}/{day.year:04d} 23:59:59"
    return start, end


def akamai_edge_reference(response: httpx.Response) -> str | None:
    """Edge reference when this response is an Akamai or other HTTP 403 block."""
    try:
        text = unescape(response.text)
    except Exception:
        text = ""
    denied = response.status_code == 403 or (
        "Access Denied" in text and "edgesuite" in text.lower()
    )
    if not denied:
        return None
    match = _EDGE_REFERENCE.search(text)
    return match.group(1) if match else "unparsed"


def classify_ptr_asset(ticker: str, name: str, asset_type_label: str) -> tuple[str, str | None, bool]:
    """Use the asset name when the ticker is blank or the line is not a stock.

    ``non_equity_type`` rejects bonds, munis, funds, and ETFs before a symbol
    can be treated as an equity ticker.
    """
    kind = non_equity_type(name)
    symbol = " ".join(ticker.split()).upper()
    blank = symbol in _BLANK_TICKER
    stock = asset_type_label.strip().casefold() == "stock"
    asset_name = " ".join(name.split())
    if not blank and kind is None and stock and _EQUITY_TICKER.fullmatch(symbol):
        return symbol, "common_stock", True
    return asset_name or "UNKNOWN", kind, False


def _plain(value: str) -> str:
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", value)).split())


def _iso_date(value: str) -> str | None:
    match = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", value.strip())
    if not match:
        return None
    month, day, year = match.groups()
    return f"{year}-{month}-{day}"


def parse_report_cell(cell: str) -> dict[str, str | None]:
    match = _HREF.search(cell)
    if not match:
        raise ValueError("senate_efd_malformed_records")
    href = unescape(match.group(1))
    label = _plain(cell)
    amendment = _AMENDMENT.search(label)
    path = urlsplit(href).path
    if not path.startswith("/"):
        path = urlsplit(urljoin(SENATE_EFD_ORIGIN, href)).path
    if path.startswith(SENATE_EFD_PTR_PATH):
        kind = "ptr"
    elif path.startswith(SENATE_EFD_PAPER_PATH):
        kind = "paper"
    else:
        kind = "other"
    found = _UUID.search(path)
    return {
        "href": href,
        "kind": kind,
        "uuid": found.group(0).lower() if found else None,
        "amendment_label": f"Amendment {amendment.group(1)}" if amendment else None,
    }


def parse_ptr_transactions(html: str) -> list[dict[str, str]]:
    table = next(
        (
            item
            for item in _TABLE.findall(html)
            if "Transaction Date" in item and "Asset Name" in item
        ),
        None,
    )
    if table is None:
        raise ValueError("senate_efd_ptr_table_missing")
    parsed = []
    for position, row in enumerate(_ROW.findall(table), start=1):
        cells = [_plain(cell) for cell in _CELL.findall(row)]
        if len(cells) < 8:
            continue
        number = cells[0] if re.fullmatch(r"\d+", cells[0]) else str(position)
        parsed.append(
            {
                "row_index": number,
                "transaction_date": cells[1],
                "owner": cells[2],
                "ticker": cells[3],
                "asset_name": cells[4],
                "asset_type_label": cells[5],
                "transaction_type": cells[6],
                "amount": cells[7],
            }
        )
    return parsed


class OfficialSenateEFDProvider:
    def __init__(
        self,
        *,
        lookback_years: int | None = None,
        now: datetime | None = None,
        http: httpx.Client | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self.lookback_years = (
            HOUSE_FILING_YEAR_LOOKBACK if lookback_years is None else lookback_years
        )
        self.now = now or datetime.now(UTC)
        self.http = http
        self._sleep = sleep or time.sleep

    def fetch(self) -> SenateEFDFetch:
        owns = self.http is None
        client = self.http or httpx.Client(
            timeout=30.0,
            follow_redirects=True,
            headers={"User-Agent": SENATE_EFD_USER_AGENT},
        )
        self.http = client
        try:
            try:
                records = self._collect()
            except SenateEFDBlocked as exc:
                return SenateEFDFetch("BLOCKED", (), exc.edge_reference, "BLOCKED")
            except SenateEFDRateLimit:
                return SenateEFDFetch("RateLimit", (), None, "RateLimit")
            return SenateEFDFetch("HEALTHY", tuple(records))
        finally:
            if owns:
                client.close()
                self.http = None

    def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        headers = {"User-Agent": SENATE_EFD_USER_AGENT, **(kwargs.pop("headers", None) or {})}
        delays = (0, *SENATE_EFD_RETRY_SLEEPS)
        for attempt, delay in enumerate(delays):
            if delay:
                self._sleep(delay)
            try:
                response = self.http.request(method, url, headers=headers, **kwargs)
            except httpx.TransportError:
                if attempt == len(delays) - 1:
                    raise
                continue
            reference = akamai_edge_reference(response)
            if reference is not None:
                raise SenateEFDBlocked(reference)
            if response.status_code == 429:
                raise SenateEFDRateLimit()
            if 500 <= response.status_code <= 504:
                if attempt == len(delays) - 1:
                    response.raise_for_status()
                continue
            response.raise_for_status()
            return response
        raise AssertionError("unreachable senate efd retry state")

    def _collect(self) -> list[dict]:
        if self.lookback_years < 1:
            raise ValueError("lookback_years must be positive")
        home = self._request("GET", SENATE_EFD_HOME_URL)
        token = _CSRF.search(home.text)
        if token is None:
            raise ValueError("senate_efd_csrf_missing")
        self._request(
            "POST",
            SENATE_EFD_HOME_URL,
            data={"csrfmiddlewaretoken": token.group(1), "prohibition_agreement": "1"},
            headers={"Referer": SENATE_EFD_HOME_URL},
        )
        csrf = self.http.cookies.get("csrftoken") or token.group(1)
        headers = {
            "Referer": SENATE_EFD_SEARCH_URL,
            "X-CSRFToken": csrf,
            "X-Requested-With": "XMLHttpRequest",
        }
        reports = self._report_rows(headers)
        output: list[dict] = []
        seen: set[str] = set()
        for report in reports:
            if len(report) < 5 or not all(isinstance(cell, str) for cell in report[:5]):
                raise ValueError("senate_efd_malformed_records")
            parsed = parse_report_cell(report[3])
            href = str(parsed["href"])
            if href in seen:
                continue
            seen.add(href)
            subject = " ".join(part for part in (report[0].strip(), report[1].strip()) if part) or "UNKNOWN"
            filed = _iso_date(report[4])
            url = urljoin(SENATE_EFD_ORIGIN, href)
            amendment = parsed["amendment_label"]
            if parsed["kind"] != "ptr":
                output.append(self._filing(subject, url, filed, amendment))
                continue
            if not parsed["uuid"]:
                raise ValueError("senate_efd_malformed_records")
            self._sleep(SENATE_EFD_PTR_PAUSE)
            page = self._request("GET", url, headers={"Referer": SENATE_EFD_SEARCH_URL})
            transactions = parse_ptr_transactions(page.text)
            if not transactions:
                output.append(self._filing(subject, url, filed, amendment))
                continue
            for item in transactions:
                asset, asset_type, eligible = classify_ptr_asset(
                    item["ticker"], item["asset_name"], item["asset_type_label"]
                )
                record_id = f"{parsed['uuid']}:{item['row_index']}"
                output.append(
                    {
                        "subject": subject,
                        "owner": item["owner"] or None,
                        "asset": asset,
                        "description": item["asset_name"] or None,
                        "asset_type": asset_type,
                        "eligible_equity_context": eligible,
                        "transaction_type": item["transaction_type"] or "UNKNOWN",
                        "transaction_date": _iso_date(item["transaction_date"]),
                        "disclosure_date": filed,
                        "amount_range": item["amount"] or None,
                        "source_url": url,
                        "source_record_id": record_id,
                        "provider": PROVIDER,
                        "record_semantics": "OFFICIAL_TRANSACTION_ROW",
                        "amendment": bool(amendment),
                        "amendment_label": amendment,
                    }
                )
        return output

    def _report_rows(self, headers: dict[str, str]) -> list[list]:
        start = 0
        rows: list[list] = []
        for _page in range(SENATE_EFD_MAX_PAGES):
            response = self._request(
                "POST", SENATE_EFD_DATA_URL, headers=headers, data=self._query(start)
            )
            try:
                payload = response.json()
            except ValueError:
                raise ValueError("senate_efd_malformed_records") from None
            data = payload.get("data") if isinstance(payload, dict) else None
            filtered = payload.get("recordsFiltered") if isinstance(payload, dict) else None
            if not isinstance(data, list) or not isinstance(filtered, int) or payload.get("result") != "ok":
                raise ValueError("senate_efd_malformed_records")
            rows.extend(data)
            start += len(data)
            if start >= filtered:
                return rows
            if not data:
                raise ValueError("senate_efd_pagination_stopped")
        raise ValueError("senate_efd_pagination_incomplete")

    def _query(self, start: int) -> dict[str, str]:
        start_date, end_date = submitted_window(self.now, self.lookback_years)
        body = {
            "draw": "1",
            "start": str(start),
            "length": str(SENATE_EFD_PAGE_LENGTH),
            "search[value]": "",
            "search[regex]": "false",
            "order[0][column]": "4",
            "order[0][dir]": "desc",
            "report_types": f"[{SENATE_EFD_PTR_TYPE_ID}]",
            "filer_types": "[]",
            "submitted_start_date": start_date,
            "submitted_end_date": end_date,
            "candidate_state": "",
            "senator_state": "",
            "office_id": "",
            "first_name": "",
            "last_name": "",
        }
        for index in range(5):
            body.update(
                {
                    f"columns[{index}][data]": str(index),
                    f"columns[{index}][name]": "",
                    f"columns[{index}][searchable]": "true",
                    f"columns[{index}][orderable]": "true",
                    f"columns[{index}][search][value]": "",
                    f"columns[{index}][search][regex]": "false",
                }
            )
        return body

    @staticmethod
    def _filing(subject: str, url: str, filed: str | None, amendment: str | None) -> dict:
        return {
            "subject": subject,
            "owner": None,
            "asset": "FINANCIAL_DISCLOSURE_FILING",
            "transaction_type": "FILING",
            "transaction_date": None,
            "disclosure_date": filed,
            "source_url": url,
            "provider": PROVIDER,
            "eligible_equity_context": False,
            "record_semantics": "FILING_NOT_TRADE_ROW",
            "amendment": bool(amendment),
            "amendment_label": amendment,
        }
