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


LIVE_FORMAT = """
<html><body><pre>
BITCOIN - CHICAGO MERCANTILE EXCHANGE                                                                   Code-133741
Commitments of Traders - Futures Only, September 15, 2026
All  :    20,773:    16,744     14,276      2,901        107      2,764     19,752     19,941:     1,021        832
Percent of Open Interest Represented by Each Category of Trader
All  :     100.0:      80.6       68.7       14.0        0.5       13.3       95.1       96.0:       4.9        4.0
MICRO BITCOIN - CHICAGO MERCANTILE EXCHANGE                                                             Code-133742
ETHER CASH SETTLED - CHICAGO MERCANTILE EXCHANGE                                                        Code-146021
Commitments of Traders - Futures Only, September 15, 2026
All  :    28,413:    24,427     21,272      3,379         30      3,379     27,836     28,030:       577        383
Percent of Open Interest Represented by Each Category of Trader
All  :     100.0:      86.0       74.9       11.9        0.1       11.9       98.0       98.7:       2.0        1.3
MICRO ETHER - CHICAGO MERCANTILE EXCHANGE                                                               Code-146022
</pre></body></html>
"""


def test_live_report_layout_uses_positions_not_the_percent_row():
    markets = parse_cftc_report(LIVE_FORMAT)
    assert markets["BTC"]["open_interest"] == 20773
    assert markets["ETH"]["open_interest"] == 28413
    assert markets["BTC"]["as_of_date"] == "2026-09-15"
    assert regime_from_markets(markets) == "bearish"
    result = ProviderResult(
        status=OperationalStatus.HEALTHY,
        records=(markets["BTC"], markets["ETH"]),
        source="cftc_direct",
    )
    context = cot_context_from_result(result, now=datetime(2026, 9, 23, tzinfo=UTC))
    assert context["status"] == "OK"
    assert context["regime"] == "bearish"
    assert context["freshness_days"] == 8


def test_stale_direct_report_is_not_erased_when_openbb_fails():
    import httpx

    from rocket.providers.cftc import CFTC_FUTURES_URL, STALE_AFTER_DAYS, fetch_cot_context

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=REPORT)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    context = fetch_cot_context(now=datetime(2026, 9, 23, tzinfo=UTC), http=client)
    assert context["endpoint"] == CFTC_FUTURES_URL
    assert context["stale_after_days"] == STALE_AFTER_DAYS
    assert context["status"] == "STALE"
    assert context["regime"] == "unknown"
    assert context["failure_kind"] != "SourcesExhausted"
    assert "0 to 14 days" in context["staleness_rule"]


def test_cftc_http_failure_keeps_the_endpoint_and_error():
    import httpx

    from rocket.providers.cftc import CFTC_FUTURES_URL, fetch_cot_context

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="down")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    context = fetch_cot_context(now=NOW, http=client)
    assert context["regime"] == "unknown"
    assert context["status"] == "UNAVAILABLE"
    assert context["endpoint"] == CFTC_FUTURES_URL
    assert context["failure_kind"] == "HTTPStatusError"


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
