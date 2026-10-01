"""The committed report is the backtest of the committed panel, not a hand edit."""

from rocket.config import PACKAGE_ROOT
from rocket.market_check.backtest import run_backtest
from rocket.market_check.config import load_config
from rocket.market_check.panel import SeriesPanel


def test_committed_report_matches_the_panel():
    panel_path = PACKAGE_ROOT / "data" / "market_check" / "panel.json"
    report_path = PACKAGE_ROOT / "docs" / "market_check" / "BACKTEST.md"
    panel = SeriesPanel.load(panel_path)
    result = run_backtest(panel, load_config())
    assert result["execution_enabled"] is False
    logged = next(row for row in result["trade_log"] if row["ticker"] == "TSLA")
    assert logged["recognized"] is True
    assert logged["status"] == "already_exited"
    assert result["markdown"] == report_path.read_text(encoding="utf-8")
