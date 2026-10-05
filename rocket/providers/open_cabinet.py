"""Free secondary OGE transaction export; never substitute issuer shares for bonds."""

import re
from datetime import UTC, datetime, timedelta
from urllib.parse import unquote, urlsplit

import httpx

from rocket.models import OperationalStatus
from rocket.people import person_id
from rocket.pit import parse_datetime
from rocket.providers.dispatch import failure_kind
from rocket.providers.http import get_read
from rocket.providers.protocols import ProviderResult

DATA_URL = "https://open-cabinet.org/data/full-dataset.json"
STRUCTURED_SOURCE_INTERIM = (
    "Quiver or manual PDF read while Open Cabinet export lags the official OGE index. "
    "Do not invent tickers from the filename."
)
_278T = re.compile(r"278-?t", re.IGNORECASE)
_TICKER = re.compile(r"[A-Z][A-Z0-9.\-]{0,9}")
_COUPON = re.compile(r"(?<!\d)\d{1,2}(?:\.\d+)?\s*%")
_DUE = re.compile(r"\b(?:DUE|MATUR)")
_BOOK_ENTRY = re.compile(r"\bB/E\b")
_MUNI = re.compile(
    r"\b(?:CNTY|COUNTY|CITY|TOWN|MUN|MUNI|MUNICIPAL|AUTH|AUTHORITY|BDS|BONDS?|"
    r"DIST|DISTRICT|RFDG|HSG|HOUSING|FACS|SCH|SCHOOL|REV|REVENUE)\b"
)
_NOTE = re.compile(r"\b(?:NOTES?|NTS?|DEBENTURES?|SR NT|SENIOR NOTE)\b")
_ETF = re.compile(r"\b(?:ETF|ETN|ISHARES|SPDR|SELECT SECTOR)\b")
_FUND = re.compile(r"\b(?:MUTUAL FUND|MONEY MARKET|FUND)\b")
_VERIFIED = {"checked", "human_verified"}


def normalize_issuer_name(value):
    """Exact-match key: case, punctuation, and spacing do not make a second name."""
    return " ".join(re.sub(r"[^A-Z0-9]+", " ", str(value).upper()).split())


def non_equity_type(description):
    """Bond, note, fund, and ETF lines never receive a stock ticker.

    ``PTC`` inside ``B/E PTC 5.00 % Due`` is a bond marker, not the issuer PTC.
    A plain issuer name such as ``PTC INC`` returns None so a later exact
    title lookup may run.
    """
    text = description.upper()
    if _ETF.search(text):
        return "etf"
    if _FUND.search(text):
        return "mutual_fund"
    if _MUNI.search(text) or (_BOOK_ENTRY.search(text) and _DUE.search(text)):
        return "municipal_bond"
    if _NOTE.search(text) or _COUPON.search(text) or _DUE.search(text) or _BOOK_ENTRY.search(text):
        return "corporate_note"
    return None


def _symbol(ticker):
    if not isinstance(ticker, str):
        return None
    symbol = ticker.strip().upper()
    return symbol if _TICKER.fullmatch(symbol) else None


def prepare_issuer_tickers(raw):
    """Normalized issuer title to one ticker. Ambiguous titles stay unresolved."""
    if not isinstance(raw, dict):
        return {}
    ready = {}
    for title, ticker in raw.items():
        key = normalize_issuer_name(title)
        if not key:
            continue
        symbol = _symbol(ticker)
        if key in ready and ready[key] != symbol:
            ready[key] = None
        elif key not in ready:
            ready[key] = symbol
    return ready


def issuer_tickers_from_company_file(payload):
    """SEC ``company_tickers.json`` titles. A title with two tickers does not resolve."""
    if not isinstance(payload, dict):
        return {}
    grouped = {}
    for row in payload.values():
        if not isinstance(row, dict):
            continue
        key = normalize_issuer_name(row.get("title", ""))
        symbol = _symbol(row.get("ticker"))
        if not key or symbol is None:
            continue
        grouped.setdefault(key, set()).add(symbol)
    return {
        key: next(iter(symbols)) if len(symbols) == 1 else None
        for key, symbols in grouped.items()
    }


def load_issuer_tickers(now):
    """Best-effort SEC title map. Any failure leaves names unresolved."""
    try:
        from rocket.providers.edgar import SECEDGAR, TICKERS_URL

        cached = SECEDGAR()._get("company_tickers", TICKERS_URL, now)
        if not isinstance(cached, dict) or cached.get("failure"):
            return {}
        return issuer_tickers_from_company_file(cached.get("payload"))
    except Exception:
        return {}


