"""Bounded current research for canonical equity candidates."""

from rocket.providers.fundamentals import fundamentals_row
from rocket.providers.portfolio import acquire_position_evidence


def acquire_equity_context(tickers):
    tickers = list(dict.fromkeys(tickers))[:30]
    rows = acquire_position_evidence(tickers, include_news=False)
    for ticker in tickers:
        rows[ticker]["fundamentals"] = dict(fundamentals_row(ticker))
        if rows[ticker]["fundamentals"].get("eps_growth") is not None and rows[ticker]["fundamentals"].get("pe_ttm") is not None:
            from rocket.providers.news import company_news_context
            rows[ticker].update(company_news_context(ticker))
    return rows
