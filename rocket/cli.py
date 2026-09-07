"""JSON-default CLI. Presentation, Discord, and scheduling belong to adapters."""

from __future__ import annotations

from pathlib import Path

import orjson
import typer

from rocket.config import rocket_home
from rocket.models import ResearchResult, exit_code
from rocket.store import ResearchStore

app = typer.Typer(add_completion=False, no_args_is_help=True, help="Rocket research engine")


def _emit(payload: dict, *, human: bool, result: ResearchResult | None = None) -> None:
    if human and result is not None:
        typer.echo(result.to_markdown())
        return
    typer.echo(orjson.dumps(payload, option=orjson.OPT_INDENT_2).decode())


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
    runs = store.list_latest()
    payload = {
        "schema": "rocket.status.v1",
        "home": str(store.root),
        "runs": runs,
        "safety_boundary": "READ_ONLY_RESEARCH_ONLY_HUMAN_GATED",
    }
    _emit(payload, human=human)
    raise typer.Exit(0)


def emit_result(result: ResearchResult, *, human: bool) -> None:
    store = ResearchStore()
    store.save_result(result)
    _emit(result.to_dict(), human=human, result=result)
    raise typer.Exit(exit_code(result))


if __name__ == "__main__":
    app()
