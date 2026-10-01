# Daily market check

Read-only regime score for three consumers. No orders.

```bash
.venv/bin/rocket market-check fetch --output data/market_check/panel.json
.venv/bin/rocket market-check run --panel data/market_check/panel.json
.venv/bin/rocket market-check backtest --panel data/market_check/panel.json \
  --report docs/market_check/BACKTEST.md
```

JSON is the default. `--human` prints the research-result markdown. `--as-of YYYY-MM-DD` replays a session. `--scorecard PATH` adds pending Cava calls whose check date falls inside the configured window (optional). `--book PATH` is a JSON weight map (`{"USDC": 0.16, "MSFT": 0.15}`) used for the Porto add/hold/trim label. `--trade-log PATH` is an optional CSV (`date,ticker,side,note`) compared with the simulated fills. It is not a cost-basis replay.

`changed` is false when today's action fingerprint matches the prior session in the same panel. Bots should message each other only when it is true.

Parameters, thresholds, costs and the event list live in `config/market_check.toml`.

## What the check scores

Each pillar is green, yellow or red from the sub-scores in that file. Risk-on still uses that weighted total. Caution and risk-off come from a rate-of-change stress score (VIX jump, credit widening, 30-year yield breakout, oil shock, BTC drawdown) with hysteresis. A quiet tape is risk-on or neutral.

| Pillar | Series | Notes |
|---|---|---|
| Rates | Treasury 2y/10y/30y, NY Fed EFFR | Level, 20-session trend, 2s10s, and 2y minus fed funds as the hike/cut proxy |
| Oil | FRED WTI/Brent spot, else futures | Level, momentum, and a 5-session shock flag that blocks adds |
| Volatility | VIX and TLT realized vol | MOVE is not on a free history. TLT 20-session realized vol is the proxy |
| Credit | FRED `BAMLH0A0HYM2` | HYG/LQD is used only if the OAS series is missing |
| Dollar and gold | ICE DXY, gold | A rising dollar or a fast gold bid is the stress side |
| Crypto | BTC 50/200, Deribit funding, DVOL | Direction, and whether options look cheap or expensive |

FOMC dates are the static decision dates in the config. CPI is the second Wednesday of the month. Payrolls are the first Friday. Both proxies are labeled in the JSON.

## Consumers

- **Perps.** `long`, `flat` or `short` BTC, a size, whether implied vol is cheap or expensive, and whether a BTC put overlay is on. Caution is flat. Puts are suppressed when the book is already short.
- **Porto.** Cash target is 35 / 40 / 42 / 45 percent for risk-on, neutral, caution and risk-off, and it steps up on an up index day. Adds only ETN, CAT, APH and AMAT in the bottom half of the trailing buy zone, and never in caution or risk-off, on an FOMC day, or on an oil shock. Trims follow TSLA, FCX, BAC, then half of META/EQIX/MSFT, then a light AMZN trim. A red name is not sold. A hard-down index day blocks every trim.
- **Phillip.** Keep, raise or lower the computed bands, and the names closest to the buy zone. The numeric bands are a trailing-range stand-in until Phillip's own bands are supplied. The watchlist is SPCX, BE, EQIX, ETN, CAT, VST, APH, CRWD, AMAT, MRVL, DDOG.

The September 2026 snapshot (about $798, and the 23 Sep TSLA sale) is context. The backtest does not replay it. There is no cost basis before 15 Sep 2026.

## Backtest

`market-check backtest` walks 2024-10-01 through 2026-09-30. Equity sessions use the SPY calendar. The decision on day T cannot read a later print; credit OAS and EFFR are lagged one calendar day. The out-of-sample split is 2025-10-01, same parameters. Sessions before 2025-09-02 are marked as an Ondo proxy (underlying prices, one for one).

The report is `docs/market_check/BACKTEST.md`. Assumptions, costs and the limits of the Black-Scholes put marks are in that file and in the JSON `assumptions` list.
