# Helius history pilot

User preference: spend Helius credits efficiently. Cache original responses,
analyze offline first, set explicit request limits, and measure consumption
before increasing the sample. No automatic full-history pagination.

Authenticated read-only access succeeded using the existing MCP environment
credential. The MCP tools were not exposed in this session; direct HTTPS used
the configured credential without printing it or saving it in research files.

Two getTransactionsForAddress requests, at most 100 full records each,
returned 200 records. Estimated cost: 20 credits under the published schedule
(10 credits per 100 full records). This is an estimate, not a billing-account
measurement. Original requests, responses, retrieval timestamps and pagination
state are cached under data/helius-pilot-2026-09-16. Cache reuse performs no
network request. No retries or subsequent pages were requested.

## Findings

The Unipcs candidate address's 100 records span 2026-09-16 15:10:58–15:22:10
UTC. Every record has only positive aggregate owner token deltas; the owner
is not a signer in any record. Ninety-six records change the USDC mint
EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v; four change other mints.
The first three USDC receipts are 0.24, 1.807627 and 0.128029 tokens.

These are not 100 demonstrated purchases. Routing programs appearing in a
transaction do not establish that its recipient initiated a trade. Fees,
referral distributions, unsolicited transfers, and relayed transactions are
possible explanations; their actual semantics are not established yet.
Absence of a signature does not by itself disprove a relayed trade. Native SOL
counterflows and transfer instructions still need reconciliation.

This reinforces the existing medium-confidence ownership hypothesis while
leaving trade attribution unresolved: holdings corroboration cannot substitute
for identifying who traded. Do not use raw wallet activity as a buy trigger.

The historical cohort sample's 100 records span June 24–September 12, with
18 failed transactions, 74 records containing token balances, and 55 with
nonzero aggregate owner token changes. It is not comparable to the first
sample over the same calendar window. Recent-N samples are for coverage
diagnostics, not performance comparisons.

## Next bounded experiment

1. Decode cached recipient transfer instructions and native SOL changes.
2. Locate a public Fomo buy with exact mint/time, then request a narrow time
   interval around it rather than paging through unrelated receipts.
3. Require transaction-level actor attribution before scoring entries.
4. Once mapping is credible, use fixed calendar windows and retain failures,
   transfers and unknown cost basis explicitly.

No PnL, entry signal, continuous collector, or trading edge was validated.

Reproduce the coverage audit without additional credits:

```sh
python3 docs/research/memecoin/helius_history_pilot.py
```
