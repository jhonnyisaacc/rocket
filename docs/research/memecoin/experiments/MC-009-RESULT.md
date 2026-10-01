# MC-009 result — independent creation-feed receipt timing

Status: `REJECTED` as a complete Pump early-discovery source. The [frozen design](MC-009-FROZEN.md) paired a free, read-only PumpPortal `subscribeNewToken` session with the Solana Labs Pump `logsSubscribe` stream for 180 seconds. The acknowledgments were 1.33 seconds apart; both captures ended normally with no collector errors. No paid trade subscription or order path was used.

## Coverage and identity

The Solana arm saved 48,997 notifications in 49,067 raw frames. The independent publicnode index contained **48,863** signatures in its fully observed interior slots, while the stream contained **48,864**. The sole extra was another all-ones signature (`1111111111111111111111111111111111111111111111111111111111111111`) carrying a nonnative CreateEvent. Its emitted mint and bonding curve had no independent transaction history; the frozen exact-coverage gate fails. There were no signatures missing from the stream. The pinned decoder found 63 CreateEvents and 8,489 TradeEvents, with no layout errors or truncated successful logs. Native non-Mayhem state transitions passed 3,511/3,511; supported quotes passed 6,289 with zero material failures.

PumpPortal saved 52 unique creation notifications: 45 labeled `pool: pump` and seven `pool: bonk`. Later independent `getTransaction` responses matched **52/52** signatures to successful chain transactions. All 45 `pump` notifications matched a decoded Pump CreateEvent and mint; the seven `bonk` notifications were valid chain transactions from a different launch program, not Pump creations. The provider's unfiltered `subscribeNewToken` stream therefore needs program scoping before a Pump universe comparison.

The frozen common core held **62** Solana CreateEvents, of which only **44** appeared in PumpPortal. The missing 18 include the all-ones artifact, three other nonnative quote launches, and **14 native quote launches**. For the strict native non-Mayhem regime used in earlier baseline experiments, PumpPortal carried **30/43** core creations and missed 13. This is a substantial coverage failure even after excluding the uncorroborated all-ones frame and out-of-scope Bonk launches. No post-hoc filter makes this capture an accepted complete feed.

## Timing

For the 44 matched core creates, PumpPortal receipt minus Solana Labs receipt had median **−182 milliseconds**, p90 **−53 milliseconds**, p99 **−33 milliseconds**, minimum −327 milliseconds and maximum +33 milliseconds. Neither arm was more than five seconds later on a matched signature. Among 51 in-core PumpPortal notifications with independent transaction block times, whole-second blockTime-to-receipt age had median **1.064 seconds** and p90 **1.352 seconds**. These are direct paired receive-clock differences and an imprecise block-age proxy, respectively. This three-minute fast interval does not rule out the longer public-feed delay bursts observed in MC-005/MC-006.

## Decision and evidence

PumpPortal was slightly earlier on matched names but missed roughly one quarter of the native Pump creations in the frozen core and mixed in seven Bonk launches. It cannot define the complete early-launch universe or support an entry baseline. The official public log arm also failed its exact-coverage gate due to the recurring all-ones synthetic-looking frame. Continue toward a dedicated transaction-identified stream with independent chain index reconciliation and explicit rejection/quarantine of uncorroborated notifications; keep actual receive clocks and full negative universe. No economic outcome or strategy rule is promoted from this acquisition test.

[Both raw captures, manifests, independent index pages, decoded observations, 52 transaction responses, audit and comparison](../data/mc009-create-feed-20260924.tar.gz), archive SHA-256 `b3e3fe98409d266547845a6a5b4f5e8c3198b53e2088e9d10f1c6974c25e7cae`. PumpPortal raw SHA-256 `adb73d27949f25399798e29798eaf708c704ca6f0de1ecd28418d78ad9f8c442`; Solana raw SHA-256 `e2cb0cda51895e4aeb76d330305ac03d1cf693933af1b302a933f3ee0c04c074`. The saved index and responses reproduced the audit and comparison byte for byte offline.
