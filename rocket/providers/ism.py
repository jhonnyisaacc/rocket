"""ISM identity and publisher parse. Headline PMI ≠ industry rankings. Never NMFBAI-as-composite."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, time, timedelta
from html import unescape
from typing import Literal

from rocket.clock import NY, exchange_holidays

ReportKind = Literal["manufacturing", "services"]
_MONTH_PATTERN = (
    r"(?:January|February|March|April|May|June|July|"
    r"August|September|October|November|December)"
)
_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")
_EXPANDING_RE = re.compile(
    r"industries\s+reporting\s+growth[^:]*:\s*(?P<body>[^.]+)\.",
    re.IGNORECASE,
)
_CONTRACTING_RE = re.compile(
    r"industries\s+reporting\s+(?:a\s+)?contraction[^:]*:\s*(?P<body>[^.]+)\.",
    re.IGNORECASE,
)


@dataclass
class ISMIndustryRanking:
    industry: str
    trend: Literal["expanding", "contracting"]
    rank: int


@dataclass
class ISMReport:
    kind: ReportKind
    report_month: str
    pmi: float | None
    expanding: list[ISMIndustryRanking] = field(default_factory=list)
    contracting: list[ISMIndustryRanking] = field(default_factory=list)
    source_url: str | None = None


def publication_at(reference: datetime, kind: str) -> datetime:
    month = (reference.replace(day=28) + timedelta(days=4)).replace(day=1)
    holidays = exchange_holidays(month.year)
    day, count = month.date(), 0
    while True:
        if day.weekday() < 5 and day not in holidays:
            count += 1
        if count == (1 if kind == "manufacturing" else 3):
            return datetime.combine(day, time(10), NY).astimezone(UTC)
        day += timedelta(days=1)


def expected_reference(kind: str, now: datetime) -> datetime:
    reference = (now.astimezone(NY).replace(day=1) - timedelta(days=1)).replace(day=1)
    if publication_at(reference, kind) > now:
        reference = (reference - timedelta(days=1)).replace(day=1)
    return reference


def release_identity(report: ISMReport, now: datetime) -> dict:
    reference = datetime.strptime(report.report_month, "%B %Y").replace(tzinfo=UTC)
    published = publication_at(reference, report.kind)
    expected = expected_reference(report.kind, now)
    status = (
        "UNPUBLISHED"
        if published > now
        else "CURRENT"
        if reference.strftime("%Y-%m") == expected.strftime("%Y-%m")
        else "STALE"
    )
    return {
        "report_type": report.kind.upper(),
        "reference_month": reference.strftime("%Y-%m"),
        "expected_reference_month": expected.strftime("%Y-%m"),
        "publication_date": published.date().isoformat(),
        "publication_at": published.isoformat(),
        "publication_date_basis": "first/third US business day at 10:00 America/New_York",
        "retrieved_at": now.isoformat(),
        "source_url": report.source_url,
        "release_status": status,
    }


def _strip_html(html: str) -> str:
    without_code = re.sub(
        r"<\s*(script|style|noscript)\b[^>]*>.*?<\s*/\s*\1\s*>",
        " ",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return _WHITESPACE_RE.sub(" ", unescape(_TAG_RE.sub(" ", without_code))).strip()


def _extract_heading_texts(html: str) -> list[str]:
    values: list[str] = []
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if title_match:
        values.append(_strip_html(title_match.group(1)))
    for heading_match in re.finditer(r"<h[12][^>]*>(.*?)</h[12]>", html, re.IGNORECASE | re.DOTALL):
        values.append(_strip_html(heading_match.group(1)))
    return [item for item in values if item]


def _extract_kind_aligned_month(text: str, kind_label: str) -> str | None:
    patterns = (
        rf"(?P<month>{_MONTH_PATTERN}\s+\d{{4}})\s+{kind_label}\b",
        rf"{kind_label}\s+(?:ISM(?:®)?\s+)?(?:Report\s+On\s+Business(?:®)?\s+)?(?:for\s+)?(?P<month>{_MONTH_PATTERN}\s+\d{{4}})",
        rf"{kind_label}[^\n\r]{{0,120}}?(?P<month>{_MONTH_PATTERN}\s+\d{{4}})",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group("month")
    return None


def _extract_report_month(html: str, *, text: str, kind: ReportKind, source_url: str) -> str:
    kind_label = "Manufacturing" if kind == "manufacturing" else "Services"
    if "prnewswire.com" in source_url.lower():
        slug_match = re.search(rf"(?P<month>{_MONTH_PATTERN})[-_](?P<year>\d{{4}})", source_url, re.IGNORECASE)
        if slug_match:
            return f"{slug_match.group('month').capitalize()} {slug_match.group('year')}"
    roundup = re.search(r"roundup-([a-z]+)-(\d{4})-" + kind, source_url, re.IGNORECASE)
    if roundup:
        for heading in _extract_heading_texts(html):
            if re.search(r"\b" + roundup[1] + r"\s+" + kind + r"\b", heading, re.IGNORECASE):
                return f"{roundup[1].capitalize()} {roundup[2]}"
    for heading in _extract_heading_texts(html):
        month = _extract_kind_aligned_month(heading, kind_label)
        if month:
            return month
    month = _extract_kind_aligned_month(text, kind_label)
    if month:
        return month
    match = re.search(rf"(?P<month>{_MONTH_PATTERN}\s+\d{{4}})", text)
    return match.group("month") if match else "Unknown"


def _extract_pmi(text: str, kind: ReportKind, *, source_url: str | None = None) -> float | None:
    kind_label = "Manufacturing" if kind == "manufacturing" else "Services"
    if source_url:
        slug_match = re.search(r"pmi-at-(\d{2}(?:-\d)?)-", source_url, re.IGNORECASE)
        if slug_match is not None:
            return float(slug_match.group(1).replace("-", "."))
    registered = re.search(
        rf"{kind_label}\s+PMI(?:®)?\s+registered\s+(\d{{2}}\.\d)\s*percent",
        text,
        re.IGNORECASE,
    )
    if registered is not None:
        return float(registered.group(1))
    at_headline = re.search(rf"{kind_label}\s+PMI(?:®)?\s+at\s+(\d{{2}}\.\d)\b", text, re.IGNORECASE)
    if at_headline is not None:
        return float(at_headline.group(1))
    return None


def _split_industries(body: str) -> list[str]:
    normalized = re.sub(r"[;,]\s*and\s+", "; ", body, flags=re.IGNORECASE)
    normalized = re.sub(r"\s+and\s+", "; ", normalized, flags=re.IGNORECASE)
    return [chunk.strip().rstrip(".").strip('"').lower() for chunk in re.split(r"\s*;\s*", normalized) if chunk.strip()]


def _parse_industry_list(text: str, *, trend: Literal["expanding", "contracting"]) -> list[ISMIndustryRanking]:
    pattern = _EXPANDING_RE if trend == "expanding" else _CONTRACTING_RE
    match = pattern.search(text)
    if match is None:
        return []
    return [
        ISMIndustryRanking(industry=name, trend=trend, rank=i)
        for i, name in enumerate(_split_industries(match.group("body")), start=1)
    ]


def extract_prnewswire_url(html: str, *, roundup_url: str, kind: ReportKind) -> str | None:
    links = re.findall(r'https://www\.prnewswire\.com/news-releases/[^"\'\s<]+', html)
    if not links:
        return None
    identity = re.search(r"roundup-([a-z]+)-(\d{4})-" + kind, roundup_url)
    preferred = [url for url in links if f"{kind}-pmi" in url]
    if identity:
        marker = f"{identity[1]}-{identity[2]}"
        preferred = [url for url in preferred if marker in url.lower()]
    return unescape(preferred[0]) if len(set(preferred)) == 1 else None


def parse_ism_html(html: str, *, kind: ReportKind, source_url: str) -> ISMReport:
    text = _strip_html(html)
    month = _extract_report_month(html, text=text, kind=kind, source_url=source_url)
    headings = _extract_heading_texts(html)
    if headings:
        title = headings[0]
        other = "Services" if kind == "manufacturing" else "Manufacturing"
        label = "Manufacturing" if kind == "manufacturing" else "Services"
        if other.lower() in title.lower() and label.lower() not in title.lower():
            raise ValueError("ISM report type disagrees with release heading")
        heading_month = _extract_kind_aligned_month(title, label)
        if heading_month and heading_month.lower() != month.lower():
            raise ValueError("ISM URL and release heading disagree on reference month")
    pmi = _extract_pmi(text, kind, source_url=source_url)
    headline = re.split(r"WHAT RESPONDENTS ARE SAYING", text, flags=re.IGNORECASE)[0]
    return ISMReport(
        kind=kind,
        report_month=month,
        pmi=pmi,
        expanding=_parse_industry_list(headline, trend="expanding"),
        contracting=_parse_industry_list(headline, trend="contracting"),
        source_url=source_url,
    )
