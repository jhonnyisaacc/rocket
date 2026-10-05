"""Direction control commands for the existing Rocket JSON CLI."""

from pathlib import Path

import typer

from rocket.research.governance import DEFAULT_STATE, packet, read, record_result, review, start

app = typer.Typer(help="Research direction admission; never trading permission")


def emit(value: dict) -> None:
    import json

    typer.echo(json.dumps(value, indent=2))
    if value.get("decision") == "WORKFLOW_BLOCK":
        raise typer.Exit(2)


def fail(exc: Exception) -> None:
    emit(
        {
            "decision": "WORKFLOW_BLOCK",
            "reasons": ["INVALID_GOVERNANCE_INPUT"],
            "detail": str(exc),
            "execution_enabled": False,
        }
    )


@app.command("review")
def check(
    checkpoint: Path = typer.Option(..., exists=True),
    state: Path = typer.Option(DEFAULT_STATE, exists=True),
    independent_review: Path | None = typer.Option(None, exists=True),
    packet_out: Path | None = typer.Option(None),
) -> None:
    """Export bounded reviewer input and evaluate a supplied independent verdict."""
    try:
        s, c = read(state), read(checkpoint)
        if packet_out:
            from rocket.research.governance import save

            save(packet_out, packet(s, c))
        verdict = review(s, c, read(independent_review) if independent_review else None)
    except (ValueError, TypeError, KeyError, OSError) as exc:
        fail(exc)
        return
    emit(verdict)


@app.command("start")
def admit(
    experiment: str,
    checkpoint: Path = typer.Option(..., exists=True),
    independent_review: Path = typer.Option(..., exists=True),
    state: Path = typer.Option(DEFAULT_STATE, exists=True),
) -> None:
    """Consume one direction budget and persist reviewed admission before work."""
    try:
        c = read(checkpoint)
        if c.get("experiment") != experiment:
            raise ValueError("experiment/checkpoint mismatch")
        verdict = start(state, c, read(independent_review))
    except (ValueError, TypeError, KeyError, OSError) as exc:
        fail(exc)
        return
    emit(verdict)


@app.command("record-result")
def resolve(
    result: Path = typer.Option(..., exists=True),
    state: Path = typer.Option(DEFAULT_STATE, exists=True),
) -> None:
    """Accumulate cohort evidence and close automatic continuation after a result."""
    try:
        verdict = record_result(state, read(result))
    except (ValueError, TypeError, KeyError, OSError) as exc:
        fail(exc)
        return
    emit(verdict)


@app.command("step")
def step(
    experiment: str,
    action: str = typer.Option(..., "--action"),
    state: Path = typer.Option(DEFAULT_STATE, exists=True),
) -> None:
    """Validate an internal step under the same frozen admission, without new budget."""
    from rocket.research.governance import require_experiment_step

    try:
        verdict = require_experiment_step(experiment, action, state)
    except (ValueError, TypeError, KeyError, OSError) as exc:
        fail(exc)
        return
    emit(verdict)
