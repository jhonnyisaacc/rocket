# FUT-006 bounded post-study result

Status: `GROSS_GATE_FAILED_POST_STUDY`, 2026-09-24. The exact
[FUT-006 contract](FUT-006.md) was frozen at `cfb8916` before its
order-flow-conditioned outcomes were read. Its source audit and scorer were
committed at `c72b085`. No 2025 signal return or 2026 holdout was scored.

## Source and chronology

The official Binance BTCUSDT and ETHUSDT daily `aggTrades` ZIPs for
November–December 2024 and January 1, 2025 were downloaded with matching
`.CHECKSUM` files. The [source audit](../../../research/futures/fut006_source_acquire.py)
verified each official ZIP hash, seven-column schema, UTC date bounds,
ordered timestamps, consecutive aggregate IDs within and across all 62 days
per contract, and all scheduled signal and delayed price-proxy windows. BTC
contributed **112,642,019** rows and ETH **129,418,833**, including January
1 used for the final exit proxy. Their compressed ZIPs totaled **3.122 GB**.
The ignored local source manifest SHA-256 is
`f9f6c580e54ceffb1cc1b7efe63c3c3e260f88a9af349569ef21ee503455b19a`.
The checksum-repaired Binance funding database matched its frozen SHA-256
`e42cfcfc5d244293a9a3327a5009c05723c541b1d86ed3a5050a08c7f97e863b`;
the scorer found no exposed funding gap.

Each signal used only trades in seconds 0–9 at 00:15 and 12:15 UTC. Its first
trade in seconds 20–29 supplied the entry proxy, and the same clock twelve
hours later supplied the exit proxy. Positions were continuous and
nonoverlapping; fee cost depended on actual target changes, with initial
entry and final exit charged. Both assets and all **122** scheduled portfolio
intervals were included. The [deterministic scorer](../../../research/futures/fut006_score.py)
used the frozen 5 bp-per-side primary and 10 bp-per-side stress, plus actual
signed funding. The ignored local result SHA-256 is
`ffcd1db8d55a65c5cee5c4b6af05ae916d4eb630f0c53f31d2ac69901a94007d`.

## Frozen gate

Mean returns below are **basis points per twelve-hour portfolio interval**.
BTC and ETH have equal notional weight. Net includes funding and turnover.

| Scope | Intervals | Gross | Net, 5 bp/side | Net, 10 bp/side |
| --- | ---: | ---: | ---: | ---: |
| Pooled BTC/ETH | 122 | **−2.5332** | **−7.4381** | **−12.5201** |
| November | 60 | +2.6287 | −2.8603 | −8.6936 |
| December | 62 | −7.5286 | −11.8683 | −16.2231 |
| BTC alone | 122 | −24.8550 | −30.1930 | −35.9307 |
| ETH alone | 122 | +19.7886 | +15.3168 | +10.8905 |
| Always-long BTC/ETH control | 122 | +25.8258 | +23.6018 | +23.5198 |

The pooled target changed **124 unit-notional sides** over 122 intervals;
at 5 bp per side that averaged **5.0820 bp** of transaction cost per
interval. Signed funding contributed an average **0.1771 bp credit**. Thus
the primary net mean equals gross −2.5332 + funding credit 0.1771 − fee
5.0820 = **−7.4381 bp**. Compounding the interval portfolio returns gave
**−10.31%** at 5 bp/side and **−15.71%** at 10 bp/side. The always-long
comparator compounded **+29.67%** at 5 bp/side; its different turnover and
the bull-market period are part of the comparison, not a causal attribution
to order flow.

The predeclared gross and both net point-estimate gates all failed. A
61-day block bootstrap for the pooled 5 bp/side mean gave a wide 95% interval
of **[−38.98, +24.75] bp per interval**. This short post-study window does
not establish a precise population effect; it does establish that the
specific frozen rule did not clear its cheap gate. BTC supplied 50 long and
72 short intervals; ETH supplied 60 long and 62 short; neither had cash
intervals. Gross daily P&L was dispersed and offsetting: the best five UTC
days summed to +0.2637 in portfolio return units and the worst five to
−0.2668, against total arithmetic gross −0.0309. There is no positive-total
"best five share" to report.

## Interpretation

Close the exact always-signed, fixed-clock, twelve-hour BTC/ETH rule as a
standalone strategy candidate. Do not reverse the sign, choose ETH alone,
retain only November, move the clock, or add a threshold from this result.
The data show a negative pooled gross point estimate before costs, while
asset outcomes differ strongly and uncertainty is wide. This is not a
replication of every regression in the source paper and does not reject all
intraday order flow. It does not justify spending the conditional 2025 tape
or the untouched 2026 holdout on this rule.

The source price is the first *trade* in a delayed ten-second bin, not an
executable taker quote. Actual spreads, impact and Hyperliquid transfer
remain unmeasured; the 10 bp/side scenario is a cost stress, not measured
slippage. These limits make a promotion claim weaker, while the negative
gross gate already rejects this exact cheap falsifier. No `ENTER_*` decision
is validated; execution remains disabled.
