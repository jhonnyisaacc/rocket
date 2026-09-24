# FUT-004 discovery gross-information result

Status: `GROSS_GATE_FAILED_WITHIN_PROVISIONAL_SETTLEMENT_BOUNDS`, 2026-09-24. This applies the [frozen FUT-004 rule](FUT-004.md) and its [pre-result source amendment](FUT-004-DATA.md) to **2022–2023 discovery only**. The 2024 replication, 2025 follow-up and 2026 final holdout were not scored for this factor.

## Frozen gate result

The factor ranked 60,369 causally eligible symbol-days on 698 entry days and assigned 29,652 long/short symbol-day weights. Five next-day entry attempts had no usable open and remained cash; seven admitted positions without a next open received the predeclared minute-index settlement envelopes with 5% price stress. No selected price or funding exposure remains unresolved within those provisional envelopes. This result is **gross**, before transaction costs and held funding.

| Settlement scenario | 2022 mean daily gross | 2023 mean daily gross | Combined mean daily gross | Combined compounded gross |
| --- | ---: | ---: | ---: | ---: |
| Adverse envelope + 5% stress | −0.03985% | −0.00031% | −0.01923% | −14.14% |
| Middle estimate | −0.03795% | +0.00034% | −0.01798% | −13.38% |
| Favorable envelope + 5% stress | −0.03609% | +0.00099% | −0.01675% | −12.64% |

The middle case has 334 days in 2022 and 364 in 2023. Its calendar-month block bootstrap (24 months, 10,000 resamples, seed `20260924`) gives a 95% interval for combined mean daily gross of **−0.07854% to +0.04608%**. The mean is negative in 2022 under every settlement scenario, and the combined lower interval endpoint is negative in every scenario. Thus **none** passes the predeclared requirement that both annual gross means and the combined lower bootstrap endpoint be positive. The exact high-basis-long/low-basis-short one-day perpetual factor is closed at its cheap gross gate; no 20/40bps net score, 2024/2025 outcome, opposite-side rescue, quantile change or live `ENTER_*` decision follows from this trial.

## Attribution and limits

The middle-case 2022 factor compounded −12.70%; 2023 was almost flat arithmetically but compounded −0.79%. Combined gross maximum drawdown was −32.17% with mean gross exposure 99.98%. 2022 Q1, Q2 and Q4 gross means were negative, while Q3 was positive; 2023's first two quarters were negative and last two positive. This pattern offers no stable annual gross information under the frozen rule. Across all 698 days, long contributions summed −0.10857 and short contributions −0.01693 in portfolio-return units. The seven forced settlements summed approximately −0.02323 in the middle case; they matter, but their predeclared ±5% stress cannot reverse the negative 2022 annual mean. These are diagnostic attributions, not a selected asset, side or quarter strategy.

The minute-index prices are bounds rather than exact official second-level settlements; LUNA retains a late-trade cutoff caveat. The 20/40bps assumptions were not evaluated here because the gross falsifier failed. The daily-open proxy also has optimistic near-zero decision latency. A different funding-carry or execution-timing hypothesis would require its own mechanism and frozen test; this result only rejects the exact FUT-004 directional factor on this historical source and bound. The cited dated-futures basis study is a motivation, not a claim this perpetual-only result refutes it. Hyperliquid transfer and prospective shadow remain untested.

The local ignored gross report SHA-256 is `ba63742644601472fd9d93498ba9285ef94f7c6403b14b7183c06cab2d06d709`. Source fingerprints: repaired futures database `e42cfcfc5d244293a9a3327a5009c05723c541b1d86ed3a5050a08c7f97e863b`, selected weights `9dc451efc91cca893f45b29791896fc608e9f55e5132692da8409b2927cfe4c2`, seven-event pack `1ff17aa4f3c3ea4f4fc1787764a2684d83ec4326fa8bb2747595c924ff6a75d7`. `research/futures/fut004_gross.py` refuses changed fingerprints. The pre-result strategy commit is `417d0a3` and source amendment commit is `210e454`.
