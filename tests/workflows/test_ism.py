from datetime import UTC, datetime

from rocket.models import OperationalStatus, ResearchStatus
from rocket.providers.ism import (
    ISMReport,
    expected_reference,
    extract_prnewswire_url,
    fetch_ism_report,
    latest_roundup_url,
    parse_ism_html,
    release_identity,
)
from rocket.store import ResearchStore
from rocket.workflows.ism import IsmWorkflow
from tests.harness import assert_research_result, is_registered

NOW = datetime(2026, 9, 7, 15, tzinfo=UTC)


def test_ism_is_registered():
    assert is_registered("ism")


def test_release_identity_current_stale_unpublished():
    for kind in ("manufacturing", "services"):
        assert release_identity(ISMReport(kind, "August 2026", 50.0), NOW)["release_status"] == "CURRENT"
        assert release_identity(ISMReport(kind, "August 2022", 50.0), NOW)["release_status"] == "STALE"
        assert release_identity(ISMReport(kind, "September 2026", 50.0), NOW)["release_status"] == "UNPUBLISHED"
        assert release_identity(ISMReport(kind, "August 2026", 50.0), NOW)["report_type"] == kind.upper()


def test_services_publication_gate():
    assert expected_reference("services", datetime(2026, 9, 3, 13, 59, tzinfo=UTC)).month == 7
    assert expected_reference("services", datetime(2026, 9, 3, 14, 0, tzinfo=UTC)).month == 8


def test_roundup_selects_own_release_and_month():
    current = "https://www.prnewswire.com/news-releases/services-pmi-at-55-4-august-2026-report.html"
    old = "https://www.prnewswire.com/news-releases/services-pmi-at-56-9-august-2022-report.html"
    html = f'<h1>ISM PMI Reports Roundup: August Services</h1><p>Services last expanded in August 2022</p><a href="{old}">history</a><a href="{current}">current</a>'
    url = "https://www.ismworld.org/blog/2026/ism-pmi-reports-roundup-august-2026-services/"
    assert extract_prnewswire_url(html, roundup_url=url, kind="services") == current
    assert parse_ism_html(html, kind="services", source_url=url).report_month == "August 2026"


def test_headline_rankings_never_take_subindex_lists():
    html = (
        "<h1>August 2026 Manufacturing</h1>Manufacturing PMI registered 54.6 percent. "
        "The industries reporting growth are: Primary Metals. "
        "The industries reporting a contraction are: Wood Products; and Chemical Products. "
        "WHAT RESPONDENTS ARE SAYING Employment industries reporting contraction are: Primary Metals."
    )
    report = parse_ism_html(html, kind="manufacturing", source_url="https://ism.test/release")
    assert [row.industry for row in report.contracting] == ["wood products", "chemical products"]
    assert report.pmi == 54.6


def test_ism_workflow_healthy_no_setup(tmp_path):
    report = ISMReport("manufacturing", "August 2026", 54.6, source_url="https://ism.test")
    result = IsmWorkflow(store=ResearchStore(tmp_path)).run(
        now=NOW,
        reports={"manufacturing": report, "services": ISMReport("services", "August 2026", 55.4)},
        napm={"reference_month": "2026-08", "value": 54.6},
    )
    assert_research_result(result)
    assert result.operational.status is OperationalStatus.PARTIAL
    assert result.payload["reports"]["manufacturing"]["headline_status"] == "HEADLINE_VALID"
    assert result.payload["reports"]["manufacturing"]["industry_rankings_status"] == "UNAVAILABLE"
    assert result.status is ResearchStatus.NO_SETUP
    assert result.payload["nmfbai_substituted_for_services_composite"] is False


def test_latest_roundup_url_picks_kind():
    sitemap = """
    <url><loc>https://www.ismworld.org/blog/2026/ism-pmi-reports-roundup-august-2026-manufacturing/</loc></url>
    <url><loc>https://www.ismworld.org/blog/2026/ism-pmi-reports-roundup-august-2026-services/</loc></url>
    """
    assert latest_roundup_url(sitemap, "services").endswith("-services/")


def test_fetch_ism_report_follows_roundup(monkeypatch):
    roundup = "https://www.ismworld.org/blog/2026/ism-pmi-reports-roundup-august-2026-manufacturing/"
    release = "https://www.prnewswire.com/news-releases/manufacturing-pmi-at-54-6-august-2026-report.html"
    pages = {
        "https://www.ismworld.org/sitemap.xml": f"<url><loc>{roundup}</loc></url>",
        roundup: f'<h1>August Manufacturing</h1><a href="{release}">release</a>',
        release: (
            "<h1>August 2026 Manufacturing</h1>Manufacturing PMI registered 54.6 percent. "
            "The industries reporting growth are: Primary Metals."
        ),
    }

    class _Response:
        def __init__(self, text):
            self.text = text

        def raise_for_status(self):
            return None

    class _Client:
        def get(self, url):
            return _Response(pages[url])

        def close(self):
            raise AssertionError("injected client must not be closed")

    report = fetch_ism_report("manufacturing", http=_Client())
    assert report.pmi == 54.6
    assert report.source_url == release
