"""Official House and OGE filing providers. Filing-level evidence, not invented trades."""

from __future__ import annotations

import re
import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from html import unescape
from urllib.parse import urljoin

import httpx

HOUSE_SEARCH_URL = "https://disclosures-clerk.house.gov/FinancialDisclosure"
HOUSE_SEARCH_RESULT_URL = "https://disclosures-clerk.house.gov/FinancialDisclosure/ViewMemberSearchResult"
OGE_INDEX_URL = "https://www.oge.gov/web/oge.nsf/Officials%20Individual%20Disclosures%20Search%20Collection?OpenForm"
# Public records API advertised by the index page. Version is discovered, not pinned.
OGE_API_URL_RE = re.compile(r"https://extapps2\.oge\.gov/201/Presiden\.nsf/API\.xsp/v(\d+)/rest")
# Three attempts. Sleep 1s before the second and 2s before the third.
# Transport errors and HTTP 500-504 only; schema errors and other 4xx do not retry.
OGE_RETRY_SLEEPS = (1, 2)
_REASON_TOKEN = re.compile(r"^[a-z0-9_]{1,64}$")


class OGEProviderError(ValueError):
    """OGE schema or validation failure. ``reason`` is a stable token, not a message."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def discover_oge_api_url(html: str) -> str:
    """Highest-version public records URL in the OGE index HTML."""
    best: tuple[int, str] | None = None
    for match in OGE_API_URL_RE.finditer(unescape(html)):
        version = int(match.group(1))
        if best is None or version > best[0]:
            best = (version, match.group(0))
    if best is None:
        raise OGEProviderError("oge_index_api_marker_missing")
    return best[1]


def executive_failure_status(exc: BaseException) -> dict[str, str]:
    """Executive ``provider_status`` entry after a failed OGE fetch.

    ``reason`` is copied only when it matches ``^[a-z0-9_]{1,64}$``.
    Exception text and request URLs are never copied. Adapters may branch
    on these tokens:

    - ``oge_index_api_marker_missing`` — index HTML has no public records API URL
    - ``oge_index_empty`` — records API returned no current rows
    - ``oge_index_stale_or_future`` — newest ``docDate`` is outside the 45-day window
    - ``oge_subject_filter_ignored`` — a row does not match the requested subject
    - ``oge_pagination_stopped`` — a page was empty before ``recordsFiltered``
    - ``oge_pagination_incomplete`` — the bounded page walk did not finish
    - ``oge_malformed_records`` — JSON shape or ``docDate`` could not be read
    - ``transport_error`` — connection or timeout, no response status
    - ``http_`` plus a three-digit status, such as ``http_503``
    """
    from rocket.providers.dispatch import failure_kind

    entry = {"status": "UNAVAILABLE", "failure_kind": failure_kind(exc)}
    reason = None
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        if 100 <= code <= 599:
            reason = f"http_{code}"
    elif isinstance(exc, httpx.TransportError):
        reason = "transport_error"
    else:
        candidate = getattr(exc, "reason", None)
        if isinstance(candidate, str):
            reason = candidate
    if isinstance(reason, str) and _REASON_TOKEN.fullmatch(reason):
        entry["reason"] = reason
    return entry


def _links(html: str, *, base_url: str) -> list[str]:
    return [urljoin(base_url, href) for href in re.findall(r'''href=["']([^"']+)["']''', html, re.IGNORECASE)]


class OfficialHouseDisclosureProvider:
    def __init__(
        self,
        *,
        subjects: Sequence[str] = ("Nancy Pelosi",),
        filing_year: int | None = None,
        http: httpx.Client | None = None,
    ) -> None:
        self.subjects = tuple(subjects)
        self.filing_year = filing_year
        self.http = http or httpx.Client(timeout=20.0, follow_redirects=True)

    def fetch(self) -> list[dict[str, str | None]]:
        index = self.http.get(HOUSE_SEARCH_URL)
        index.raise_for_status()
        token_matches = re.findall(
            r'''name=["'](__RequestVerificationToken|[^"']*token[^"']*)["'][^>]*value=["']([^"']*)["']''',
            index.text,
            re.IGNORECASE,
        )
        hidden = {name: value for name, value in token_matches}
        year = str(self.filing_year or datetime.now(UTC).year)
        output: list[dict[str, str | None]] = []
        for subject in self.subjects:
            last_name = subject.split()[-1]
            data = {**hidden, "LastName": last_name, "FilingYear": year, "State": "", "District": ""}
            response = self.http.post(HOUSE_SEARCH_RESULT_URL, data=data)
            response.raise_for_status()
            if not re.search(r"<table|no (?:records|results)|no matching", response.text, re.IGNORECASE) and not any(
                ".pdf" in url.lower() for url in _links(response.text, base_url=HOUSE_SEARCH_URL)
            ):
                raise ValueError("House results schema unavailable")
            from rocket.people import person_id
            for tr in re.findall(r"<tr\b[^>]*>.*?</tr>", response.text, re.IGNORECASE | re.DOTALL):
                name_cell = re.search(r'<td[^>]*data-label="Name"[^>]*>(.*?)</td>', tr, re.IGNORECASE | re.DOTALL)
                name = unescape(re.sub(r"<[^>]+>", " ", name_cell[1])).strip() if name_cell else "UNKNOWN"
                if person_id(subject) and person_id(name) != person_id(subject):
                    continue
                links = _links(tr, base_url=HOUSE_SEARCH_URL)
                if len(links) != 1:
                    continue
                link = links[0]
                if "ptr-pdf" not in link.lower() and not link.lower().endswith(".pdf"):
                    continue
                output.append(
                    {
                        "subject": name,
                        "requested_subject": subject,
                        "owner": None,
                        "asset": "FINANCIAL_DISCLOSURE_FILING",
                        "transaction_type": "FILING",
                        "transaction_date": None,
                        "disclosure_date": None,
                        "source_url": link,
                        "provider": "official_house_disclosures",
                    }
                )
        seen: set[str] = set()
        return [row for row in output if not (row["source_url"] in seen or seen.add(str(row["source_url"])))]


class OfficialOGEExecutiveDisclosureProvider:
    def __init__(
        self,
        *,
        subject: str = "Donald Trump",
        index_url: str = OGE_INDEX_URL,
        document_urls: Sequence[str] | None = None,
        http: httpx.Client | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self.subject = subject
        self.index_url = index_url
        self.document_urls = tuple(document_urls or ())
        self.http = http or httpx.Client(timeout=20.0, follow_redirects=True)
        self._sleep = sleep or time.sleep

    def _read(self, url: str, **kwargs):
        delays = (0, *OGE_RETRY_SLEEPS)
        for attempt, delay in enumerate(delays):
            if delay:
                self._sleep(delay)
            try:
                response = self.http.get(url, **kwargs)
                response.raise_for_status()
                return response
            except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                retryable = isinstance(exc, httpx.TransportError) or (
                    isinstance(exc, httpx.HTTPStatusError) and 500 <= exc.response.status_code <= 504
                )
                if not retryable or attempt == len(delays) - 1:
                    raise
        raise AssertionError("unreachable OGE retry state")

    def fetch(self) -> list[dict[str, str | None]]:
        if self.document_urls:
            return [self._filing(url, "UNKNOWN", None) for url in dict.fromkeys(self.document_urls)]
        index = self._read(self.index_url)
        api_url = discover_oge_api_url(index.text)
        latest = self._page(api_url=api_url, subject="", start=0, length=1)
        if not latest["data"]:
            raise OGEProviderError("oge_index_empty")
        try:
            latest_date = datetime.fromisoformat(latest["data"][0]["docDate"]).date()
        except (TypeError, ValueError, KeyError):
            raise OGEProviderError("oge_malformed_records") from None
        if not timedelta(0) <= datetime.now(UTC).date() - latest_date <= timedelta(days=45):
            raise OGEProviderError("oge_index_stale_or_future")
        output = []
        for start in range(0, 500, 100):
            page = self._page(
                api_url=api_url, subject=self.subject.split()[-1], start=start, length=100
            )
            for row in page["data"]:
                try:
                    name = row["name"]
                    added = row["docDate"]
                    markup = row["type"]
                except (TypeError, KeyError):
                    raise OGEProviderError("oge_malformed_records") from None
                if self.subject.split()[-1].lower() not in str(name).lower():
                    raise OGEProviderError("oge_subject_filter_ignored")
                from rocket.people import person_id

                if person_id(self.subject) and person_id(name) != person_id(self.subject):
                    continue
                for url in _links(str(markup), base_url=self.index_url):
                    if url.lower().endswith(".pdf"):
                        output.append(self._filing(url, name, added))
            if start + len(page["data"]) >= page["recordsFiltered"]:
                return list({r["source_url"]: r for r in output}.values())
            if not page["data"]:
                raise OGEProviderError("oge_pagination_stopped")
        raise OGEProviderError("oge_pagination_incomplete")

    def _page(self, *, api_url: str, subject, start, length):
        params = {
            "draw": "1",
            "start": str(start),
            "length": str(length),
            "search[value]": "",
            "search[regex]": "false",
            "order[0][column]": "0",
            "order[0][dir]": "desc",
        }
        for i, key in enumerate(("docDate", "title", "type", "name", "agency", "level")):
            params.update(
                {
                    f"columns[{i}][data]": key,
                    f"columns[{i}][name]": "",
                    f"columns[{i}][searchable]": "true",
                    f"columns[{i}][orderable]": "true",
                    f"columns[{i}][search][value]": subject if i == 3 else "",
                    f"columns[{i}][search][regex]": "false",
                }
            )
        response = self._read(api_url, params=params)
        try:
            page = response.json()
        except ValueError:
            raise OGEProviderError("oge_malformed_records") from None
        if (
            not isinstance(page, dict)
            or not isinstance(page.get("data"), list)
            or not isinstance(page.get("recordsFiltered"), int)
        ):
            raise OGEProviderError("oge_malformed_records")
        return page

    @staticmethod
    def _filing(url, subject, added):
        return {
            "subject": subject,
            "owner": None,
            "asset": "PUBLIC_FINANCIAL_DISCLOSURE",
            "transaction_type": "FILING_OBSERVED",
            "transaction_date": None,
            "disclosure_date": None,
            "source_url": url,
            "provider": "official_oge",
            "index_added_at": added,
            "retrieved_at": datetime.now(UTC).isoformat(),
        }
