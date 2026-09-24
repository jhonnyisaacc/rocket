# FUT-010 fixed 2025 gross pilot result

Status: `GROSS_OR_FEE_FLOOR_FAILED`, 2026-09-24. The
[FUT-010 contract](FUT-010.md) was frozen at `6be17f1` before any
loss-close-conditioned future price return was read. The deterministic
[scorer](../../../research/futures/fut010_score.py) used only the two pinned
2025 Parquet shards in the contract. The local JSON report has SHA-256
`4d9ef1e19ad3fca92ed42c4629571bd14974b5352ae88bb84dd03a1e23c4ec20`.

## Preset gates

All **222** scheduled BTC/ETH coin-decisions were active; neither zero net
flow nor a missing ten-second VWAP proxy caused cash. July had 82 active
events and October 140, so each exceeded the frozen 50-event date minimum
and the pooled sample exceeded 150. The sample gate passed.

| Fixed date | Active events | Mean optimistic price gross | Same-bin always-long | Same-bin always-short | Mean after 9 bp fee floor | Mean after 20 bp stress |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2025-07-28 | 82 | +3.873 bp | −7.149 bp | +7.149 bp | −5.127 bp | −16.127 bp |
| 2025-10-10 | 140 | +3.431 bp | +0.520 bp | −0.520 bp | −5.569 bp | −16.569 bp |
| Pooled diagnostic | 222 | +3.594 bp | −2.313 bp | +2.313 bp | −5.406 bp | −16.406 bp |

The two predeclared date means both failed the **gross >9 bp** fee-floor
gate. July also failed the incremental gate against its stronger
always-short control. October exceeded its directional controls but still
fell well below the fee floor. The pooled median optimistic gross was
+2.852 bp, and its descriptive 95% hour-block resampling interval was
−1.009 to +8.018 bp. This interval is not a two-date generalization
claim; the thirty-minute event positions overlap.

Coin/date means were +3.680/+4.066 bp for BTC/ETH in July and
+3.326/+3.535 bp in October. They are reported to show composition, not
to select a coin. The rule predicted long 58 of 82 July coin-decisions;
July's unconditional short gained, explaining its incremental failure.
October had 69 long and 71 short predictions. No side, coin, gap-adjacent
window, threshold, entry clock or holding horizon was rescored.

## Scope and decision

The fill mirror had complete selected fields, paired counterparties and
verified contiguous windows, but no independent official source checksum.
The October shard also has an eight-hour source gap, which the frozen
pilot excluded. The price proxy is the VWAP of observed market trades,
not a realizable Rocket fill; spread, impact and funding were omitted
optimistically. Base taker fees alone overwhelm the mean gross move on
both dates. Adding spread or impact to this exact base-fee model only
deepens the shortfall; different fee tiers or funding economics would
need a separate, explicit contract.

Close the **exact all-wallet, five-minute-flow, one-minute-delay,
thirty-minute-hold** directional proxy. The source paper's classified
front-end cohort and forced liquidations are different mechanisms and
remain untested by FUT-010. No 2026 outcome was read, and no production
scan or execution behavior changed.
