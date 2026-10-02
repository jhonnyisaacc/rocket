# FUT-001: first 2025 OOS cheap gate under bounded settlements

Status: `COST_SENSITIVE_NOT_PROMOTED`, 2026-09-24. The [20/60/120-day contract](FUT-001.md), chronological split, and [settlement sensitivity/decision rule](FUT-001-SETTLEMENT-SCENARIO.md) were committed before this first 2025 OOS score. This is a bounded historical scenario, not an exact exchange settlement ledger or a live strategy validation.

## Primary result

The 2025 OOS has 364 scored entry days. Its 35 candidate intraday settlements and 17 next-day rejected orders are represented explicitly. All modeled exposed outcomes are resolved across the predeclared cutoff, minute-price, funding and 5% price-stress scenarios. The 70 events across discovery and OOS each have checksum-verified minute trade/index archives and dated Binance notice leads; the [source limitations](FUT-001-SETTLEMENT-SCENARIO.md) still apply.

| 2025 OOS scenario | Multi 20bps mean daily net | Multi 20bps compounded | Multi 40bps mean daily net | Multi 40bps compounded |
| --- | ---: | ---: | ---: | ---: |
| Adverse range plus 5% price stress | +0.00493% | -1.46% | -0.00150% | -3.74% |
| Official-cutoff minute-close approximation | +0.00539% | -1.30% | -0.00104% | -3.58% |
| Favorable range plus 5% price stress | +0.00583% | -1.14% | -0.00060% | -3.43% |

For the middle 20bps case, annualized Sharpe is 0.077, maximum drawdown is -28.4%, mean gross exposure is 0.309, and mean active names is 279. Gross directional return averages +0.01780% per day; funding and turnover drag over the year are 0.02177 and 0.02340 of initial notional, respectively. The 40bps turnover drag is 0.04680. The positive arithmetic daily mean and negative compounded return coexist because the return path is volatile.

The frozen cheap falsifier specified a **nonpositive 20bps mean** as rejection of the exact baseline. That condition was not met. Its separate cost rule says positive at 20bps but nonpositive at 40bps is **cost-sensitive and not promoted**; this holds even at the favorable 5% settlement stress. A calendar-month block bootstrap of the 20bps middle case gives a 95% interval of **-0.0737% to +0.0821% mean daily net**, including zero. Twelve months provide limited precision. No validated positive expectancy or `ENTER_*` decision follows.

## Controls and attribution

Cash earns zero. The frozen single 60-day control has a 2025 middle-case mean daily net of +0.04278% at 20bps and +0.03548% at 40bps, with compounded returns +10.83% and +7.93%. Its 20bps Sharpe is 0.477 and maximum drawdown is -33.5%; its calendar-month bootstrap interval for mean daily net is **-0.0824% to +0.1763%**, also including zero. It is a control, not a selected successor strategy. The multi-minus-single 20bps point difference is -0.03739% per day; a paired calendar-month resampling interval spans zero, so superiority is not established.

The equal-weight gross predictive statistic `forecast × next-open return` over eligible symbol-days is approximately **0.00000019** for multi-horizon in 2023–2024 discovery and **0.00009053** in 2025 OOS. The 60-day control is **-0.00006527** in discovery and **+0.00051278** in OOS. The statistic is uncosted and not a portfolio return. The primary portfolio's 2025 gross short contribution is +0.1192 of initial notional versus -0.0544 on longs, before funding and transaction costs; this side split is explanatory, not an authorized short-only variant. OOS quarter mean net returns alternate: positive in Q1/Q4 and negative in Q2/Q3. The apparent one-year control advantage and side/quarter slices are not promotion evidence.

## Decision and next research question

Keep FUT-001 as a historical cost-sensitive result under bounded settlement assumptions. Do not run the predeclared plateau variants as a rescue search, tune a side filter, change the OOS year, or spend the untouched 2026 holdout on this weak baseline. Audit account-tier taker fees and the second-level settlement-price assumption; independent replication and an explicitly frozen next experiment are needed before any trend component can be promoted. The most useful next distinction is whether gross forecast information can survive a causal turnover/cost design across independent periods and on the intended execution venue, rather than selecting the 60-day control from this one OOS year.

Reproduction inputs under ignored `.rocket/futures_data/`: normalized SQLite SHA-256 `c6017a5a445578af1a36f82d62478f53336f62c8adbc67b24ce2f08a6b49e9ef`, candidate JSON SHA-256 `a92b5889f8b531d21fbebe67ea2d7f3efda852f430e913e2aeb14d53d4471529`, discovery report SHA-256 `4e79f614cfa4d5713ce5104d2b68bf226e63ce9301a1b4d89af91fbc630dfb98`, and first OOS report SHA-256 `d277184584678728ff4d01009f28a4e5c5554246252cb21e6c135c42283b9f1c`. The deterministic scorer and tests are in `research/futures/settlement_scenario.py` and `tests/research/test_settlement_scenario.py`.
