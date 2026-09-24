# FUT-011 result: HYPE 120-minute close-loser reversal fails the two-date gate

Status: `GROSS_OR_FEE_FLOOR_FAILED`, 2026-09-24. The [contract](FUT-011.md)
was frozen and pushed in commit `8c4aaad` before any HYPE conditioned
future price return was read. The [scorer](../../../research/futures/fut011_score.py)
uses only its two SHA-pinned 2025 source shards and contiguous seven-hour
windows. The local canonical JSON result has SHA-256
`c166d93742a3493e6cadd0a2b0d8bdc7f621c3665c54a07dbc25d9bcdb16e179`.
Run with DuckDB using
`python research/futures/fut011_score.py AUGUST.parquet SEPTEMBER.parquet`.

## Frozen gate

The all-wallet HYPE rule netted unmarked voluntary loss-realizing taker
close notional over each five-minute bin, waited one minute after the bin,
entered opposite to the net close direction at an optimistic ten-second
trade VWAP, and exited 120 minutes later at the same proxy. Require at
least 50 active events per date and 100 pooled. On **each** date, mean
active gross must exceed 9 bp and both same-bin always-long and
always-short controls. The two dates are 2025-08-31 and 2025-09-28,
`[03:00,10:00)` UTC. This is a separate author-motivated HYPE horizon
test, not a revision of FUT-010's failed 30-minute BTC/ETH rule.

## Score

All 59 scheduled opportunities per date were active, 118 pooled. The
selected contiguous segments had 322,409 and 320,412 consecutive blocks,
respectively; no proxy price was missing. The first date had 18 long and
41 short predictions; the second had 44 long and 15 short.

| UTC date | Active | Mean gross bp | Median gross bp | Always long bp | Always short bp | Gross less 9 bp | Gross less 20 bp |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2025-08-31 | 59 | +4.973 | −0.305 | −11.218 | +11.218 | −4.027 | −15.027 |
| 2025-09-28 | 59 | +13.649 | +12.542 | −43.340 | +43.340 | +4.649 | −6.351 |
| Pooled, diagnostic | 118 | +9.311 | +2.680 | −27.279 | +27.279 | +0.311 | −10.689 |

The sample gate passes. **August fails both the 9 bp fee floor and its
always-short control. September clears 9 bp gross but trails its
always-short control by 29.691 bp.** Thus the predeclared two-date gate
fails even before spread, impact, funding, or a true order-placement
delay. The pooled hour-block 95% diagnostic interval for mean gross is
`[−9.457,+29.607]` bp; these overlapping positions across two Sunday
windows are not independent trades or evidence of robust profitability.

## Decision and limits

Close the **exact HYPE all-wallet, five-minute close-flow,
one-minute-delay, 120-minute-hold** rule. Do not select September,
always-short, a different horizon, a larger loss threshold, or a wallet
slice from this result. The author chart's HYPE close-loser markout is
measured from a different event clock and is not a costed Rocket return;
FUT-011 does not reproduce its front-end cohort. Six 2025 fill order-ID
spot checks returned `unknownOid` through the current public order-status
API, so historical `FrontendMarket` membership remains an unresolved
source question. The mirror still lacks an independent official checksum
and executable bid/ask/depth; neither is needed to reject this rule's
predeclared gross and incremental gate. The 2026 final holdout and
production `rocket crypto scan --json` remain untouched.
