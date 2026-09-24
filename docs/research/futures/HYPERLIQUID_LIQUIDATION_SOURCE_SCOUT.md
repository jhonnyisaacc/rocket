# Hyperliquid market-liquidation source and sample audit

Status: `TWELVE_METADATA_SELECTED_SHARDS_AUDITED_RETURN_FREE`, 2026-09-24. No
liquidation-conditioned future return, trading rule, or FUT-012 contract
has been calculated or registered. This scout tests whether the free
block-fill mirror can identify forced market closes and whether its many
fills represent enough independent opportunities for a directional trial.

## Mechanism and data meaning

The [venue documentation](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/liquidations)
says liquidation first attempts to close a position through market orders
on the book. A deeper loss can transfer positions to the liquidator vault
as a backstop, a different mechanism. The [official fill schema](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/websocket/subscriptions)
allows an optional `liquidation` object with `liquidatedUser`, `markPx`, and
`method: market | backstop`. A fill marker appears on both wallet sides of
the same trade; only the liquidated wallet's taker close is a candidate
directional event. Backstop transfers cannot be assumed to produce the
same ordinary market trade. A forced close can realize positive P&L in one
position when the account as a whole breaches margin; negative `closedPnl`
must not be required for a liquidation event.

An [author presentation](https://drive.google.com/file/d/1qUTWDaL6j-cWBO8myGAg7cGxLjMBLs3C/view)
plots a strongly negative HYPE liquidation markout through 120 minutes
(slide 47). It is measured from the distressed fill, not after a Rocket
observation and executable entry. Its visual effect is a research prior,
not a fee-clearing delayed return estimate.

## Return-free audit

The [streaming auditor](../../../research/futures/hyperliquid_liquidation_source_audit.py)
checks the SHA-256 and block sequence of each existing mirror shard,
groups the two wallet-fill rows by `(block_number, coin, tid)`, compares
both liquidation markers, checks that exactly one taker is the liquidated
wallet and that its direction is a close, and counts distinct orders,
wallets, five-minute bins and 30-minute bins. It reads current event
prices only to identify fields, never a price after an event. BTC, ETH,
and HYPE are the fixed liquid perps for this source screen.

| Shard cutoff | Marked market trades, BTC / ETH / HYPE | Market-wide 5m bins | Market-wide 30m bins | Source gap count |
| --- | ---: | ---: | ---: | ---: |
| 2025-07-28 `17` | 334 / 493 / 29 | 15 | 6 | 0 |
| 2025-09-01 `0` | 389 / 671 / 16 | 15 | 7 | 1 |
| 2025-09-15 `11` | 71 / 4 / 393 | 10 | 5 | 2 |
| 2025-09-29 `0` | 3 / 4 / 36 | 9 | 5 | 1 |
| 2025-10-10 `14` | 290 / 150 / 177 | 14 | 7 | 1 |
| **Total across distinct shard windows** | **1,087 / 1,322 / 651** | **63** | **30** | — |

The five Parquet SHA-256 values are recorded in the
[close-flow source scout](HYPERLIQUID_CLOSE_FLOW_SOURCE_SCOUT.md) for four
shards; the fifth source-only file is
`batch_upto_20250915_11.lz4_1765114256.parquet`, SHA-256
`90d7ffe83b73ee610874c00cd16980e9854285beaf751b420831f19eca884e91`.
Local JSON reports are at
`/private/tmp/hl-liquidation-{july,august,sept15,september,october}-audit.json`.
No selected trade had a missing partner, a one-sided or disagreeing
marker, a nonclosing taker, or a taker wallet different from
`liquidatedUser`. All 3,060 marked selected trades had `method=market`;
none had `method=backstop` in these shards. There were 112 market
liquidation taker fills with nonnegative `closedPnl`, confirming that
negative realized P&L is an invalid forced-event filter. These checks
support the mirror's internal marker semantics, not its independent
fidelity to official S3 or complete historical coverage.

The **3,060 fills are not 3,060 independent opportunities**. For example,
the August 31 ETH 03:50 UTC five-minute bin contains 169 marked trades,
while the whole September 29 cutoff shard has only nine market-wide
five-minute bins with any liquidation. BTC, ETH and HYPE events often
share the same market-wide burst. The 30 market-wide half-hour bins across
five short, gapped shards are an upper bound on separated episodes, not
an effective sample size or a daily return series. October 10 also
contains a known large source gap and a market cascade. A trial on only
these shards would overweight a few shocks.

## Interim gate after five shards

The next step was to use the public [block-fill mirror inventory](https://huggingface.co/datasets/gionuibk/hyperliquid-node-fills-by-block)
to preselect **calendar-spaced 2025 source windows using metadata alone**
and audit complete contiguous blocks and independent market-wide event
bins before inspecting future returns. Keep market and backstop methods
separate, and aggregate multiple liquidated orders within an episode
before scoring. Freeze the event definition, observation/entry clock,
hold, source hashes, dates, fee floor, and same-time directional controls
as a new experiment only after coverage and episode count are known.
If wider coverage remains too sparse, close this liquidation mechanism's
directional gate without treating fill count as evidence of a sample.
Any gross survivor still needs official-source cross-check, bid/ask depth,
funding, and realistic latency. The 2026 final holdout is untouched.

## Calendar-spaced extension and usable episode count

To solve the narrow-shard coverage issue, we selected seven additional
weekly 2025 batch dates **from the public file listing, before reading
event prices or outcomes**: August 4, 11, 18, 25, September 8, 22 and
October 6. For each date, the lowest numbered shard of at least 150 MB
was chosen from metadata alone. This is a source sample, not an outcome
selection or a continuous day reconstruction. The seven files total
1,623,728,143 bytes and were downloaded with their listed sizes.

| Batch date / shard suffix | SHA-256 | Marked trades | Market-wide 5m bins | Eligible 5m bins | Spaced eligible episodes |
| --- | --- | ---: | ---: | ---: | ---: |
| Aug 4 / `13` | `d4213cc7882a93763c71eae4b25fc476bc8a35e2b9f1ea40ef3fa7523e810671` | 2,404 | 16 | 0 | 0 |
| Aug 11 / `2` | `1bd48b47834a8e1ab9fefede6c8de46b91ebd3021aecab5a51da114b38a4b7e1` | 2,359 | 20 | 5 | 3 |
| Aug 18 / `2` | `d5b9921ac4f34274c372933ba3278e4f9b05c8f9e9b85169de7f8c983921c7da` | 5,830 | 19 | 9 | 3 |
| Aug 25 / `12` | `7d4898fe9f7b5cb0f3dbb48ab0e25acfb452a99e6a2f09a693e25a52d662d190` | 2,670 | 16 | 4 | 1 |
| Sep 8 / `8` | `0a8eb26f6be83bb56cbb734007ac67c5b70b03d54e3bac5112e338bdf4050935` | 408 | 25 | 14 | 5 |
| Sep 22 / `0` | `924fde716a52970d94b1530a9106106384a70443b9af6264c36fd84f2b72ddc4` | 13,400 | 25 | 4 | 3 |
| Oct 6 / `12` | `98e6b9e984b4d76d656b4bf868bd0f1f348389fb3f585ea34bfb131ff78c385b` | 889 | 13 | 1 | 1 |
| **Seven-shard total** | — | **27,960** | **134** | **37** | **16** |

The [return-free eligibility counter](../../../research/futures/hyperliquid_liquidation_eligibility.py)
requires a complete five-minute observation bin, decision at bin end plus
one minute, and room for a ten-second entry proxy and 120-minute hold to
end within the same consecutive-block segment. It then counts the first
market-wide bin of each cluster, suppressing later bins for 30 minutes.
It checks **time coverage only**; it does not inspect future trade prices,
proxy availability, returns, direction, or fees. Across all 12 shards,
31,020 marked market trades occupy 197 market-wide five-minute bins;
only **49** bins satisfy the source-time requirement and only **21**
separated episodes remain. HYPE alone has 14 coin-level spaced episodes
across the shards. None of the seven weekly shards had a marker-side,
taker-wallet, or close-direction inconsistency; again every observed
marked trade was `method=market`. Many forced closes have positive
position-level `closedPnl`, consistent with account-level liquidation.

**Decision:** a 120-minute directional score on these disconnected shards
would have a few shock clusters masquerading as thousands of trades.
Continue the data gate by stitching complete calendar days from the
mirror's hourly source paths, validating block continuity and source
overlap, then count nonoverlapping delayed opportunities across more
separate dates. The public mirror's 113.8 GB inventory makes this a
tractable acquisition problem, not a demonstrated impossibility. Freeze
FUT-012 only after a multi-date independent-episode sample and exact
entry/exit proxy coverage are established. Do not select a shorter hold,
coin or shock date from any return in this source-only work.

## Complete-day reconstruction: source gate cleared for a cheap pilot

The public inventory lists 24 numbered hourly shards (`0`–`23`) for
seven 2025 batch dates. September 18 and 25 were selected first as
calendar-spaced full days; August 14 and October 4 were then selected
from the same metadata inventory to bracket them. The
[four-day SHA manifest](source_manifests/hyperliquid_full_days_2025.json)
pins all 96 downloaded Parquet files, 4,540,345,911 bytes in total. Every
hourly object matched its metadata size. Reading each day's 24 files
together in block-number order found one **fully consecutive** block
stream per day with no duplicate block ranges or source gaps:

| UTC day | Consecutive blocks | Market liquidation trades | Backstop trades | Market-wide raw 5m bins | Time-eligible 5m bins | 30m-spaced market-wide episodes | HYPE spaced / both trade proxies present |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2025-08-14 | 1,062,039 | 47,856 | 235 | 82 | 77 | 24 | 16 / 16 |
| 2025-09-18 | 1,086,383 | 753 | 0 | 25 | 25 | 9 | 6 / 6 |
| 2025-09-25 | 1,082,973 | 17,848 | 0 | 95 | 87 | 28 | 23 / 23 |
| 2025-10-04 | 1,077,543 | 656 | 0 | 24 | 24 | 12 | 9 / 9 |
| **Total** | **4,308,938** | **67,113** | **235** | **226** | **213** | **73** | **54 / 54** |

The August 14 backstop rows are **not** ordinary liquidated-wallet taker
closes: their taker differs from `liquidatedUser` and their direction is
`Liquidated Cross Long` or `Liquidated Isolated Long`. The auditor's 235
taker/close exception counts on that day are exactly these backstop
rows. All market-method rows on the four days have matching paired
markers, one liquidated-wallet taker, and closing directions. There were
no marked trades with a block receipt over 60 seconds late. The
eligibility counter then checked, using trade **timestamps only**, that
each of 54 HYPE episodes has at least one observed trade in both the
proposed ten-second entry and exit proxy windows. This establishes price
source presence, not spread, depth, quote availability, latency, or a
tradable fill.

The four dates supply a multi-date cheap HYPE gross pilot sample, but
Aug 14 and Sep 25 together contribute 39 of 54 HYPE episodes and were
large liquidation cascades. Date breakdowns and chronological-half
controls are therefore essential; pooled fill-weighted performance
would mislead. No outcome price was read in this reconstruction. A
separate [FUT-012 contract](experiments/FUT-012.md) freezes the intended
pilot and source hashes before any conditioned return.
