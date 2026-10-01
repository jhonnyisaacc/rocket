"""Daily check JSON contract."""

import json
from datetime import date, timedelta

from typer.testing import CliRunner

from rocket.cli import app
from rocket.market_check.config import load_config
from rocket.market_check.panel import SeriesPanel
from rocket.market_check.workflow import MarketCheckWorkflow
from rocket.models import ResearchStatus
from tests.harness import assert_research_result, is_registered

CFG = load_config()


def _panel() -> SeriesPanel:
    days = []
    cursor = date(2025, 3, 3)
    while len(days) < 80:
        if cursor.weekday() < 5:
            days.append(cursor)
        cursor += timedelta(days=1)
    series = {}
    levels = {
        "yield_2y": 3.4, "yield_10y": 3.5, "yield_30y": 4.0, "fed_funds": 3.5,
        "wti": 70.0, "vix": 14.0, "hy_oas": 3.2, "tlt": 90.0, "dollar": 103.0,
        "gold": 2400.0, "btc": 60000.0, "dvol": 48.0, "spy": 500.0, "qqq": 430.0,
    }
    for name in (*levels, *CFG.portfolio.universe, *CFG.phillip.names):
        series[name] = {day.isoformat(): levels.get(name, 100.0) for day in days}
    return SeriesPanel(series, {"sources": {"yield_10y": "fixture"}})


def test_market_check_is_registered():
    assert is_registered("market_check")
    assert is_registered("market_check.backtest")


def test_run_is_a_research_result_and_replay_has_no_live_flag(tmp_path):
    panel = _panel()
    day = panel.dates("spy")[-1]
    result = MarketCheckWorkflow(CFG, store=None).run(panel, asof=day)
    assert_research_result(result)
    assert result.payload["execution_enabled"] is False
    assert result.payload["regime"] in {"risk-on", "neutral", "caution", "risk-off"}
    assert result.payload["perps"]["direction"] in {"long", "flat", "short"}
    assert result.payload["porto"]["action"] in {"add", "hold", "trim"}
    assert result.payload["phillip"]["band_stance"] in {"keep", "raise", "lower"}
    assert "changed" in result.payload
    assert result.payload.get("loaded_live_context") is not True
    path = tmp_path / "panel.json"
    panel.write(path)
    runner = CliRunner()
    response = runner.invoke(app, ["market-check", "run", "--panel", str(path), "--as-of", day.isoformat(), "--state-dir", str(tmp_path / "state")])
    assert response.exit_code == 0, response.stdout
    body = json.loads(response.stdout)
    assert body["payload"]["execution_enabled"] is False
    assert body["workflow"] == "market_check"
    assert body["status"] in {ResearchStatus.NO_SETUP.value, ResearchStatus.INSUFFICIENT_EVIDENCE.value}
