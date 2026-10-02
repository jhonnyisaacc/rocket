# FUT-013 result: delayed BTC-led perpetual transfer

Status: `GROSS_OR_INCREMENTAL_FEE_FLOOR_FAILED`, 2026-09-25. The
[contract](FUT-013.md) and [nine-file source manifest](../source_manifests/cross_crypto_minute_2024_2025.json)
were committed as `267f822` and pushed before the BTC-conditioned
future perp returns were read. The [scorer](../../../../research/futures/fut013_score.py)
reverified all source SHA-256 values, minute clock completeness and
source bar invariants. Its full local JSON report SHA-256 is
`0ad170258a47968210752d7aec3eafa894437e3f7d396403f2b4c623444ac91c`.

All four 2025 target-month cells exceed the frozen 1,000-active minimum.
Scheduled / active per target were 4,318 / 4,266 in November 2024,
4,318 / 4,218 in April 2025 and 4,462 / 4,214 in August 2025. Cash
reasons per target were 52, 100 and 245 flat BTC predictor minutes,
plus three zero-volume source/proxy events in August. BTC sign balance
per target was 2,127 long / 2,139 short, 2,148 / 2,070, and
2,056 / 2,158 by month. The ten-minute per-target holding windows do
not overlap; ETH and SOL positions can be concurrent.

| UTC month | Target | Active | Mean gross bp | Median bp | Always-long bp | Always-short bp | Own-lag bp | Gross less 9 bp |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2024-11 diagnostic | ETH | 4,266 | +0.208 | +0.297 | +0.964 | −0.964 | +0.043 | −8.792 |
| 2024-11 diagnostic | SOL | 4,266 | −0.672 | +0.421 | +0.849 | −0.849 | −0.406 | −9.672 |
| 2025-04 check | ETH | 4,218 | +0.213 | −0.340 | +0.053 | −0.053 | +0.348 | −8.787 |
| 2025-04 check | SOL | 4,218 | +0.076 | 0.000 | +0.533 | −0.533 | +0.421 | −8.924 |
| 2025-08 check | ETH | 4,214 | −0.316 | −0.492 | +0.333 | −0.333 | −0.273 | −9.316 |
| 2025-08 check | SOL | 4,214 | −0.182 | 0.000 | +0.377 | −0.377 | +0.323 | −9.182 |
| **Pooled diagnostic** | **Both** | **25,396** | **−0.112** | **0.000** | **+0.520** | **−0.520** | **+0.075** | **−9.112** |

The frozen 2025 gross fee-floor gate fails on all four cells by at least
8.787 bp. April ETH also trails its own-lag control; both April SOL
and August SOL trail their own-lag and directional controls. The
diagnostic November 2024 month is similarly sub-fee. Gross less the
20 bp stress is −19.787/−19.924 bp in April and −20.316/−20.182 bp
in August for ETH/SOL. A seeded pooled UTC-day-block 95% diagnostic
interval for active gross is **−0.798 to +0.572 bp**; the interval is
not needed to establish the much larger fee-floor failure.

This closes the **exact** always-signed BTC prior-minute rule with a
one-minute delay and ten-minute ETH/SOL perpetual hold. No coin,
month, side, clock, threshold or nearby hold rescue is authorized from
these results. The source paper's fitted cross-coin spot portfolio,
other information-diffusion mechanisms and future venue transfer were
not tested. Binance minute opens are optimistic proxies, with spread,
impact, depth, latency and funding omitted; those omissions only
strengthen the rejection at the gross fee floor. The 2026 final holdout
and production `rocket crypto scan --json` remain untouched.
