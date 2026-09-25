# Quarter-hour order flow: paper-to-execution economic gate

Status: `PAPER_PRIOR_ONLY`, 2026-09-24. This is a decision on research
priority, not FUT-006, a Rocket backtest, or a rejection of all order flow.
No order-flow-conditioned 2025 return was read for this note.

The [primary paper](https://arxiv.org/html/2607.09426v2) contains **two
different forecasting questions**. Its Section 5 walk-forward model forecasts
the *first ten seconds* of each quarter hour using information available
before the boundary. Appendix A.5 converts that model to mean sign-weighted
gross return of **0.375 bp BTC** and **0.532 bp ETH** per boundary over
July 2021–October 2024. These are measured from a reference price the authors
explicitly say need not be attainable; they do not report a net trading
strategy. The paper compares a roughly 0.5 bp gross effect with its 5 bp
Binance taker fee **per side**. At a standard two-taker round trip, fees alone
are 10 bp, before spread, impact, or latency. This makes a boundary-crossing
standalone taker trade uneconomic on the reported mean; no full-tape Rocket
replication of that *specific* model is warranted now.

Section 6 is a **separate** question: after the first ten seconds have elapsed,
does their measured taker-volume imbalance forecast returns over four to
twelve hours? The paper anchors each forward return at the last trade price
*within* the signal's ten-second bin. That price is an optimistic proxy for a
decision made after the bin closes; an executable test must enter later. Its
Appendix A.4 BTC/ETH twelve-hour slopes are **6.39/5.40 bp per unit of
imbalance**, and the sign-only robustness slopes in A.5 are **2.73/2.38 bp
per sign unit**. These are in-sample regression coefficients, not mean
returns of a causal sign-trading strategy, executable quotes, or upper bounds
for selective trading. The paper's component interquartile effects do not
turn them into an implementable P&L either.

[Hyperliquid's current fee schedule](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees)
lists tier-zero perpetual taker fees of **4.5 bp per side**, or **9 bp**
round trip, before spread, impact and funding; maker fees and tier discounts
require a distinct fill model and account assumptions. These schedules and
the paper's historical Binance fees are comparison scales, not the observed
cost of any Rocket order. A simple always-signed BTC/ETH ten-second imbalance
trade at a twelve-hour horizon therefore has a weak *economic prior* relative
to intended-venue taker cost. The paper does not provide the post-signal,
costed, nonoverlapping position returns needed to accept or reject it.

## Acquisition decision

Do not download the full **16.64 GB** 2025 BTC/ETH aggregate-trade tape merely
to reproduce the paper's statistical significance or the already sub-fee
opening forecast. The [source scout](ORDERFLOW_SOURCE_SCOUT.md) has established
archive presence and one-day integrity; neither is a strategy edge. A further
order-flow trial requires a separately frozen, bounded **post-study**
falsifier with an explicit after-bin entry proxy, position overlap policy,
turnover, funding, 9 bp two-taker cost floor, concentration check, and rule
for promoting acquisition of later dates. Use an early post-October-2024
period before reading its order-flow-conditioned outcomes; keep 2026 as the
final holdout. A trial cannot choose a threshold, hour, side, contract, or
holding horizon from that falsifier's return results and then report it as
independent validation. A viable Binance result still needs direct
Hyperliquid order-flow measurement and executable quote/fill validation.

This gate defers the expensive acquisition and does not spend the 2025 or
2026 order-flow holdouts. The next research choice should compare the
expected value of that bounded intraday trial against independent mechanisms
with lower data and execution costs. No `ENTER_*` contract is validated.