class OpenCabinetExportError(ValueError):
    """Export age is unusable. Rows stay withheld; callers still get exported_at."""

    def __init__(self, exported: datetime | None) -> None:
        super().__init__("stale or future dataset export")
        self.exported = exported


def document_key(url):
    parsed = urlsplit(str(url))
    if parsed.scheme != "https" or parsed.hostname not in {"extapps2.oge.gov", "www.oge.gov"}:
        raise ValueError("not an OGE document")
    path = unquote(parsed.path).lower()
    if not path.endswith(".pdf"):
        raise ValueError("not an OGE PDF")
    return parsed.hostname, path


def _index_date(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)).date()
    except ValueError:
        return None


def structured_coverage(official_records, *, exported_at=None, covered_urls=(), now=None, export_usable=None):
    """Classify 278-T filings that have no Open Cabinet rows. Never invent trades."""
    now = now or datetime.now(UTC)
    exported = exported_at if isinstance(exported_at, datetime) else parse_datetime(exported_at)
    if export_usable is None:
        export_usable = exported is not None and timedelta(0) <= now - exported <= timedelta(days=14)
    covered = set()
    for url in covered_urls:
        try:
            covered.add(document_key(url))
        except ValueError:
            continue
    uncovered = []
    for filing in official_records:
        url = filing.get("source_url")
        if not url or not _278T.search(unquote(str(url))):
            continue
        try:
            key = document_key(url)
        except ValueError:
            key = None
        if key and key in covered:
            continue
        index_day = _index_date(filing.get("index_added_at"))
        export_earlier = (
            not export_usable
            or exported is None
            or (index_day is not None and exported.date() < index_day)
        )
        uncovered.append({
            "source_url": url,
            "index_added_at": filing.get("index_added_at"),
            "status": "OC_STALE" if export_earlier else "MISSING_STRUCTURED_ROWS",
            "needs_structured_source": True,
        })
    newest = None
    for row in uncovered:
        day = _index_date(row.get("index_added_at"))
        if day and (newest is None or day > newest):
            newest = day
    lag = (newest - exported.date()).days if newest and exported is not None else None
    if any(row["status"] == "OC_STALE" for row in uncovered):
        status = "OC_STALE"
    elif uncovered:
        status = "MISSING_STRUCTURED_ROWS"
    elif not export_usable:
        status = "OC_STALE"
    else:
        status = "COVERED"
    return {
        "provider": "open_cabinet",
        "exported_at": exported.isoformat() if exported else None,
        "needs_structured_source": bool(uncovered),
        "status": status,
        "uncovered_filings": uncovered,
        "export_lag_days": lag,
        "interim": STRUCTURED_SOURCE_INTERIM,
        "refresh": "Open Cabinet is re-fetched each run; rocket cannot force a republish.",
    }


