"""Bounded current research for canonical equity candidates."""

from rocket.providers.fundamentals import fundamentals_row
from rocket.providers.portfolio import acquire_position_evidence


def acquire_equity_context(tickers, *, state_dir=None):
    tickers = list(dict.fromkeys(tickers))[:30]
    rows = acquire_position_evidence(tickers, include_news=False)
    from rocket.providers.edgar import SECEDGAR
    from rocket.providers.fmp import FMPClient

    fmp, edgar = FMPClient(), SECEDGAR(state_dir=state_dir)
    for ticker in tickers:
        rows[ticker]["fundamentals"] = dict(fundamentals_row(ticker, fmp=fmp, edgar=edgar,
                                   price=rows[ticker].get("market_state", {}).get("current_price")))
        if rows[ticker]["fundamentals"].get("eps_growth") is not None and rows[ticker]["fundamentals"].get("pe_ttm") is not None:
            from rocket.providers.news import company_news_context
            rows[ticker].update(company_news_context(ticker))
    return rows
