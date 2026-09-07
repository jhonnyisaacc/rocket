from typer.testing import CliRunner

from rocket.cli import app


def test_help_lists_phase1_and_phase2_commands():
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for name in ("status", "macro", "cava", "watch", "portfolio", "crypto"):
        assert name in result.stdout
