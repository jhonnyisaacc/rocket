"""Closing support and optional ATR from the same Yahoo daily chart response."""

import math
from datetime import UTC, datetime
from itertools import pairwise

from rocket.providers.shorts import _chart_result


def equity_history(symbol, http):
    result = _chart_result(symbol, http)
    quote = result['indicators']['quote'][0]
    closes = [float(v) for v in quote['close'] if v is not None]
    observed = datetime.fromtimestamp(result['meta']['regularMarketTime'], UTC).isoformat()
    atr = prior_atr_14(quote)
    return closes, observed, atr


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