class OpenCabinetProvider:
    def __init__(self, *, http=None, issuer_tickers=None):
        self.http = http
        # None loads SEC company_tickers when a row still needs a name.
        # A dict, including an empty one, is used as given and does not fetch.
        self.issuer_tickers = issuer_tickers

    def person_history(self, name="Donald Trump", *, official_records=(), now=None):
        if person_id(name) != "donald_trump":
            return ProviderResult(OperationalStatus.UNAVAILABLE, source="open_cabinet",
                                  failure_kind="UnsupportedPersonIdentity")
        try:
            if self.http is None:
                with httpx.Client(timeout=30) as client:
                    payload = get_read(client, DATA_URL).json()
            else:
                payload = get_read(self.http, DATA_URL).json()
            return self._normalize(payload, official_records, now or datetime.now(UTC))
        except OpenCabinetExportError as exc:
            return ProviderResult(
                OperationalStatus.UNAVAILABLE, source="open_cabinet", failure_kind="OC_STALE",
                extras={"dataset_url": DATA_URL, "exported_at": exc.exported.isoformat() if exc.exported else None,
                        "coverage": "Published OGE 278-T rows only; not complete holdings or annual reports."},
            )
        except Exception as exc:
            return ProviderResult(OperationalStatus.UNAVAILABLE, source="open_cabinet",
                                  failure_kind=failure_kind(exc))

    def _issuer_names(self, now):
        if self.issuer_tickers is not None:
            return prepare_issuer_tickers(self.issuer_tickers)
        return load_issuer_tickers(now)

    def _normalize(self, payload, official_records, now):
        exported = parse_datetime(payload.get("exportedAt"))
        if exported is None or not timedelta(0) <= now - exported <= timedelta(days=14):
            raise OpenCabinetExportError(exported)
        officials = payload["officials"]
        matches = [o for o in officials if person_id(o.get("name")) == "donald_trump"]
        if len(matches) != 1 or not isinstance(matches[0].get("transactions"), list):
            raise ValueError("missing or ambiguous person history")
        official = matches[0]
        transactions = official["transactions"]
        if not transactions or len(transactions) != official["transactionCount"] + official.get("underReviewCount", 0):
            raise ValueError("incomplete transaction export")
        postings = {}
        for filing in official_records:
            if person_id(filing.get("subject")) != "donald_trump":
                continue
            # OGE's index timestamp has no timezone. Use only its posted calendar
            # date, explicitly labelled as such, never as a PIT availability clock.
            value = filing.get("index_added_at")
            added = datetime.fromisoformat(value).date() if value else None
            if added and added <= now.date():
                key = document_key(filing["source_url"])
                postings[key] = min(postings.get(key, added), added)
        rows, ids, pending = [], set(), []
        for row in transactions:
            record_id = row["recordId"]
            if not isinstance(record_id, str) or not record_id or record_id in ids:
                raise ValueError("missing or duplicate transaction identity")
            ids.add(record_id)
            key = document_key(row["sourceUrl"])
            traded = datetime.fromisoformat(row["date"]).date()
            if traded > exported.date() or row["type"] not in {"Purchase", "Sale", "Sale (Full)", "Sale (Partial)", "Exchange"}:
                raise ValueError("invalid transaction date or type")
            description = row["description"]
            if not isinstance(description, str) or not description.strip():
                raise ValueError("missing instrument description")
            ticker = row.get("resolvedTicker")
            instrument = row.get("instrumentType")
            # T1 is the source's strongest symbol resolution. Retain its secondary
            # provenance: trade-column checks alone do not verify the asset name.
            eligible = bool(instrument == "common_stock"
                            and row.get("resolutionTier") == "T1"
                            and row.get("verificationState") in _VERIFIED
                            and isinstance(ticker, str)
                            and _TICKER.fullmatch(ticker))
            # The 09.8.2026 batch left instrument type and ticker null on rows
            # whose text was still checked. Classify before any name lookup so
            # a bond token cannot become a stock ticker.
            needs_name = not eligible and ticker is None and instrument is None
            if needs_name:
                kind = non_equity_type(description)
                if kind:
                    instrument = kind
                    needs_name = False
                elif row.get("verificationState") not in _VERIFIED:
                    needs_name = False
            posted = postings.get(key)
            rows.append({
                "subject": official["name"], "owner": None,
                "asset": ticker if eligible else description,
                "description": description, "asset_type": instrument,
                "eligible_equity_context": eligible,
                "transaction_type": row["type"], "transaction_date": row["date"],
                "amount_range": row.get("amount"), "source_record_id": record_id,
                "disclosure_date": posted.isoformat() if posted else None,
                "disclosure_date_basis": "OGE_INDEX_POSTED_DATE" if posted else "UNKNOWN",
                "source_url": row["sourceUrl"], "provider": "open_cabinet",
                "source_family": "secondary", "underlying_source_family": "executive",
                "verification_state": row.get("verificationState"),
                "resolution_tier": row.get("resolutionTier"), "resolved_ticker": ticker,
                "record_semantics": "SECONDARY_OGE_TRANSACTION_ROW",
            })
            if needs_name:
                pending.append(len(rows) - 1)
        if pending:
            names = self._issuer_names(now)
            for index in pending:
                symbol = names.get(normalize_issuer_name(rows[index]["description"]))
                if not isinstance(symbol, str):
                    continue
                rows[index]["asset"] = symbol
                rows[index]["asset_type"] = "common_stock"
                rows[index]["eligible_equity_context"] = True
                rows[index]["resolution_tier"] = "sec_exact_name"
                rows[index]["resolved_ticker"] = symbol
        return ProviderResult(OperationalStatus.HEALTHY, tuple(rows), now, source="open_cabinet",
                              extras={"dataset_url": DATA_URL, "exported_at": exported.isoformat(),
                                      "attribution": "Open Cabinet — https://open-cabinet.org/download",
                                      "coverage": "Published OGE 278-T rows only; not complete holdings or annual reports.",
                                      "transaction_records": len(rows),
                                      "eligible_common_stock_records": sum(r["eligible_equity_context"] for r in rows),
                                      "rows_with_posted_date": sum(r["disclosure_date"] is not None for r in rows)})
