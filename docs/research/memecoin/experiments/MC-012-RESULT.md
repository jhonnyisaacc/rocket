# MC-012 result — later alternate-pool discovery diagnostic

Status: **no alternate venue surfaced for the 54 curve-unavailable names in this later third-party lookup**. This is bounded discovery evidence, not an as-of exit quote, complete DEX index or realized liquidation outcome. The [design](MC-012-FROZEN.md) and deterministic 108-mint [selection](../data/mc012-pool-selection-20260924.json) were committed as `38181c3` before the four API batch requests.

The selected MC-010 names were all 54 native non-Mayhem `EXIT_UNAVAILABLE:insufficient exit liquidity` cases and 54 hash-selected controls from 129 quoted names. Four read-only calls to the documented [DEX Screener Solana token-pairs API](https://docs.dexscreener.com/api/reference) returned HTTP 200 on their first attempts. Every request and response body, mint list, receive clock and raw-body hash is saved. The lookup happened after the MC-010 cohort, so none of its market fields can be assigned to the original 67-second decision or exit clock.

| Group | Mints queried | Later listed pairs | Non-`pumpfun` pair on any mint | Non-`pumpfun` pair with listed creation at/before frozen exit |
| --- | ---: | ---: | ---: | ---: |
| Curve unavailable | 54 | 54 `pumpfun` | 0/54 | 0/54 |
| Quoted control | 54 | 53 `pumpfun`, 1 `pumpswap` | 1/54 | 0/54 |

The control PumpSwap listing was for mint `DJhAWE4tuVFNw57JLBEw6sJbtF6xntFPFkbmXTMJpump`, with `pairCreatedAt` 16:39:58 UTC versus its frozen 16:38:57.493 UTC exit clock. MC-010's independently captured Pump completion/migration events for that mint also arrived around 16:39:58 UTC, supporting **later** migration rather than an earlier exit. No curve-unavailable mint had a same-mint completion or migration event in the covered Pump log panel.

The absence of a listed alternate pair in a later API response **does not prove** no route existed at 67 seconds: DEX Screener describes automatic listing after a pool has at least one transaction, and its index scope, update timing and historical state are not a complete chain-state proof. Conversely, a pair listing would not supply size-aware output, reserves, priority cost or an achieved fill. MC-010's zero-recovery stress stays a scenario; no exit return or entry decision is relabeled. The negative quoted-only MC-010 top returns also mean that discovering an extra exit venue alone would not establish a positive rank.

The [evidence archive](../data/mc012-pool-discovery-20260924.tar.gz) has SHA-256 `a282cd5aa83fdc6d9e17b6621bd58ba84ca22f67f1874dc09463f7f91c04c6b2`; the deterministic report has SHA-256 `ef1b3b116395ec8799a8e3322ac1dea09e4bbd4619c7e46019ed6dd4484cbc09`. An extracted-archive replay reproduced the report byte for byte. The next defensible exit test requires contemporaneous venue state and a size-aware route quote or signed fill simulation at the frozen exit clock, with unknowns retained. A new prospective cohort and bounded quote source are required; later discovery cannot reconstruct those values.
