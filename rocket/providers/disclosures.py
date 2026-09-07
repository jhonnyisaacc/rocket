"""Official House and OGE filing providers. Filing-level evidence, not invented trades."""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from urllib.parse import urljoin

import httpx

HOUSE_SEARCH_URL = "https://disclosures-clerk.house.gov/FinancialDisclosure"
HOUSE_SEARCH_RESULT_URL = "https://disclosures-clerk.house.gov/FinancialDisclosure/ViewMemberSearchResult"
OGE_INDEX_URL = "https://www.oge.gov/web/oge.nsf/Officials%20Individual%20Disclosures%20Search%20Collection?OpenForm"
OGE_API_URL = "https://extapps2.oge.gov/201/Presiden.nsf/API.xsp/v2/rest"


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
            for link in _links(response.text, base_url=HOUSE_SEARCH_URL):
                if "ptr-pdf" not in link.lower() and not link.lower().endswith(".pdf"):
                    continue
                output.append(
                    {
                        "subject": "UNKNOWN",
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
    ) -> None:
        self.subject = subject
        self.index_url = index_url
        self.document_urls = tuple(document_urls or ())
        self.http = http or httpx.Client(timeout=20.0, follow_redirects=True)

    def fetch(self) -> list[dict[str, str | None]]:
        if self.document_urls:
            return [self._filing(url, "UNKNOWN", None) for url in dict.fromkeys(self.document_urls)]
        index = self.http.get(self.index_url)
        index.raise_for_status()
        if OGE_API_URL not in index.text:
            raise ValueError("OGE collection schema missing its public records API")
        latest = self._page(subject="", start=0, length=1)
        if not latest["data"]:
            raise ValueError("OGE current index is empty")
        latest_date = datetime.fromisoformat(latest["data"][0]["docDate"]).date()
        if not timedelta(0) <= datetime.now(UTC).date() - latest_date <= timedelta(days=45):
            raise ValueError("OGE current index is stale or future dated")
        output = []
        for start in range(0, 500, 100):
            page = self._page(subject=self.subject.split()[-1], start=start, length=100)
            for row in page["data"]:
                name = row["name"]
                if self.subject.split()[-1].lower() not in name.lower():
                    raise ValueError("OGE server ignored the subject filter")
                for url in _links(row["type"], base_url=self.index_url):
                    if url.lower().endswith(".pdf"):
                        output.append(self._filing(url, name, row["docDate"]))
            if start + len(page["data"]) >= page["recordsFiltered"]:
                return list({r["source_url"]: r for r in output}.values())
            if not page["data"]:
                raise ValueError("OGE pagination stopped before total")
        raise ValueError("OGE bounded pagination incomplete")

    def _page(self, *, subject, start, length):
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
        response = self.http.get(OGE_API_URL, params=params)
        response.raise_for_status()
        page = response.json()
        if not isinstance(page, dict) or not isinstance(page.get("data"), list) or not isinstance(
            page.get("recordsFiltered"), int
        ):
            raise ValueError("Malformed OGE records response")
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
