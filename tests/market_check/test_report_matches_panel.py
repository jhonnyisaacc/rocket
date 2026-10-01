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
    # v6 trims TSLA into early-2025 strength, rebuys it in the April
    # redeploy (high-beta sleeve), and then never trims it again: the
    # strength gates never pass during its grinding 2025-2026 decline, so
    # the simulated book still holds TSLA when the real book sells. The
    # logged sale is honestly unmatched — pin that, not a false agreement.
    assert logged["recognized"] is False
    assert logged["status"] == "unmatched"
    tsla = [t for t in result["portfolio"]["trades"] if t["ticker"] == "TSLA"]
    buys = [t for t in tsla if t["side"] == "buy" and t["date"] >= "2025-04-01"]
    sells = [t for t in tsla if t["side"] == "sell" and t["date"] >= "2025-04-01"]
    assert buys and not sells
    assert result["markdown"] == report_path.read_text(encoding="utf-8")
