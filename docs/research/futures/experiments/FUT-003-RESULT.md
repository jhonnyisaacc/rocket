# FUT-003: Bybit 2022 transfer of the frozen trend baseline

Status: `VENUE_TRANSFER_COST_SENSITIVE_NOT_PROMOTED`, 2026-09-24. The [strategy contract](FUT-003.md) and [data/settlement gate](FUT-003-DATA.md) were committed before any Bybit strategy return was scored. This tests the **old** FUT-001 rule on another venue in a calendar year already inspected on Binance. It is not a fresh market-regime holdout or a new mechanism.

## Frozen falsifier and result

The exact 20/60/120-day forecast required a positive equal-weight gross predictive statistic and positive mean daily portfolio net at **both** 20bps and 40bps round-trip costs plus funding. Its gross statistic was only +0.006764% forecast-times-return over 15,508 resolved symbol-days. The middle settlement case had a +0.001626% 20bps daily mean and **-0.005403% at 40bps**. The 40bps mean remained negative from -0.005451% to -0.005347% across the adverse-to-favorable 5% settlement stress. Therefore the cost robustness condition fails throughout the frozen sensitivity range.

| 2022 score (364 entry days) | Mean daily net, 20bps | Mean daily net, 40bps | 20bps compounded | 20bps Sharpe | 20bps max drawdown | 20bps month-bootstrap 95% interval for daily mean |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Multi-horizon baseline | +0.001626% | **-0.005403%** | -5.07% | 0.017 | -27.70% | -0.1373% to +0.1273% |
| Frozen 60-day control | -0.003399% | -0.011205% | -8.15% | -0.032 | -34.81% | -0.1651% to +0.1680% |
| Cash | 0 | 0 | 0 | — | 0 | — |

The multi-horizon middle-scenario daily mean decomposes into +0.013593% gross, 0.004939% funding drag, and 0.007029% transaction drag at 20bps. Total absolute target-weight turnover is 25.584 portfolio-notional units, or 0.0703 per scored day; the 40bps transaction drag doubles on the same turnover. Second-quarter mean daily net is +0.2278% at 20bps, but third-quarter mean is -0.1587%; all twelve-month bootstrap intervals include zero. The positive 2022 Bybit gross point estimate does not establish stable directional information. Long gross contribution is -0.0906 and short gross contribution +0.1401 in portfolio-return units; these are attribution, not a post-result side selection. FIL, BIT, and BCH are the largest absolute gross contributors, with no permitted asset carve-out.

Three held cessations were represented: LUNA at its [announced special 0.024 USDT settlement](https://t.me/s/Bybit_API_Announcements?before=94), plus FTT and SRM with predeclared 30/60-minute index envelopes and 5% stress. One unfilled next-day LUNA order remained cash. All 20 scenario/component/cost combinations report zero unresolved exposed outcomes. The FTT/SRM prices remain **provisional**; the 20/40bps costs are historical sensitivities, not verified account-tier executable costs. The catalog may omit old closed names, and the same calendar period already informed FUT-002. These limits preclude promotion even if the 40bps test had passed.

## Decision

`VENUE_TRANSFER_COST_SENSITIVE_NOT_PROMOTED`. The old multi-horizon rule does not earn further tuning, a live `ENTER_*` contract, or access to the untouched 2026 Binance final holdout. The next strategy trial must have a distinct gross-information mechanism with its own frozen falsifier. A separate Hyperliquid overlap and prospective shadow would still be needed for any future survivor.

Reproduction: `research/futures/fut003.py` against the hashed tape and settlement candidates in [FUT-003-DATA](FUT-003-DATA.md). Ignored local result SHA-256 `ca0e16031e10599717d4d63d17dc1124d1e87d6669a0baa9c58873ee7821e908`.
