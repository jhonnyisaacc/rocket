# FUT-012 result: delayed HYPE market-liquidation reversal

Status: `GROSS_OR_INCREMENTAL_FEE_FLOOR_FAILED`, 2026-09-24.
The [rule and gates](FUT-012.md) were committed as `e9c6a03` and pushed
before any liquidation-conditioned future trade price was read. The
[scorer](../../../../research/futures/fut012_score.py) verified all 96
source file hashes and sizes from the [manifest](../source_manifests/hyperliquid_full_days_2025.json),
consecutive blocks, HYPE taker/maker pairs, matching liquidation markers,
and full UTC day coverage. Its full JSON output has SHA-256
`5b9546ce33711ae9e6eea18ad7004944c228fe15e380041894cc2248a19e87d0`.

All 54 source-eligible, 30-minute-separated HYPE episodes were active:
16, 6, 23, and 9 by date. There were no zero-net-flow decisions, late
qualifying liquidations or missing ten-second trade proxies. Long/short
signals were 9/7, 1/5, 18/5, and 8/1, respectively. This passes the
frozen ≥5 active per day and ≥40 pooled sample gate. These are event
returns that can overlap; they do not represent a portfolio return.

| UTC date | Active | Mean gross bp | Median gross bp | Always-long bp | Always-short bp | Gross less 9 bp | Gross less 20 bp |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2025-08-14 | 16 | +169.665 | +164.759 | +14.631 | −14.631 | +160.665 | +149.665 |
| 2025-09-18 | 6 | −10.078 | −22.063 | +1.639 | −1.639 | −19.078 | −30.078 |
| 2025-09-25 | 23 | −2.312 | −6.703 | −43.252 | +43.252 | −11.312 | −22.312 |
| 2025-10-04 | 9 | +41.219 | +42.014 | +40.166 | −40.166 | +32.219 | +21.219 |
| **First two dates** | **22** | **+120.644** | **+102.317** | **+11.088** | **−11.088** | **+111.644** | **+100.644** |
| **Last two dates** | **32** | **+9.931** | **+14.486** | **−19.791** | **+19.791** | **+0.931** | **−10.069** |
| **Pooled diagnostic** | **54** | **+55.037** | **+43.242** | **−7.211** | **+7.211** | **+46.037** | **+35.037** |

The first chronological half clears the 9 bp gross fee floor and both
same-bin directional controls. The second half clears the 9 bp gross
floor by only 0.931 bp and **fails** the incremental check: +9.931 bp
versus +19.791 bp always-short. September 25 itself is negative gross
and far below its always-short control. The frozen both-halves gate
therefore fails. The pooled +55.037 bp is dominated by the August 14
cascade and cannot override the second-half failure. A seeded pooled
hour-block resampling diagnostic gives a 95% interval of +0.237 to
+111.663 bp, but the small cluster count and two shock-heavy dates make
this unsuitable as a profitability claim.

This closes the exact market-liquidation HYPE sign, one-minute delay,
120-minute hold, and 30-minute episode rule. Do not flip a side, choose
August, shorten the hold, or select a size threshold from these results.
Trade VWAP is an optimistic proxy; spread, depth, impact, latency and
funding were not measured. The 2026 final holdout and production scan
remain untouched. Any further liquidation mechanism needs a separately
justified, newly frozen contract on fresh dates.
