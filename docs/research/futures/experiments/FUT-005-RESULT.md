# FUT-005: COT positioning-change replication result

Status: `GROSS_GATE_FAILED_2023`, 2026-09-24. The [trial contract](FUT-005.md)
was frozen at commit `2538180`, and its freeze SHA entered the ledger at
`be8b884`, before any COT-conditioned outcome was scored. The scorer reads
only the declared 2023–2024 Binance outcome window; 2025 COT-conditioned
outcomes and the 2026 final holdout remain unread.

## Data and checks

The scorer verified the frozen CFTC source manifest SHA-256
`a51fc0dc3461ad67ddd85b9e531b60f783546dc91a28c9f5e635bb7a8d6a830a`
and the repaired Binance database SHA-256
`e42cfcfc5d244293a9a3327a5009c05723c541b1d86ed3a5050a08c7f97e863b`.
It used 365 daily entry intervals in 2023 and 366 in 2024. Every BTC entry
and next-open exit was present. Funding cadence passed on every exposed day;
there is no matched-only omission or forced settlement. The CFTC 2023 ION
publication disruption caused 24 consecutive stale-signal cash days,
February 15–March 10, as required by the frozen 21-day age rule. There are
no stale-signal cash days in 2024. Opening, reversals and partition exits
are included in turnover. Full deterministic local daily result SHA-256:
`ae83edc43a499403b326f2f2c0856b5b30002132b4e93ca02ed4755432688c43`.

| Year | Active long / short days | Turnover units | Daily gross mean | Daily funding drag | Daily net mean, 20bps | Daily net mean, 40bps | Compounded net, 20bps |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2023 | 173 / 168 | 42 | −0.07429% | +0.00457% | **−0.09036%** | −0.10187% | −34.13% |
| 2024 | 186 / 180 | 64 | +0.05414% | +0.00112% | +0.03553% | +0.01805% | −1.16% |

The combined 24-month block-bootstrap 95% interval for the 20bps mean daily
net return is **−0.17661% to +0.13738%**. It spans zero. The frozen
two-year cheap gate required positive gross *and* 20bps net daily means in
both years. The 2023 gross and net means are negative, so the gate fails
before conditional 2025. The 2024 positive arithmetic mean does not rescue
the two-year gate; its compounded 20bps return was negative, and its
positive contribution was concentrated in Q1. The 2024 Q1/Q2/Q3/Q4 sums
of daily 20bps net returns were +46.11%, −12.29%, −19.12% and −1.70%.

| Month | 2023 daily 20bps net mean | 2024 daily 20bps net mean |
| --- | ---: | ---: |
| Jan | +0.2355% | +0.2382% |
| Feb | −0.1554% | +1.2362% |
| Mar | +0.2291% | +0.0928% |
| Apr | −0.4062% | −0.0427% |
| May | +0.2321% | −0.3588% |
| Jun | −0.5836% | +0.0039% |
| Jul | −0.0160% | +0.4818% |
| Aug | +0.2610% | −0.5713% |
| Sep | −0.1542% | −0.5448% |
| Oct | −0.1930% | +0.2603% |
| Nov | −0.0016% | −0.2664% |
| Dec | −0.5638% | −0.0574% |

The 2023 long days contributed +42.56 percentage points of gross daily
returns in sum; short days contributed −69.67 points. In 2024, corresponding
contributions were +56.62 and −36.80. This attributes the 2023 gross
failure primarily to the short side in a rising BTC year, without authorizing
a long-only slice or sign inversion. The same-calendar always-long control
had +0.28595% and +0.22212% daily 20bps net means in 2023 and 2024; the
seven-day price-only control had +0.02222% and −0.03942%. Neither control
was selected as a successor by this result.

## Conclusion and limit

`FUT-005` fails its **gross-information** requirement in 2023. The observed
2024 signal was not stable in compounding or later quarters. Close the exact
paper-signed, always-signed CME positioning-change rule after the declared
release lag. Do not tune its side, COT subgroup, lag, threshold or holding
period, and do not read its conditional 2025 outcome. This does not reject
every use of COT as market context or an incremental feature, nor does it
establish that the published study's own regression was wrong: the Rocket
trial tests a different costed, delayed-entry perpetual implementation.
No Rocket `ENTER_*` behavior changes; execution remains disabled.
