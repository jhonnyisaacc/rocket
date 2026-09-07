# Crypto futures strategy polish — live scan is top-100; edge not validated

Status: open tracking issue. The **scan job is V1 production**. This issue is strategy polish, not a second engine.

## What V1 does live

`rocket crypto scan` on the **current top 100 by market cap** plus liquid perpetual markets (NAVE PR44 funnel). Cadence stays with the adapter (~6-hourly).

## Why the strategy still needs an issue

- Evaluate is research-only; bounded out-of-sample, fees, funding, and slippage are not a proven executable edge.
- Historical duplicate engines are dropped. Polish happens on the **one** funnel.
- Tickers outside the point-in-time top 100 stay excluded.
- COT is market regime, not an altcoin signal. Cava is overlay only.
- Missed-move audits find blind spots; they must not be fed back into the live scan as hindsight.

## Keep exploring here

Filter thresholds, liquidity/OI, paper-cost realism, OOS evaluate, missed-move systematic gaps — without a second production owner.
