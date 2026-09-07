from datetime import UTC, datetime, timedelta

from rocket.models import OperationalStatus
from rocket.providers.cftc import (
    bias_from_speculator_pct,
    cot_context_from_result,
    parse_cftc_report,
    regime_from_markets,
)
from rocket.providers.protocols import ProviderResult

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)

REPORT = """
<html><body><pre>
BITCOIN - CHICAGO MERCANTILE EXCHANGE                                           Code-133741
FUTURES ONLY POSITIONS AS OF May 27, 2025
All  :    40,000     5,000    15,000     2,000     8,000     7,000
CHANGES IN COMMITMENTS FROM LAST WEEK
            100        10       -20         0         5         4
ETHER CASH SETTLED - CHICAGO MERCANTILE EXCHANGE                                Code-146021
FUTURES ONLY POSITIONS AS OF May 27, 2025
All  :    20,000     2,000     8,000     1,000     4,000     3,000
CHANGES IN COMMITMENTS FROM LAST WEEK
             50         5       -10         0         2         1
</pre></body></html>
"""


def test_parse_cftc_btc_eth_and_contrarian_bias():
    markets = parse_cftc_report(REPORT)
    assert set(markets) == {"BTC", "ETH"}
    assert markets["BTC"]["bias"] == "bullish"
    assert markets["ETH"]["bias"] == "bullish"
    assert regime_from_markets(markets) == "bullish"


def test_spec_long_is_bearish():
    assert bias_from_speculator_pct(6.0) == "bearish"
    assert bias_from_speculator_pct(-3.0) == "neutral"


def test_disagreement_is_neutral_regime():
    assert regime_from_markets({"BTC": {"bias": "bullish"}, "ETH": {"bias": "bearish"}}) == "neutral"


def test_stale_report_does_not_set_regime():
    result = ProviderResult(
        status=OperationalStatus.HEALTHY,
        records=(
            {"asset": "BTC", "bias": "bullish", "as_of_date": (NOW - timedelta(days=30)).date().isoformat()},
            {"asset": "ETH", "bias": "bullish", "as_of_date": (NOW - timedelta(days=30)).date().isoformat()},
        ),
        source="cftc_direct",
    )
    context = cot_context_from_result(result, now=NOW)
    assert context["status"] == "STALE"
    assert context["regime"] == "unknown"
