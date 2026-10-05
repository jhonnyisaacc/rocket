"""Governance CLI: no experiment fitting, market acquisition or execution."""

import json
from pathlib import Path

import typer

from rocket.research.governance import GateError, disposition, next_item, score, verify_repository

app = typer.Typer(help="Frozen research governance; no trading authority")


@app.command("verify")
def verify(base: str | None = typer.Option(None, "--base")) -> None:
    """Verify current hashes and immutable base-branch evidence."""
    try:
        result = verify_repository(Path.cwd(), base)
    except (GateError, OSError, KeyError, ValueError) as exc:
        typer.echo(json.dumps({"status": "BLOCKED", "reason": str(exc)}))
        raise typer.Exit(2) from exc
    typer.echo(json.dumps(result))


@app.command("score")
def official_score(experiment_id: str) -> None:
    """Run only an admitted frozen scorer, recording even rejected preflight attempts."""
    result = score(Path.cwd(), experiment_id)
    typer.echo(json.dumps(result))
    raise typer.Exit({"PASS": 0, "FAIL": 1, "BLOCKED": 2}[result["result"]])


@app.command("next")
def select_next(snapshot: Path = typer.Option(..., exists=True, readable=True)) -> None:
    """Select admitted Ready work from a timestamped, independently verified Project snapshot."""
    try:
        data = json.loads(snapshot.read_text())
        if not data.get("audited_at") or not data.get("project_url"):
            raise GateError("Timestamped Project snapshot required")
        result = next_item(data["items"])
    except (GateError, KeyError, OSError, ValueError) as exc:
        typer.echo(json.dumps({"status": "BLOCKED", "reason": str(exc)}))
        raise typer.Exit(2) from exc
    typer.echo(json.dumps({"selected": result}))


@app.command("disposition")
def gate_disposition(
    receipt: Path = typer.Option(..., exists=True, readable=True),
    audit: Path = typer.Option(..., exists=True, readable=True),
) -> None:
    """Emit the deterministic downstream decision for an independently audited code gate."""
    try:
        result = disposition(Path.cwd(), json.loads(receipt.read_text()), audit=json.loads(audit.read_text()))
    except (GateError, KeyError, OSError, ValueError) as exc:
        typer.echo(json.dumps({"status": "BLOCKED", "reason": str(exc)}))
        raise typer.Exit(2) from exc
    typer.echo(json.dumps(result))
