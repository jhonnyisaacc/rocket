from typer.testing import CliRunner

from rocket.cli import app
from rocket.models import OperationalStatus, ResearchStatus, exit_code
from rocket.workflows.fixture import FixtureWorkflow


def test_status_cli_json_default(tmp_path, monkeypatch):
    monkeypatch.setenv("ROCKET_HOME", str(tmp_path))
    runner = CliRunner()
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "rocket.status.v1" in result.stdout
    assert "discord" not in result.stdout.lower()


def test_exit_code_zero_on_healthy_no_setup(now):
    result = FixtureWorkflow().scan(
        decision_time=now,
        available_at=now,
        operational=OperationalStatus.HEALTHY,
        research=ResearchStatus.NO_SETUP,
    )
    assert exit_code(result) == 0


def test_exit_code_two_on_unavailable(now):
    result = FixtureWorkflow().scan(
        decision_time=now,
        available_at=now,
        operational=OperationalStatus.UNAVAILABLE,
        research=ResearchStatus.INSUFFICIENT_EVIDENCE,
        warnings=("provider down",),
    )
    assert exit_code(result) == 2


def test_invalid_watch_json_is_structured_diagnostic(tmp_path):
    import json

    from typer.testing import CliRunner

    from rocket.cli import app
    path = tmp_path / 'watches.json'
    path.write_text('{broken')
    r = CliRunner().invoke(app, ['watch', 'check', '--watches', str(path), '--state-dir', str(tmp_path / 'store')])
    assert r.exit_code != 0
    data = json.loads(r.stdout)
    assert data['presentation']['diagnostic_only']
    assert data['reasons'][0]['code'] == 'INVALID_INPUT'
