"""JSON-default CLI. Presentation, Discord, and scheduling belong to adapters."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import orjson
import typer

from rocket.config import rocket_home
from rocket.models import OperationalStatus, ResearchResult, exit_code
from rocket.store import ResearchStore

app = typer.Typer(add_completion=False, no_args_is_help=True, help="Rocket research engine")
watch_app = typer.Typer(help="Deterministic price watches")
portfolio_app = typer.Typer(help="Caller-owned portfolio review")
crypto_app = typer.Typer(help="Crypto futures top-100 research")
options_app = typer.Typer(help="Options research primitives; never auto-validated")
memecoin_app = typer.Typer(help="Memecoin primitives; no validated edge")
app.add_typer(watch_app, name="watch")
app.add_typer(portfolio_app, name="portfolio")
app.add_typer(crypto_app, name="crypto")
app.add_typer(options_app, name="options")
app.add_typer(memecoin_app, name="memecoin")


def _emit(payload: dict, *, human: bool, result: ResearchResult | None = None) -> None:
    if human and result is not None:
        typer.echo(result.to_markdown())
        return
    typer.echo(orjson.dumps(payload, option=orjson.OPT_INDENT_2).decode())


def emit_result(result: ResearchResult, *, human: bool) -> None:
    _emit(result.to_dict(), human=human, result=result)
    raise typer.Exit(exit_code(result))


def configuration_failure(workflow, store, *, human):
    from datetime import UTC, datetime

    from rocket.models import OperationalReport, ReasonCode, ResearchReason, ResearchStatus
    now = datetime.now(UTC)
    result = ResearchResult(workflow=workflow, status=ResearchStatus.ERROR,
                            operational=OperationalReport(OperationalStatus.ERROR), decision_time=now,
                            started_at=now, warnings=("Caller input or configuration could not be parsed; operator correction is required.",),
                            reasons=(ResearchReason(ReasonCode.INVALID_INPUT, ("valid caller input/configuration file",)),),
                            payload={"execution_enabled": False})
    store.save_result(result)
    emit_result(result, human=human)


@app.callback()
def _root() -> None:
    """Rocket: read-only research. JSON on stdout."""


@app.command("status")
def status(
    state_dir: Path | None = typer.Option(None, "--state-dir", help="Override ROCKET_HOME."),
    human: bool = typer.Option(False, "--human", help="Markdown instead of JSON."),
    json_out: bool = typer.Option(True, "--json/--no-json", help="JSON (default)."),
) -> None:
    """Latest run per workflow: operational vs research status."""
    del json_out
    store = ResearchStore(state_dir or rocket_home())
    payload = {
        "schema": "rocket.status.v1",
        "home": str(store.root),
        "runs": store.list_latest(),
        "safety_boundary": "READ_ONLY_RESEARCH_ONLY_HUMAN_GATED",
    }
    _emit(payload, human=human)
    raise typer.Exit(0)


@app.command("macro")
def macro(
    state_dir: Path | None = typer.Option(None, "--state-dir"),
    human: bool = typer.Option(False, "--human"),
    json_out: bool = typer.Option(True, "--json/--no-json"),
) -> None:
    """Canonical US rates and liquidity. Independent of Cava."""
    del json_out
    from rocket.workflows.macro import MacroWorkflow

    store = ResearchStore(state_dir or rocket_home())
    emit_result(MacroWorkflow(store=store).run(), human=human)


@app.command("cava")
def cava(
    rss_file: Path | None = typer.Option(None, "--rss-file", exists=True, readable=True),
    state_dir: Path | None = typer.Option(None, "--state-dir"),
    human: bool = typer.Option(False, "--human"),
    json_out: bool = typer.Option(True, "--json/--no-json"),
) -> None:
    """Cava overlay: RSS → transcript → claims → corroboration."""
    del json_out
    from rocket.providers.supadata import SupadataTranscriptProvider
    from rocket.workflows.cava import CavaWorkflow

    store = ResearchStore(state_dir or rocket_home())
    workflow = CavaWorkflow(store=store)
    try:
        if rss_file:
            rss_xml = rss_file.read_text(encoding="utf-8")
            result = workflow.run(rss_xml=rss_xml, transcript_provider=SupadataTranscriptProvider())
        else:
            from rocket.providers.cava_discovery import discover_videos
            discovery = discover_videos()
            if discovery.result:
                result = workflow.run(discovery=discovery, transcript_provider=SupadataTranscriptProvider())
            else:
                result = workflow.unavailable("Video discovery exhausted: " + ", ".join(f"{a.name}:{a.failure_kind}" for a in discovery.attempts), providers=discovery.attempts)
    except httpx.HTTPError as exc:
        result = workflow.unavailable(f"Cava RSS unavailable: {type(exc).__name__}")
    emit_result(result, human=human)


@watch_app.command("check")
def watch_check(
    watches: Path = typer.Option(..., "--watches", exists=True, readable=True),
    prices_file: Path | None = typer.Option(None, "--prices-file", exists=True, readable=True),
    state_dir: Path | None = typer.Option(None, "--state-dir"),
    human: bool = typer.Option(False, "--human"),
    json_out: bool = typer.Option(True, "--json/--no-json"),
) -> None:
    """Deterministic ABOVE/BELOW/CROSS/ZONE checks. No model."""
    del json_out
    from rocket.workflows.watch import WatchWorkflow, load_watches

    store = ResearchStore(state_dir or rocket_home())
    try:
        rows = load_watches(watches)
        prices = None
        if prices_file is not None:
            payload = json.loads(prices_file.read_text(encoding="utf-8"))
            prices = payload.get("prices", payload) if isinstance(payload, dict) else None
            if not isinstance(prices, dict):
                raise ValueError("prices must be a mapping")
    except (ValueError, TypeError, OSError):
        configuration_failure("watch.check", store, human=human)
    emit_result(WatchWorkflow(store=store).run(rows, prices=prices), human=human)


@portfolio_app.command("review")
def portfolio_review(
    state: Path = typer.Option(..., "--state", exists=True, readable=True),
    evidence_file: Path | None = typer.Option(None, "--evidence-file", exists=True, readable=True),
    refresh_inventory: bool = typer.Option(False, "--refresh-inventory"),
    state_dir: Path | None = typer.Option(None, "--state-dir"),
    human: bool = typer.Option(False, "--human"),
    json_out: bool = typer.Option(True, "--json/--no-json"),
) -> None:
    """Per-position review. Wallet inventory is read-only and optional."""
    del json_out
    from rocket.providers.inventory import SolanaOndoInventory
    from rocket.workflows.portfolio import PortfolioWorkflow, load_portfolio_state

    store = ResearchStore(state_dir or rocket_home())
    try:
        book = load_portfolio_state(state)
        evidence = json.loads(evidence_file.read_text(encoding="utf-8")) if evidence_file else None
        if evidence is not None and (not isinstance(evidence, dict) or any(not isinstance(v, dict) for v in evidence.values())):
            raise ValueError("position evidence must be a mapping")
        inventory = SolanaOndoInventory() if refresh_inventory else None
    except (ValueError, TypeError, OSError):
        configuration_failure("portfolio.review", store, human=human)
    emit_result(
        PortfolioWorkflow(store=store, inventory=inventory).run(
            book,
            evidence,
            refresh_inventory=refresh_inventory,
        ),
        human=human,
    )


@crypto_app.command("scan")
def crypto_scan(
    fixture: Path | None = typer.Option(None, "--fixture", exists=True, readable=True),
    cot_regime: str = typer.Option("unknown", "--cot-regime"),
    state_dir: Path | None = typer.Option(None, "--state-dir"),
    human: bool = typer.Option(False, "--human"),
    json_out: bool = typer.Option(True, "--json/--no-json"),
) -> None:
    """Top-100 market-cap universe plus liquid-perp funnel. Replay with --fixture."""
    del json_out
    from rocket.workflows.crypto import CryptoWorkflow

    store = ResearchStore(state_dir or rocket_home())
    workflow = CryptoWorkflow(store=store)
    if fixture:
        result = workflow.scan_from_fixture(fixture, cot_regime=cot_regime)
    else:
        result = workflow.scan_live(cot_regime=cot_regime)
    emit_result(result, human=human)


@crypto_app.command("evaluate")
def crypto_evaluate(
    outcomes: Path = typer.Option(..., "--outcomes", exists=True, readable=True),
    scan_file: Path | None = typer.Option(None, "--scan-file", exists=True, readable=True),
    state_dir: Path | None = typer.Option(None, "--state-dir"),
    human: bool = typer.Option(False, "--human"),
    json_out: bool = typer.Option(True, "--json/--no-json"),
) -> None:
    del json_out
    from rocket.models import ResearchResult as Result
    from rocket.workflows.crypto import CryptoWorkflow

    store = ResearchStore(state_dir or rocket_home())
    scan = Result.from_dict(json.loads(scan_file.read_text(encoding="utf-8"))) if scan_file else store.load_result("crypto.scan")
    if scan is None:
        raise typer.BadParameter("no scan result; pass --scan-file or run crypto scan")
    raw = json.loads(outcomes.read_text(encoding="utf-8"))
    rows = raw.get("outcomes", raw) if isinstance(raw, dict) else raw
    emit_result(CryptoWorkflow(store=store).evaluate(scan, rows), human=human)


@crypto_app.command("missed")
def crypto_missed(
    outcomes: Path = typer.Option(..., "--outcomes", exists=True, readable=True),
    scan_file: Path | None = typer.Option(None, "--scan-file", exists=True, readable=True),
    state_dir: Path | None = typer.Option(None, "--state-dir"),
    human: bool = typer.Option(False, "--human"),
    json_out: bool = typer.Option(True, "--json/--no-json"),
) -> None:
    del json_out
    from rocket.models import ResearchResult as Result
    from rocket.workflows.crypto import CryptoWorkflow

    store = ResearchStore(state_dir or rocket_home())
    scan = Result.from_dict(json.loads(scan_file.read_text(encoding="utf-8"))) if scan_file else store.load_result("crypto.scan")
    if scan is None:
        raise typer.BadParameter("no scan result; pass --scan-file or run crypto scan")
    raw = json.loads(outcomes.read_text(encoding="utf-8"))
    rows = raw.get("outcomes", raw) if isinstance(raw, dict) else raw
    emit_result(CryptoWorkflow(store=store).missed(scan, rows), human=human)


@app.command("ism")
def ism(
    manufacturing_html: Path | None = typer.Option(None, "--manufacturing-html", exists=True, readable=True),
    services_html: Path | None = typer.Option(None, "--services-html", exists=True, readable=True),
    state_dir: Path | None = typer.Option(None, "--state-dir"),
    human: bool = typer.Option(False, "--human"),
    json_out: bool = typer.Option(True, "--json/--no-json"),
) -> None:
    """Manufacturing and services ISM. Headline stays separate from rankings."""
    del json_out
    from rocket.providers.ism import fetch_ism_report, parse_ism_html
    from rocket.workflows.ism import IsmWorkflow

    reports = {}
    provider_failures = {}
    if manufacturing_html:
        reports["manufacturing"] = parse_ism_html(
            manufacturing_html.read_text(encoding="utf-8"),
            kind="manufacturing",
            source_url=str(manufacturing_html),
        )
    if services_html:
        reports["services"] = parse_ism_html(
            services_html.read_text(encoding="utf-8"),
            kind="services",
            source_url=str(services_html),
        )
    if not reports:
        for kind in ("manufacturing", "services"):
            try:
                reports[kind] = fetch_ism_report(kind)
            except (httpx.HTTPError, TypeError, ValueError) as exc:
                provider_failures[kind] = type(exc).__name__
                continue
    store = ResearchStore(state_dir or rocket_home())
    emit_result(IsmWorkflow(store=store).run(reports=reports or None, provider_failures=provider_failures,
                                           research_companies=not (manufacturing_html or services_html)), human=human)


@app.command("disclosures")
def disclosures(
    person: list[str] | None = typer.Option(None, "--person", help="Exact person name; repeat to select several. Defaults to Nancy Pelosi and Donald Trump."),
    state_dir: Path | None = typer.Option(None, "--state-dir"),
    human: bool = typer.Option(False, "--human"),
    json_out: bool = typer.Option(True, "--json/--no-json"),
) -> None:
    """Official House + OGE filings. Healthy no-new is not a provider failure."""
    del json_out
    from rocket.providers.disclosures import (
        OfficialHouseDisclosureProvider,
        OfficialOGEExecutiveDisclosureProvider,
    )
    from rocket.workflows.disclosures import DisclosureWorkflow

    store = ResearchStore(state_dir or rocket_home())
    congress, executive, secondary = [], [], []
    subjects = person or ["Nancy Pelosi", "Donald Trump"]
    status = {}
    extra_warnings: list[str] = []
    from datetime import UTC, datetime

    from rocket.people import person_id
    from rocket.providers.dispatch import failure_kind
    from rocket.providers.fmp import FMPClient

    selected = {person_id(s) for s in subjects}
    if None in selected:
        status["person_filter"] = {"status": "UNAVAILABLE", "failure_kind": "UnsupportedPersonIdentity"}
    if "nancy_pelosi" in selected:
        for year in range(datetime.now(UTC).year, datetime.now(UTC).year - 3, -1):
            try:
                congress.extend(OfficialHouseDisclosureProvider(filing_year=year).fetch())
                status[f"congress:{year}"] = {"status": "OK"}
            except Exception as exc:
                status[f"congress:{year}"] = {"status": "UNAVAILABLE", "failure_kind": failure_kind(exc)}
    if "donald_trump" in selected:
        try:
            executive = OfficialOGEExecutiveDisclosureProvider().fetch()
            status["executive"] = {"status": "OK"}
        except Exception as exc:
            status["executive"] = {"status": "UNAVAILABLE", "failure_kind": failure_kind(exc)}
    if "donald_trump" in selected:
        status["trump_transaction_history"] = {"status": "UNAVAILABLE", "failure_kind": "UnsupportedCapability"}
    fmp = FMPClient()
    history = fmp.person_history() if "nancy_pelosi" in selected else None
    if history is not None:
        status["pelosi_secondary_history"] = {"status": "UNAVAILABLE" if history.status is OperationalStatus.UNAVAILABLE else "OK", "failure_kind": history.failure_kind}
    historical_records = list(history.records) if history else []
    from rocket.candidates import caller_references
    references, reference_coverage = caller_references()
    emit_result(
        DisclosureWorkflow(store=store).run(
            congress_records=congress,
            executive_records=executive,
            secondary_records=secondary,
            provider_status=status,
            warnings=extra_warnings,
            subjects=subjects,
            historical_records=historical_records,
            history_acquisition={
                "structured_provider": "fmp.house-trades-by-name" if history else None,
                "official_documents": "filing metadata only; no PDF/OCR ingestion",
                "trump_transaction_history": "not implemented",
            },
            portfolio_tickers=references["portfolio"], watch_tickers=references["watch"],
            cross_system_coverage=reference_coverage,
            research_opportunities=True,
        ),
        human=human,
    )


@app.command("shorts")
def shorts(
    input_file: Path | None = typer.Option(None, "--input-file", exists=True, readable=True),
    state_dir: Path | None = typer.Option(None, "--state-dir"),
    human: bool = typer.Option(False, "--human"),
    json_out: bool = typer.Option(True, "--json/--no-json"),
) -> None:
    """Autonomous multi-factor short scan. Macro alone cannot select."""
    del json_out
    from rocket.workflows.shorts import ShortsWorkflow

    store = ResearchStore(state_dir or rocket_home())
    if input_file:
        raw = json.loads(input_file.read_text(encoding="utf-8"))
        rows = raw.get("rows", raw) if isinstance(raw, dict) else raw
    else:
        emit_result(ShortsWorkflow(store=store).scan_live(), human=human)
        return
    emit_result(ShortsWorkflow(store=store).scan(rows), human=human)


@options_app.command("scan")
def options_scan(
    domain: str = typer.Option("crypto", "--domain"),
    input_file: Path = typer.Option(..., "--input-file", exists=True, readable=True),
    state_dir: Path | None = typer.Option(None, "--state-dir"),
    human: bool = typer.Option(False, "--human"),
    json_out: bool = typer.Option(True, "--json/--no-json"),
) -> None:
    del json_out
    from rocket.workflows.options import OptionsWorkflow

    raw = json.loads(input_file.read_text(encoding="utf-8"))
    rows = raw.get("rows", raw) if isinstance(raw, dict) else raw
    store = ResearchStore(state_dir or rocket_home())
    emit_result(OptionsWorkflow(store=store).scan(domain, rows), human=human)


@options_app.command("evaluate")
def options_evaluate(
    domain: str = typer.Option("crypto", "--domain"),
    outcomes: Path = typer.Option(..., "--outcomes", exists=True, readable=True),
    state_dir: Path | None = typer.Option(None, "--state-dir"),
    human: bool = typer.Option(False, "--human"),
    json_out: bool = typer.Option(True, "--json/--no-json"),
) -> None:
    del json_out
    from rocket.workflows.options import OptionsWorkflow

    raw = json.loads(outcomes.read_text(encoding="utf-8"))
    rows = raw.get("outcomes", raw) if isinstance(raw, dict) else raw
    store = ResearchStore(state_dir or rocket_home())
    emit_result(OptionsWorkflow(store=store).evaluate(domain, rows), human=human)


@memecoin_app.command("status")
def memecoin_status(
    state_dir: Path | None = typer.Option(None, "--state-dir"),
    human: bool = typer.Option(False, "--human"),
    json_out: bool = typer.Option(True, "--json/--no-json"),
) -> None:
    del json_out
    from rocket.workflows.memecoin import MemecoinWorkflow

    store = ResearchStore(state_dir or rocket_home())
    emit_result(MemecoinWorkflow(store=store).status(), human=human)


@memecoin_app.command("scan")
def memecoin_scan(
    input_file: Path = typer.Option(..., "--input", exists=True, readable=True),
    state_dir: Path | None = typer.Option(None, "--state-dir"),
    human: bool = typer.Option(False, "--human"),
    json_out: bool = typer.Option(True, "--json/--no-json"),
) -> None:
    del json_out
    from rocket.workflows.memecoin import MemecoinWorkflow

    raw = json.loads(input_file.read_text(encoding="utf-8"))
    rows = raw.get("rows", raw) if isinstance(raw, dict) else raw
    store = ResearchStore(state_dir or rocket_home())
    emit_result(MemecoinWorkflow(store=store).scan(rows), human=human)


@memecoin_app.command("collect")
def memecoin_collect(
    spool: Path = typer.Option(..., "--spool"),
    input_file: Path | None = typer.Option(None, "--input", exists=True, readable=True),
    state_dir: Path | None = typer.Option(None, "--state-dir"),
    human: bool = typer.Option(False, "--human"),
    json_out: bool = typer.Option(True, "--json/--no-json"),
) -> None:
    """Append raw frames to the spool. Not a strategy job and not a live websocket."""
    del json_out
    from rocket.capture.spool import RawCaptureSpool
    from rocket.workflows.memecoin import MemecoinWorkflow, frames_from_payload

    raw = json.loads(input_file.read_text(encoding="utf-8")) if input_file else []
    writer = RawCaptureSpool(spool, max_bytes=8 * 1024 * 1024 * 1024, reserve_bytes=1024 * 1024 * 1024)
    try:
        result = MemecoinWorkflow(store=ResearchStore(state_dir or rocket_home())).collect(
            writer,
            frames_from_payload(raw),
        )
    finally:
        writer.close()
    emit_result(result, human=human)


@memecoin_app.command("evaluate")
def memecoin_evaluate(
    outcomes: Path = typer.Option(..., "--outcomes", exists=True, readable=True),
    scan_file: Path | None = typer.Option(None, "--scan-file", exists=True, readable=True),
    state_dir: Path | None = typer.Option(None, "--state-dir"),
    human: bool = typer.Option(False, "--human"),
    json_out: bool = typer.Option(True, "--json/--no-json"),
) -> None:
    del json_out
    from rocket.models import ResearchResult as Result
    from rocket.workflows.memecoin import MemecoinWorkflow

    store = ResearchStore(state_dir or rocket_home())
    scan = Result.from_dict(json.loads(scan_file.read_text(encoding="utf-8"))) if scan_file else store.load_result("memecoin.scan")
    if scan is None:
        raise typer.BadParameter("no scan result; pass --scan-file or run memecoin scan")
    raw = json.loads(outcomes.read_text(encoding="utf-8"))
    rows = raw.get("outcomes", raw) if isinstance(raw, dict) else raw
    emit_result(MemecoinWorkflow(store=store).evaluate(scan, rows), human=human)


if __name__ == "__main__":
    app()
