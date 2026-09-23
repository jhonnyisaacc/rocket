# Source audit and wallet attribution pilot

Observation session: 2026-09-16, approximately 14:40–14:50 UTC. Research status:
`NO_EDGE_VALIDATED`. This pass acquired data and tested attribution; it did not
run a returns backtest or enable monitoring/execution.

## Acquired data and reproducibility

Downloaded [RED-COHORT release 21765387](https://zenodo.org/records/21765387)
(8,769,673 bytes), by Arati Uday Kamat, CC-BY-4.0. The archive is retained at
`data/red-cohort-21765387/source.zip`. SHA256:
`f908d10f459e52de0e6f0d77af26db262e41a521dfe3872f30bd795e255841d0`.
Bundled code was read, not executed. A separately written standard-library
audit reads ZIP/JSON/gzip data and generates the audit plus wallet registry:

```sh
python3 docs/research/memecoin/audit_cohort_archive.py \
  docs/research/memecoin/data/red-cohort-21765387/source.zip \
  docs/research/memecoin/data/red-cohort-21765387
```

Computed directly: 1,012 cohorts; 2,965 unique wallet strings; 2,964 valid
32-byte Solana addresses and one redacted string excluded from the registry;
5,975 distinct catalogue mints; 6,306 cohort/mint rows. Cohort sizes match
their distinct address counts. All registry rows are historical candidates,
with no username attribution, profitability estimate, or live eligibility.

The intra file contains 20,163 rows over 20,162 mints; 9,081 rows have first
rank greater than ten. It is a broader set of intra-launch hints, not the full
first-ten buyer corpus. No intra row has an `available_at` clock. The full buyer
and launch files required for the published PSM are absent; the README says
the buyer corpus is available on request. Reading the included results JSON
does not reproduce the analysis. We have not contacted the author.

The top nine-address cohort has 42 catalogue hits. Its median total SOL per
hit is 0.7781, 19 hits are below 0.2 SOL, and ten have same-second timestamps.
These counts measure activity, not skill, intent, or profit. The catalogue's
per-mint `n_wallets` is explicitly a buyer-row count. Do not interpret it as
independent traders agreeing. The detection code also takes the first ten
observed records, which does not prove that early records were never missed.

The release declares provisional patent filings and commercial licensing
claims; preserve this provenance and review terms before product reuse.

## Source correction

[Paper v3](https://arxiv.org/abs/2607.02795v3) replaces earlier naive results
with adjusted outside-buyer lift of 16.1% (95% CI 13.0–19.4%) and SOL-inflow
lift of 6.3% (CI -0.5–15.1%). The activity-matched placebo is explicitly biased.
The previous protocol mistakenly required beating it as a valid control.
Corrected that, the requirement for positive median return, and the proposal
to select exit rules using the final holdout. These corrections do not prove
any strategy works.

## Live chain check of a catalogue wallet

Queried `getSignaturesForAddress` for
`789sBYAGntSyAPoS4ZH3zo3SUFuv1jeAjPeaq7muVany` on the public Solana RPC.
It returned one September transaction followed by June transactions.
The most recent [transaction](https://solscan.io/tx/4W9rHzoS4Vcx6J6tt4VbmZkbqZ2qXYJeMR4SesV3g5fnyAza1EY558YpTd6UX5RsPYqyx8NhncPUyXJWoPWaSwXG)
has no pre/post token balances and shows system account creation/transfer
instructions. This is not evidence of a recent token purchase. Thus recent
wallet activity alone cannot qualify a historical cohort as active traders.
This was one spot check, not a census of all cohort wallets.

## Fomo attribution pilot: Unipcs

Public lookup at [Fomo Wallet Finder](https://fomowalletfinder.com/?handle=unipcs)
returned candidate Solana address
`2heJbC32Tpfcb3nbUb5ER61K11FGZVfVGtVnDm6LDogF` and EVM address
`0x0a6ebed0155edb4b21d92ad02897a626cd90119e`. Treat the site's VERIFIED badge
as a vendor claim. The EVM mapping was not tested.

Independently opened the public Fomo position details and queried Solana
`getTokenAccountsByOwner` for the candidate and the exact mints:

| Asset | Fomo displayed balance | RPC exact balance | RPC context slot |
| --- | ---: | ---: | ---: |
| USELESS | 15.8M | 15,876,386.804966 | 447549213 |
| KORI | 14M | 14,094,024.262326 | 447549317 |

USELESS mint: `Dz9mQ9NzkBcCsuGPFJ3r1bS4wgqKMHBPiVuniW8Mbonk`;
[Fomo position](https://fomo.family/profile/unipcs?tradeId=c67d250b-df85-4244-a4ab-59a9171c86a2).
KORI mint: `HtTYHz1Kf3rrQo6AqDLmss7gq5WrkWAaXn3tupUZbonk`;
[Fomo position](https://fomo.family/profile/unipcs?tradeId=416b238b-7079-482a-a9ee-66b46131b00c).

Conclusion: medium-confidence candidate, supported by two approximate holdings
matches. The UI uses abbreviated quantities, so these are not exact-match
proofs. No signed ownership proof or time-separated trade-delta match was
obtained. Next attribution check: observe a new public fill, verify balance
changes at its transaction, then repeat at another timestamp. Shared custody,
relay addresses and wallet rotation remain alternative explanations.

[Hoodwatch's own technical account](https://hoodwatch.dev/blog/fomo-family-on-solana)
claims that profile addresses differ from trading wallets and that relayed
swaps require reading token-owner balance changes. It is a vendor's report,
not independently established for all Fomo accounts. It provides a useful
implementation hypothesis: do not equate fee payer with trader.

## A concrete PnL confound found in the UI

The [INU position](https://fomo.family/profile/unipcs?tradeId=80869427-7238-451d-9c66-ec0498e5eb34)
showed $126,049.60 invested, of which $114,885.89 was a Received event; two
displayed buys totalled $11,167.75 (minor rounding difference in totals).
KORI explicitly showed Received from external wallet, with all four events
classified Received. This is not an accusation or proof of inaccurate PnL.
It shows why inherited cost basis and transfers must be reconciled before
scoring acquisition timing, copying purchases, or claiming realized returns.

## Changes that make the workflow more useful

1. Separate research sessions from capture. Three sessions/day can audit
   labels and adjust the next experiment; an hours-scale signal needs continuous
   transaction capture and measured notification delay. Local power-off is a
   data gap, not a quiet market. No continuous collector was started this pass.
2. Use two candidate sources: historical anonymous cohort addresses, and
   publicly attributed Fomo traders. Keep their evidence and sampling biases.
3. Requalify historical wallets for actual swaps and recent repeated behavior.
   A transfer, account creation, or dust receipt does not count as a buy.
4. Measure followers' delayed, executable returns. Reconstruct entries at
   5s/30s/120s/300s after a detectable event; evaluate fixed notional and costs.
   A leader's own return is not the follower's return.
5. Compare cohort arrivals, independently qualified traders arriving, and
   market-flow-only triggers. Related wallets count as one possible actor.
6. Treat +100%/+200% as first-passage outcomes: probability of reaching the
   target before an adverse barrier or timeout. Learn barriers only in
   training/validation. Include delistings, failed sells, and capture gaps.
7. Freeze the policy before forward observation; stratify by launchpad and
   chain. SCRIBE was displayed as MeteoraDBC; INU is on Robinhood; USELESS/KORI
   are Solana. Pooling these as Pump.fun launches would invalidate inference.

PumpPortal currently documents free creation/migration streams but metered
account/token trades requiring a funded API key. No key was funded or metered
stream enabled. [Provider documentation](https://pumpportal.fun/data-api/real-time/).
The bounded public RPC reads succeeded, establishing an immediate read-only
pilot path; their success does not establish production throughput.

## Remaining empirical work

The actual bottleneck is a representative, timestamped buy/sell and executable
price panel. We have a concrete candidate registry and one corroborated public
identity lead, but no costed prospective signal outcomes yet. The next bounded
experiment should test data continuity and delayed copyability for a small
preselected sample before expanding to thousands of wallets. Three days can
reveal data/latency failures and generate pilot outcomes; it cannot establish
durable profitability across market regimes.
