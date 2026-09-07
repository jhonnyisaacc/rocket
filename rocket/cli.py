"""JSON-default CLI. Presentation, Discord, and scheduling belong to adapters."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import orjson
import typer

from rocket.config import rocket_home
from rocket.models import ResearchResult, exit_code
from rocket.store import ResearchStore

app = typer.Typer(add_completion=False, no_args_is_help=True, help="Rocket research engine")
watch_app = typer.Typer(help="Deterministic price watches")
portfolio_app = typer.Typer(help="Caller-owned portfolio review")
crypto_app = typer.Typer(help="Crypto futures top-100 research")
app.add_typer(watch_app, name="watch")
app.add_typer(portfolio_app, name="portfolio")
app.add_typer(crypto_app, name="crypto")


def _emit(payload: dict, *, human: bool, result: ResearchResult | None = None) -> None:
    if human and result is not None:
        typer.echo(result.to_markdown())
        return
    typer.echo(orjson.dumps(payload, option=orjson.OPT_INDENT_2).decode())


def emit_result(result: ResearchResult, *, human: bool) -> None:
    _emit(result.to_dict(), human=human, result=result)
    raise typer.Exit(exit_code(result))


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
    from rocket.workflows.cava import CAVA_RSS_URL, CavaWorkflow

    store = ResearchStore(state_dir or rocket_home())
    workflow = CavaWorkflow(store=store)
    try:
        rss_xml = rss_file.read_text(encoding="utf-8") if rss_file else httpx.get(CAVA_RSS_URL, timeout=20.0).text
        result = workflow.run(rss_xml=rss_xml, transcript_provider=SupadataTranscriptProvider())
    except httpx.HTTPError as exc:
        result = workflow.unavailable(f"Cava RSS unavailable: {exc}")
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
    rows = load_watches(watches)
    prices = None
    if prices_file is not None:
        payload = json.loads(prices_file.read_text(encoding="utf-8"))
        prices = payload.get("prices", payload) if isinstance(payload, dict) else {}
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
    book = load_portfolio_state(state)
    evidence = json.loads(evidence_file.read_text(encoding="utf-8")) if evidence_file else {}
    emit_result(
        PortfolioWorkflow(store=store, inventory=SolanaOndoInventory() if refresh_inventory else None).run(
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


if __name__ == "__main__":
    app()
