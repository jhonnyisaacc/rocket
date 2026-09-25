# FUT-002: earlier-year 60-day control replication

Status: `REPLICATION_FAILED_2022`, 2026-09-24. The [protocol](FUT-002.md) was committed before any 2021–2022 return was scored; the [data and cessation gate](FUT-002-DATA.md) was committed at `dd78562` before this run. This is a retrospective trial selected after the 2025 control result. The 2026 final holdout was not accessed.

## Frozen falsifier and result

The 60-day control had to have a **positive mean daily net return in both 2021 and 2022 at 20bps**, and a positive combined mean at 40bps. The 2022 condition fails throughout the predeclared minute-index cutoff/price/funding sensitivity, including the additional 5% price stress. The favorable-stress 2022 mean remains -0.00902% per day. A positive combined return does not rescue a failed year-specific condition.

| Period (364 entry days per year) | 60-day mean daily net, 20bps | 60-day mean daily net, 40bps | 20bps compounded | 20bps Sharpe | 20bps max drawdown | 20bps month-bootstrap 95% interval for daily mean |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2021 | +0.16199% | +0.15442% | +62.98% | 1.320 | -33.40% | -0.0636% to +0.4167% |
| 2022 | **-0.00945%** | -0.01680% | -10.65% | -0.087 | -34.63% | -0.1605% to +0.1536% |
| Combined, 728 days | +0.07627% | +0.06881% | +45.61% | 0.658 | -44.59% | -0.0655% to +0.2318% |

Numbers above use the middle settlement scenario. The 20bps 2022 mean spans -0.00987% to -0.00902% across adverse through favorable 5% stress; its compounded result spans -10.79% to -10.52%. At 40bps, the 2022 mean spans -0.01722% to -0.01638%. The 2021 mean spans +0.16197% to +0.16201% at 20bps. Bootstrap resamples whole calendar months 10,000 times with fixed seed; twelve months per year are too few to make precise confidence claims, and all displayed intervals include zero.

## Attribution and comparators

The 2021 middle-scenario daily mean decomposes into +0.22333% gross, 0.05377% funding drag, and 0.00757% transaction drag at 20bps. The 2022 mean decomposes into +0.00279% gross, 0.00488% funding drag, and 0.00736% transaction drag. The 2022 gross forecast-times-return statistic is negative (-0.000155 across 47,506 resolved symbol-days); in 2021 it is +0.001499 across 33,613. The 2021 gain is concentrated early: first-quarter mean daily net +0.8186%; the remaining three quarters average near zero or negative. Positive 2021 annual compounding therefore does not show stable monthly expectancy.

Cash is zero. The frozen 20/60/120-day comparator also has a negative 2022 mean (-0.01116% at 20bps and -0.01765% at 40bps), despite a positive 2021 mean (+0.08279% at 20bps). This comparison is descriptive; neither side nor asset subset was selected after the score. For the 60-day 2022 gross contribution, shorts total +0.1404 and longs -0.1302 portfolio-return units; no single top asset explains the failed net year. The 2022 20bps portfolio averages 42.1% gross exposure, 12 forced settlements and nine rejected next-day orders. All scenario results have zero unresolved exposed outcomes. The LUNA notice/minute discrepancy remains a provisional settlement-price limitation, and actual account-tier execution costs and the intended Hyperliquid venue remain unmeasured.

## Decision

The exact selected control is `REPLICATION_FAILED_2022` and is not a validated strategy. Do not relax the year-specific falsifier, choose a winning slice, or spend the untouched 2026 holdout to recover this trial. The broader futures pillar has no `ENTER_*` decision. A different mechanism would require a new frozen hypothesis and independent evidence; it cannot inherit this control's 2021 gain as proof.

Reproduction: `research/futures/fut002.py` against the versioned database and candidate files documented in [FUT-002-DATA](FUT-002-DATA.md). The ignored local report SHA-256 is `b9751977c51d14d3694f8b01be37f433dac6db1521d25b337dd59bc5680bc799`; database SHA-256 `e42cfcfc5d244293a9a3327a5009c05723c541b1d86ed3a5050a08c7f97e863b`; candidate SHA-256 `f081927f50791613b78a9ec7d8e3038f59a485c39f6df9c8401b45ed386d9ca6`.
