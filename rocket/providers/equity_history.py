"""Closing support and optional ATR from the same Yahoo daily chart response."""

import math
from datetime import UTC, datetime, timedelta
from itertools import pairwise

from rocket.clock import NY, latest_completed_session, session_close, session_day
from rocket.providers.shorts import _chart_result


def equity_history(symbol, http, *, now=None, include_daily_basis=False):
    result = _chart_result(symbol, http)
    quote = result['indicators']['quote'][0]
    closes = [float(v) for v in quote['close'] if v is not None]
    observed = datetime.fromtimestamp(result['meta']['regularMarketTime'], UTC).isoformat()
    atr = prior_atr_14(quote)
    if include_daily_basis:
        return closes, observed, atr, completed_daily_basis(result, now or datetime.now(UTC))
    return closes, observed, atr


def completed_daily_basis(result, now):
    """Exclude partial/future sessions; support precedes the assessed daily close.

    Keep the shared live technical fields intact. ISM uses this separate snapshot
    to avoid intraday changes to its close, support, ATR and decision threshold.
    """
    try:
        quote = result['indicators']['quote'][0]
        stamps = result['timestamp']
        closes = quote['close']
        if len(stamps) != len(closes):
            return {}
        days = [datetime.fromtimestamp(stamp, UTC).astimezone(NY).date() for stamp in stamps]
        if days != sorted(set(days)):
            return {}
        completed = latest_completed_session(now)
        indices = [i for i, day in enumerate(days) if session_day(day) and day <= completed]
        if len(indices) < 21 or days[indices[-1]] != completed:
            return {}
        required, day = [], completed
        while len(required) < 21:
            if session_day(day):
                required.append(day)
            day -= timedelta(days=1)
        if [days[i] for i in indices[-21:]] != required[::-1]:
            return {}
        selected = [float(closes[i]) for i in indices[-21:]]
        if not all(math.isfinite(v) and v > 0 for v in selected):
            return {}
        # prior_atr_14 excludes its final bar: here that is the assessed close.
        # Align the subset without removing missing OHLC from prior sessions.
        ohlc = {k: [quote[k][i] for i in indices] for k in ('high', 'low', 'close')
                if isinstance(quote.get(k), list) and len(quote[k]) == len(stamps)}
        return {'latest_close': selected[-1], 'latest_close_at': session_close(completed).isoformat(),
                'low_20': min(selected[:-1]), 'average_20': sum(selected[-20:]) / 20,
                'atr_14': prior_atr_14(ohlc), 'source': 'Yahoo Finance chart API',
                'session': completed.isoformat(),
                'support_basis': '20 completed daily closes preceding assessed close'}
    except (ValueError, TypeError, KeyError, IndexError, OverflowError):
        return {}


def prior_atr_14(quote):
    """Simple 14-bar ATR, excluding the latest (possibly partial) daily bar.

    Require aligned finite OHLC bars; never filter missing highs/lows and bridge
    gaps. A missing ATR does not discard otherwise usable closing history.
    """
    arrays = [quote.get(k, []) for k in ('high', 'low', 'close')]
    if any(not isinstance(a, (list, tuple)) for a in arrays):
        return None
    if len({len(a) for a in arrays}) != 1 or len(arrays[0]) < 16:
        return None
    try:
        bars = [tuple(float(v) for v in bar) for bar in list(zip(*arrays))[-16:-1]]
        if any(not all(math.isfinite(v) and v > 0 for v in bar)
               or not bar[1] <= bar[2] <= bar[0] for bar in bars):
            return None
        ranges = [max(high - low, abs(high - previous[2]), abs(low - previous[2]))
                  for previous, (high, low, close) in pairwise(bars)]
        value = sum(ranges) / 14
        return value if value > 0 else None
    except (TypeError, ValueError, OverflowError):
        return None
